"""
FHFA House Price Index (HPI) by ZIP code.
Downloads and caches the ZIP-level annual HPI data for 7 days.

The FHFA publishes ZIP-level HPI as a zipped CSV:
  https://www.fhfa.gov/hpi/download?file=HPI_AT_BDL_ZIP5.csv
Expected CSV format: zip_code,year,annual_chg[,...]
"""
import io
import os
import time
import zipfile
from typing import Any

import httpx

FHFA_URL = "https://www.fhfa.gov/hpi/download?file=HPI_AT_BDL_ZIP5.csv"
CACHE_PATH = "/tmp/fhfa_hpi.zip"
CACHE_TTL = 7 * 86_400  # 7 days


def _cache_valid() -> bool:
    if not os.path.exists(CACHE_PATH):
        return False
    return (time.time() - os.path.getmtime(CACHE_PATH)) < CACHE_TTL


async def _download_hpi() -> bytes:
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(FHFA_URL)
        resp.raise_for_status()
        return resp.content


async def _get_hpi_bytes() -> bytes:
    if _cache_valid():
        with open(CACHE_PATH, "rb") as f:
            return f.read()
    raw = await _download_hpi()
    with open(CACHE_PATH, "wb") as f:
        f.write(raw)
    return raw


def _extract_csv(raw_bytes: bytes) -> str:
    """Extract the first CSV file from the zip archive."""
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv"))
        return zf.read(name).decode("utf-8", errors="replace")


def _parse_hpi_csv(csv_text: str, zip_code: str) -> list[dict[str, Any]]:
    """
    Parse the FHFA ZIP HPI CSV and return rows for the given ZIP sorted newest-first.
    Expects columns: zip_code, year, annual_chg (additional columns are ignored).
    """
    lines = csv_text.splitlines()
    if not lines:
        return []

    header = [h.strip().lower() for h in lines[0].split(",")]
    try:
        zip_idx = header.index("zip_code")
        year_idx = header.index("year")
        chg_idx = header.index("annual_chg")
    except ValueError:
        return []

    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) <= max(zip_idx, year_idx, chg_idx):
            continue
        if parts[zip_idx].strip().lstrip("0") != zip_code.lstrip("0") and parts[zip_idx].strip() != zip_code:
            continue
        try:
            annual_chg = float(parts[chg_idx].strip())
        except ValueError:
            continue
        rows.append({
            "zip_code": zip_code,
            "year": parts[year_idx].strip(),
            "annual_chg": annual_chg,
        })

    rows.sort(key=lambda r: r["year"], reverse=True)
    return rows


def _compute_hpi_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive YoY change, 3-year average, trend, and most recent year."""
    if not rows:
        return {}

    yoy = rows[0]["annual_chg"]
    three_yr = sum(r["annual_chg"] for r in rows[:3]) / len(rows[:3])

    if yoy > 1.0:
        trend = "appreciating"
    elif yoy < -1.0:
        trend = "depreciating"
    else:
        trend = "flat"

    return {
        "yoy_change_pct": round(yoy, 2),
        "three_yr_avg_chg_pct": round(three_yr, 2),
        "hpi_trend": trend,
        "as_of_year": int(rows[0]["year"]),
    }


async def fetch_fhfa_hpi(zip_code: str) -> dict[str, Any]:
    """
    Fetch FHFA ZIP-level HPI for the given ZIP code.
    Returns YoY change, 3-year average, and trend direction.
    Caches the national file for 7 days.
    """
    try:
        raw = await _get_hpi_bytes()
        csv_text = _extract_csv(raw)
    except Exception as exc:
        return {"error": f"Failed to download FHFA HPI data: {exc}"}

    rows = _parse_hpi_csv(csv_text, zip_code)
    if not rows:
        return {"zip_code": zip_code, "error": "No FHFA HPI data found for this ZIP"}

    stats = _compute_hpi_stats(rows)
    return {"zip_code": zip_code, **stats}
