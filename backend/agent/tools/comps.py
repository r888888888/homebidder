"""
Fetch comparable sales (comps) for a given property address.

Primary path:  homeharvest → Realtor.com + Redfin (lower legal risk, structured output)
Fallback path: Redfin Stingray /gis-csv endpoint with a shapely bounding-box polygon
               centered on the geocoded subject address (no JS rendering required)
"""

import asyncio
import csv
import datetime as dt
import io
import math
import random
import re
from typing import Any
from urllib.parse import urlencode

import httpx
from shapely.geometry import Point

from .scraper import _USER_AGENTS

RENTCAST_AVM_URL = "https://api.rentcast.io/v1/avm/value"


# ---------------------------------------------------------------------------
# Haversine distance (miles)
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in miles between two lat/lon points."""
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Adaptive radius by Bay Area ZIP density
# ---------------------------------------------------------------------------

# Dense urban SF ZIP codes (Mission, Castro, SoMa, Richmond, Sunset, etc.)
_DENSE_SF_ZIPS = {
    "94102", "94103", "94104", "94105", "94107", "94108", "94109",
    "94110", "94111", "94112", "94113", "94114", "94115", "94116",
    "94117", "94118", "94119", "94120", "94121", "94122", "94123",
    "94124", "94125", "94126", "94127", "94128", "94129", "94130",
    "94131", "94132", "94133", "94134",
}

# Dense urban Oakland / Berkeley ZIP codes
_DENSE_OAKLAND_ZIPS = {
    "94601", "94602", "94603", "94605", "94606", "94607", "94608",
    "94609", "94610", "94611", "94612", "94613", "94618", "94619",
    "94621", "94702", "94703", "94704", "94705", "94706", "94707",
    "94708", "94709", "94710",
}

_DENSE_ZIPS = _DENSE_SF_ZIPS | _DENSE_OAKLAND_ZIPS

# Suburban Bay Area ZIP codes (Peninsula, South Bay, East Bay suburbs)
_SUBURBAN_BAY_AREA_ZIPS = {
    # Marin
    "94901", "94903", "94904", "94920", "94924", "94925", "94930",
    "94939", "94941", "94945", "94947", "94949", "94960", "94965",
    # Peninsula / South Bay
    "94002", "94005", "94010", "94014", "94015", "94019", "94025",
    "94027", "94028", "94030", "94044", "94061", "94062", "94063",
    "94065", "94066", "94070", "94080", "94401", "94402", "94403",
    "94404", "94501", "94502", "94506", "94507", "94509", "94513",
    "94514", "94516", "94517", "94518", "94519", "94520", "94521",
    "94523", "94526", "94528", "94530", "94531", "94536", "94538",
    "94539", "94541", "94542", "94544", "94545", "94546", "94547",
    "94549", "94550", "94551", "94552", "94553", "94555", "94556",
    "94558", "94559", "94561", "94563", "94564", "94565", "94566",
    "94568", "94569", "94572", "94577", "94578", "94579", "94580",
    "94582", "94583", "94585", "94586", "94587", "94588", "94595",
    "94596", "94597", "94598",
    # Santa Clara County
    "94022", "94024", "94035", "94040", "94041", "94043", "94301",
    "94302", "94303", "94304", "94305", "94306", "94086", "94087",
    "94088", "94089", "95002", "95008", "95013", "95014", "95020",
    "95032", "95035", "95037", "95046", "95050", "95051", "95054",
    "95070", "95110", "95111", "95112", "95116", "95117", "95118",
    "95119", "95120", "95121", "95122", "95123", "95124", "95125",
    "95126", "95127", "95128", "95129", "95130", "95131", "95132",
    "95133", "95134", "95135", "95136", "95138", "95139", "95148",
}


def _adaptive_radius(zip_code: str) -> float:
    """
    Return a search radius in miles appropriate for the zip code density.
    - Dense SF/Oakland: 0.3 mi
    - Suburban Bay Area: 0.75 mi
    - Everything else: 1.0 mi
    """
    z = str(zip_code).strip()
    if z in _DENSE_ZIPS:
        return 0.3
    if z in _SUBURBAN_BAY_AREA_ZIPS:
        return 0.75
    return 1.0


# ---------------------------------------------------------------------------
# Primary: homeharvest (Realtor.com + Redfin)
# ---------------------------------------------------------------------------

async def fetch_comps(
    address: str,
    city: str,
    state: str,
    zip_code: str,
    subject_lat: float | None = None,
    subject_lon: float | None = None,
    subject_sqft: int | None = None,
    subject_property_type: str | None = None,
    bedrooms: int | None = None,
    max_results: int = 100,
) -> list[dict[str, Any]]:
    """
    Search for recently sold comps near the subject property.
    Tries homeharvest first; falls back to Redfin Stingray if it fails.

    Phase 4 additions:
    - subject_lat/lon: used to compute per-comp distance_miles via haversine
    - subject_sqft: when provided, filters comps to ±25% sqft of subject
    - pct_over_asking: (sold_price - list_price) / list_price * 100, or None
    - distance_miles: haversine distance from subject, or None when comp lacks coords
    """
    subject_type_norm = _normalize_property_type(subject_property_type)

    try:
        df = await asyncio.to_thread(_scrape_homeharvest_comps, zip_code, bedrooms, max_results)
        if df is not None and not df.empty:
            comps = _process_df(
                df,
                address,
                subject_lat,
                subject_lon,
                subject_sqft,
                max_results,
                subject_type_norm,
            )
            return await _fill_missing_sqft(comps)
    except Exception:
        pass

    # Fallback: geocode address → Redfin Stingray /gis-csv
    try:
        coords = await _geocode_census(address, city, state, zip_code)
        if coords:
            return await _stingray_comps(
                *coords,
                bedrooms=bedrooms,
                max_results=max_results,
                subject_property_type=subject_type_norm,
            )
    except Exception:
        pass

    return []


def _scrape_homeharvest_comps(location: str, bedrooms: int | None, max_results: int):
    """Synchronous — run via asyncio.to_thread. Returns a DataFrame or None."""
    from homeharvest import scrape_property

    df = scrape_property(
        listing_type="sold",
        location=location,
        past_days=90,
        limit=max_results*3,
    )

    if df is None or df.empty:
        return df

    if bedrooms is not None:
        df = df[df["beds"].between(bedrooms - 1, bedrooms + 1, inclusive="both")]

    return df


def _fmt_date(val: Any) -> str | None:
    """Return ISO date string 'YYYY-MM-DD' from a pandas Timestamp, date, or string; None for missing."""
    if val is None:
        return None
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    return s[:10] if s else None


def _process_df(
    df,
    subject_address: str,
    subject_lat: float | None,
    subject_lon: float | None,
    subject_sqft: int | None,
    max_results: int,
    subject_property_type: str | None = None,
) -> list[dict[str, Any]]:
    """Convert homeharvest DataFrame to list of comp dicts with Phase 4 enrichments."""
    comps = []
    for _, row in df.iterrows():
        sqft = _safe(row, "sqft")
        comp_property_type = _safe(row, "style") or _safe(row, "property_type")
        comp_type_norm = _normalize_property_type(comp_property_type)
        comp_address = _safe(row, "street", "")
        comp_unit = _safe(row, "unit_number") or _safe(row, "unit") or _safe(row, "apartment")
        comp_sold_date = _fmt_date(_safe(row, "last_sold_date"))

        if subject_property_type:
            if comp_type_norm != subject_property_type:
                continue

        # Ignore the subject property itself when it sold recently (last 30 days).
        if _is_recent_same_property_sale(subject_address, comp_address, comp_unit, comp_sold_date):
            continue

        # sqft similarity filter (±25%) — only when subject_sqft provided
        if subject_sqft is not None and sqft is not None:
            if abs(sqft - subject_sqft) / subject_sqft > 0.25:
                continue

        sold_price = _safe(row, "sold_price") or _safe(row, "list_price")
        list_price = _safe(row, "list_price")

        # pct_over_asking
        if sold_price is not None and list_price is not None and list_price != 0:
            pct_over_asking = round((sold_price - list_price) / list_price * 100, 2)
        else:
            pct_over_asking = None

        # distance_miles
        comp_lat = _safe(row, "latitude")
        comp_lon = _safe(row, "longitude")
        if subject_lat is not None and subject_lon is not None and comp_lat is not None and comp_lon is not None:
            distance_miles = round(_haversine(subject_lat, subject_lon, comp_lat, comp_lon), 4)
        else:
            distance_miles = None

        comps.append({
            "address": comp_address,
            "unit": comp_unit,
            "city": _safe(row, "city", ""),
            "state": _safe(row, "state", ""),
            "zip_code": _safe(row, "zip_code", ""),
            "sold_price": sold_price,
            "list_price": list_price,
            "sold_date": comp_sold_date,
            "bedrooms": _safe(row, "beds"),
            "bathrooms": (_safe(row, "full_baths") or 0) + (_safe(row, "half_baths") or 0) * 0.5 or None,
            "sqft": sqft,
            "lot_size": _safe(row, "lot_sqft"),
            "property_type": comp_property_type,
            "price_per_sqft": round(sold_price / sqft, 2) if sold_price and sqft else None,
            "url": _safe(row, "property_url", ""),
            "latitude": comp_lat,
            "longitude": comp_lon,
            "pct_over_asking": pct_over_asking,
            "distance_miles": distance_miles,
            "source": "homeharvest",
        })

        if len(comps) >= max_results:
            break

    return comps


async def _fill_missing_sqft(comps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    For any comp missing sqft, fetch it from RentCast /v1/avm/value in parallel.
    Only comps with sqft=None are queried; all requests run concurrently.

    Set RENTCAST_SQFT_FALLBACK=0 to disable (useful in development to reduce API calls).
    """
    import os
    api_key = os.environ.get("RENTCAST_API_KEY")
    fallback_enabled = os.environ.get("RENTCAST_SQFT_FALLBACK", "1") not in ("0", "false", "False")
    missing_indices = [i for i, c in enumerate(comps) if c["sqft"] is None]
    if not missing_indices or not api_key or not fallback_enabled:
        return comps

    headers = {"X-Api-Key": api_key, "Accept": "application/json"}

    async def _fetch_sqft(comp: dict) -> int | None:
        addr = f"{comp['address']}, {comp['city']}, {comp['state']} {comp['zip_code']}"
        url = RENTCAST_AVM_URL + "?" + urlencode({"address": addr})
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            sqft = data.get("subjectProperty", {}).get("squareFootage")
            return int(sqft) if sqft is not None else None
        except Exception:
            return None

    results = await asyncio.gather(*[_fetch_sqft(comps[i]) for i in missing_indices])
    for i, sqft in zip(missing_indices, results):
        comps[i]["sqft"] = sqft
        sold_price = comps[i].get("sold_price")
        if sqft is not None and sold_price is not None:
            comps[i]["price_per_sqft"] = round(sold_price / sqft, 2)
    return comps


def _safe(row: Any, key: str, default: Any = None) -> Any:
    """Safely read a pandas Series value, returning default for NaN/None."""
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
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        return float(val)
    return val


# ---------------------------------------------------------------------------
# Fallback: Redfin Stingray /gis-csv with shapely bounding box
# ---------------------------------------------------------------------------

async def _geocode_census(
    address: str, city: str, state: str, zip_code: str
) -> tuple[float, float] | None:
    """
    Geocode an address using the free Census Geocoding API.
    Returns (lat, lng) or None if not found.
    """
    params = {
        "street": address,
        "city": city,
        "state": state,
        "zip": zip_code,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }
    url = "https://geocoding.geo.census.gov/geocoder/locations/address?" + urlencode(params)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    coords = matches[0]["coordinates"]
    return float(coords["y"]), float(coords["x"])  # lat, lng


async def _stingray_comps(
    lat: float,
    lng: float,
    bedrooms: int | None = None,
    max_results: int = 10,
    subject_property_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Call the Redfin Stingray /gis-csv endpoint with a bounding-box polygon
    generated by shapely. Returns recently sold comps as structured dicts.
    """
    lat_offset = 0.5 / 69.0
    lng_offset = 0.5 / 49.0

    bbox = Point(lng, lat).buffer(
        max(lat_offset, lng_offset),
        cap_style=3,
    )
    wkt_poly = bbox.wkt

    params: dict[str, Any] = {
        "status_type": 2,
        "num_homes": min(max_results, 350),
        "sold_within_days": 180,
        "poly": wkt_poly,
        "sf": _redfin_sf_filter_value(subject_property_type),
    }
    if bedrooms:
        params["num_beds"] = bedrooms

    url = "https://www.redfin.com/stingray/api/gis-csv?" + urlencode(params)
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/csv,*/*",
        "Referer": "https://www.redfin.com/",
    }

    await asyncio.sleep(random.uniform(1.5, 3.5))

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    return _parse_stingray_csv(resp.text, max_results)


def _parse_stingray_csv(text: str, max_results: int) -> list[dict[str, Any]]:
    comps = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        if len(comps) >= max_results:
            break
        try:
            sold_price = _float(row.get("PRICE"))
            sqft = _float(row.get("SQUARE FEET"))
            comps.append({
                "address": row.get("ADDRESS", ""),
                "unit": row.get("UNIT") or row.get("UNIT NUMBER") or None,
                "city": row.get("CITY", ""),
                "state": row.get("STATE OR PROVINCE", ""),
                "zip_code": row.get("ZIP OR POSTAL CODE", ""),
                "sold_price": sold_price,
                "list_price": None,
                "sold_date": row.get("SOLD DATE", ""),
                "bedrooms": _int(row.get("BEDS")),
                "bathrooms": _float(row.get("BATHS")),
                "sqft": sqft,
                "price_per_sqft": round(sold_price / sqft, 2) if sold_price and sqft else None,
                "url": row.get("URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)", ""),
                "latitude": None,
                "longitude": None,
                "pct_over_asking": None,
                "distance_miles": None,
                "source": "redfin_stingray",
            })
        except (ValueError, TypeError):
            continue
    return comps


def _float(val: Any) -> float | None:
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _int(val: Any) -> int | None:
    f = _float(val)
    return int(f) if f is not None else None


def _normalize_property_type(value: str | None) -> str | None:
    """Normalize raw property type labels to one of: sfh, condo, townhome."""
    if not value:
        return None
    v = str(value).strip().lower()
    if "condo" in v:
        return "condo"
    if "town" in v:
        return "townhome"
    if any(token in v for token in ("single", "sfh", "sfr", "house")):
        return "sfh"
    return None


def _extract_unit_token(text: str | None) -> str | None:
    if not text:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    normalized = re.sub(r"[-_/]+", " ", raw)
    m = re.search(
        r"(?i)(?:#\s*([\w-]+)|\bunit\s+([\w-]+)|\bapt\.?\s+([\w-]+)|\bsuite\s+([\w-]+)|\bste\.?\s+([\w-]+))",
        normalized,
    )
    if m:
        for g in m.groups():
            if g:
                return g.lower()
    return None


def _normalize_unit_value(value: str | None) -> str | None:
    """Normalize an explicit or raw unit field value from comp feeds."""
    explicit = _extract_unit_token(value)
    if explicit:
        return explicit
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    # Comp feeds often provide plain unit tokens like "515".
    plain = re.sub(r"[^a-zA-Z0-9-]", "", raw).lower()
    return plain or None


def _strip_unit_designator(address: str) -> str:
    cleaned = re.sub(
        r"(?i)(?:,\s*|\s+)(?:#\s*[\w-]+|apt\.?\s*[\w-]+|apartment\s*[\w-]+|unit\s*[\w-]+|suite\s*[\w-]+|ste\.?\s*[\w-]+)\b",
        "",
        address,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    return cleaned.strip(" ,")


def _normalize_street_base(text: str | None) -> str:
    if not text:
        return ""
    head = str(text).split(",")[0]
    no_unit = _strip_unit_designator(head)
    out = re.sub(r"[^a-zA-Z0-9 ]", " ", no_unit).lower()
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def _parse_iso_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _is_recent_same_property_sale(
    subject_address: str,
    comp_address: str | None,
    comp_unit: str | None,
    comp_sold_date: str | None,
    days: int = 30,
) -> bool:
    sold_date = _parse_iso_date(comp_sold_date)
    if sold_date is None:
        return False

    today = dt.date.today()
    if sold_date < today - dt.timedelta(days=days) or sold_date > today:
        return False

    if _normalize_street_base(subject_address) != _normalize_street_base(comp_address):
        return False

    subject_unit = _extract_unit_token(subject_address)
    comp_unit_norm = _normalize_unit_value(comp_unit)

    # For non-unit properties (SFH), matching address with no unit on both sides is enough.
    if subject_unit is None and comp_unit_norm is None:
        return True
    if subject_unit is None or comp_unit_norm is None:
        return False
    return subject_unit == comp_unit_norm


def _redfin_sf_filter_value(subject_property_type: str | None) -> str:
    """
    Redfin Stingray `sf` param:
    1=house, 2=condo, 3=townhouse, 6=multi-family, 13=mobile.
    """
    if subject_property_type == "sfh":
        return "1"
    if subject_property_type == "condo":
        return "2"
    if subject_property_type == "townhome":
        return "3"
    return "1,2,3,6,13"
