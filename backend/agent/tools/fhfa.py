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
import os
import time
from pathlib import Path
from typing import Any

import httpx
import openpyxl

from agent.tools.zillow_hpi import fetch_zillow_hpi

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


def _parse_hpi_xlsx(cache_path: str, zip_code: str) -> list[dict[str, Any]]:
    """
    Stream the FHFA ZIP5 HPI XLSX row-by-row using openpyxl read_only mode.
    Never loads the full workbook into memory.
    Rows with null annual change (first year of recording) are skipped.
    """
    zip_int = int(zip_code)
    wb = openpyxl.load_workbook(cache_path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        zip_col_idx = year_col_idx = chg_col_idx = None
        rows: list[dict[str, Any]] = []

        for i, xl_row in enumerate(ws.iter_rows(values_only=True)):
            if i < _HEADER_ROW:  # skip notes rows (0-indexed 0..4)
                continue
            if i == _HEADER_ROW:  # header row (0-indexed 5)
                header = [str(c).strip() if c is not None else "" for c in xl_row]
                try:
                    zip_col_idx = header.index(_ZIP_COL)
                    year_col_idx = header.index(_YEAR_COL)
                    chg_col_idx = header.index(_CHG_COL)
                except ValueError:
                    break
                continue
            if zip_col_idx is None:
                continue
            row_vals = list(xl_row)
            if len(row_vals) <= max(zip_col_idx, year_col_idx, chg_col_idx):
                continue
            if row_vals[zip_col_idx] != zip_int:
                continue
            chg = row_vals[chg_col_idx]
            if chg is None:  # first year of recording has no prior year to compare
                continue
            yr = row_vals[year_col_idx]
            if yr is None:
                continue
            rows.append({
                "zip_code": zip_code,
                "year": str(int(yr)),
                "annual_chg": float(chg),
            })
    finally:
        wb.close()

    rows.sort(key=lambda r: r["year"], reverse=True)
    return rows


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


async def fetch_fhfa_hpi(zip_code: str) -> dict[str, Any]:
    """
    Fetch FHFA ZIP-level HPI for the given ZIP code.
    Returns YoY change, 3-year average, and trend direction.
    Does not perform network downloads at request time.
    """
    if not os.path.exists(CACHE_PATH):
        return {
            "zip_code": zip_code,
            "error": "FHFA HPI cache missing. Run prefetch_backend_data.py to download datasets.",
        }

    try:
        rows = _parse_hpi_xlsx(CACHE_PATH, zip_code)
    except Exception as exc:
        return {"zip_code": zip_code, "error": f"Failed to parse FHFA HPI data: {exc}"}

    if not rows:
        return await fetch_zillow_hpi(zip_code)

    stats = _compute_hpi_stats(rows)
    return {"zip_code": zip_code, **stats}
