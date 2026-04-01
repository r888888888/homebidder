"""
Tool: lookup_property_by_address

1. Geocode the free-text address via the Census Geocoder API.
2. Attempt to pull listing details from homeharvest (Realtor.com + Redfin).
3. Fall back to RentCast AVM for unlisted / off-market properties.
Returns a unified property dict and the geocoded coordinates.
"""

import asyncio
import os
import re
from typing import Any
from urllib.parse import urlencode, quote

import httpx

CENSUS_GEOCODER_URL = (
    "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
)
RENTCAST_BASE_URL = "https://api.rentcast.io/v1/properties"


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def lookup_property_by_address(address: str) -> dict[str, Any]:
    """
    Geocode an address, scrape listing data, and return a unified property dict.

    Returns keys: address_matched, latitude, longitude, county, state, zip_code,
    price, bedrooms, bathrooms, sqft, year_built, lot_size, property_type,
    hoa_fee, days_on_market, price_history, avm_estimate, source.

    Raises ValueError if the address cannot be geocoded.
    """
    geo = await _geocode(address)

    # Prefer exact user input for condo/unit lookups, then fall back to
    # geocoder-normalized address if needed.
    candidates = [address]
    if geo["address_matched"] and geo["address_matched"] != address:
        candidates.append(geo["address_matched"])

    listing: dict[str, Any] = {}
    rentcast: dict | None = None
    for candidate in candidates:
        listing, rentcast = await asyncio.gather(
            _homeharvest_listing(candidate),
            _rentcast_data(candidate),
        )
        if listing or (rentcast and rentcast.get("avm") is not None):
            break

    avm = rentcast["avm"] if rentcast else None
    rc_sqft = rentcast["sqft"] if rentcast else None

    # Determine source
    if listing:
        source = listing.pop("source", "homeharvest")
    else:
        source = "rentcast" if avm is not None else "none"

    return {
        # Geocoder fields (county falls back to homeharvest — geocoder omits it)
        "address_matched": geo["address_matched"],
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "county": listing.get("county") or geo["county"],
        "state": geo["state"],
        "zip_code": geo["zip_code"],
        # Listing fields (None when not found)
        "price": listing.get("price"),
        "bedrooms": listing.get("bedrooms"),
        "bathrooms": listing.get("bathrooms"),
        "sqft": listing.get("sqft") or rc_sqft,
        "year_built": listing.get("year_built"),
        "lot_size": listing.get("lot_size"),
        "property_type": listing.get("property_type"),
        "hoa_fee": listing.get("hoa_fee"),
        "days_on_market": listing.get("days_on_market"),
        "list_date": listing.get("list_date"),
        "city": listing.get("city"),
        "neighborhoods": listing.get("neighborhoods"),
        "price_history": listing.get("price_history", []),
        # AVM
        "avm_estimate": avm,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Step 1 — Census geocoder
# ---------------------------------------------------------------------------

async def _geocode(address: str) -> dict[str, Any]:
    candidates = [address]
    stripped = _strip_unit_designator(address)
    if stripped and stripped != address:
        candidates.append(stripped)

    async with httpx.AsyncClient(timeout=15) as client:
        for candidate in candidates:
            params = {
                "address": candidate,
                "benchmark": "Public_AR_Current",
                "format": "json",
            }
            url = CENSUS_GEOCODER_URL + "?" + urlencode(params)

            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

            matches = data.get("result", {}).get("addressMatches", [])
            if not matches:
                continue

            match = matches[0]
            components = match.get("addressComponents", {})
            coords = match["coordinates"]

            return {
                "address_matched": match["matchedAddress"],
                "latitude": float(coords["y"]),
                "longitude": float(coords["x"]),
                "county": components.get("county", ""),
                "state": components.get("state", ""),
                "zip_code": components.get("zip", ""),
            }

    raise ValueError(f"Address not found by Census geocoder: {address!r}")


# ---------------------------------------------------------------------------
# Step 2a — homeharvest listing data
# ---------------------------------------------------------------------------

async def _homeharvest_listing(matched_address: str) -> dict[str, Any]:
    """
    Fetch active/recent listing data via homeharvest.
    Returns an empty dict if nothing is found or if homeharvest raises.
    """
    try:
        df = await asyncio.to_thread(_scrape_homeharvest, matched_address)
    except Exception:
        return {}

    if df is None or df.empty:
        return {}

    row = df.iloc[0]
    full_baths = _safe(row, "full_baths") or 0
    half_baths = _safe(row, "half_baths") or 0
    list_date_raw = _safe(row, "list_date")
    neighborhoods_raw = _safe(row, "neighborhoods")
    return {
        "price": _safe(row, "list_price"),
        "bedrooms": _safe(row, "beds"),
        "bathrooms": full_baths + half_baths * 0.5 if (full_baths or half_baths) else None,
        "sqft": _safe(row, "sqft"),
        "year_built": _safe(row, "year_built"),
        "lot_size": _safe(row, "lot_sqft"),
        "property_type": _safe(row, "style", ""),
        "hoa_fee": _safe(row, "hoa_fee"),
        "days_on_market": _safe(row, "days_on_mls"),
        "list_date": str(list_date_raw) if list_date_raw is not None else None,
        "city": _safe(row, "city"),
        "county": _safe(row, "county"),
        "neighborhoods": str(neighborhoods_raw) if neighborhoods_raw is not None else None,
        "price_history": _safe(row, "price_history", []) or [],
        "source": "homeharvest",
    }


def _scrape_homeharvest(location: str):
    """Synchronous — called via asyncio.to_thread."""
    from homeharvest import scrape_property

    return scrape_property(
        listing_type="for_sale",
        location=location,
        limit=1,
    )


# ---------------------------------------------------------------------------
# Step 2b — RentCast AVM
# ---------------------------------------------------------------------------

RENTCAST_AVM_URL = "https://api.rentcast.io/v1/avm/value"


async def _rentcast_data(matched_address: str) -> dict | None:
    """
    Fetch AVM estimate from RentCast's /v1/avm/value endpoint.
    squareFootage is extracted from subjectProperty in the same response.
    Returns {"avm": float | None, "sqft": int | None} or None if the call fails.
    """
    api_key = os.environ.get("RENTCAST_API_KEY")
    if not api_key:
        return None

    url = RENTCAST_AVM_URL + "?" + urlencode({"address": matched_address})
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        price = data.get("price")
        sqft = data.get("subjectProperty", {}).get("squareFootage")
        return {
            "avm": float(price) if price is not None else None,
            "sqft": int(sqft) if sqft is not None else None,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _safe(row: Any, key: str, default: Any = None) -> Any:
    import pandas as pd
    import numpy as np
    val = row.get(key, default)
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    # Coerce numpy scalars to native Python types so json.dumps works
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        return float(val)
    return val


def _strip_unit_designator(address: str) -> str:
    """
    Remove common condo/apartment unit tokens to improve geocoder hit rate.
    Example: "450 Sanchez St #5, San Francisco, CA 94114" ->
             "450 Sanchez St, San Francisco, CA 94114"
    """
    cleaned = re.sub(
        r"(?i)(?:,\s*|\s+)(?:#\s*[\w-]+|apt\.?\s*[\w-]+|apartment\s*[\w-]+|unit\s*[\w-]+|suite\s*[\w-]+|ste\.?\s*[\w-]+)\b",
        "",
        address,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    return cleaned.strip(" ,")
