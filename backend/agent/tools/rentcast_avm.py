"""
Tool: fetch_avm_estimate

Calls the RentCast AVM API to obtain an automated valuation for a property.
Gated behind the enable_rentcast_avm feature flag. Returns None on any failure
or when the flag is off, so callers can always treat None as "no AVM available".
"""

import logging
from urllib.parse import urlencode

import httpx

from config import settings

log = logging.getLogger(__name__)

RENTCAST_AVM_URL = "https://api.rentcast.io/v1/avm/value"


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
