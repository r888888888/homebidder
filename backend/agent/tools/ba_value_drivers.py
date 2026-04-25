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
from .rentcast_avm import fetch_rentcast_rent_estimate

BART_CACHE_PATH = str(Path(__file__).parent.parent.parent / "data" / "bart_stations.json")
BART_CACHE_TTL = 30 * 86_400  # 30 days

CALTRAIN_CACHE_PATH = str(Path(__file__).parent.parent.parent / "data" / "caltrain_stations.json")

MUNI_CACHE_PATH = str(Path(__file__).parent.parent.parent / "data" / "muni_stops.json")

SCHOOLS_CACHE_PATH = str(Path(__file__).parent.parent.parent / "data" / "schools.json")

# Key MUNI Metro (light rail) stops. These are the underground Market St subway
# stations plus surface stops on J/K/L/M/N/T lines and the 2022 Central Subway.
# Coordinates are approximate; a full GTFS import would cover bus stops too, but
# MUNI Metro stops are the primary transit-premium driver. ~75 stops, linear scan
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
    # T Third Central Subway extension (underground, opened 2022)
    {"name": "Chinatown-Rose Pak (T Third)", "lat": 37.7953, "lon": -122.4079, "system": "MUNI"},
    {"name": "Union Square/Market St (T Third)", "lat": 37.7875, "lon": -122.4082, "system": "MUNI"},
    {"name": "Yerba Buena/Moscone (T Third)", "lat": 37.7813, "lon": -122.4038, "system": "MUNI"},
    # N Judah surface stops (Cole Valley → Inner Sunset → Outer Sunset → Ocean Beach)
    {"name": "Carl & Cole (N Judah)", "lat": 37.7662, "lon": -122.4498, "system": "MUNI"},
    {"name": "Judah & Arguello (N Judah)", "lat": 37.7631, "lon": -122.4580, "system": "MUNI"},
    {"name": "Judah & 4th Ave (N Judah)", "lat": 37.7631, "lon": -122.4606, "system": "MUNI"},
    {"name": "Judah & 7th Ave (N Judah)", "lat": 37.7631, "lon": -122.4645, "system": "MUNI"},
    {"name": "9th Ave & Irving (N Judah)", "lat": 37.7636, "lon": -122.4671, "system": "MUNI"},
    {"name": "Judah & 11th Ave (N Judah)", "lat": 37.7632, "lon": -122.4697, "system": "MUNI"},
    {"name": "Judah & 14th Ave (N Judah)", "lat": 37.7632, "lon": -122.4736, "system": "MUNI"},
    {"name": "Judah & 16th Ave (N Judah)", "lat": 37.7632, "lon": -122.4762, "system": "MUNI"},
    {"name": "19th Ave & Irving (N Judah)", "lat": 37.7636, "lon": -122.4803, "system": "MUNI"},
    {"name": "Judah & 21st Ave (N Judah)", "lat": 37.7630, "lon": -122.4829, "system": "MUNI"},
    {"name": "Judah & 25th Ave (N Judah)", "lat": 37.7630, "lon": -122.4881, "system": "MUNI"},
    {"name": "28th Ave & Judah (N Judah)", "lat": 37.7630, "lon": -122.4912, "system": "MUNI"},
    {"name": "Judah & 31st Ave (N Judah)", "lat": 37.7629, "lon": -122.4951, "system": "MUNI"},
    {"name": "Judah & 33rd Ave (N Judah)", "lat": 37.7629, "lon": -122.4977, "system": "MUNI"},
    {"name": "37th Ave & Judah (N Judah)", "lat": 37.7629, "lon": -122.5038, "system": "MUNI"},
    {"name": "Judah & 40th Ave (N Judah)", "lat": 37.7629, "lon": -122.5080, "system": "MUNI"},
    {"name": "Judah & 43rd Ave (N Judah)", "lat": 37.7629, "lon": -122.5119, "system": "MUNI"},
    {"name": "La Playa & Judah (N Judah)", "lat": 37.7629, "lon": -122.5094, "system": "MUNI"},
    # J Church surface stops (Noe Valley → Glen Park)
    {"name": "Church & 17th St (J Church)", "lat": 37.7644, "lon": -122.4281, "system": "MUNI"},
    {"name": "Church & 18th St (J Church)", "lat": 37.7627, "lon": -122.4280, "system": "MUNI"},
    {"name": "Church & 20th St (J Church)", "lat": 37.7593, "lon": -122.4281, "system": "MUNI"},
    {"name": "22nd St & Church (J Church)", "lat": 37.7552, "lon": -122.4282, "system": "MUNI"},
    {"name": "24th St & Church (J Church)", "lat": 37.7522, "lon": -122.4282, "system": "MUNI"},
    {"name": "Church & 26th St (J Church)", "lat": 37.7502, "lon": -122.4283, "system": "MUNI"},
    {"name": "30th St & Church (J Church)", "lat": 37.7465, "lon": -122.4295, "system": "MUNI"},
    {"name": "Church & Cesar Chavez (J Church)", "lat": 37.7432, "lon": -122.4254, "system": "MUNI"},
    # T Third Street surface stops (Mission Bay → Potrero → Bayview → Visitacion Valley)
    {"name": "2nd & Berry (T Third)", "lat": 37.7762, "lon": -122.3912, "system": "MUNI"},
    {"name": "4th & King (T Third)", "lat": 37.7770, "lon": -122.3942, "system": "MUNI"},
    {"name": "16th & 3rd (T Third)", "lat": 37.7643, "lon": -122.3880, "system": "MUNI"},
    {"name": "18th & 3rd (T Third)", "lat": 37.7609, "lon": -122.3879, "system": "MUNI"},
    {"name": "20th & 3rd (T Third)", "lat": 37.7579, "lon": -122.3878, "system": "MUNI"},
    {"name": "22nd St (T Third)", "lat": 37.7573, "lon": -122.3878, "system": "MUNI"},
    {"name": "23rd & 3rd (T Third)", "lat": 37.7539, "lon": -122.3878, "system": "MUNI"},
    {"name": "Cesar Chavez (T Third)", "lat": 37.7501, "lon": -122.3878, "system": "MUNI"},
    {"name": "Oakdale & 3rd (T Third)", "lat": 37.7437, "lon": -122.3873, "system": "MUNI"},
    {"name": "Palou & 3rd (T Third)", "lat": 37.7411, "lon": -122.3872, "system": "MUNI"},
    {"name": "Gilman & 3rd (T Third)", "lat": 37.7385, "lon": -122.3870, "system": "MUNI"},
    {"name": "Bayview–Hunter's Point (T Third)", "lat": 37.7347, "lon": -122.3873, "system": "MUNI"},
    {"name": "Visitacion Valley (T Third)", "lat": 37.7211, "lon": -122.4097, "system": "MUNI"},
    # K/M Ocean Ave and Balboa Park area
    {"name": "Balboa Park Station (K/M)", "lat": 37.7218, "lon": -122.4474, "system": "MUNI"},
    {"name": "Ocean & Lee (K Ingleside)", "lat": 37.7261, "lon": -122.4558, "system": "MUNI"},
    {"name": "Ocean & Miramar (K Ingleside)", "lat": 37.7283, "lon": -122.4593, "system": "MUNI"},
    {"name": "St Francis Circle (K/L/M)", "lat": 37.7364, "lon": -122.4538, "system": "MUNI"},
    {"name": "Ocean & Aptos (K/M)", "lat": 37.7289, "lon": -122.4600, "system": "MUNI"},
    {"name": "19th Ave & Holloway (K/M)", "lat": 37.7234, "lon": -122.4800, "system": "MUNI"},
    {"name": "Geneva & Naples (M Ocean View)", "lat": 37.7170, "lon": -122.4483, "system": "MUNI"},
    {"name": "Broad & Plymouth (M Ocean View)", "lat": 37.7155, "lon": -122.4437, "system": "MUNI"},
    # L Taraval surface stops (West Portal → Outer Sunset → Ocean Beach)
    {"name": "Taraval & 10th Ave (L Taraval)", "lat": 37.7408, "lon": -122.4689, "system": "MUNI"},
    {"name": "Taraval & 14th Ave (L Taraval)", "lat": 37.7402, "lon": -122.4740, "system": "MUNI"},
    {"name": "Taraval & 17th Ave (L Taraval)", "lat": 37.7399, "lon": -122.4778, "system": "MUNI"},
    {"name": "19th Ave & Ulloa (L Taraval)", "lat": 37.7399, "lon": -122.4804, "system": "MUNI"},
    {"name": "Taraval & 21st Ave (L Taraval)", "lat": 37.7399, "lon": -122.4830, "system": "MUNI"},
    {"name": "22nd Ave & Ulloa (L Taraval)", "lat": 37.7399, "lon": -122.4841, "system": "MUNI"},
    {"name": "Taraval & 23rd Ave (L Taraval)", "lat": 37.7399, "lon": -122.4856, "system": "MUNI"},
    {"name": "Taraval & 25th Ave (L Taraval)", "lat": 37.7399, "lon": -122.4882, "system": "MUNI"},
    {"name": "Taraval & 27th Ave (L Taraval)", "lat": 37.7399, "lon": -122.4908, "system": "MUNI"},
    {"name": "Taraval & 30th Ave (L Taraval)", "lat": 37.7399, "lon": -122.4947, "system": "MUNI"},
    {"name": "32nd Ave & Taraval (L Taraval)", "lat": 37.7399, "lon": -122.4973, "system": "MUNI"},
    {"name": "Taraval & 36th Ave (L Taraval)", "lat": 37.7399, "lon": -122.5024, "system": "MUNI"},
    {"name": "Taraval & 40th Ave (L Taraval)", "lat": 37.7399, "lon": -122.5075, "system": "MUNI"},
    {"name": "Taraval & 44th Ave (L Taraval)", "lat": 37.7399, "lon": -122.5119, "system": "MUNI"},
    {"name": "46th Ave & Taraval (L Taraval)", "lat": 37.7399, "lon": -122.5143, "system": "MUNI"},
    {"name": "Taraval & Sunset Blvd (L Taraval)", "lat": 37.7399, "lon": -122.5169, "system": "MUNI"},
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

# Curated Bay Area public schools with approximate CAASPP 2022-23 proficiency rates.
# math_pct / ela_pct = % of students meeting or exceeding standards (all grades combined).
# This list is the fallback; run scripts/fetch_schools.py to replace with real CAASPP data.
_BAY_AREA_SCHOOLS: list[dict[str, Any]] = [
    # San Francisco — Elementary
    {"name": "Clarendon Elementary", "lat": 37.7543, "lon": -122.4574, "type": "elementary", "grades": "K-8", "math_pct": 56.0, "ela_pct": 63.0},
    {"name": "Alamo Elementary", "lat": 37.7508, "lon": -122.4313, "type": "elementary", "grades": "K-5", "math_pct": 60.0, "ela_pct": 65.0},
    {"name": "John Muir Elementary", "lat": 37.7582, "lon": -122.4043, "type": "elementary", "grades": "K-5", "math_pct": 35.0, "ela_pct": 45.0},
    {"name": "McKinley Elementary", "lat": 37.7661, "lon": -122.4258, "type": "elementary", "grades": "K-5", "math_pct": 42.0, "ela_pct": 52.0},
    {"name": "Grattan Elementary", "lat": 37.7647, "lon": -122.4483, "type": "elementary", "grades": "K-5", "math_pct": 58.0, "ela_pct": 64.0},
    {"name": "Alice Fong Yu Elementary", "lat": 37.7488, "lon": -122.4714, "type": "elementary", "grades": "K-8", "math_pct": 65.0, "ela_pct": 68.0},
    {"name": "Rooftop Elementary", "lat": 37.7500, "lon": -122.4434, "type": "elementary", "grades": "K-8", "math_pct": 63.0, "ela_pct": 70.0},
    {"name": "Miraloma Elementary", "lat": 37.7347, "lon": -122.4484, "type": "elementary", "grades": "K-5", "math_pct": 60.0, "ela_pct": 66.0},
    {"name": "Cesar Chavez Elementary", "lat": 37.7487, "lon": -122.4167, "type": "elementary", "grades": "K-8", "math_pct": 18.0, "ela_pct": 28.0},
    {"name": "Sunset Elementary", "lat": 37.7597, "lon": -122.4750, "type": "elementary", "grades": "K-5", "math_pct": 52.0, "ela_pct": 58.0},
    # San Francisco — Middle
    {"name": "James Denman Middle School", "lat": 37.7227, "lon": -122.4296, "type": "middle", "grades": "6-8", "math_pct": 25.0, "ela_pct": 35.0},
    {"name": "Everett Middle School", "lat": 37.7641, "lon": -122.4261, "type": "middle", "grades": "6-8", "math_pct": 32.0, "ela_pct": 42.0},
    {"name": "Aptos Middle School", "lat": 37.7301, "lon": -122.4637, "type": "middle", "grades": "6-8", "math_pct": 48.0, "ela_pct": 56.0},
    {"name": "Marina Middle School", "lat": 37.8001, "lon": -122.4319, "type": "middle", "grades": "6-8", "math_pct": 52.0, "ela_pct": 60.0},
    {"name": "Presidio Middle School", "lat": 37.7843, "lon": -122.4618, "type": "middle", "grades": "6-8", "math_pct": 50.0, "ela_pct": 58.0},
    # San Francisco — High School
    {"name": "Galileo High School", "lat": 37.8018, "lon": -122.4351, "type": "high", "grades": "9-12", "math_pct": 30.0, "ela_pct": 42.0},
    {"name": "Abraham Lincoln High School", "lat": 37.7268, "lon": -122.4885, "type": "high", "grades": "9-12", "math_pct": 36.0, "ela_pct": 48.0},
    {"name": "Lowell High School", "lat": 37.7285, "lon": -122.4766, "type": "high", "grades": "9-12", "math_pct": 71.0, "ela_pct": 76.0},
    {"name": "Mission High School", "lat": 37.7629, "lon": -122.4244, "type": "high", "grades": "9-12", "math_pct": 20.0, "ela_pct": 32.0},
    {"name": "George Washington High School", "lat": 37.7806, "lon": -122.4668, "type": "high", "grades": "9-12", "math_pct": 38.0, "ela_pct": 50.0},
    {"name": "Balboa High School", "lat": 37.7241, "lon": -122.4399, "type": "high", "grades": "9-12", "math_pct": 22.0, "ela_pct": 34.0},
    {"name": "Thurgood Marshall High School", "lat": 37.7200, "lon": -122.4370, "type": "high", "grades": "9-12", "math_pct": 18.0, "ela_pct": 28.0},
    # Oakland
    {"name": "Peralta Elementary (Oakland)", "lat": 37.8285, "lon": -122.2590, "type": "elementary", "grades": "K-5", "math_pct": 30.0, "ela_pct": 40.0},
    {"name": "Westlake Middle School (Oakland)", "lat": 37.8247, "lon": -122.2479, "type": "middle", "grades": "6-8", "math_pct": 20.0, "ela_pct": 28.0},
    {"name": "Oakland Technical High School", "lat": 37.8317, "lon": -122.2468, "type": "high", "grades": "9-12", "math_pct": 28.0, "ela_pct": 38.0},
    # Berkeley
    {"name": "Malcolm X Elementary (Berkeley)", "lat": 37.8619, "lon": -122.2714, "type": "elementary", "grades": "K-5", "math_pct": 55.0, "ela_pct": 62.0},
    {"name": "King Middle School (Berkeley)", "lat": 37.8680, "lon": -122.2852, "type": "middle", "grades": "6-8", "math_pct": 45.0, "ela_pct": 56.0},
    {"name": "Berkeley High School", "lat": 37.8691, "lon": -122.2671, "type": "high", "grades": "9-12", "math_pct": 40.0, "ela_pct": 55.0},
    # San Jose
    {"name": "Lincoln Elementary (San Jose)", "lat": 37.3587, "lon": -121.9052, "type": "elementary", "grades": "K-5", "math_pct": 38.0, "ela_pct": 48.0},
    {"name": "Hoover Middle School (San Jose)", "lat": 37.3388, "lon": -121.9044, "type": "middle", "grades": "6-8", "math_pct": 40.0, "ela_pct": 50.0},
    {"name": "Lincoln High School (San Jose)", "lat": 37.3193, "lon": -121.9196, "type": "high", "grades": "9-12", "math_pct": 35.0, "ela_pct": 45.0},
]


def _load_schools() -> list[dict[str, Any]]:
    try:
        with open(SCHOOLS_CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, list) else _BAY_AREA_SCHOOLS
    except FileNotFoundError:
        return _BAY_AREA_SCHOOLS


async def prefetch_schools(force: bool = False) -> bool:
    """Write the built-in Bay Area school list to disk.
    Returns True when written, False when the file already exists and force is False.
    """
    if not force and os.path.exists(SCHOOLS_CACHE_PATH):
        return False
    with open(SCHOOLS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(_BAY_AREA_SCHOOLS, f)
    return True


def find_nearby_schools(
    lat: float,
    lon: float,
    schools: list[dict[str, Any]],
    max_miles: float = 2.0,
) -> list[dict[str, Any]]:
    """Return the nearest school of each type (elementary/middle/high) within max_miles."""
    best: dict[str, dict[str, Any] | None] = {"elementary": None, "middle": None, "high": None}

    for school in schools:
        s_lat = school.get("lat")
        s_lon = school.get("lon")
        if s_lat is None or s_lon is None:
            continue
        stype = school.get("type", "").lower()
        if stype not in best:
            continue
        dist = _haversine_miles(lat, lon, float(s_lat), float(s_lon))
        if dist > max_miles:
            continue
        current = best[stype]
        if current is None or dist < current["distance_miles"]:
            best[stype] = {
                "name": school.get("name"),
                "type": stype,
                "grades": school.get("grades"),
                "distance_miles": round(dist, 3),
                "math_pct": school.get("math_pct"),
                "ela_pct": school.get("ela_pct"),
            }

    return [v for v in best.values() if v is not None]


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
    user_id=None,
) -> dict[str, Any]:
    """Compute Bay Area-specific value drivers with no external paid APIs."""
    lot_size = property.get("lot_size")
    is_adu_candidate = bool(lot_size and float(lot_size) >= 3000 and _is_sfr(property.get("property_type")))

    rent_estimate_source: str | None = None
    rent_range_low: float | None = None
    rent_range_high: float | None = None

    if user_id is not None:
        # Registered users: try RentCast property-specific rent AVM first
        # (neighborhood-aware, tuned to bed/bath/sqft)
        rc_rent = await fetch_rentcast_rent_estimate(
            address=property.get("address_matched") or property.get("address_input") or "",
            beds=property.get("bedrooms"),
            baths=property.get("bathrooms"),
            sqft=property.get("sqft"),
            property_type=property.get("property_type"),
        )
        if rc_rent is not None:
            zip_median_rent = rc_rent["rent"]
            rent_range_low = rc_rent["rentRangeLow"]
            rent_range_high = rc_rent["rentRangeHigh"]
            rent_estimate_source = "rentcast"
        else:
            zip_median_rent = await _fetch_zip_median_rent(zip_code, beds=property.get("bedrooms"))
            rent_estimate_source = "census" if zip_median_rent is not None else None
    else:
        # Anonymous users: Census ACS zip-code median only
        zip_median_rent = await _fetch_zip_median_rent(zip_code, beds=property.get("bedrooms"))
        rent_estimate_source = "census" if zip_median_rent is not None else None

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
    nearby_schools: list[dict[str, Any]] = []

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

        schools = _load_schools()
        nearby_schools = find_nearby_schools(float(lat), float(lon), schools)

    return {
        "adu_potential": is_adu_candidate,
        "adu_rent_estimate": adu_rent_estimate,
        "zip_median_rent": zip_median_rent,
        "rent_estimate_source": rent_estimate_source,
        "rent_range_low": rent_range_low,
        "rent_range_high": rent_range_high,
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
        "nearby_schools": nearby_schools,
    }
