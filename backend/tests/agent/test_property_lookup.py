"""
Tests for lookup_property_by_address tool.
All external HTTP calls and homeharvest are mocked — no real network requests.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

CENSUS_RESPONSE = {
    "result": {
        "addressMatches": [
            {
                "matchedAddress": "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
                "coordinates": {"x": -122.4313, "y": 37.7612},
                "addressComponents": {
                    "zip": "94114",
                    "state": "CA",
                    "county": "San Francisco",
                },
            }
        ]
    }
}

HOMEHARVEST_ROW = {
    "street": "450 Sanchez St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94114",
    "list_price": 1_250_000.0,
    "beds": 3,
    "full_baths": 2,
    "half_baths": None,
    "sqft": 1800,
    "year_built": 1928,
    "lot_sqft": 2500,
    "style": "SINGLE_FAMILY",
    "hoa_fee": None,
    "days_on_mls": 5,
    "list_date": "2026-03-27 10:00:00",
    "price_history": [],
    "property_url": "https://www.redfin.com/CA/San-Francisco/450-Sanchez-St",
}

RENTCAST_RESPONSE = {
    "price": 1_300_000,
    "priceRangeLow": 1_200_000,
    "priceRangeHigh": 1_400_000,
    "confidence": "HIGH",
}


def _make_census_mock():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = CENSUS_RESPONSE
    return resp


def _make_rentcast_mock():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = RENTCAST_RESPONSE
    return resp


def _make_homeharvest_df(rows: list[dict]):
    """Build a minimal pandas DataFrame from a list of row dicts."""
    import pandas as pd
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Geocoding tests
# ---------------------------------------------------------------------------

class TestGeocoding:
    async def test_geocode_returns_matched_address(self):
        """lookup_property_by_address geocodes the address via Census API."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["address_matched"] == "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114"

    async def test_geocode_returns_lat_lon(self):
        """Geocoded result includes latitude and longitude."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert abs(result["latitude"] - 37.7612) < 0.001
        assert abs(result["longitude"] - (-122.4313)) < 0.001

    async def test_geocode_returns_county_state_zip(self):
        """Geocoded result includes county, state, and zip_code."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["county"] == "San Francisco"
        assert result["state"] == "CA"
        assert result["zip_code"] == "94114"

    async def test_geocode_no_match_raises(self):
        """If the Census geocoder finds no match, a ValueError is raised."""
        from agent.tools.property_lookup import lookup_property_by_address

        no_match_response = MagicMock()
        no_match_response.raise_for_status = MagicMock()
        no_match_response.json.return_value = {"result": {"addressMatches": []}}

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = no_match_response

            with pytest.raises(ValueError, match="not found"):
                await lookup_property_by_address("123 Fake St, Nowhere, CA 00000")


# ---------------------------------------------------------------------------
# Homeharvest listing data tests
# ---------------------------------------------------------------------------

class TestHomeharvest:
    async def test_listing_fields_populated_from_homeharvest(self):
        """When homeharvest returns data, listing fields are in the result."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {
                "price": 1_250_000.0,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "sqft": 1800,
                "year_built": 1928,
                "lot_size": 2500,
                "property_type": "SINGLE_FAMILY",
                "hoa_fee": None,
                "days_on_market": 5,
                "price_history": [],
                "source": "homeharvest",
            }
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["price"] == 1_250_000.0
        assert result["bedrooms"] == 3
        assert result["sqft"] == 1800
        assert result["year_built"] == 1928
        assert result["source"] == "homeharvest"

    async def test_source_is_homeharvest_when_listing_found(self):
        """Result source is 'homeharvest' when that path succeeds."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {"price": 1_000_000.0, "source": "homeharvest"}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["source"] == "homeharvest"


# ---------------------------------------------------------------------------
# RentCast AVM fallback tests
# ---------------------------------------------------------------------------

class TestRentCastFallback:
    async def test_avm_included_when_homeharvest_returns_nothing(self):
        """When homeharvest returns no data, RentCast AVM fills avm_estimate."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = 1_300_000.0

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["avm_estimate"] == 1_300_000.0

    async def test_source_is_rentcast_when_homeharvest_missing(self):
        """Source is 'rentcast' when homeharvest returned nothing but RentCast did."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = 1_300_000.0

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["source"] == "rentcast"

    async def test_avm_included_alongside_homeharvest_listing(self):
        """avm_estimate is included even when homeharvest has a listing price."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {"price": 1_250_000.0, "source": "homeharvest"}
            mock_rc.return_value = 1_300_000.0

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["avm_estimate"] == 1_300_000.0


# ---------------------------------------------------------------------------
# Result structure tests
# ---------------------------------------------------------------------------

class TestResultStructure:
    async def test_result_has_required_keys(self):
        """Result dict always includes all required keys."""
        from agent.tools.property_lookup import lookup_property_by_address

        required_keys = {
            "address_matched", "latitude", "longitude", "county", "state", "zip_code",
            "price", "bedrooms", "bathrooms", "sqft", "year_built", "lot_size",
            "property_type", "hoa_fee", "days_on_market", "list_date", "price_history",
            "avm_estimate", "source",
        }

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_avm", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )


# ---------------------------------------------------------------------------
# Internal helpers tests
# ---------------------------------------------------------------------------

class TestHomeharvestListingHelper:
    async def test_homeharvest_listing_returns_dict(self):
        """_homeharvest_listing returns a dict with listing fields from a df row."""
        import pandas as pd
        from agent.tools.property_lookup import _homeharvest_listing

        df = _make_homeharvest_df([HOMEHARVEST_ROW])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("450 SANCHEZ ST, SAN FRANCISCO, CA, 94114")

        assert result["price"] == 1_250_000.0
        assert result["bedrooms"] == 3
        assert result["year_built"] == 1928

    async def test_list_date_included_in_result(self):
        """_homeharvest_listing passes list_date through as a string."""
        from agent.tools.property_lookup import _homeharvest_listing

        df = _make_homeharvest_df([HOMEHARVEST_ROW])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("450 SANCHEZ ST, SAN FRANCISCO, CA, 94114")

        assert result["list_date"] == "2026-03-27 10:00:00"

    async def test_list_date_is_none_when_missing(self):
        """_homeharvest_listing returns list_date=None if the column is absent."""
        from agent.tools.property_lookup import _homeharvest_listing

        row_without_date = {k: v for k, v in HOMEHARVEST_ROW.items() if k != "list_date"}
        df = _make_homeharvest_df([row_without_date])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("450 SANCHEZ ST, SAN FRANCISCO, CA, 94114")

        assert result["list_date"] is None

    async def test_homeharvest_listing_returns_empty_dict_when_df_empty(self):
        """_homeharvest_listing returns {} when homeharvest finds nothing."""
        import pandas as pd
        from agent.tools.property_lookup import _homeharvest_listing

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = pd.DataFrame()

            result = await _homeharvest_listing("123 Unlisted St, SF, CA, 94110")

        assert result == {}

    async def test_homeharvest_listing_returns_empty_dict_on_exception(self):
        """_homeharvest_listing returns {} if homeharvest raises."""
        from agent.tools.property_lookup import _homeharvest_listing

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.side_effect = RuntimeError("homeharvest error")

            result = await _homeharvest_listing("some address")

        assert result == {}


class TestRentCastAvmHelper:
    async def test_rentcast_avm_returns_price_when_key_set(self):
        """_rentcast_avm returns the AVM price when RENTCAST_API_KEY is set."""
        from agent.tools.property_lookup import _rentcast_avm
        import os

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}), \
             patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_rentcast_mock()

            result = await _rentcast_avm("450 Sanchez St, San Francisco, CA 94114")

        assert result == 1_300_000.0

    async def test_rentcast_avm_returns_none_when_no_key(self):
        """_rentcast_avm returns None when RENTCAST_API_KEY is not set."""
        from agent.tools.property_lookup import _rentcast_avm
        import os

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("RENTCAST_API_KEY", None)
            result = await _rentcast_avm("450 Sanchez St, San Francisco, CA 94114")

        assert result is None

    async def test_rentcast_avm_returns_none_on_http_error(self):
        """_rentcast_avm returns None when the RentCast API call fails."""
        from agent.tools.property_lookup import _rentcast_avm
        import os
        import httpx

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}), \
             patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.HTTPError("connection error")

            result = await _rentcast_avm("450 Sanchez St, San Francisco, CA 94114")

        assert result is None
