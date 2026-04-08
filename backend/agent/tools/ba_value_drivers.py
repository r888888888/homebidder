"""Bay Area investment value drivers: ADU, rent control, and transit proximity."""

import json
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any

import httpx

import os
from urllib.parse import quote as _url_quote

ACS_B25064 = "B25064_001E"


async def _fetch_zip_median_rent(zip_code: str) -> float | None:
    api_key = os.environ.get("CENSUS_API_KEY")
    if not api_key or not zip_code:
        return None

    url = (
        "https://api.census.gov/data/2022/acs/acs5"
        f"?get={ACS_B25064}&for=zip+code+tabulation+area:{_url_quote(zip_code)}&key={_url_quote(api_key)}"
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

CALTRAIN_PATH = Path(__file__).parent.parent.parent / "data" / "caltrain_stations.json"

_bart_cache: list[dict[str, Any]] | None = None

_RENT_CONTROL_CITIES = {
    "san francisco": {"name": "San Francisco", "max_year": 1978, "implications": "Likely subject to SF Rent Ordinance for older rentals."},
    "oakland": {"name": "Oakland", "max_year": 9999, "implications": "Most Oakland rentals are covered by local rent adjustment rules."},
    "berkeley": {"name": "Berkeley", "max_year": 1979, "implications": "Likely subject to Berkeley rent stabilization for older units."},
    "mountain view": {"name": "Mountain View", "max_year": 9999, "implications": "May be covered by CSFRA rent stabilization rules."},
    "east palo alto": {"name": "East Palo Alto", "max_year": 9999, "implications": "Local rent stabilization may cap annual increases."},
    "hayward": {"name": "Hayward", "max_year": 9999, "implications": "Rent review/stabilization protections may apply."},
    "san jose": {"name": "San Jose", "max_year": 1979, "implications": "Likely covered by Apartment Rent Ordinance for older multifamily stock."},
}


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.7613
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return radius_miles * c


def _is_sfr(property_type: str | None) -> bool:
    if not property_type:
        return False
    normalized = property_type.strip().upper()
    return normalized in {"SINGLE_FAMILY", "SFR", "SFH"}


def _load_caltrain_stations() -> list[dict[str, Any]]:
    if not CALTRAIN_PATH.exists():
        return []
    with open(CALTRAIN_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, list) else []


async def _fetch_bart_stations() -> list[dict[str, Any]]:
    global _bart_cache
    if _bart_cache is not None:
        return _bart_cache

    bart_stations_url = f"https://api.bart.gov/api/stn.aspx?key={_url_quote(os.environ.get('BART_API_KEY', ''))}&cmd=stns&json=y"

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.get(bart_stations_url)
        response.raise_for_status()
        payload = response.json()

    stations = (((payload.get("root") or {}).get("stations") or {}).get("station") or [])
    normalized: list[dict[str, Any]] = []
    for station in stations:
        try:
            normalized.append(
                {
                    "name": station.get("name"),
                    "lat": float(station.get("gtfs_latitude")),
                    "lon": float(station.get("gtfs_longitude")),
                    "system": "BART",
                }
            )
        except (TypeError, ValueError):
            continue

    _bart_cache = normalized
    return normalized


def _nearest_station(lat: float, lon: float, stations: list[dict[str, Any]]) -> tuple[str | None, float | None, str | None]:
    if not stations:
        return None, None, None

    nearest_name: str | None = None
    nearest_distance: float | None = None
    nearest_system: str | None = None

    for station in stations:
        s_lat = station.get("lat")
        s_lon = station.get("lon")
        if s_lat is None or s_lon is None:
            continue
        distance = _haversine_miles(lat, lon, float(s_lat), float(s_lon))
        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_name = station.get("name")
            nearest_system = station.get("system")

    if nearest_distance is None:
        return None, None, None
    return nearest_name, round(nearest_distance, 3), nearest_system


def _rent_control(city: str | None, year_built: int | None) -> dict[str, Any]:
    if not city:
        return {"rent_controlled": False, "rent_control_city": None, "implications": "No city-level rent-control rule detected."}

    key = city.strip().lower()
    rule = _RENT_CONTROL_CITIES.get(key)
    if not rule:
        return {"rent_controlled": False, "rent_control_city": None, "implications": "No city-level rent-control rule detected."}

    if year_built is None or int(year_built) <= int(rule["max_year"]):
        return {
            "rent_controlled": True,
            "rent_control_city": rule["name"],
            "implications": rule["implications"],
        }

    return {"rent_controlled": False, "rent_control_city": rule["name"], "implications": "Likely exempt by construction vintage."}


async def fetch_ba_value_drivers(
    property: dict[str, Any],
    zip_code: str,
) -> dict[str, Any]:
    """Compute Bay Area-specific value drivers with no external paid APIs."""
    lot_size = property.get("lot_size")
    is_adu_candidate = bool(lot_size and float(lot_size) >= 3000 and _is_sfr(property.get("property_type")))

    zip_median_rent = await _fetch_zip_median_rent(zip_code)
    adu_rent_estimate = round(zip_median_rent * 0.65, 2) if (is_adu_candidate and zip_median_rent is not None) else None

    rent_control = _rent_control(property.get("city"), property.get("year_built"))

    lat = property.get("latitude")
    lon = property.get("longitude")
    nearest_name: str | None = None
    nearest_distance: float | None = None
    nearest_system: str | None = None
    transit_premium_likely = False

    if lat is not None and lon is not None:
        bart = await _fetch_bart_stations()
        caltrain = [
            {"name": s.get("name"), "lat": s.get("lat"), "lon": s.get("lon"), "system": "Caltrain"}
            for s in _load_caltrain_stations()
        ]
        nearest_name, nearest_distance, nearest_system = _nearest_station(float(lat), float(lon), bart + caltrain)
        transit_premium_likely = bool(nearest_distance is not None and nearest_distance <= 0.5)

    return {
        "adu_potential": is_adu_candidate,
        "adu_rent_estimate": adu_rent_estimate,
        "zip_median_rent": zip_median_rent,
        "rent_controlled": rent_control["rent_controlled"],
        "rent_control_city": rent_control["rent_control_city"],
        "implications": rent_control["implications"],
        "nearest_bart_station": nearest_name if nearest_system == "BART" else None,
        "bart_distance_miles": nearest_distance if nearest_system == "BART" else None,
        "nearest_transit_station": nearest_name,
        "transit_distance_miles": nearest_distance,
        "transit_system": nearest_system,
        "transit_premium_likely": transit_premium_likely,
    }
