"""
Tool: lookup_property_by_address

1. Geocode the free-text address via the Census Geocoder API.
2. Attempt to pull listing details from homeharvest (Realtor.com + Redfin).
Returns a unified property dict and the geocoded coordinates.
"""

import asyncio
import re
from typing import Any
from urllib.parse import urlencode

import httpx

from .description_signals import extract_description_signals
from .condition_llm import evaluate_condition_with_llm, merge_signal_results

CENSUS_GEOCODER_URL = (
    "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
)


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
    for candidate in candidates:
        listing_candidate = await _homeharvest_listing(candidate)
        if listing_candidate:
            listing = listing_candidate
            break

    # HomeHarvest direct address search can miss valid condo units for certain
    # Realtor records. For unit inputs, try a nearby for-sale building search
    # and select the row matching the requested unit.
    if not listing and _extract_unit_token(address):
        base_address = _strip_unit_designator(address)
        if base_address:
            listing = await _homeharvest_nearby_unit_listing(base_address, address)

    # Determine source
    if listing:
        source = listing.pop("source", "homeharvest")
    else:
        source = "none"

    listing_description = listing.get("listing_description")
    rule_signals = extract_description_signals(listing_description)
    llm_signals = await evaluate_condition_with_llm(listing_description)
    description_signals = merge_signal_results(rule_signals, llm_signals)

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
        # Listing fields
        "price": listing.get("price"),
        "bedrooms": listing.get("bedrooms"),
        "bathrooms": listing.get("bathrooms"),
        "sqft": listing.get("sqft"),
        "year_built": listing.get("year_built"),
        "lot_size": listing.get("lot_size"),
        "property_type": listing.get("property_type"),
        "hoa_fee": listing.get("hoa_fee"),
        "days_on_market": listing.get("days_on_market"),
        "list_date": listing.get("list_date"),
        "city": listing.get("city"),
        "neighborhoods": listing.get("neighborhoods"),
        "listing_description": listing_description,
        "description_signals": description_signals,
        "price_history": listing.get("price_history", []),
        "avm_estimate": None,
        "listing_url": listing.get("property_url") or None,
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
    Falls back to recently sold data when no active listing is found.
    Returns an empty dict if nothing is found or if homeharvest raises.
    """
    # Try active for-sale listing first
    try:
        df = await asyncio.to_thread(_scrape_homeharvest, matched_address)
    except Exception:
        df = None

    if df is not None and not df.empty:
        row = _select_best_homeharvest_row(df, matched_address)
        if row is not None:
            # If the row has no meaningful listing data (e.g. a building-level APARTMENT
            # record returned by the search), treat it as no listing found.
            has_data = any([
                _safe(row, "list_price") is not None,
                _safe(row, "beds") is not None,
                _safe(row, "sqft") is not None,
                _safe(row, "year_built") is not None,
            ])
            if has_data:
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
                    "listing_description": _first_nonempty_text(
                        _safe(row, "text"),
                        _safe(row, "description"),
                        _safe(row, "remarks"),
                        _safe(row, "listing_remarks"),
                        _safe(row, "public_remarks"),
                    ),
                    "price_history": _safe(row, "price_history", []) or [],
                    "unit": str(unit_raw).strip() if unit_raw else None,
                    "property_url": str(_safe(row, "property_url", "") or ""),
                    "source": "homeharvest",
                }

    # Fallback: recently sold listing provides property characteristics for off-market homes
    return await _homeharvest_sold_listing(matched_address)


async def _homeharvest_sold_listing(matched_address: str) -> dict[str, Any]:
    """
    Fallback: look up recently sold data when no active for-sale listing is found.
    Returns an empty dict if nothing is found or if homeharvest raises.
    """
    try:
        df = await asyncio.to_thread(_scrape_homeharvest_sold, matched_address)
    except Exception:
        return {}

    if df is None or df.empty:
        return {}

    row = _select_best_homeharvest_row(df, matched_address)
    if row is None:
        return {}

    has_data = any([
        _safe(row, "sold_price") is not None,
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
    unit_raw = (
        _safe(row, "unit_number")
        or _safe(row, "unit")
        or _safe(row, "apartment")
        or _extract_unit_token(_safe(row, "street", ""))
    )
    sold_price = _safe(row, "sold_price")
    return {
        "price": sold_price if sold_price is not None else _safe(row, "list_price"),
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
        "listing_description": _first_nonempty_text(
            _safe(row, "text"),
            _safe(row, "description"),
            _safe(row, "remarks"),
            _safe(row, "listing_remarks"),
            _safe(row, "public_remarks"),
        ),
        "price_history": _safe(row, "price_history", []) or [],
        "unit": str(unit_raw).strip() if unit_raw else None,
        "property_url": str(_safe(row, "property_url", "") or ""),
        "source": "homeharvest_sold",
    }


async def _homeharvest_nearby_unit_listing(base_address: str, query_address: str) -> dict[str, Any]:
    """
    Fallback for unit addresses: search nearby for-sale listings around the
    building and choose the row that best matches the requested unit.
    """
    try:
        df = await asyncio.to_thread(_scrape_homeharvest_nearby, base_address)
    except Exception:
        return {}

    if df is None or df.empty:
        return {}

    row = _select_best_homeharvest_row(df, query_address)
    if row is None:
        return {}

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
        "listing_description": _first_nonempty_text(
            _safe(row, "text"),
            _safe(row, "description"),
            _safe(row, "remarks"),
            _safe(row, "listing_remarks"),
            _safe(row, "public_remarks"),
        ),
        "price_history": _safe(row, "price_history", []) or [],
        "unit": str(unit_raw).strip() if unit_raw else None,
        "property_url": str(_safe(row, "property_url", "") or ""),
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


def _scrape_homeharvest_nearby(location: str):
    """Synchronous nearby for-sale search around a building address."""
    from homeharvest import scrape_property

    return scrape_property(
        listing_type="for_sale",
        location=location,
        radius=0.05,
        limit=500,
    )


def _scrape_homeharvest_sold(location: str):
    """Synchronous recently-sold listing search. Called via asyncio.to_thread."""
    from homeharvest import scrape_property

    return scrape_property(
        listing_type="sold",
        location=location,
        past_days=180,
        limit=20,
    )



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


def _first_nonempty_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


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


def _same_street_number(base1: str, base2: str) -> bool:
    """Return True when both normalised bases start with the same street number."""
    def _first(s: str) -> str:
        parts = s.split()
        return parts[0] if parts else ""
    return _first(base1) == _first(base2)


def _select_best_homeharvest_row(df: Any, query_address: str):
    """
    Choose the best-matching homeharvest row for query_address.
    Important for multi-unit buildings where top result may be another unit.

    Returns None when no row has any address overlap with the query, so callers
    can return {} rather than displaying a completely wrong property.
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

        # Fall back to structured unit fields when street and URL lack a unit token
        if row_unit is None:
            for field in ("unit_number", "unit", "apartment"):
                val = _safe(row, field)
                if val is not None:
                    candidate = str(val).strip().lower()
                    if candidate:
                        row_unit = candidate
                        break

        score = 0
        base_matched = False

        if target_base and row_base:
            if row_base == target_base:
                score += 4
                base_matched = True
            elif _same_street_number(target_base, row_base) and (
                target_base in row_base or row_base in target_base
            ):
                # Partial match only when street numbers agree — prevents e.g.
                # "184 Caroline Way" from matching a "84 Caroline Way" query.
                score += 2
                base_matched = True

        if target_unit:
            # Only award unit score when the base address also matched.
            # A same-numbered unit at a different building (e.g. "1240 Ellis St #2"
            # for a "1250 Ellis St #2" query) must not score positively — the unit
            # bonus alone would push it past the best_score <= 0 guard.
            if not target_base or base_matched:
                if row_unit == target_unit or url_unit == target_unit:
                    score += 8
                elif row_unit is None and url_unit is None:
                    # Row has no unit info at all — when the query specifies a
                    # unit, a bare building-level record is not a valid match.
                    # Use a penalty large enough to push the score below 0 so the
                    # best_score <= 0 guard rejects it (base match is +4).
                    score -= 5
                else:
                    score -= 4
        elif row_unit is not None or url_unit is not None:
            # No unit in query: mildly prefer bare-address rows so a unit listing
            # doesn't beat a bare-address row on a tie.
            score -= 1

        if score > best_score:
            best_score = score
            best_row = row

    # If no row overlaps the target address at all, signal no valid match.
    if target_base and best_score <= 0:
        return None

    return best_row


def _listing_lookup_candidates(address: str, matched_address: str | None) -> list[str]:
    """
    Build deduped listing lookup candidates:
    1) exact user input
    2) unit-wording variant (if input includes '#')
    3) geocoder normalized address — ONLY when it includes unit info or the
       original address has no unit (avoids finding the wrong building-level record).
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

    # Include geocoder-matched address only if it won't lose unit information.
    # When the original has a unit but the geocoder strips it, searching the bare
    # street address can find the wrong building-level or SINGLE_FAMILY record.
    has_unit = bool(_extract_unit_token(address))
    matched_has_unit = bool(_extract_unit_token(matched_address)) if matched_address else False
    if not has_unit or matched_has_unit:
        _add(matched_address)

    return candidates
