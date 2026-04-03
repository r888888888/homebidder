"""
California natural hazard zone checks.

Shapefile sources (GeoJSON, loaded lazily from backend/data/):
  - ap_fault_zones.geojson     — CGS Alquist-Priolo Earthquake Fault Zones
  - liquefaction_zones.geojson — CGS Seismic Hazard Zones (liquefaction)
  - fire_hazard_zones.geojson  — CalFire Fire Hazard Severity Zones (FHSZ)

FEMA flood zone: live point query to the FEMA MSC ArcGIS REST API.

Data download URLs (run once to populate backend/data/):
  AP Fault Zones:
    https://maps.conservation.ca.gov/cgs/EQZApp/data/AP_Zones_2025.zip
  Liquefaction:
    https://maps.conservation.ca.gov/cgs/shzp/MapData/ (county-level shapefiles)
  CalFire FHSZ:
    https://gis.data.cnra.ca.gov/api/download/v1/items/901a8f49d4914f4c8d55e4b1d91e5c02/GeoJSON?layers=0
"""
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import Point, shape

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"

FEMA_URL = (
    "https://msc.fema.gov/arcgis/rest/services/NFHL_Print/NFHLQuery/MapServer/28/query"
)

CALFIRE_FHSZ_URL = (
    "https://gis.data.cnra.ca.gov/api/download/v1/items/"
    "901a8f49d4914f4c8d55e4b1d91e5c02/GeoJSON?layers=0"
)

MYHAZARDS_FIRE_GEOJSON_URL = (
    "https://services.arcgis.com/BLN4oKB0N1YSgvY8/arcgis/rest/services/"
    "MyHazards_Hazard_Areas/FeatureServer/9/query"
)

CGS_LIQUEFACTION_GEOJSON_URL = (
    "https://services2.arcgis.com/zr3KAIbsRSUyARHG/arcgis/rest/services/"
    "CGS_Liquefaction_Zones/FeatureServer/0/query"
)

CGS_FAULT_GEOJSON_URL = (
    "https://services2.arcgis.com/zr3KAIbsRSUyARHG/arcgis/rest/services/"
    "CGS_Alquist_Priolo_Fault_Zones/FeatureServer/0/query"
)

MYHAZARDS_LIQUEFACTION_URL = (
    "https://services.arcgis.com/BLN4oKB0N1YSgvY8/arcgis/rest/services/"
    "MyHazards_Hazard_Areas/FeatureServer/1/query"
)

MYHAZARDS_FIRE_URL = (
    "https://services.arcgis.com/BLN4oKB0N1YSgvY8/arcgis/rest/services/"
    "MyHazards_Hazard_Areas/FeatureServer/9/query"
)

# ---------------------------------------------------------------------------
# Shapefile loaders (lazy, module-level cache)
# ---------------------------------------------------------------------------

_fault_cache: list | None = None
_liq_cache: list | None = None
_fire_cache: list | None = None


def _load_geojson_features(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    if not path.exists():
        log.warning("Shapefile not found: %s — hazard check disabled", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("features", [])


def _load_fault_zones() -> list:
    """Return list of shapely Polygon/MultiPolygon objects for AP fault zones."""
    global _fault_cache
    if _fault_cache is None:
        features = _load_geojson_features("ap_fault_zones.geojson")
        _fault_cache = [shape(f["geometry"]) for f in features if f.get("geometry")]
    return _fault_cache


def _normalize_liquefaction_geojson(data: dict) -> dict:
    out_features: list[dict] = []
    for f in data.get("features", []):
        props = dict(f.get("properties", {}))
        # CGS service does not expose LIQSUSCEP directly; use conservative class
        props.setdefault("LIQSUSCEP", "MODERATE")
        out_features.append(
            {
                "type": "Feature",
                "geometry": f.get("geometry"),
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": out_features}


def _load_liquefaction_zones() -> list[dict]:
    global _liq_cache
    if _liq_cache is None:
        _liq_cache = _load_geojson_features("liquefaction_zones.geojson")
    return _liq_cache


def _normalize_myhazards_geojson(data: dict) -> dict:
    out_features: list[dict] = []
    for f in data.get("features", []):
        props = dict(f.get("properties", {}))
        sev = str(props.get("potential_severity", "")).upper().strip()
        if sev:
            props["HAZ_CLASS"] = sev
        out_features.append(
            {
                "type": "Feature",
                "geometry": f.get("geometry"),
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": out_features}


def _load_fire_hazard_zones() -> list[dict]:
    global _fire_cache
    if _fire_cache is None:
        _fire_cache = _load_geojson_features("fire_hazard_zones.geojson")
    return _fire_cache


async def prefetch_ca_hazard_geojson(force: bool = False) -> dict[str, bool]:
    """
    Download and cache statewide CA hazard GeoJSON files used by request-time checks.
    Returns per-file booleans indicating whether each file was refreshed.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "ap_fault_zones.geojson": False,
        "liquefaction_zones.geojson": False,
        "fire_hazard_zones.geojson": False,
    }

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        fault_path = DATA_DIR / "ap_fault_zones.geojson"
        if force or not fault_path.exists():
            try:
                params = {
                    "where": "1=1",
                    "outFields": "*",
                    "returnGeometry": "true",
                    "f": "geojson",
                }
                resp = await client.get(CGS_FAULT_GEOJSON_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                fault_path.write_text(json.dumps(data), encoding="utf-8")
                results["ap_fault_zones.geojson"] = True
            except Exception as exc:
                log.warning("Failed to prefetch fault zones: %s", exc)

        liq_path = DATA_DIR / "liquefaction_zones.geojson"
        if force or not liq_path.exists():
            try:
                params = {
                    "where": "1=1",
                    "outFields": "*",
                    "returnGeometry": "true",
                    "f": "geojson",
                }
                resp = await client.get(CGS_LIQUEFACTION_GEOJSON_URL, params=params)
                resp.raise_for_status()
                normalized = _normalize_liquefaction_geojson(resp.json())
                liq_path.write_text(json.dumps(normalized), encoding="utf-8")
                results["liquefaction_zones.geojson"] = True
            except Exception as exc:
                log.warning("Failed to prefetch liquefaction zones: %s", exc)

        fire_path = DATA_DIR / "fire_hazard_zones.geojson"
        if force or not fire_path.exists():
            try:
                resp = await client.get(CALFIRE_FHSZ_URL)
                resp.raise_for_status()
                fire_path.write_bytes(resp.content)
                results["fire_hazard_zones.geojson"] = True
            except Exception as exc:
                log.warning("Failed to prefetch CalFire FHSZ, trying fallback: %s", exc)
                try:
                    params = {
                        "where": "1=1",
                        "outFields": "potential_severity,hazard,sra_or_lra",
                        "returnGeometry": "true",
                        "f": "geojson",
                    }
                    fallback_resp = await client.get(MYHAZARDS_FIRE_GEOJSON_URL, params=params)
                    fallback_resp.raise_for_status()
                    normalized = _normalize_myhazards_geojson(fallback_resp.json())
                    fire_path.write_text(json.dumps(normalized), encoding="utf-8")
                    results["fire_hazard_zones.geojson"] = True
                except Exception as fallback_exc:
                    log.warning("Failed to prefetch MyHazards fire fallback: %s", fallback_exc)

    global _fault_cache, _liq_cache, _fire_cache
    _fault_cache = None
    _liq_cache = None
    _fire_cache = None
    return results


# ---------------------------------------------------------------------------
# Point-in-polygon checks
# ---------------------------------------------------------------------------

def _check_fault_zone(lat: float, lon: float, polygons: list) -> bool:
    """Return True if the point falls within any Alquist-Priolo fault zone polygon."""
    pt = Point(lon, lat)
    return any(pt.within(poly) for poly in polygons)


_LIQUEFACTION_MAP = {
    "VERY HIGH": "High",
    "HIGH": "High",
    "MODERATE": "Moderate",
    "MEDIUM": "Moderate",
    "LOW": "Low",
    "VERY LOW": "Low",
}


def _check_liquefaction(lat: float, lon: float, features: list[dict]) -> str | None:
    """Return 'High', 'Moderate', 'Low', or None based on CGS liquefaction zones."""
    pt = Point(lon, lat)
    for f in features:
        geom = f.get("geometry")
        props = f.get("properties", {})
        if not geom:
            continue
        if pt.within(shape(geom)):
            raw = (props.get("LIQSUSCEP") or "").upper().strip()
            return _LIQUEFACTION_MAP.get(raw, "Low")
    return None


_FIRE_MAP = {
    "VHFHSZ": "Very High",
    "VERY HIGH": "Very High",
    "HIGH": "High",
    "MODERATE": "Moderate",
    "MEDIUM": "Moderate",
}


def _check_fire_hazard(lat: float, lon: float, features: list[dict]) -> str | None:
    """Return 'Very High', 'High', 'Moderate', or None based on CalFire FHSZ."""
    pt = Point(lon, lat)
    for f in features:
        geom = f.get("geometry")
        props = f.get("properties", {})
        if not geom:
            continue
        if pt.within(shape(geom)):
            raw = (props.get("HAZ_CLASS") or "").upper().strip()
            return _FIRE_MAP.get(raw, "Moderate")
    return None


# ---------------------------------------------------------------------------
# FEMA flood zone API
# ---------------------------------------------------------------------------

async def _query_fema_flood_zone(lat: float, lon: float) -> dict:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
        "f": "json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(FEMA_URL, params=params)
        resp.raise_for_status()
        return resp.json()


async def _query_myhazards_liquefaction(lat: float, lon: float) -> str | None:
    """
    Query CA MyHazards liquefaction layer.
    Returns a conservative categorical risk or None when outside mapped zone.
    """
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
        "outFields": "hazard,hazard_description",
        "returnGeometry": "false",
        "f": "json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(MYHAZARDS_LIQUEFACTION_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        return None
    attrs = features[0].get("attributes", {})
    desc = str(attrs.get("hazard_description", "")).lower()
    if "very high" in desc or "high" in desc:
        return "High"
    if "low" in desc:
        return "Low"
    return "Moderate"


async def _query_myhazards_fire(lat: float, lon: float) -> str | None:
    """Query CA MyHazards fire layer and map potential severity to canonical labels."""
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
        "outFields": "potential_severity,hazard",
        "returnGeometry": "false",
        "f": "json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(MYHAZARDS_FIRE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        return None
    attrs = features[0].get("attributes", {})
    raw = str(attrs.get("potential_severity", "")).upper().strip()
    if raw in {"VERY HIGH", "HIGH", "MODERATE"}:
        return _FIRE_MAP.get(raw, "Moderate")
    return None


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

async def fetch_ca_hazard_zones(lat: float, lon: float) -> dict[str, Any]:
    """
    Return CA natural hazard zone classifications for a given lat/lon.

    Keys:
      alquist_priolo   — bool: property in CGS AP Earthquake Fault Zone
      liquefaction_risk — 'High'/'Moderate'/'Low'/None
      fire_hazard_zone  — 'Very High'/'High'/'Moderate'/None
      flood_zone        — FEMA FLD_ZONE code (e.g. 'AE', 'X') or None
      flood_zone_sfha   — bool: Special Flood Hazard Area (mandatory insurance)
    """
    fault_zones = _load_fault_zones()
    liq_features = _load_liquefaction_zones()
    fire_features = _load_fire_hazard_zones()

    alquist_priolo = _check_fault_zone(lat, lon, fault_zones)
    liquefaction_risk = _check_liquefaction(lat, lon, liq_features)
    fire_hazard_zone = _check_fire_hazard(lat, lon, fire_features)

    flood_zone: str | None = None
    flood_zone_sfha: bool = False
    try:
        fema_data = await _query_fema_flood_zone(lat, lon)
        features = fema_data.get("features", [])
        if features:
            attrs = features[0].get("attributes", {})
            flood_zone = attrs.get("FLD_ZONE") or None
            flood_zone_sfha = str(attrs.get("SFHA_TF", "F")).upper() == "T"
    except Exception as exc:
        log.warning("FEMA flood zone query failed: %s", exc)

    return {
        "alquist_priolo": alquist_priolo,
        "liquefaction_risk": liquefaction_risk,
        "fire_hazard_zone": fire_hazard_zone,
        "flood_zone": flood_zone,
        "flood_zone_sfha": flood_zone_sfha,
    }
