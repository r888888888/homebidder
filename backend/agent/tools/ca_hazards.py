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
from shapely import STRtree
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

ARCGIS_PAGE_SIZE = 2000

# ---------------------------------------------------------------------------
# Shapefile loaders (lazy, module-level cache)
# ---------------------------------------------------------------------------

_fault_cache: list | None = None
_fault_tree: STRtree | None = None
_liq_cache: list | None = None
_liq_tree: STRtree | None = None
_fire_cache: list | None = None
_fire_tree: STRtree | None = None


def _load_geojson_features(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    if not path.exists():
        log.warning("Shapefile not found: %s — hazard check disabled", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("features", [])


def _load_fault_zones() -> tuple[list, STRtree]:
    """Return (polygons, STRtree) for AP fault zones, built once."""
    global _fault_cache, _fault_tree
    if _fault_cache is None:
        features = _load_geojson_features("ap_fault_zones.geojson")
        _fault_cache = [shape(f["geometry"]) for f in features if f.get("geometry")]
        _fault_tree = STRtree(_fault_cache)
        log.info("Loaded %d AP fault zone polygons (STRtree built)", len(_fault_cache))
    return _fault_cache, _fault_tree


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


def _load_liquefaction_zones() -> tuple[list[dict], STRtree]:
    global _liq_cache, _liq_tree
    if _liq_cache is None:
        _liq_cache = _load_geojson_features("liquefaction_zones.geojson")
        geoms = [shape(f["geometry"]) for f in _liq_cache if f.get("geometry")]
        _liq_tree = STRtree(geoms)
        log.info("Loaded %d liquefaction zone features (STRtree built)", len(_liq_cache))
    return _liq_cache, _liq_tree


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


def _load_fire_hazard_zones() -> tuple[list[dict], STRtree]:
    global _fire_cache, _fire_tree
    if _fire_cache is None:
        _fire_cache = _load_geojson_features("fire_hazard_zones.geojson")
        geoms = [shape(f["geometry"]) for f in _fire_cache if f.get("geometry")]
        _fire_tree = STRtree(geoms)
        log.info("Loaded %d fire hazard zone features (STRtree built)", len(_fire_cache))
    return _fire_cache, _fire_tree


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

    log.info("Starting CA hazard prefetch (force=%s)", force)

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        async def fetch_geojson_paginated(url: str, params: dict[str, str]) -> dict:
            features: list[dict] = []
            offset = 0
            page = 1
            while True:
                page_params = dict(params)
                page_params["resultOffset"] = str(offset)
                page_params["resultRecordCount"] = str(ARCGIS_PAGE_SIZE)
                log.info(
                    "Prefetch page %d from %s (offset=%d, page_size=%d)",
                    page,
                    url,
                    offset,
                    ARCGIS_PAGE_SIZE,
                )
                resp = await client.get(url, params=page_params)
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("features", []) or []
                features.extend(batch)
                log.info(
                    "Fetched page %d from %s: batch=%d cumulative=%d",
                    page,
                    url,
                    len(batch),
                    len(features),
                )

                exceeded = bool((data.get("properties") or {}).get("exceededTransferLimit"))
                if not exceeded or not batch:
                    log.info(
                        "Completed paginated fetch for %s (pages=%d total_features=%d)",
                        url,
                        page,
                        len(features),
                    )
                    break
                offset += len(batch)
                page += 1

            return {"type": "FeatureCollection", "features": features}

        fault_path = DATA_DIR / "ap_fault_zones.geojson"
        if force or not fault_path.exists():
            log.info("Prefetching AP fault zones to %s", fault_path)
            try:
                params = {
                    "where": "1=1",
                    "outFields": "*",
                    "returnGeometry": "true",
                    "f": "geojson",
                }
                data = await fetch_geojson_paginated(CGS_FAULT_GEOJSON_URL, params)
                fault_path.write_text(json.dumps(data), encoding="utf-8")
                results["ap_fault_zones.geojson"] = True
                log.info(
                    "Saved AP fault zones (%d features) to %s",
                    len(data.get("features", [])),
                    fault_path,
                )
            except Exception as exc:
                log.warning("Failed to prefetch fault zones: %s", exc)
        else:
            log.info("Skipping AP fault zones prefetch; file already exists at %s", fault_path)

        liq_path = DATA_DIR / "liquefaction_zones.geojson"
        if force or not liq_path.exists():
            log.info("Prefetching liquefaction zones to %s", liq_path)
            try:
                params = {
                    "where": "1=1",
                    "outFields": "*",
                    "returnGeometry": "true",
                    "f": "geojson",
                }
                data = await fetch_geojson_paginated(CGS_LIQUEFACTION_GEOJSON_URL, params)
                normalized = _normalize_liquefaction_geojson(data)
                liq_path.write_text(json.dumps(normalized), encoding="utf-8")
                results["liquefaction_zones.geojson"] = True
                log.info(
                    "Saved liquefaction zones (%d features) to %s",
                    len(normalized.get("features", [])),
                    liq_path,
                )
            except Exception as exc:
                log.warning("Failed to prefetch liquefaction zones: %s", exc)
        else:
            log.info("Skipping liquefaction prefetch; file already exists at %s", liq_path)

        fire_path = DATA_DIR / "fire_hazard_zones.geojson"
        if force or not fire_path.exists():
            log.info("Prefetching fire hazard zones to %s", fire_path)
            try:
                resp = await client.get(CALFIRE_FHSZ_URL)
                resp.raise_for_status()
                fire_path.write_bytes(resp.content)
                results["fire_hazard_zones.geojson"] = True
                log.info("Saved CalFire fire hazard zones to %s (%d bytes)", fire_path, len(resp.content))
            except Exception as exc:
                log.warning("Failed to prefetch CalFire FHSZ, trying fallback: %s", exc)
                try:
                    params = {
                        "where": "1=1",
                        "outFields": "potential_severity,hazard,sra_or_lra",
                        "returnGeometry": "true",
                        "f": "geojson",
                    }
                    data = await fetch_geojson_paginated(MYHAZARDS_FIRE_GEOJSON_URL, params)
                    normalized = _normalize_myhazards_geojson(data)
                    fire_path.write_text(json.dumps(normalized), encoding="utf-8")
                    results["fire_hazard_zones.geojson"] = True
                    log.info(
                        "Saved MyHazards fire fallback (%d features) to %s",
                        len(normalized.get("features", [])),
                        fire_path,
                    )
                except Exception as fallback_exc:
                    log.warning("Failed to prefetch MyHazards fire fallback: %s", fallback_exc)
        else:
            log.info("Skipping fire hazard prefetch; file already exists at %s", fire_path)

    global _fault_cache, _fault_tree, _liq_cache, _liq_tree, _fire_cache, _fire_tree
    _fault_cache = None
    _fault_tree = None
    _liq_cache = None
    _liq_tree = None
    _fire_cache = None
    _fire_tree = None
    log.info("Completed CA hazard prefetch: %s", results)
    return results


# ---------------------------------------------------------------------------
# Point-in-polygon checks
# ---------------------------------------------------------------------------

def _check_fault_zone(lat: float, lon: float, polygons: list, tree: STRtree) -> bool:
    """Return True if the point falls within any Alquist-Priolo fault zone polygon."""
    pt = Point(lon, lat)
    return len(tree.query(pt, predicate="within")) > 0


_LIQUEFACTION_MAP = {
    "VERY HIGH": "High",
    "HIGH": "High",
    "MODERATE": "Moderate",
    "MEDIUM": "Moderate",
    "LOW": "Low",
    "VERY LOW": "Low",
}


def _check_liquefaction(lat: float, lon: float, features: list[dict], tree: STRtree) -> str | None:
    """Return 'High', 'Moderate', 'Low', or None based on CGS liquefaction zones."""
    pt = Point(lon, lat)
    for idx in tree.query(pt, predicate="within"):
        props = features[idx].get("properties", {})
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


def _check_fire_hazard(lat: float, lon: float, features: list[dict], tree: STRtree) -> str | None:
    """Return 'Very High', 'High', 'Moderate', or None based on CalFire FHSZ."""
    pt = Point(lon, lat)
    for idx in tree.query(pt, predicate="within"):
        props = features[idx].get("properties", {})
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
    fault_zones, fault_tree = _load_fault_zones()
    liq_features, liq_tree = _load_liquefaction_zones()
    fire_features, fire_tree = _load_fire_hazard_zones()

    alquist_priolo = _check_fault_zone(lat, lon, fault_zones, fault_tree)
    liquefaction_risk = _check_liquefaction(lat, lon, liq_features, liq_tree)
    fire_hazard_zone = _check_fire_hazard(lat, lon, fire_features, fire_tree)

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
