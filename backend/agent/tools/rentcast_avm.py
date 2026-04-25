"""
Tools: fetch_avm_estimate, fetch_rentcast_rent_estimate

fetch_avm_estimate calls the RentCast AVM API to obtain an automated valuation
for a property. fetch_rentcast_rent_estimate calls the RentCast rent AVM to get
a property-specific monthly rent estimate (neighborhood-aware, bed/bath/sqft tuned).

Both are gated behind the enable_rentcast_avm feature flag. They return None (or
an empty dict) on any failure or when the flag is off.
"""

import logging
from urllib.parse import urlencode

import httpx

from config import settings

log = logging.getLogger(__name__)

RENTCAST_AVM_URL = "https://api.rentcast.io/v1/avm/value"
RENTCAST_RENT_AVM_URL = "https://api.rentcast.io/v1/avm/rent/long-term"

_PROPERTY_TYPE_MAP: dict[str, str] = {
    "SINGLE_FAMILY": "Single Family",
    "SFR": "Single Family",
    "SFH": "Single Family",
    "CONDO": "Condo",
    "TOWNHOUSE": "Townhouse",
    "MULTI_FAMILY": "Multi Family",
}


async def fetch_avm_estimate(address: str) -> int | None:
    """
    Call the RentCast AVM endpoint for the given address.

    Returns the integer price estimate, or None when:
      - The feature flag (ENABLE_RENTCAST_AVM) is disabled
      - No API key is configured (RENTCAST_API_KEY absent)
      - The API returns an error or rate-limit response
      - The response is missing the expected 'price' field
    """
    if not settings.enable_rentcast_avm:
        return None

    api_key = settings.rentcast_api_key
    if not api_key:
        return None

    url = RENTCAST_AVM_URL + "?" + urlencode({"address": address})
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"X-Api-Key": api_key})
            resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("RentCast AVM call failed for %r: %s", address, exc)
        return None

    price = data.get("price")
    if price is None:
        log.warning("RentCast AVM response for %r missing 'price' key", address)
        return None

    return int(price)


async def fetch_rentcast_rent_estimate(
    address: str,
    beds: int | None = None,
    baths: float | None = None,
    sqft: int | None = None,
    property_type: str | None = None,
) -> dict | None:
    """
    Call the RentCast rent AVM endpoint for the given address.

    Returns a dict with keys rent, rentRangeLow, rentRangeHigh (all floats),
    or None when:
      - The feature flag (ENABLE_RENTCAST_AVM) is disabled
      - No API key is configured (RENTCAST_API_KEY absent)
      - The API returns an error or rate-limit response
      - The response is missing the expected 'rent' field
    """
    if not settings.enable_rentcast_avm:
        return None

    api_key = settings.rentcast_api_key
    if not api_key:
        return None

    body: dict = {"address": address}
    if beds is not None:
        body["bedrooms"] = beds
    if baths is not None:
        body["bathrooms"] = baths
    if sqft is not None:
        body["squareFootage"] = sqft
    if property_type is not None:
        mapped = _PROPERTY_TYPE_MAP.get(str(property_type).strip().upper())
        if mapped:
            body["propertyType"] = mapped

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                RENTCAST_RENT_AVM_URL,
                params=body,
                headers={"X-Api-Key": api_key},
            )
            resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("RentCast rent AVM call failed for %r: %s", address, exc)
        return None

    rent = data.get("rent")
    if rent is None:
        log.warning("RentCast rent AVM response for %r missing 'rent' key", address)
        return None

    return {
        "rent": float(rent),
        "rentRangeLow": float(data.get("rentRangeLow") or 0),
        "rentRangeHigh": float(data.get("rentRangeHigh") or 0),
    }
