"""
Freddie Mac 30-year mortgage rate (PMMS) via FRED.
"""

import csv
import io
import logging

import httpx

log = logging.getLogger(__name__)

FRED_PMMS_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
FALLBACK_MORTGAGE_RATE_PCT = 6.5


async def fetch_freddie_mac_mortgage_rate() -> dict:
    """
    Fetch latest Freddie Mac 30-year fixed average rate from FRED CSV.
    Returns dict with latest non-empty observation.
    """
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.get(FRED_PMMS_CSV_URL)

    rows = csv.DictReader(io.StringIO(response.text))
    latest_date = None
    latest_rate = None
    for row in rows:
        value = (row.get("MORTGAGE30US") or "").strip()
        date = (row.get("DATE") or "").strip()
        if not date:
            continue
        try:
            rate = float(value)
        except ValueError:
            continue
        latest_date = date
        latest_rate = rate

    if latest_date is None or latest_rate is None:
        raise ValueError("No numeric mortgage rate values found in FRED PMMS feed")

    return {
        "series": "MORTGAGE30US",
        "rate_pct": round(latest_rate, 2),
        "as_of": latest_date,
        "source": "fred_freddie_mac",
    }


async def get_current_mortgage_rate_pct(
    fallback_rate_pct: float = FALLBACK_MORTGAGE_RATE_PCT,
) -> float:
    """
    Return current mortgage rate percentage; fallback on network/parse issues.
    """
    try:
        result = await fetch_freddie_mac_mortgage_rate()
        return float(result["rate_pct"])
    except Exception as exc:  # noqa: BLE001
        log.warning("Mortgage rate fetch failed; using fallback %.2f%%: %s", fallback_rate_pct, exc)
        return fallback_rate_pct
