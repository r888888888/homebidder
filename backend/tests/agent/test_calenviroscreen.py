"""
Tests for fetch_calenviroscreen_data — CalEnviroScreen 4.0 local file lookup.
The GeoJSON file is mocked; no real filesystem I/O in most tests.
"""

import json
import pytest
from unittest.mock import patch, mock_open


# Minimal GeoJSON FeatureCollection with one census tract polygon
# (a small square in SF for testing)
SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-122.44, 37.72],
                    [-122.43, 37.72],
                    [-122.43, 37.73],
                    [-122.44, 37.73],
                    [-122.44, 37.72],
                ]],
            },
            "properties": {
                "TrafficP": 85.3,
                "DieselPM_P": 72.1,
                "PM2_5_P": 64.8,
                "CIscoreP": 78.5,
                "Tract": "6075016100",
            },
        }
    ],
}


def _patch_data_file(data: dict):
    """Patch open() for the calenviroscreen GeoJSON file and reset the module cache."""
    return patch(
        "builtins.open",
        mock_open(read_data=json.dumps(data)),
    )


class TestFetchCalenviroscreenData:
    def setup_method(self):
        # Reset the module-level cache before each test
        import agent.tools.calenviroscreen as mod
        mod._ces_geoms = None
        mod._ces_props = None
        mod._ces_tree = None

    def test_returns_dict_with_expected_keys(self):
        from agent.tools.calenviroscreen import fetch_calenviroscreen_data

        with patch("pathlib.Path.exists", return_value=True), \
             _patch_data_file(SAMPLE_GEOJSON):
            result = fetch_calenviroscreen_data(37.725, -122.435)

        assert result is not None
        assert "traffic_proximity_pct" in result
        assert "diesel_pm_pct" in result
        assert "pm25_pct" in result
        assert "ces_score_pct" in result

    def test_percentile_values_parsed_correctly(self):
        from agent.tools.calenviroscreen import fetch_calenviroscreen_data

        with patch("pathlib.Path.exists", return_value=True), \
             _patch_data_file(SAMPLE_GEOJSON):
            result = fetch_calenviroscreen_data(37.725, -122.435)

        assert result is not None
        assert result["traffic_proximity_pct"] == pytest.approx(85.3)
        assert result["diesel_pm_pct"] == pytest.approx(72.1)
        assert result["pm25_pct"] == pytest.approx(64.8)
        assert result["ces_score_pct"] == pytest.approx(78.5)

    def test_returns_none_when_point_outside_all_tracts(self):
        from agent.tools.calenviroscreen import fetch_calenviroscreen_data

        # Coords far outside the sample polygon (e.g., New York)
        with patch("pathlib.Path.exists", return_value=True), \
             _patch_data_file(SAMPLE_GEOJSON):
            result = fetch_calenviroscreen_data(40.71, -74.00)

        assert result is None

    def test_returns_none_when_data_file_missing(self):
        from agent.tools.calenviroscreen import fetch_calenviroscreen_data

        with patch("pathlib.Path.exists", return_value=False):
            result = fetch_calenviroscreen_data(37.725, -122.435)

        assert result is None

    def test_cache_is_populated_on_second_call(self):
        import agent.tools.calenviroscreen as mod
        from agent.tools.calenviroscreen import fetch_calenviroscreen_data

        with patch("pathlib.Path.exists", return_value=True), \
             _patch_data_file(SAMPLE_GEOJSON):
            fetch_calenviroscreen_data(37.725, -122.435)
            assert mod._ces_tree is not None
            # Second call should use the in-memory index (open not called again)
            fetch_calenviroscreen_data(37.725, -122.435)
