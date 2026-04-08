"""
Tests for ba_value_drivers.py.
"""

from unittest.mock import AsyncMock, Mock, patch


class TestFetchBaValueDrivers:
    async def test_adu_potential_and_rent_control_and_transit_walkshed(self):
        from agent.tools.ba_value_drivers import fetch_ba_value_drivers

        bart_data = {
            "root": {
                "stations": {
                    "station": [
                        {"name": "16TH ST MISSION", "gtfs_latitude": "37.765062", "gtfs_longitude": "-122.419694"}
                    ]
                }
            }
        }

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
             patch("agent.tools.ba_value_drivers.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = Mock(
                raise_for_status=Mock(),
                json=Mock(return_value=bart_data),
            )

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
