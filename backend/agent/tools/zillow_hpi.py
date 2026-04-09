"""
Zillow Home Value Index (ZHVI) by ZIP code.
Reads a prefetched ZIP-level monthly ZHVI CSV cache.

Zillow publishes ZIP-level ZHVI as a CSV:
  https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv

Used as a fallback when FHFA ZIP5 HPI does not cover a given ZIP code.
"""
import io
import os
import time
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

ZILLOW_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
CACHE_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "zillow_zhvi.csv")
CACHE_TTL = 7 * 86_400  # 7 days

_REGION_COL = "RegionName"


def _cache_valid() -> bool:
    if not os.path.exists(CACHE_PATH):
        return False
    return (time.time() - os.path.getmtime(CACHE_PATH)) < CACHE_TTL


async def _download_zhvi() -> bytes:
    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        resp = await client.get(ZILLOW_URL)
        resp.raise_for_status()
        return resp.content


async def prefetch_zillow_zhvi(force: bool = False) -> bool:
    """
    Download and cache the Zillow ZIP-level ZHVI CSV.
    Returns True when a download happened, False when cache was already fresh.
    """
    if not force and _cache_valid():
        return False

    raw = await _download_zhvi()
    with open(CACHE_PATH, "wb") as f:
        f.write(raw)
    return True


def _compute_annual_changes(yearly_values: dict[int, float]) -> list[dict[str, Any]]:
    """
    Given a mapping of {year: home_value}, compute annual percentage changes.
    Returns list of {year, annual_chg} sorted newest-first.
    The earliest year is excluded (no prior year to compare against).
    """
    years = sorted(yearly_values.keys())
    if len(years) < 2:
        return []

    rows = []
    for i in range(1, len(years)):
        yr = years[i]
        prev_yr = years[i - 1]
        v_now = yearly_values[yr]
        v_prev = yearly_values[prev_yr]
        if v_prev and v_prev != 0:
            chg = (v_now / v_prev - 1.0) * 100.0
            rows.append({"year": str(yr), "annual_chg": round(chg, 2)})

    rows.sort(key=lambda r: r["year"], reverse=True)
    return rows


def _parse_zhvi_csv(raw_bytes: bytes, zip_code: str) -> list[dict[str, Any]]:
    """
    Parse the Zillow ZHVI CSV and return annual-change rows for the given ZIP.
    Uses the last value of each calendar year as the year's representative value.
    """
    df = pd.read_csv(io.BytesIO(raw_bytes), dtype={_REGION_COL: str})

    # ZIP codes may be stored without leading zeros; normalize both sides
    zip_norm = zip_code.lstrip("0") or "0"
    df[_REGION_COL] = df[_REGION_COL].str.lstrip("0").fillna("0")
    row = df[df[_REGION_COL] == zip_norm]

    if row.empty:
        return []

    # Extract date columns (format YYYY-MM-DD)
    date_cols = [c for c in df.columns if len(c) == 10 and c[4] == "-" and c[7] == "-"]
    if not date_cols:
        return []

    values = row[date_cols].iloc[0]
    values = values.dropna()

    # Group by year, take the last (most recent) month of each year
    yearly: dict[int, float] = {}
    for col, val in values.items():
        yr = int(col[:4])
        # Keep the latest month per year
        if yr not in yearly or col > max(
            (c for c in values.index if c[:4] == str(yr)), default=""
        ):
            yearly[yr] = float(val)

    return _compute_annual_changes(yearly)


def _compute_hpi_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive YoY change, 3-year average, 5-year average, trend, and most recent year."""
    if not rows:
        return {}

    yoy = rows[0]["annual_chg"]
    three_yr = sum(r["annual_chg"] for r in rows[:3]) / len(rows[:3])
    five_yr_rows = rows[:5]
    five_yr = sum(r["annual_chg"] for r in five_yr_rows) / len(five_yr_rows)

    if yoy > 1.0:
        trend = "appreciating"
    elif yoy < -1.0:
        trend = "depreciating"
    else:
        trend = "flat"

    return {
        "yoy_change_pct": round(yoy, 2),
        "three_yr_avg_chg_pct": round(three_yr, 2),
        "five_yr_avg_chg_pct": round(five_yr, 2),
        "hpi_trend": trend,
        "as_of_year": int(rows[0]["year"]),
    }


async def fetch_zillow_hpi(zip_code: str) -> dict[str, Any]:
    """
    Fetch Zillow ZHVI-derived HPI for the given ZIP code.
    Returns YoY change, 3-year average, and trend direction.
    Does not perform network downloads at request time.
    """
    try:
        with open(CACHE_PATH, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return {
            "zip_code": zip_code,
            "error": "Zillow ZHVI cache missing. Run prefetch_backend_data.py to download datasets.",
        }
    except Exception as exc:
        return {"zip_code": zip_code, "error": f"Failed to read Zillow ZHVI cache: {exc}"}

    try:
        rows = _parse_zhvi_csv(raw, zip_code)
    except Exception as exc:
        return {"zip_code": zip_code, "error": f"Failed to parse Zillow ZHVI data: {exc}"}

    if not rows:
        return {"zip_code": zip_code, "error": "No Zillow ZHVI data found for this ZIP"}

    stats = _compute_hpi_stats(rows)
    return {"zip_code": zip_code, **stats, "source": "Zillow ZHVI"}
