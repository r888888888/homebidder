"""
Tests for ca_hazards.py — fetch_ca_hazard_zones.
Uses synthetic GeoJSON fixtures and mocked FEMA API.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shapely.geometry import Point, shape

from agent.tools.ca_hazards import (
    _check_fault_zone,
    _check_fire_hazard,
    _check_liquefaction,
    fetch_ca_hazard_zones,
)

# ---------------------------------------------------------------------------
# Synthetic GeoJSON helpers
# ---------------------------------------------------------------------------

def _make_polygon_geojson(rings: list[list[list[float]]]) -> dict:
    """Return a GeoJSON FeatureCollection with one polygon feature."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": rings},
            }
        ],
    }


def _make_fire_hazard_geojson(level: str, rings: list[list[list[float]]]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"HAZ_CLASS": level},
                "geometry": {"type": "Polygon", "coordinates": rings},
            }
        ],
    }


def _make_liquefaction_geojson(risk: str, rings: list[list[list[float]]]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"LIQSUSCEP": risk},
                "geometry": {"type": "Polygon", "coordinates": rings},
            }
        ],
    }


# A small square around (lat=37.80, lon=-122.40) — inside = in zone
ZONE_RING = [
    [[-122.41, 37.79], [-122.39, 37.79], [-122.39, 37.81], [-122.41, 37.81], [-122.41, 37.79]]
]
# Point clearly inside
LAT_IN, LON_IN = 37.800, -122.400
# Point clearly outside
LAT_OUT, LON_OUT = 37.700, -122.300


# ---------------------------------------------------------------------------
# _check_fault_zone
# ---------------------------------------------------------------------------

class TestCheckFaultZone:
    def test_inside_fault_zone_returns_true(self):
        geojson = _make_polygon_geojson(ZONE_RING)
        polygons = [shape(f["geometry"]) for f in geojson["features"]]
        assert _check_fault_zone(LAT_IN, LON_IN, polygons) is True

    def test_outside_fault_zone_returns_false(self):
        geojson = _make_polygon_geojson(ZONE_RING)
        polygons = [shape(f["geometry"]) for f in geojson["features"]]
        assert _check_fault_zone(LAT_OUT, LON_OUT, polygons) is False

    def test_empty_polygons_returns_false(self):
        assert _check_fault_zone(LAT_IN, LON_IN, []) is False


# ---------------------------------------------------------------------------
# _check_liquefaction
# ---------------------------------------------------------------------------

class TestCheckLiquefaction:
    @pytest.mark.parametrize("liq_value,expected", [
        ("HIGH", "High"),
        ("MODERATE", "Moderate"),
        ("LOW", "Low"),
        ("VERY HIGH", "High"),
    ])
    def test_maps_risk_levels(self, liq_value, expected):
        geojson = _make_liquefaction_geojson(liq_value, ZONE_RING)
        features = geojson["features"]
        result = _check_liquefaction(LAT_IN, LON_IN, features)
        assert result == expected

    def test_outside_all_zones_returns_none(self):
        geojson = _make_liquefaction_geojson("HIGH", ZONE_RING)
        features = geojson["features"]
        result = _check_liquefaction(LAT_OUT, LON_OUT, features)
        assert result is None

    def test_empty_features_returns_none(self):
        assert _check_liquefaction(LAT_IN, LON_IN, []) is None


# ---------------------------------------------------------------------------
# _check_fire_hazard
# ---------------------------------------------------------------------------

class TestCheckFireHazard:
    @pytest.mark.parametrize("haz_class,expected", [
        ("VHFHSZ", "Very High"),
        ("HIGH", "High"),
        ("MODERATE", "Moderate"),
    ])
    def test_maps_fire_hazard_levels(self, haz_class, expected):
        geojson = _make_fire_hazard_geojson(haz_class, ZONE_RING)
        features = geojson["features"]
        result = _check_fire_hazard(LAT_IN, LON_IN, features)
        assert result == expected

    def test_outside_fire_zone_returns_none(self):
        geojson = _make_fire_hazard_geojson("VHFHSZ", ZONE_RING)
        features = geojson["features"]
        result = _check_fire_hazard(LAT_OUT, LON_OUT, features)
        assert result is None

    def test_empty_features_returns_none(self):
        assert _check_fire_hazard(LAT_IN, LON_IN, []) is None


# ---------------------------------------------------------------------------
# fetch_ca_hazard_zones (integration, mocked data loading + FEMA API)
# ---------------------------------------------------------------------------

MOCK_FAULT_GEOJSON = _make_polygon_geojson(ZONE_RING)
MOCK_LIQ_GEOJSON = _make_liquefaction_geojson("HIGH", ZONE_RING)
MOCK_FIRE_GEOJSON = _make_fire_hazard_geojson("VHFHSZ", ZONE_RING)
MOCK_FEMA_RESPONSE = {"features": [{"attributes": {"FLD_ZONE": "AE", "SFHA_TF": "T"}}]}


class TestFetchCaHazardZones:
    @pytest.fixture(autouse=True)
    def mock_shapefile_data(self):
        """Inject synthetic shapefile data so no real files are needed."""
        with patch("agent.tools.ca_hazards._load_fault_zones",
                   return_value=[shape(f["geometry"]) for f in MOCK_FAULT_GEOJSON["features"]]), \
             patch("agent.tools.ca_hazards._load_liquefaction_zones",
                   return_value=MOCK_LIQ_GEOJSON["features"]), \
             patch("agent.tools.ca_hazards._load_fire_hazard_zones",
                   return_value=MOCK_FIRE_GEOJSON["features"]):
            yield

    async def test_inside_all_zones(self):
        fema_mock = AsyncMock(return_value=MOCK_FEMA_RESPONSE)
        with patch("agent.tools.ca_hazards._query_fema_flood_zone", fema_mock):
            result = await fetch_ca_hazard_zones(LAT_IN, LON_IN)

        assert result["alquist_priolo"] is True
        assert result["liquefaction_risk"] == "High"
        assert result["fire_hazard_zone"] == "Very High"
        assert result["flood_zone"] == "AE"

    async def test_outside_all_zones(self):
        fema_no_hit = AsyncMock(return_value={"features": []})
        with patch("agent.tools.ca_hazards._query_fema_flood_zone", fema_no_hit):
            result = await fetch_ca_hazard_zones(LAT_OUT, LON_OUT)

        assert result["alquist_priolo"] is False
        assert result["liquefaction_risk"] is None
        assert result["fire_hazard_zone"] is None
        assert result["flood_zone"] is None

    async def test_fema_api_error_returns_none_flood_zone(self):
        fema_error = AsyncMock(side_effect=Exception("timeout"))
        with patch("agent.tools.ca_hazards._query_fema_flood_zone", fema_error):
            result = await fetch_ca_hazard_zones(LAT_IN, LON_IN)

        assert result["flood_zone"] is None
        # Other fields still populated from shapefiles
        assert result["alquist_priolo"] is True

    async def test_sfha_flag_present_when_in_special_flood_zone(self):
        fema_sfha = AsyncMock(return_value={"features": [{"attributes": {"FLD_ZONE": "AE", "SFHA_TF": "T"}}]})
        with patch("agent.tools.ca_hazards._query_fema_flood_zone", fema_sfha):
            result = await fetch_ca_hazard_zones(LAT_IN, LON_IN)

        assert result["flood_zone_sfha"] is True

    async def test_sfha_false_for_minimal_risk_zone(self):
        fema_x = AsyncMock(return_value={"features": [{"attributes": {"FLD_ZONE": "X", "SFHA_TF": "F"}}]})
        with patch("agent.tools.ca_hazards._query_fema_flood_zone", fema_x):
            result = await fetch_ca_hazard_zones(LAT_OUT, LON_OUT)

        assert result["flood_zone_sfha"] is False
