"""Rental estimate tool with RentCast primary and ACS fallback."""

import os
from typing import Any
from urllib.parse import quote

import httpx

RENTCAST_RENT_URL = "https://api.rentcast.io/v1/avm/rent/long-term"
ACS_B25064 = "B25064_001E"


def _null_result(source: str = "none") -> dict[str, Any]:
    return {
        "rent_estimate": None,
        "rent_low": None,
        "rent_high": None,
        "confidence": None,
        "source": source,
    }


async def _fetch_zip_median_rent(zip_code: str) -> float | None:
    api_key = os.environ.get("CENSUS_API_KEY")
    if not api_key or not zip_code:
        return None

    url = (
        "https://api.census.gov/data/2022/acs/acs5"
        f"?get={ACS_B25064}&for=zip+code+tabulation+area:{quote(zip_code)}&key={quote(api_key)}"
    )

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    if len(data) < 2:
        return None

    headers, row = data[0], data[1]
    try:
        idx = headers.index(ACS_B25064)
        value = int(row[idx])
    except (ValueError, IndexError):
        return None

    if value < 0:
        return None
    return float(value)


async def _fetch_rentcast(matched_address: str) -> dict[str, Any] | None:
    api_key = os.environ.get("RENTCAST_API_KEY")
    if not api_key:
        return None

    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(RENTCAST_RENT_URL, params={"address": matched_address}, headers=headers)
        response.raise_for_status()
        payload = response.json()

    rent = payload.get("rent")
    if rent is None:
        return None

    return {
        "rent_estimate": float(rent),
        "rent_low": float(payload["rentRangeLow"]) if payload.get("rentRangeLow") is not None else None,
        "rent_high": float(payload["rentRangeHigh"]) if payload.get("rentRangeHigh") is not None else None,
        "confidence": payload.get("confidence"),
        "source": "rentcast",
    }


async def fetch_rental_estimate(matched_address: str, zip_code: str) -> dict[str, Any]:
    """Return rental estimate using RentCast; fallback to ACS ZCTA median gross rent."""
    try:
        rentcast = await _fetch_rentcast(matched_address)
        if rentcast is not None:
            return rentcast
    except Exception:
        pass

    try:
        acs_rent = await _fetch_zip_median_rent(zip_code)
    except Exception:
        acs_rent = None

    if acs_rent is None:
        return _null_result(source="none")

    return {
        "rent_estimate": round(acs_rent),
        "rent_low": None,
        "rent_high": None,
        "confidence": "low",
        "source": "census_acs_b25064",
    }
