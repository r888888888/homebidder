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

    # Prefer exact user input (and unit variants) before geocoder-normalized
    # address so condo/unit listings can be found.
    candidates = _listing_lookup_candidates(address, geo["address_matched"])

    listing: dict[str, Any] = {}
    rentcast: dict | None = None
    avm_fallback: dict | None = None
    for candidate in candidates:
        listing_candidate, rentcast_candidate = await asyncio.gather(
            _homeharvest_listing(candidate),
            _rentcast_data(candidate),
        )
        if listing_candidate:
            listing = listing_candidate
            rentcast = rentcast_candidate
            break
        if rentcast_candidate and rentcast_candidate.get("avm") is not None and avm_fallback is None:
            avm_fallback = rentcast_candidate

    if rentcast is None:
        rentcast = avm_fallback

    avm = rentcast.get("avm") if rentcast else None
    rc_sqft = rentcast.get("sqft") if rentcast else None
    rc_bedrooms = rentcast.get("bedrooms") if rentcast else None
    rc_bathrooms = rentcast.get("bathrooms") if rentcast else None
    rc_year_built = rentcast.get("year_built") if rentcast else None

    # Determine source
    if listing:
        source = listing.pop("source", "homeharvest")
    else:
        source = "rentcast" if avm is not None else "none"

    return {
        "address_input": address,
        # Geocoder fields (county falls back to homeharvest — geocoder omits it)
        "address_matched": geo["address_matched"],
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "county": listing.get("county") or geo["county"],
        "state": geo["state"],
        "zip_code": geo["zip_code"],
        # Unit number: prefer homeharvest structured field, fall back to parsing user input
        "unit": listing.get("unit") or _extract_unit_token(address),
        # Listing fields — RentCast subjectProperty used as fallback for off-market properties
        "price": listing.get("price"),
        "bedrooms": listing.get("bedrooms") or rc_bedrooms,
        "bathrooms": listing.get("bathrooms") or rc_bathrooms,
        "sqft": listing.get("sqft") or rc_sqft,
        "year_built": listing.get("year_built") or rc_year_built,
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

    row = _select_best_homeharvest_row(df, matched_address)

    # If the row has no meaningful listing data (e.g. a building-level APARTMENT
    # record returned by the search), treat it as no listing found.
    has_data = any([
        _safe(row, "list_price") is not None,
        _safe(row, "beds") is not None,
        _safe(row, "sqft") is not None,
        _safe(row, "year_built") is not None,
    ])
    if not has_data:
        return {}

    full_baths = _safe(row, "full_baths") or 0
    half_baths = _safe(row, "half_baths") or 0
    list_date_raw = _safe(row, "list_date")
    neighborhoods_raw = _safe(row, "neighborhoods")
    # Unit: prefer structured field from homeharvest, fall back to street parse
    unit_raw = (
        _safe(row, "unit_number")
        or _safe(row, "unit")
        or _safe(row, "apartment")
        or _extract_unit_token(_safe(row, "street", ""))
    )
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
        "unit": str(unit_raw).strip() if unit_raw else None,
        "source": "homeharvest",
    }


def _scrape_homeharvest(location: str):
    """Synchronous — called via asyncio.to_thread."""
    from homeharvest import scrape_property

    return scrape_property(
        listing_type="for_sale",
        location=location,
        limit=20,
    )


# ---------------------------------------------------------------------------
# Step 2b — RentCast AVM
# ---------------------------------------------------------------------------

RENTCAST_AVM_URL = "https://api.rentcast.io/v1/avm/value"


async def _rentcast_data(matched_address: str) -> dict | None:
    """
    Fetch AVM estimate from RentCast's /v1/avm/value endpoint.
    Also extracts property characteristics from subjectProperty for use as
    fallbacks when homeharvest has no listing data (e.g. off-market condos).
    Returns {"avm", "sqft", "bedrooms", "bathrooms", "year_built"} or None on failure.
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
        subj = data.get("subjectProperty", {})
        sqft = subj.get("squareFootage")
        bedrooms = subj.get("bedrooms")
        bathrooms = subj.get("bathrooms")
        year_built = subj.get("yearBuilt")
        return {
            "avm": float(price) if price is not None else None,
            "sqft": int(sqft) if sqft is not None else None,
            "bedrooms": int(bedrooms) if bedrooms is not None else None,
            "bathrooms": float(bathrooms) if bathrooms is not None else None,
            "year_built": int(year_built) if year_built is not None else None,
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


def _to_unit_wording(address: str) -> str:
    """Convert '#515' style address token to 'Unit 515'."""
    return re.sub(r"(?i)#\s*([\w-]+)\b", r"Unit \1", address)


def _extract_unit_token(text: str | None) -> str | None:
    if not text:
        return None
    normalized = str(text)
    # Realtor URLs often encode unit as `...-Unit-515...`; normalize separators
    # so token extraction can match both plain text and URL slugs.
    normalized = re.sub(r"[-_/]+", " ", normalized)
    m = re.search(
        r"(?i)(?:#\s*([\w-]+)|\bunit\s+([\w-]+)|\bapt\.?\s+([\w-]+)|\bsuite\s+([\w-]+)|\bste\.?\s+([\w-]+))",
        normalized,
    )
    if not m:
        return None
    for g in m.groups():
        if g:
            return g.lower()
    return None


def _normalize_street_base(text: str | None) -> str:
    """
    Normalize a street address to comparable base form without unit suffixes.
    """
    if not text:
        return ""
    head = str(text).split(",")[0]
    no_unit = _strip_unit_designator(head)
    out = re.sub(r"[^a-zA-Z0-9 ]", " ", no_unit).lower()
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def _select_best_homeharvest_row(df: Any, query_address: str):
    """
    Choose the best-matching homeharvest row for query_address.
    Important for multi-unit buildings where top result may be another unit.
    """
    target_unit = _extract_unit_token(query_address)
    target_base = _normalize_street_base(query_address)

    best_row = df.iloc[0]
    best_score = -10_000

    for _, row in df.iterrows():
        street = _safe(row, "street", "")
        row_base = _normalize_street_base(street)
        row_unit = _extract_unit_token(street)
        url_unit = _extract_unit_token(_safe(row, "property_url", ""))

        score = 0

        if target_base and row_base:
            if row_base == target_base:
                score += 4
            elif target_base in row_base or row_base in target_base:
                score += 2

        if target_unit:
            if row_unit == target_unit or url_unit == target_unit:
                score += 8
            elif row_unit is None and url_unit is None:
                score -= 1
            else:
                score -= 4

        if score > best_score:
            best_score = score
            best_row = row

    return best_row


def _listing_lookup_candidates(address: str, matched_address: str | None) -> list[str]:
    """
    Build deduped listing lookup candidates:
    1) exact user input
    2) unit-wording variant (if input includes '#')
    3) geocoder normalized address
    """
    candidates: list[str] = []

    def _add(value: str | None) -> None:
        if not value:
            return
        v = value.strip()
        if v and v not in candidates:
            candidates.append(v)

    _add(address)
    if "#" in address:
        _add(_to_unit_wording(address))
    _add(matched_address)
    return candidates
