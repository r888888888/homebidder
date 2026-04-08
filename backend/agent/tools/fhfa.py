"""
FHFA House Price Index (HPI) by ZIP code.
Reads a prefetched ZIP-level annual HPI XLSX cache.

The FHFA publishes ZIP-level HPI as an XLSX file:
  https://www.fhfa.gov/hpi/download/annual/hpi_at_zip5.xlsx

XLSX structure:
  Rows 0-4: title / notes (skipped)
  Row 5:    column headers — "Five-Digit ZIP Code", "Year", "Annual Change (%)", ...
  Row 6+:   data rows; "Annual Change (%)" is NaN for the first recorded year
"""
import io
import os
import time
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

FHFA_URL = "https://www.fhfa.gov/hpi/download/annual/hpi_at_zip5.xlsx"
CACHE_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "fhfa_hpi.xlsx")
CACHE_TTL = 7 * 86_400  # 7 days

_ZIP_COL = "Five-Digit ZIP Code"
_YEAR_COL = "Year"
_CHG_COL = "Annual Change (%)"
_HEADER_ROW = 5  # 0-indexed; rows 0-4 are notes


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
    with open(CACHE_PATH, "rb") as f:
        return f.read()


async def prefetch_fhfa_hpi_dataset(force: bool = False) -> bool:
    """
    Download and cache the national FHFA ZIP5 HPI workbook.
    Returns True when a download happened, False when cache was already fresh.
    """
    if not force and _cache_valid():
        return False

    raw = await _download_hpi()
    with open(CACHE_PATH, "wb") as f:
        f.write(raw)
    return True


def _parse_hpi_xlsx(raw_bytes: bytes, zip_code: str) -> list[dict[str, Any]]:
    """
    Parse the FHFA ZIP5 HPI XLSX and return rows for the given ZIP sorted newest-first.
    Rows with NaN annual change (first year of recording) are skipped.
    """
    df = pd.read_excel(io.BytesIO(raw_bytes), engine="openpyxl", header=_HEADER_ROW)

    # Normalize column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    # Filter to the requested ZIP (stored as int in the XLSX)
    zip_int = int(zip_code)
    df = df[df[_ZIP_COL] == zip_int]

    # Drop rows where annual change is NaN (first year of recording has no change)
    df = df.dropna(subset=[_CHG_COL])

    if df.empty:
        return []

    rows = [
        {
            "zip_code": zip_code,
            "year": str(int(row[_YEAR_COL])),
            "annual_chg": float(row[_CHG_COL]),
        }
        for _, row in df.iterrows()
    ]

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
    Does not perform network downloads at request time.
    """
    try:
        raw = await _get_hpi_bytes()
    except FileNotFoundError:
        return {
            "zip_code": zip_code,
            "error": "FHFA HPI cache missing. Run prefetch_backend_data.py to download datasets.",
        }
    except Exception as exc:
        return {"zip_code": zip_code, "error": f"Failed to read FHFA HPI cache: {exc}"}

    try:
        rows = _parse_hpi_xlsx(raw, zip_code)
    except Exception as exc:
        return {"zip_code": zip_code, "error": f"Failed to parse FHFA HPI data: {exc}"}

    if not rows:
        return {"zip_code": zip_code, "error": "No FHFA HPI data found for this ZIP"}

    stats = _compute_hpi_stats(rows)
    return {"zip_code": zip_code, **stats}
