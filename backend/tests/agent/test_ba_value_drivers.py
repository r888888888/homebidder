"""
Tests for ba_value_drivers.py.
"""

import json
import os
from unittest.mock import AsyncMock, Mock, patch


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
