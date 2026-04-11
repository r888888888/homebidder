"""
Tool: fetch_crime_data

Fetches crime incident counts near a property within a 0.5-mile radius
over the last 90 days.

Routing:
  - San Francisco county → DataSF Socrata API (SFPD, free, no key required)
  - All other Bay Area counties → SpotCrime API (requires SPOTCRIME_API_KEY)

Distinguishes violent crimes (homicide, robbery, assault, rape) from
property crimes (burglary, theft, motor vehicle theft, arson).
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RADIUS_MILES = 0.5
_RADIUS_METERS = int(_RADIUS_MILES * 1609.34)  # ≈ 804 m
_PERIOD_DAYS = 90

# DataSF SFPD incident category sets
_SFPD_VIOLENT: set[str] = {
    "Homicide", "Robbery", "Assault", "Rape", "Human Trafficking",
}
_SFPD_PROPERTY: set[str] = {
    "Burglary", "Larceny Theft", "Motor Vehicle Theft", "Arson", "Stolen Property",
}

# SpotCrime type sets
_SPOTCRIME_VIOLENT: set[str] = {"Assault", "Robbery", "Shooting", "Homicide"}
_SPOTCRIME_PROPERTY: set[str] = {"Theft", "Burglary", "Arson", "Vandalism"}

_NULL_RESULT: dict[str, Any] = {
    "violent_count": None,
    "property_count": None,
    "total_count": None,
    "radius_miles": _RADIUS_MILES,
    "period_days": _PERIOD_DAYS,
    "source": None,
    "top_violent_types": [],
    "top_property_types": [],
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def fetch_crime_data(
    latitude: float,
    longitude: float,
    county: str,
) -> dict[str, Any]:
    """
    Fetch crime statistics near a property.

    Routes to DataSF (free) for San Francisco county, SpotCrime (API key
    required) for other Bay Area counties. Returns violent_count,
    property_count, total_count, top crime types, and source attribution.
    """
    county_lower = (county or "").strip().lower()
    if county_lower == "san francisco":
        return await _fetch_datasf(latitude, longitude)
    return await _fetch_spotcrime(latitude, longitude)


# ---------------------------------------------------------------------------
# DataSF — San Francisco only
# ---------------------------------------------------------------------------

async def _fetch_datasf(lat: float, lon: float) -> dict[str, Any]:
    """Query DataSF SFPD incident reports API (no API key required)."""
    start_date = (datetime.utcnow() - timedelta(days=_PERIOD_DAYS)).strftime(
        "%Y-%m-%dT00:00:00"
    )
    url = "https://data.sfgov.org/resource/wg3w-h783.json"
    params = {
        "$where": (
            f"within_circle(point,{lat},{lon},{_RADIUS_METERS}) "
            f"AND incident_datetime >= '{start_date}'"
        ),
        "$select": "incident_category,incident_subcategory",
        "$limit": 1000,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            incidents = resp.json()
    except Exception as exc:
        log.warning("DataSF crime fetch failed: %s", exc)
        return _NULL_RESULT.copy()

    violent_types: dict[str, int] = {}
    property_types: dict[str, int] = {}

    for incident in incidents:
        category = incident.get("incident_category") or "Other"
        if category in _SFPD_VIOLENT:
            violent_types[category] = violent_types.get(category, 0) + 1
        elif category in _SFPD_PROPERTY:
            property_types[category] = property_types.get(category, 0) + 1

    violent_count = sum(violent_types.values())
    property_count = sum(property_types.values())

    return {
        "violent_count": violent_count,
        "property_count": property_count,
        "total_count": violent_count + property_count,
        "radius_miles": _RADIUS_MILES,
        "period_days": _PERIOD_DAYS,
        "source": "SFPD / DataSF",
        "top_violent_types": _top_types(violent_types),
        "top_property_types": _top_types(property_types),
    }


# ---------------------------------------------------------------------------
# SpotCrime — non-SF Bay Area cities
# ---------------------------------------------------------------------------

async def _fetch_spotcrime(lat: float, lon: float) -> dict[str, Any]:
    """Query SpotCrime API (requires SPOTCRIME_API_KEY env var)."""
    api_key = settings.spotcrime_api_key
    if not api_key:
        return _NULL_RESULT.copy()

    url = "https://api.spotcrime.com/crimes.json"
    params = {
        "lat": lat,
        "lon": lon,
        "distance": _RADIUS_MILES,
        "key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("SpotCrime fetch failed: %s", exc)
        return _NULL_RESULT.copy()

    cutoff = datetime.utcnow() - timedelta(days=_PERIOD_DAYS)
    violent_types: dict[str, int] = {}
    property_types: dict[str, int] = {}

    for crime in data.get("crimes") or []:
        date_str = (crime.get("date") or "")[:10]
        try:
            incident_date = datetime.strptime(date_str, "%m/%d/%Y")
            if incident_date < cutoff:
                continue
        except ValueError:
            pass  # include if date is unparseable

        crime_type = crime.get("type") or "Other"
        if crime_type in _SPOTCRIME_VIOLENT:
            violent_types[crime_type] = violent_types.get(crime_type, 0) + 1
        elif crime_type in _SPOTCRIME_PROPERTY:
            property_types[crime_type] = property_types.get(crime_type, 0) + 1

    violent_count = sum(violent_types.values())
    property_count = sum(property_types.values())

    return {
        "violent_count": violent_count,
        "property_count": property_count,
        "total_count": violent_count + property_count,
        "radius_miles": _RADIUS_MILES,
        "period_days": _PERIOD_DAYS,
        "source": "SpotCrime",
        "top_violent_types": _top_types(violent_types),
        "top_property_types": _top_types(property_types),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _top_types(counts: dict[str, int], n: int = 3) -> list[str]:
    return sorted(counts, key=counts.__getitem__, reverse=True)[:n]
