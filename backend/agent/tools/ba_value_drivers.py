"""Bay Area investment value drivers: ADU, rent control, and transit proximity."""

import json
import os
import time
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from urllib.parse import quote as _url_quote

import httpx

from config import settings

BART_CACHE_PATH = str(Path(__file__).parent.parent.parent / "data" / "bart_stations.json")
BART_CACHE_TTL = 30 * 86_400  # 30 days

CALTRAIN_CACHE_PATH = str(Path(__file__).parent.parent.parent / "data" / "caltrain_stations.json")

MUNI_CACHE_PATH = str(Path(__file__).parent.parent.parent / "data" / "muni_stops.json")

# Key MUNI Metro (light rail) stops. These are the underground Market St subway
# stations plus major surface stops on J/K/L/M/N/T lines. Coordinates are
# approximate; a full GTFS import would cover bus stops too, but MUNI Metro
# stops are the primary transit-premium driver. With ~35 stops a linear scan
# with haversine is fast enough — no spatial index required.
_MUNI_METRO_STOPS = [
    # Market St underground subway (shared by J/K/L/M/N/T)
    {"name": "Embarcadero Station", "lat": 37.7929, "lon": -122.3971, "system": "MUNI"},
    {"name": "Montgomery St Station", "lat": 37.7894, "lon": -122.4012, "system": "MUNI"},
    {"name": "Powell St Station", "lat": 37.7844, "lon": -122.4078, "system": "MUNI"},
    {"name": "Civic Center Station", "lat": 37.7799, "lon": -122.4139, "system": "MUNI"},
    {"name": "Van Ness Station", "lat": 37.7748, "lon": -122.4195, "system": "MUNI"},
    {"name": "Church St Station", "lat": 37.7672, "lon": -122.4285, "system": "MUNI"},
    {"name": "Castro Station", "lat": 37.7626, "lon": -122.4350, "system": "MUNI"},
    {"name": "Forest Hill Station", "lat": 37.7571, "lon": -122.4545, "system": "MUNI"},
    {"name": "West Portal Station", "lat": 37.7397, "lon": -122.4659, "system": "MUNI"},
    # N Judah surface stops
    {"name": "Carl & Cole (N Judah)", "lat": 37.7662, "lon": -122.4498, "system": "MUNI"},
    {"name": "9th Ave & Irving (N Judah)", "lat": 37.7636, "lon": -122.4671, "system": "MUNI"},
    {"name": "19th Ave & Irving (N Judah)", "lat": 37.7636, "lon": -122.4803, "system": "MUNI"},
    {"name": "28th Ave & Judah (N Judah)", "lat": 37.7630, "lon": -122.4912, "system": "MUNI"},
    {"name": "37th Ave & Judah (N Judah)", "lat": 37.7629, "lon": -122.5038, "system": "MUNI"},
    {"name": "La Playa & Judah (N Judah)", "lat": 37.7629, "lon": -122.5094, "system": "MUNI"},
    # J Church surface stops
    {"name": "22nd St & Church (J Church)", "lat": 37.7552, "lon": -122.4282, "system": "MUNI"},
    {"name": "24th St & Church (J Church)", "lat": 37.7522, "lon": -122.4282, "system": "MUNI"},
    {"name": "30th St & Church (J Church)", "lat": 37.7465, "lon": -122.4295, "system": "MUNI"},
    # T Third Street
    {"name": "4th & King (T Third)", "lat": 37.7770, "lon": -122.3942, "system": "MUNI"},
    {"name": "22nd St (T Third)", "lat": 37.7573, "lon": -122.3878, "system": "MUNI"},
    {"name": "Cesar Chavez (T Third)", "lat": 37.7501, "lon": -122.3878, "system": "MUNI"},
    {"name": "Bayview–Hunter's Point (T Third)", "lat": 37.7347, "lon": -122.3873, "system": "MUNI"},
    {"name": "Visitacion Valley (T Third)", "lat": 37.7211, "lon": -122.4097, "system": "MUNI"},
    # K/L/M west of West Portal
    {"name": "St Francis Circle (K/L/M)", "lat": 37.7364, "lon": -122.4538, "system": "MUNI"},
    {"name": "Ocean & Aptos (K/M)", "lat": 37.7289, "lon": -122.4600, "system": "MUNI"},
    {"name": "19th Ave & Holloway (K/M)", "lat": 37.7234, "lon": -122.4800, "system": "MUNI"},
    {"name": "19th Ave & Ulloa (L Taraval)", "lat": 37.7399, "lon": -122.4804, "system": "MUNI"},
    {"name": "22nd Ave & Ulloa (L Taraval)", "lat": 37.7399, "lon": -122.4841, "system": "MUNI"},
    {"name": "32nd Ave & Taraval (L Taraval)", "lat": 37.7399, "lon": -122.4973, "system": "MUNI"},
    {"name": "46th Ave & Taraval (L Taraval)", "lat": 37.7399, "lon": -122.5143, "system": "MUNI"},
]

_CALTRAIN_STATIONS = [
    {"name": "San Francisco", "lat": 37.7764, "lon": -122.3947},
    {"name": "22nd Street", "lat": 37.7574, "lon": -122.3927},
    {"name": "Bayshore", "lat": 37.7061, "lon": -122.4014},
    {"name": "South San Francisco", "lat": 37.6557, "lon": -122.4047},
    {"name": "Millbrae", "lat": 37.6000, "lon": -122.3867},
    {"name": "San Mateo", "lat": 37.5681, "lon": -122.3258},
    {"name": "Redwood City", "lat": 37.4852, "lon": -122.2319},
    {"name": "Palo Alto", "lat": 37.4435, "lon": -122.1652},
    {"name": "Mountain View", "lat": 37.3944, "lon": -122.0763},
    {"name": "Sunnyvale", "lat": 37.3784, "lon": -122.0311},
    {"name": "San Jose Diridon", "lat": 37.3299, "lon": -121.9025},
]

ACS_B25064 = "B25064_001E"  # median gross rent, all units

# ACS B25031: median gross rent by number of bedrooms
_ACS_B25031_BY_BEDS: dict[int, str] = {
    0: "B25031_002E",
    1: "B25031_003E",
    2: "B25031_004E",
    3: "B25031_005E",
    4: "B25031_006E",
}
_ACS_B25031_5PLUS = "B25031_007E"


def _bedroom_acs_var(beds: int | None) -> str | None:
    if beds is None:
        return None
    beds_int = int(beds)
    if beds_int >= 5:
        return _ACS_B25031_5PLUS
    return _ACS_B25031_BY_BEDS.get(beds_int)


async def _fetch_zip_median_rent(zip_code: str, beds: int | None = None) -> float | None:
    api_key = settings.census_api_key
    if not api_key or not zip_code:
        return None

    bedroom_var = _bedroom_acs_var(beds)
    get_vars = f"{bedroom_var},{ACS_B25064}" if bedroom_var else ACS_B25064

    url = (
        "https://api.census.gov/data/2022/acs/acs5"
        f"?get={get_vars}&for=zip+code+tabulation+area:{_url_quote(zip_code)}&key={_url_quote(api_key)}"
    )

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    if len(data) < 2:
        return None

    headers, row = data[0], data[1]

    if bedroom_var:
        try:
            idx = headers.index(bedroom_var)
            value = int(row[idx])
            if value >= 0:
                return float(value)
        except (ValueError, IndexError):
            pass

    # Fall back to all-units median
    try:
        idx = headers.index(ACS_B25064)
        value = int(row[idx])
    except (ValueError, IndexError):
        return None

    if value < 0:
        return None
    return float(value)

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
    try:
        with open(CALTRAIN_CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, list) else _CALTRAIN_STATIONS
    except FileNotFoundError:
        return _CALTRAIN_STATIONS


async def prefetch_caltrain_stations(force: bool = False) -> bool:
    """
    Write the built-in Caltrain station list to disk.
    Returns True when written, False when the file already exists and force is False.
    """
    if not force and os.path.exists(CALTRAIN_CACHE_PATH):
        return False
    with open(CALTRAIN_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(_CALTRAIN_STATIONS, f)
    return True


def _load_muni_stops() -> list[dict[str, Any]]:
    try:
        with open(MUNI_CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, list) else _MUNI_METRO_STOPS
    except FileNotFoundError:
        return _MUNI_METRO_STOPS


async def prefetch_muni_stops(force: bool = False) -> bool:
    """
    Write the built-in MUNI Metro stop list to disk.
    Returns True when written, False when the file already exists and force is False.
    """
    if not force and os.path.exists(MUNI_CACHE_PATH):
        return False
    with open(MUNI_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(_MUNI_METRO_STOPS, f)
    return True


def _bart_cache_valid() -> bool:
    if not os.path.exists(BART_CACHE_PATH):
        return False
    return (time.time() - os.path.getmtime(BART_CACHE_PATH)) < BART_CACHE_TTL


async def _download_bart_stations() -> list[dict[str, Any]]:
    bart_stations_url = f"https://api.bart.gov/api/stn.aspx?key={_url_quote(settings.bart_api_key)}&cmd=stns&json=y"

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
    return normalized


async def prefetch_bart_stations(force: bool = False) -> bool:
    """
    Download and cache BART stations to disk.
    Returns True when a download happened, False when cache was already fresh.
    """
    if not force and _bart_cache_valid():
        return False

    stations = await _download_bart_stations()
    with open(BART_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(stations, f)
    return True


async def _fetch_bart_stations() -> list[dict[str, Any]]:
    """Read BART stations from disk cache. Does not make network calls at request time."""
    global _bart_cache
    if _bart_cache is not None:
        return _bart_cache

    try:
        with open(BART_CACHE_PATH, "r", encoding="utf-8") as f:
            stations = json.load(f)
        _bart_cache = stations
        return stations
    except FileNotFoundError:
        return []
    except Exception:
        return []


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

    zip_median_rent = await _fetch_zip_median_rent(zip_code, beds=property.get("bedrooms"))
    adu_rent_estimate = round(zip_median_rent * 0.65, 2) if (is_adu_candidate and zip_median_rent is not None) else None

    rent_control = _rent_control(property.get("city"), property.get("year_built"))

    lat = property.get("latitude")
    lon = property.get("longitude")
    nearest_name: str | None = None
    nearest_distance: float | None = None
    nearest_system: str | None = None
    transit_premium_likely = False

    nearest_muni_stop: str | None = None
    muni_distance_miles: float | None = None

    if lat is not None and lon is not None:
        bart = await _fetch_bart_stations()
        caltrain = [
            {"name": s.get("name"), "lat": s.get("lat"), "lon": s.get("lon"), "system": "Caltrain"}
            for s in _load_caltrain_stations()
        ]
        muni = _load_muni_stops()
        nearest_name, nearest_distance, nearest_system = _nearest_station(float(lat), float(lon), bart + caltrain + muni)
        transit_premium_likely = bool(nearest_distance is not None and nearest_distance <= 0.5)

        nearest_muni_name, nearest_muni_dist, _ = _nearest_station(float(lat), float(lon), muni)
        nearest_muni_stop = nearest_muni_name
        muni_distance_miles = nearest_muni_dist

    return {
        "adu_potential": is_adu_candidate,
        "adu_rent_estimate": adu_rent_estimate,
        "zip_median_rent": zip_median_rent,
        "rent_controlled": rent_control["rent_controlled"],
        "rent_control_city": rent_control["rent_control_city"],
        "implications": rent_control["implications"],
        "nearest_bart_station": nearest_name if nearest_system == "BART" else None,
        "bart_distance_miles": nearest_distance if nearest_system == "BART" else None,
        "nearest_muni_stop": nearest_muni_stop,
        "muni_distance_miles": muni_distance_miles,
        "nearest_transit_station": nearest_name,
        "transit_distance_miles": nearest_distance,
        "transit_system": nearest_system,
        "transit_premium_likely": transit_premium_likely,
    }
