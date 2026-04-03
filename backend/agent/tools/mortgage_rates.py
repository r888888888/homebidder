"""Mortgage rates tool (Freddie Mac PMMS via FRED)."""

import os
import time
from typing import Any

import httpx

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
CACHE_TTL_SECONDS = 24 * 60 * 60

_cache: dict[str, Any] = {
    "value": None,
    "fetched_at_epoch": None,
}


async def _fetch_latest_series_value(series_id: str, api_key: str) -> tuple[float, str]:
    params = {
        "series_id": series_id,
        "sort_order": "desc",
        "limit": 1,
        "file_type": "json",
        "api_key": api_key,
    }
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.get(FRED_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    observations = payload.get("observations") or []
    if not observations:
        raise ValueError(f"No observations returned for {series_id}")

    obs = observations[0]
    value = float(obs["value"])
    as_of_date = str(obs["date"])
    return round(value, 2), as_of_date


async def fetch_mortgage_rates() -> dict[str, Any]:
    """Return latest 30-year and 15-year fixed mortgage rates from FRED with a 24h memory cache."""
    now = time.time()
    cached_value = _cache.get("value")
    fetched_at = _cache.get("fetched_at_epoch")
    if cached_value and fetched_at and (now - float(fetched_at)) < CACHE_TTL_SECONDS:
        return cached_value

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY is required")

    rate30, as_of_30 = await _fetch_latest_series_value("MORTGAGE30US", api_key)
    rate15, as_of_15 = await _fetch_latest_series_value("MORTGAGE15US", api_key)

    as_of_date = max(as_of_30, as_of_15)
    result = {
        "rate_30yr_fixed": rate30,
        "rate_15yr_fixed": rate15,
        "as_of_date": as_of_date,
        "source": "Freddie Mac PMMS via FRED",
    }

    _cache["value"] = result
    _cache["fetched_at_epoch"] = now
    return result
