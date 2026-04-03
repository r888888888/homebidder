"""
Tests for ca_hazards.py — fetch_ca_hazard_zones.
Uses synthetic GeoJSON fixtures and mocked FEMA API.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shapely.geometry import Point, shape

from agent.tools.ca_hazards import (
    FEMA_URL,
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

    async def test_falls_back_to_live_queries_when_local_data_missing(self):
        """When local hazard GeoJSON files are absent, live fallback queries populate fire/liquefaction."""
        with patch("agent.tools.ca_hazards._load_fault_zones", return_value=[]), \
             patch("agent.tools.ca_hazards._load_liquefaction_zones", return_value=[]), \
             patch("agent.tools.ca_hazards._load_fire_hazard_zones", return_value=[]), \
             patch("agent.tools.ca_hazards._query_myhazards_fire", new=AsyncMock(return_value="High"), create=True) as fire_mock, \
             patch("agent.tools.ca_hazards._query_myhazards_liquefaction", new=AsyncMock(return_value="Moderate"), create=True) as liq_mock, \
             patch("agent.tools.ca_hazards._query_fema_flood_zone", new=AsyncMock(return_value={"features": []})):
            result = await fetch_ca_hazard_zones(LAT_IN, LON_IN)

        assert result["fire_hazard_zone"] == "High"
        assert result["liquefaction_risk"] == "Moderate"
        fire_mock.assert_awaited_once()
        liq_mock.assert_awaited_once()


class TestHazardEndpointConfig:
    def test_fema_uses_nfhl_print_query_layer(self):
        """FEMA NFHL endpoint migrated under NFHL_Print/NFHLQuery MapServer layer 28."""
        assert "NFHL_Print/NFHLQuery/MapServer/28/query" in FEMA_URL


# ---------------------------------------------------------------------------
# CalFire auto-download when GeoJSON file is missing
# ---------------------------------------------------------------------------

class TestCalFireAutoDownload:
    def test_missing_file_triggers_download(self, tmp_path):
        """If fire_hazard_zones.geojson is absent, _load_fire_hazard_zones downloads it."""
        import json
        from agent.tools.ca_hazards import _load_fire_hazard_zones

        fire_geojson = json.dumps(MOCK_FIRE_GEOJSON).encode()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = fire_geojson

        with patch("agent.tools.ca_hazards.DATA_DIR", tmp_path), \
             patch("agent.tools.ca_hazards._fire_cache", None), \
             patch("agent.tools.ca_hazards.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=mock_resp)
            ))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            features = _load_fire_hazard_zones()

        assert len(features) == 1
        assert features[0]["properties"]["HAZ_CLASS"] == "VHFHSZ"
        # File should be saved to disk
        assert (tmp_path / "fire_hazard_zones.geojson").exists()

    def test_download_failure_returns_empty_list(self, tmp_path):
        """If download fails, _load_fire_hazard_zones returns [] without raising."""
        import httpx as httpx_mod
        from agent.tools.ca_hazards import _load_fire_hazard_zones

        with patch("agent.tools.ca_hazards.DATA_DIR", tmp_path), \
             patch("agent.tools.ca_hazards._fire_cache", None), \
             patch("agent.tools.ca_hazards.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(
                get=MagicMock(side_effect=Exception("connection timeout"))
            ))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            features = _load_fire_hazard_zones()

        assert features == []

    def test_legacy_download_failure_falls_back_to_myhazards_geojson(self, tmp_path):
        """If legacy CalFire URL fails, fallback MyHazards GeoJSON should populate fire features."""
        from agent.tools.ca_hazards import _load_fire_hazard_zones

        myhaz_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"potential_severity": "Very High"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[-122.41, 37.79], [-122.39, 37.79], [-122.39, 37.81], [-122.41, 37.81], [-122.41, 37.79]]],
                    },
                }
            ],
        }

        mock_legacy_resp = MagicMock()
        mock_legacy_resp.raise_for_status = MagicMock(side_effect=Exception("legacy url failed"))

        mock_fallback_resp = MagicMock()
        mock_fallback_resp.raise_for_status = MagicMock()
        mock_fallback_resp.json = MagicMock(return_value=myhaz_geojson)

        mock_client = MagicMock()
        mock_client.get = MagicMock(side_effect=[mock_legacy_resp, mock_fallback_resp])

        with patch("agent.tools.ca_hazards.DATA_DIR", tmp_path), \
             patch("agent.tools.ca_hazards._fire_cache", None), \
             patch("agent.tools.ca_hazards.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            features = _load_fire_hazard_zones()

        assert len(features) == 1
        # Fallback loader should normalize MyHazards potential_severity -> HAZ_CLASS-like field
        assert features[0]["properties"]["HAZ_CLASS"] == "VERY HIGH"


class TestCgsAutoDownload:
    def test_missing_liquefaction_file_triggers_cgs_download(self, tmp_path):
        """If liquefaction GeoJSON is absent, loader should download from CGS service."""
        from agent.tools.ca_hazards import _load_liquefaction_zones

        liq_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"LIQSUSCEP": "MODERATE"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[-122.41, 37.79], [-122.39, 37.79], [-122.39, 37.81], [-122.41, 37.81], [-122.41, 37.79]]],
                    },
                }
            ],
        }

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=liq_geojson)

        with patch("agent.tools.ca_hazards.DATA_DIR", tmp_path), \
             patch("agent.tools.ca_hazards._liq_cache", None), \
             patch("agent.tools.ca_hazards.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=mock_resp)
            ))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            features = _load_liquefaction_zones()

        assert len(features) == 1
        assert features[0]["properties"]["LIQSUSCEP"] == "MODERATE"
        assert (tmp_path / "liquefaction_zones.geojson").exists()

    def test_missing_fault_file_triggers_cgs_download(self, tmp_path):
        """If fault GeoJSON is absent, loader should download from CGS service."""
        from agent.tools.ca_hazards import _load_fault_zones

        fault_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[-122.41, 37.79], [-122.39, 37.79], [-122.39, 37.81], [-122.41, 37.81], [-122.41, 37.79]]],
                    },
                }
            ],
        }

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=fault_geojson)

        with patch("agent.tools.ca_hazards.DATA_DIR", tmp_path), \
             patch("agent.tools.ca_hazards._fault_cache", None), \
             patch("agent.tools.ca_hazards.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=mock_resp)
            ))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            polygons = _load_fault_zones()

        assert len(polygons) == 1
        assert (tmp_path / "ap_fault_zones.geojson").exists()
