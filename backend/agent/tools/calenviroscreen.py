"""
CalEnviroScreen 4.0 — local census tract lookup.

Data file: backend/data/calenviroscreen.geojson
Download: https://oehha.ca.gov/calenviroscreen/report/calenviroscreen-40
  → Download shapefile zip, then convert:
    ogr2ogr -f GeoJSON backend/data/calenviroscreen.geojson CES4.0Final_results_June2021_SHP.shp

CalEnviroScreen 4.0 GeoJSON property names (shapefile-derived, 10-char truncated):
  TrafficP   — Traffic proximity percentile (0–100)
  DieselPM_P — Diesel PM percentile (0–100)
  PM2_5_P    — PM2.5 percentile (0–100)
  CIscoreP   — CalEnviroScreen 4.0 score percentile (0–100, overall env burden)

Run scripts/download_calenviroscreen.py — it prints all field names after download
so you can verify these match and update if needed.

If the data file is absent the function returns None and the risk factor shows n/a.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
CES_FILE = DATA_DIR / "calenviroscreen.geojson"

# Module-level cache: list of (shapely geometry, properties dict)
_ces_cache: list[tuple[Any, dict]] | None = None


def _load_ces_features() -> list[tuple[Any, dict]]:
    global _ces_cache
    if _ces_cache is not None:
        return _ces_cache
    if not CES_FILE.exists():
        log.warning("CalEnviroScreen data file not found: %s", CES_FILE)
        _ces_cache = []
        return _ces_cache
    with open(CES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    _ces_cache = [
        (shape(feat["geometry"]), feat.get("properties", {}))
        for feat in data.get("features", [])
        if feat.get("geometry")
    ]
    log.info("Loaded %d CalEnviroScreen census tracts", len(_ces_cache))
    return _ces_cache


def fetch_calenviroscreen_data(lat: float, lon: float) -> dict[str, Any] | None:
    """
    Return CalEnviroScreen 4.0 percentile scores for the census tract
    containing the given lat/lon.

    Returns:
        {
            "traffic_proximity_pct": float,   # Traf_P  (0–100)
            "diesel_pm_pct": float,           # DslPM_P (0–100)
            "pm25_pct": float,                # PM2_5_P (0–100)
            "ces_score_pct": float,           # CIscoreP (0–100)
        }
        or None if the data file is absent or the point matches no tract.
    """
    features = _load_ces_features()
    if not features:
        return None

    pt = Point(lon, lat)
    for geom, props in features:
        if geom.contains(pt):
            try:
                return {
                    "traffic_proximity_pct": float(props["TrafficP"]),
                    "diesel_pm_pct": float(props["DieselPM_P"]),
                    "pm25_pct": float(props["PM2_5_P"]),
                    "ces_score_pct": float(props["CIscoreP"]),
                }
            except (KeyError, TypeError, ValueError) as exc:
                log.warning("CalEnviroScreen property parse error: %s | props=%s", exc, props)
                return None

    log.debug("No CalEnviroScreen tract found for lat=%s lon=%s", lat, lon)
    return None
