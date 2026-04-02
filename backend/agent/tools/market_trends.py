"""
Redfin Data Center market trends for a given ZIP code.
Downloads and caches the national ZIP-level TSV file for 24 hours.
"""
import gzip
import io
import os
import time
from typing import Any

import httpx

REDFIN_TSV_URL = (
    "https://redfin-public-data.s3.us-west-2.amazonaws.com/"
    "redfin_market_tracker/zip_code_market_tracker.tsv000.gz"
)
CACHE_PATH = "/tmp/redfin_market.tsv.gz"
CACHE_TTL = 86_400  # 24 hours


def _cache_valid() -> bool:
    if not os.path.exists(CACHE_PATH):
        return False
    return (time.time() - os.path.getmtime(CACHE_PATH)) < CACHE_TTL


async def _download_tsv() -> bytes:
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(REDFIN_TSV_URL)
        resp.raise_for_status()
        return resp.content


async def _get_tsv_bytes() -> bytes:
    if _cache_valid():
        with open(CACHE_PATH, "rb") as f:
            return f.read()
    raw = await _download_tsv()
    with open(CACHE_PATH, "wb") as f:
        f.write(raw)
    return raw


def _col(header: list[str], name: str) -> int | None:
    try:
        return header.index(name)
    except ValueError:
        return None


def _safe_float(parts: list[str], idx: int | None) -> float | None:
    if idx is None or idx >= len(parts):
        return None
    val = parts[idx].strip()
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _parse_tsv_for_zip(raw_bytes: bytes, zip_code: str) -> list[dict[str, Any]]:
    """
    Decompress and parse the Redfin national TSV, returning rows for the
    given ZIP code sorted newest-first (max 6 months).
    """
    with gzip.open(io.BytesIO(raw_bytes), "rt", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    if not lines:
        return []

    header = [h.strip() for h in lines[0].split("\t")]

    region_idx = _col(header, "region")
    period_end_idx = _col(header, "period_end")
    if region_idx is None or period_end_idx is None:
        return []

    median_sale_price_idx = _col(header, "median_sale_price")
    homes_sold_idx = _col(header, "homes_sold")
    median_dom_idx = _col(header, "median_dom")
    months_of_supply_idx = _col(header, "months_of_supply")
    sold_above_list_idx = _col(header, "sold_above_list")
    price_drops_idx = _col(header, "price_drops")

    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) <= region_idx:
            continue
        region = parts[region_idx].strip()
        # Redfin stores ZIP codes without leading zeros in some versions
        if region != zip_code and region.lstrip("0") != zip_code.lstrip("0"):
            continue

        rows.append({
            "period_end": parts[period_end_idx].strip(),
            "median_sale_price": _safe_float(parts, median_sale_price_idx),
            "homes_sold": _safe_float(parts, homes_sold_idx),
            "median_dom": _safe_float(parts, median_dom_idx),
            "months_of_supply": _safe_float(parts, months_of_supply_idx),
            "pct_sold_above_list": _safe_float(parts, sold_above_list_idx),
            "price_drops_pct": _safe_float(parts, price_drops_idx),
        })

    rows.sort(key=lambda r: r["period_end"], reverse=True)
    return rows[:6]


def _compute_trend(months: list[dict[str, Any]]) -> str:
    prices = [m["median_sale_price"] for m in months if m.get("median_sale_price")]
    if len(prices) < 2:
        return "unknown"
    newest, oldest = prices[0], prices[-1]
    change_pct = (newest - oldest) / oldest * 100
    if change_pct > 2:
        return "appreciating"
    if change_pct < -2:
        return "depreciating"
    return "flat"


async def fetch_market_trends(zip_code: str) -> dict[str, Any]:
    """
    Fetch Redfin Data Center ZIP-level market stats for the last 6 months.
    Caches the national TSV for 24 hours.
    """
    try:
        raw = await _get_tsv_bytes()
    except Exception as exc:
        return {"error": f"Failed to download market data: {exc}"}

    months = _parse_tsv_for_zip(raw, zip_code)

    if not months:
        return {"zip_code": zip_code, "error": "No market data found for this ZIP"}

    return {
        "zip_code": zip_code,
        "months": months,
        "trend": _compute_trend(months),
    }
