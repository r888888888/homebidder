"""
Tests for ca_hazards.py — fetch_ca_hazard_zones.
Uses synthetic GeoJSON fixtures and mocked FEMA API.
"""
from unittest.mock import AsyncMock, patch

import pytest
from shapely import STRtree
from shapely.geometry import shape

from agent.tools.ca_hazards import (
    FEMA_URL,
    _check_fault_zone,
    _check_fire_hazard,
    _check_liquefaction,
    fetch_ca_hazard_zones,
)


def _make_polygon_geojson(rings: list[list[list[float]]]) -> dict:
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


ZONE_RING = [
    [[-122.41, 37.79], [-122.39, 37.79], [-122.39, 37.81], [-122.41, 37.81], [-122.41, 37.79]]
]
LAT_IN, LON_IN = 37.800, -122.400
LAT_OUT, LON_OUT = 37.700, -122.300


def _build_tree(features: list[dict]) -> STRtree:
    """Build an STRtree from a list of GeoJSON feature dicts."""
    return STRtree([shape(f["geometry"]) for f in features if f.get("geometry")])


class TestCheckFaultZone:
    def test_inside_fault_zone_returns_true(self):
        geojson = _make_polygon_geojson(ZONE_RING)
        polygons = [shape(f["geometry"]) for f in geojson["features"]]
        tree = STRtree(polygons)
        assert _check_fault_zone(LAT_IN, LON_IN, polygons, tree) is True


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
        tree = _build_tree(features)
        result = _check_liquefaction(LAT_IN, LON_IN, features, tree)
        assert result == expected


class TestCheckFireHazard:
    @pytest.mark.parametrize("haz_class,expected", [
        ("VHFHSZ", "Very High"),
        ("HIGH", "High"),
        ("MODERATE", "Moderate"),
    ])
    def test_maps_fire_hazard_levels(self, haz_class, expected):
        geojson = _make_fire_hazard_geojson(haz_class, ZONE_RING)
        features = geojson["features"]
        tree = _build_tree(features)
        result = _check_fire_hazard(LAT_IN, LON_IN, features, tree)
        assert result == expected


MOCK_FAULT_GEOJSON = _make_polygon_geojson(ZONE_RING)
MOCK_LIQ_GEOJSON = _make_liquefaction_geojson("HIGH", ZONE_RING)
MOCK_FIRE_GEOJSON = _make_fire_hazard_geojson("VHFHSZ", ZONE_RING)
MOCK_FEMA_RESPONSE = {"features": [{"attributes": {"FLD_ZONE": "AE", "SFHA_TF": "T"}}]}


def _fault_tuple(geojson: dict):
    polys = [shape(f["geometry"]) for f in geojson["features"] if f.get("geometry")]
    return polys, STRtree(polys)


def _feature_tuple(geojson: dict):
    features = geojson["features"]
    tree = _build_tree(features)
    return features, tree


class TestFetchCaHazardZones:
    @pytest.fixture(autouse=True)
    def mock_shapefile_data(self):
        with patch("agent.tools.ca_hazards._load_fault_zones",
                   return_value=_fault_tuple(MOCK_FAULT_GEOJSON)), \
             patch("agent.tools.ca_hazards._load_liquefaction_zones",
                   return_value=_feature_tuple(MOCK_LIQ_GEOJSON)), \
             patch("agent.tools.ca_hazards._load_fire_hazard_zones",
                   return_value=_feature_tuple(MOCK_FIRE_GEOJSON)):
            yield

    async def test_inside_all_zones(self):
        fema_mock = AsyncMock(return_value=MOCK_FEMA_RESPONSE)
        with patch("agent.tools.ca_hazards._query_fema_flood_zone", fema_mock):
            result = await fetch_ca_hazard_zones(LAT_IN, LON_IN)

        assert result["alquist_priolo"] is True
        assert result["liquefaction_risk"] == "High"
        assert result["fire_hazard_zone"] == "Very High"
        assert result["flood_zone"] == "AE"

    async def test_no_live_fire_or_liq_fallback_when_local_data_missing(self):
        with patch("agent.tools.ca_hazards._load_fault_zones", return_value=([], STRtree([]))), \
             patch("agent.tools.ca_hazards._load_liquefaction_zones", return_value=([], STRtree([]))), \
             patch("agent.tools.ca_hazards._load_fire_hazard_zones", return_value=([], STRtree([]))), \
             patch("agent.tools.ca_hazards._query_myhazards_fire", new=AsyncMock(side_effect=AssertionError("no live fallback"))), \
             patch("agent.tools.ca_hazards._query_myhazards_liquefaction", new=AsyncMock(side_effect=AssertionError("no live fallback"))), \
             patch("agent.tools.ca_hazards._query_fema_flood_zone", new=AsyncMock(return_value={"features": []})):
            result = await fetch_ca_hazard_zones(LAT_IN, LON_IN)

        assert result["fire_hazard_zone"] is None
        assert result["liquefaction_risk"] is None


class TestHazardEndpointConfig:
    def test_fema_uses_nfhl_print_query_layer(self):
        assert "NFHL_Print/NFHLQuery/MapServer/28/query" in FEMA_URL
