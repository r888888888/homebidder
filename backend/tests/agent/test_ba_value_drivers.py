"""
Tests for ba_value_drivers.py.
"""

import json
import os
from unittest.mock import AsyncMock, Mock, MagicMock, patch


def _make_census_response(vars_and_values: dict[str, int | str]) -> list:
    """Build a minimal Census API JSON response [[headers], [values]]."""
    headers = list(vars_and_values.keys()) + ["zip code tabulation area"]
    row = [str(v) for v in vars_and_values.values()] + ["94110"]
    return [headers, row]


class TestFetchZipMedianRent:
    async def test_fetches_bedroom_specific_variable_when_beds_known(self):
        from agent.tools.ba_value_drivers import _fetch_zip_median_rent

        response_data = _make_census_response({"B25031_005E": 4500, "B25064_001E": 3200})
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        captured_url = {}

        async def fake_get(url, **kwargs):
            captured_url["url"] = url
            return mock_response

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get

        with patch.dict(os.environ, {"CENSUS_API_KEY": "testkey"}), \
             patch("agent.tools.ba_value_drivers.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_zip_median_rent("94110", beds=3)

        assert "B25031_005E" in captured_url["url"]
        assert result == 4500.0

    async def test_falls_back_to_all_units_when_bedroom_value_is_negative(self):
        from agent.tools.ba_value_drivers import _fetch_zip_median_rent

        # Census returns -1 for bedroom-specific (insufficient samples)
        response_data = _make_census_response({"B25031_005E": -1, "B25064_001E": 3200})
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"CENSUS_API_KEY": "testkey"}), \
             patch("agent.tools.ba_value_drivers.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_zip_median_rent("94110", beds=3)

        assert result == 3200.0

    async def test_uses_all_units_variable_when_beds_none(self):
        from agent.tools.ba_value_drivers import _fetch_zip_median_rent

        response_data = _make_census_response({"B25064_001E": 3500})
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        captured_url = {}

        async def fake_get(url, **kwargs):
            captured_url["url"] = url
            return mock_response

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get

        with patch.dict(os.environ, {"CENSUS_API_KEY": "testkey"}), \
             patch("agent.tools.ba_value_drivers.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_zip_median_rent("94110", beds=None)

        assert "B25031" not in captured_url["url"]
        assert result == 3500.0

    async def test_five_plus_beds_uses_b25031_007e(self):
        from agent.tools.ba_value_drivers import _fetch_zip_median_rent

        response_data = _make_census_response({"B25031_007E": 6000, "B25064_001E": 3200})
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        captured_url = {}

        async def fake_get(url, **kwargs):
            captured_url["url"] = url
            return mock_response

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get

        with patch.dict(os.environ, {"CENSUS_API_KEY": "testkey"}), \
             patch("agent.tools.ba_value_drivers.httpx.AsyncClient", return_value=mock_client):
            result = await _fetch_zip_median_rent("94110", beds=6)

        assert "B25031_007E" in captured_url["url"]
        assert result == 6000.0

    async def test_fetch_ba_value_drivers_passes_bedrooms_to_rent_fetch(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        property_data = {
            "property_type": "SINGLE_FAMILY",
            "lot_size": 4000,
            "city": "Oakland",
            "year_built": 1960,
            "latitude": None,
            "longitude": None,
            "bedrooms": 3,
        }

        captured_beds = {}

        async def fake_fetch_rent(zip_code, beds=None):
            captured_beds["beds"] = beds
            return 4200.0

        with patch("agent.tools.ba_value_drivers._load_caltrain_stations", return_value=[]), \
             patch("agent.tools.ba_value_drivers._fetch_zip_median_rent", side_effect=fake_fetch_rent), \
             patch("agent.tools.ba_value_drivers._fetch_bart_stations", new=AsyncMock(return_value=[])):
            await fetch_ba_value_drivers(property_data, "94601")

        assert captured_beds["beds"] == 3


class TestPrefetchBartStations:
    async def test_prefetch_downloads_and_writes_file(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_bart_stations

        fake_stations = [{"name": "16TH ST MISSION", "lat": 37.765062, "lon": -122.419694, "system": "BART"}]
        cache = str(tmp_path / "bart_stations.json")
        dl = AsyncMock(return_value=fake_stations)

        with patch("agent.tools.ba_value_drivers.BART_CACHE_PATH", cache), \
             patch("agent.tools.ba_value_drivers._download_bart_stations", dl):
            written = await prefetch_bart_stations(force=True)

        assert written is True
        assert os.path.exists(cache)
        with open(cache) as f:
            saved = json.load(f)
        assert saved == fake_stations
        dl.assert_awaited_once()

    async def test_prefetch_skips_when_cache_valid(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_bart_stations

        cache = str(tmp_path / "bart_stations.json")
        with open(cache, "w") as f:
            json.dump([], f)
        dl = AsyncMock(side_effect=AssertionError("should not download"))

        with patch("agent.tools.ba_value_drivers.BART_CACHE_PATH", cache), \
             patch("agent.tools.ba_value_drivers._bart_cache_valid", return_value=True), \
             patch("agent.tools.ba_value_drivers._download_bart_stations", dl):
            written = await prefetch_bart_stations(force=False)

        assert written is False
        dl.assert_not_awaited()

    async def test_prefetch_force_re_downloads_even_when_cache_valid(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_bart_stations

        fake_stations = [{"name": "EMBARCADERO", "lat": 37.7929, "lon": -122.3969, "system": "BART"}]
        cache = str(tmp_path / "bart_stations.json")
        dl = AsyncMock(return_value=fake_stations)

        with patch("agent.tools.ba_value_drivers.BART_CACHE_PATH", cache), \
             patch("agent.tools.ba_value_drivers._bart_cache_valid", return_value=True), \
             patch("agent.tools.ba_value_drivers._download_bart_stations", dl):
            written = await prefetch_bart_stations(force=True)

        assert written is True
        dl.assert_awaited_once()


class TestFetchBartStations:
    async def test_reads_from_disk_not_network(self, tmp_path):
        import agent.tools.ba_value_drivers as mod
        from agent.tools.ba_value_drivers import _fetch_bart_stations

        cached = [{"name": "16TH ST MISSION", "lat": 37.765062, "lon": -122.419694, "system": "BART"}]
        cache = str(tmp_path / "bart_stations.json")
        with open(cache, "w") as f:
            json.dump(cached, f)

        old_cache = mod._bart_cache
        mod._bart_cache = None
        try:
            with patch("agent.tools.ba_value_drivers.BART_CACHE_PATH", cache), \
                 patch("agent.tools.ba_value_drivers.httpx.AsyncClient", side_effect=AssertionError("should not call network")):
                stations = await _fetch_bart_stations()
        finally:
            mod._bart_cache = old_cache

        assert stations == cached

    async def test_returns_empty_list_when_cache_missing(self, tmp_path):
        import agent.tools.ba_value_drivers as mod
        from agent.tools.ba_value_drivers import _fetch_bart_stations

        cache = str(tmp_path / "no_such_file.json")
        old_cache = mod._bart_cache
        mod._bart_cache = None
        try:
            with patch("agent.tools.ba_value_drivers.BART_CACHE_PATH", cache):
                stations = await _fetch_bart_stations()
        finally:
            mod._bart_cache = old_cache

        assert stations == []


class TestPrefetchCaltrainStations:
    async def test_prefetch_writes_stations_to_disk(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_caltrain_stations

        cache = str(tmp_path / "caltrain_stations.json")
        with patch("agent.tools.ba_value_drivers.CALTRAIN_CACHE_PATH", cache):
            written = await prefetch_caltrain_stations(force=True)

        assert written is True
        assert os.path.exists(cache)
        with open(cache) as f:
            saved = json.load(f)
        assert len(saved) > 0
        assert all("name" in s and "lat" in s and "lon" in s for s in saved)

    async def test_prefetch_skips_when_file_exists(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_caltrain_stations

        cache = str(tmp_path / "caltrain_stations.json")
        with open(cache, "w") as f:
            json.dump([], f)

        with patch("agent.tools.ba_value_drivers.CALTRAIN_CACHE_PATH", cache):
            written = await prefetch_caltrain_stations(force=False)

        assert written is False

    async def test_prefetch_force_overwrites_existing(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_caltrain_stations, _CALTRAIN_STATIONS

        cache = str(tmp_path / "caltrain_stations.json")
        with open(cache, "w") as f:
            json.dump([], f)

        with patch("agent.tools.ba_value_drivers.CALTRAIN_CACHE_PATH", cache):
            written = await prefetch_caltrain_stations(force=True)

        assert written is True
        with open(cache) as f:
            saved = json.load(f)
        assert saved == _CALTRAIN_STATIONS


class TestFetchBaValueDrivers:
    async def test_adu_potential_and_rent_control_and_transit_walkshed(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        fake_bart = [{"name": "16TH ST MISSION", "lat": 37.765062, "lon": -122.419694, "system": "BART"}]
        fake_caltrain = [
            {"name": "22nd Street", "lat": 37.7574, "lon": -122.3927}
        ]

        property_data = {
            "property_type": "SINGLE_FAMILY",
            "lot_size": 3500,
            "city": "San Francisco",
            "year_built": 1950,
            "latitude": 37.764,
            "longitude": -122.419,
        }
        with patch("agent.tools.ba_value_drivers._load_caltrain_stations", return_value=fake_caltrain), \
             patch("agent.tools.ba_value_drivers._fetch_zip_median_rent", new=AsyncMock(return_value=4000.0)), \
             patch("agent.tools.ba_value_drivers._fetch_bart_stations", new=AsyncMock(return_value=fake_bart)):
            result = await fetch_ba_value_drivers(property_data, "94110")

        assert result["adu_potential"] is True
        assert result["adu_rent_estimate"] == 2600.0
        assert result["rent_controlled"] is True
        assert result["rent_control_city"] == "San Francisco"
        assert result["nearest_bart_station"] == "16TH ST MISSION"
        assert result["transit_premium_likely"] is True
        assert result["zip_median_rent"] == 4000.0

    async def test_zip_median_rent_included_in_output_when_available(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        property_data = {
            "property_type": "SINGLE_FAMILY",
            "lot_size": 4000,
            "city": "Oakland",
            "year_built": 1960,
            "latitude": None,
            "longitude": None,
        }

        with patch("agent.tools.ba_value_drivers._load_caltrain_stations", return_value=[]), \
             patch("agent.tools.ba_value_drivers._fetch_zip_median_rent", new=AsyncMock(return_value=3500.0)), \
             patch("agent.tools.ba_value_drivers._fetch_bart_stations", new=AsyncMock(return_value=[])):
            result = await fetch_ba_value_drivers(property_data, "94601")

        assert result["zip_median_rent"] == 3500.0

    async def test_zip_median_rent_is_none_when_census_fails(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        property_data = {
            "property_type": "CONDO",
            "lot_size": 0,
            "city": "Fremont",
            "year_built": 2000,
            "latitude": None,
            "longitude": None,
        }

        with patch("agent.tools.ba_value_drivers._load_caltrain_stations", return_value=[]), \
             patch("agent.tools.ba_value_drivers._fetch_zip_median_rent", new=AsyncMock(return_value=None)), \
             patch("agent.tools.ba_value_drivers._fetch_bart_stations", new=AsyncMock(return_value=[])):
            result = await fetch_ba_value_drivers(property_data, "94538")

        assert "zip_median_rent" in result
        assert result["zip_median_rent"] is None

    async def test_no_adu_for_small_lot_or_non_sfr(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        property_data = {
            "property_type": "CONDO",
            "lot_size": 1200,
            "city": "San Jose",
            "year_built": 2004,
            "latitude": None,
            "longitude": None,
        }

        with patch("agent.tools.ba_value_drivers._load_caltrain_stations", return_value=[]), \
             patch("agent.tools.ba_value_drivers._fetch_zip_median_rent", new=AsyncMock(return_value=None)), \
             patch("agent.tools.ba_value_drivers._fetch_bart_stations", new=AsyncMock(return_value=[])):
            result = await fetch_ba_value_drivers(property_data, "95112")

        assert result["adu_potential"] is False
        assert result["adu_rent_estimate"] is None


class TestMuniStops:
    def test_load_muni_stops_returns_builtin_when_file_missing(self, tmp_path):
        from agent.tools.ba_value_drivers import _load_muni_stops, _MUNI_METRO_STOPS

        cache = str(tmp_path / "no_file.json")
        with patch("agent.tools.ba_value_drivers.MUNI_CACHE_PATH", cache):
            stops = _load_muni_stops()

        assert stops == _MUNI_METRO_STOPS
        assert len(stops) > 0

    def test_load_muni_stops_reads_from_disk_when_file_exists(self, tmp_path):
        from agent.tools.ba_value_drivers import _load_muni_stops

        stops_data = [{"name": "Embarcadero", "lat": 37.7930, "lon": -122.3968, "system": "MUNI"}]
        cache = str(tmp_path / "muni_stops.json")
        with open(cache, "w") as f:
            json.dump(stops_data, f)

        with patch("agent.tools.ba_value_drivers.MUNI_CACHE_PATH", cache):
            stops = _load_muni_stops()

        assert stops == stops_data

    async def test_prefetch_muni_stops_writes_file(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_muni_stops

        cache = str(tmp_path / "muni_stops.json")
        with patch("agent.tools.ba_value_drivers.MUNI_CACHE_PATH", cache):
            written = await prefetch_muni_stops(force=True)

        assert written is True
        assert os.path.exists(cache)
        with open(cache) as f:
            saved = json.load(f)
        assert len(saved) > 0
        assert all("name" in s and "lat" in s and "lon" in s and "system" in s for s in saved)

    async def test_prefetch_muni_stops_skips_when_file_exists_not_forced(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_muni_stops

        cache = str(tmp_path / "muni_stops.json")
        with open(cache, "w") as f:
            json.dump([], f)

        with patch("agent.tools.ba_value_drivers.MUNI_CACHE_PATH", cache):
            written = await prefetch_muni_stops(force=False)

        assert written is False

    async def test_prefetch_muni_stops_force_overwrites_existing(self, tmp_path):
        from agent.tools.ba_value_drivers import prefetch_muni_stops, _MUNI_METRO_STOPS

        cache = str(tmp_path / "muni_stops.json")
        with open(cache, "w") as f:
            json.dump([], f)

        with patch("agent.tools.ba_value_drivers.MUNI_CACHE_PATH", cache):
            written = await prefetch_muni_stops(force=True)

        assert written is True
        with open(cache) as f:
            saved = json.load(f)
        assert saved == _MUNI_METRO_STOPS

    async def test_nearest_muni_stop_returned_when_close(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        fake_muni = [{"name": "Castro St", "lat": 37.7626, "lon": -122.4350, "system": "MUNI"}]
        property_data = {
            "property_type": "SINGLE_FAMILY",
            "lot_size": 2000,
            "city": "San Francisco",
            "year_built": 1960,
            "latitude": 37.763,
            "longitude": -122.435,
        }

        with patch("agent.tools.ba_value_drivers._load_caltrain_stations", return_value=[]), \
             patch("agent.tools.ba_value_drivers._load_muni_stops", return_value=fake_muni), \
             patch("agent.tools.ba_value_drivers._fetch_zip_median_rent", new=AsyncMock(return_value=None)), \
             patch("agent.tools.ba_value_drivers._fetch_bart_stations", new=AsyncMock(return_value=[])):
            result = await fetch_ba_value_drivers(property_data, "94114")

        assert result["nearest_muni_stop"] == "Castro St"
        assert result["muni_distance_miles"] is not None
        assert result["muni_distance_miles"] < 0.1

    async def test_muni_stop_included_in_overall_transit_search(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        # Property near MUNI Castro but farther from BART Civic Center
        fake_muni = [{"name": "Castro St", "lat": 37.7626, "lon": -122.4350, "system": "MUNI"}]
        fake_bart = [{"name": "Civic Center", "lat": 37.7799, "lon": -122.4139, "system": "BART"}]
        property_data = {
            "property_type": "CONDO",
            "lot_size": 0,
            "city": "San Francisco",
            "year_built": 2000,
            "latitude": 37.763,
            "longitude": -122.435,
        }

        with patch("agent.tools.ba_value_drivers._load_caltrain_stations", return_value=[]), \
             patch("agent.tools.ba_value_drivers._load_muni_stops", return_value=fake_muni), \
             patch("agent.tools.ba_value_drivers._fetch_zip_median_rent", new=AsyncMock(return_value=None)), \
             patch("agent.tools.ba_value_drivers._fetch_bart_stations", new=AsyncMock(return_value=fake_bart)):
            result = await fetch_ba_value_drivers(property_data, "94114")

        # Castro (MUNI) is ~0.04mi away; Civic Center (BART) is ~1.5mi away
        assert result["nearest_transit_station"] == "Castro St"
        assert result["transit_system"] == "MUNI"
        assert result["transit_premium_likely"] is True

    async def test_nearest_muni_stop_is_none_when_no_coords(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        property_data = {
            "property_type": "CONDO",
            "lot_size": 0,
            "city": "San Francisco",
            "year_built": 2000,
            "latitude": None,
            "longitude": None,
        }

        with patch("agent.tools.ba_value_drivers._load_caltrain_stations", return_value=[]), \
             patch("agent.tools.ba_value_drivers._load_muni_stops", return_value=[{"name": "Castro St", "lat": 37.7626, "lon": -122.4350, "system": "MUNI"}]), \
             patch("agent.tools.ba_value_drivers._fetch_zip_median_rent", new=AsyncMock(return_value=None)), \
             patch("agent.tools.ba_value_drivers._fetch_bart_stations", new=AsyncMock(return_value=[])):
            result = await fetch_ba_value_drivers(property_data, "94114")

        assert result["nearest_muni_stop"] is None
        assert result["muni_distance_miles"] is None
