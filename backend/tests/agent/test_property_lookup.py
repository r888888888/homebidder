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
    "neighborhoods": "Noe Valley, Castro",
    "price_history": [],
    "property_url": "https://www.redfin.com/CA/San-Francisco/450-Sanchez-St",
}

RENTCAST_RESPONSE = {
    "price": 1_300_000,
    "priceRangeLow": 1_200_000,
    "priceRangeHigh": 1_400_000,
    "subjectProperty": {
        "squareFootage": 1750,
        "lotSize": 2500,
        "bedrooms": 3,
        "bathrooms": 2,
        "yearBuilt": 1928,
        "propertyType": "Single Family",
    },
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
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["address_matched"] == "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114"

    async def test_result_includes_original_address_input(self):
        """Result includes the user-entered address for UI display."""
        from agent.tools.property_lookup import lookup_property_by_address

        query = "821 Folsom St #515, San Francisco, CA 94107"
        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address(query)

        assert result["address_input"] == query

    async def test_geocode_returns_geo_fields(self):
        """Geocoded result includes lat/lon, county, state, and zip_code."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert abs(result["latitude"] - 37.7612) < 0.001
        assert abs(result["longitude"] - (-122.4313)) < 0.001
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

    async def test_geocode_retries_without_unit_number(self):
        """
        If a condo/unit address does not match initially, geocoder should retry
        with the unit designator removed.
        """
        from agent.tools.property_lookup import lookup_property_by_address

        no_match_response = MagicMock()
        no_match_response.raise_for_status = MagicMock()
        no_match_response.json.return_value = {"result": {"addressMatches": []}}

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = [no_match_response, _make_census_mock()]
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address(
                "450 Sanchez St #5, San Francisco, CA 94114"
            )

        assert result["address_matched"] == "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114"
        assert mock_client.get.call_count == 2
        second_url = mock_client.get.call_args_list[1].args[0]
        assert "450+Sanchez+St%2C+San+Francisco%2C+CA+94114" in second_url


# ---------------------------------------------------------------------------
# Homeharvest listing data tests
# ---------------------------------------------------------------------------

class TestHomeharvest:
    async def test_listing_fields_populated_from_homeharvest(self):
        """When homeharvest returns data, listing fields are in the result."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

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

    async def test_unit_address_prefers_exact_input_for_listing_lookup(self):
        """
        Condo/unit searches should query listing sources with the full input
        address first (including unit), not only the geocoder-normalized address.
        """
        from agent.tools.property_lookup import lookup_property_by_address

        no_match_response = MagicMock()
        no_match_response.raise_for_status = MagicMock()
        no_match_response.json.return_value = {"result": {"addressMatches": []}}

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # First geocode call fails on full unit address; second succeeds on stripped.
            mock_client.get.side_effect = [no_match_response, _make_census_mock()]
            mock_hh.return_value = {"price": 1_050_000.0, "source": "homeharvest"}
            mock_rc.return_value = None

            await lookup_property_by_address("4125 24th St #4, San Francisco, CA 94114")

        first_lookup_arg = mock_hh.call_args_list[0].args[0]
        assert first_lookup_arg == "4125 24th St #4, San Francisco, CA 94114"

    async def test_unit_address_retries_with_unit_wording(self):
        """
        If '#<unit>' lookup misses, try a 'Unit <unit>' variant before falling back.
        """
        from agent.tools.property_lookup import lookup_property_by_address

        no_match_response = MagicMock()
        no_match_response.raise_for_status = MagicMock()
        no_match_response.json.return_value = {"result": {"addressMatches": []}}

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = [no_match_response, _make_census_mock()]

            # first candidate misses, second candidate (Unit wording) hits
            mock_hh.side_effect = [{}, {"price": 995_000.0, "source": "homeharvest"}]
            mock_rc.return_value = None

            result = await lookup_property_by_address(
                "821 Folsom St #515, San Francisco, CA 94107"
            )

        assert result["source"] == "homeharvest"
        assert mock_hh.call_args_list[0].args[0] == "821 Folsom St #515, San Francisco, CA 94107"
        assert mock_hh.call_args_list[1].args[0] == "821 Folsom St Unit 515, San Francisco, CA 94107"

    async def test_unit_lookup_continues_after_avm_if_listing_missing(self):
        """
        Do not stop on AVM-only results for the first candidate; keep trying
        unit variants to find a listing record.
        """
        from agent.tools.property_lookup import lookup_property_by_address

        no_match_response = MagicMock()
        no_match_response.raise_for_status = MagicMock()
        no_match_response.json.return_value = {"result": {"addressMatches": []}}

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = [no_match_response, _make_census_mock()]

            # First pass: AVM exists but listing missing; second pass finds listing.
            mock_hh.side_effect = [{}, {"price": 1_020_000.0, "source": "homeharvest"}]
            mock_rc.side_effect = [
                {"avm": 980_000.0, "sqft": None},
                None,
            ]

            result = await lookup_property_by_address(
                "821 Folsom St #515, San Francisco, CA 94107"
            )

        assert result["source"] == "homeharvest"
        assert result["price"] == 1_020_000.0
        assert mock_hh.call_count >= 2


# ---------------------------------------------------------------------------
# RentCast AVM fallback tests
# ---------------------------------------------------------------------------

class TestRentCastFallback:
    async def test_avm_included_when_homeharvest_returns_nothing(self):
        """When homeharvest returns no data, RentCast AVM fills avm_estimate."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = {"avm": 1_300_000.0, "sqft": None}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["avm_estimate"] == 1_300_000.0

    async def test_source_is_rentcast_when_homeharvest_missing(self):
        """Source is 'rentcast' when homeharvest returned nothing but RentCast did."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = {"avm": 1_300_000.0, "sqft": None}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["source"] == "rentcast"

    async def test_avm_included_alongside_homeharvest_listing(self):
        """avm_estimate is included even when homeharvest has a listing price."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {"price": 1_250_000.0, "source": "homeharvest"}
            mock_rc.return_value = {"avm": 1_300_000.0, "sqft": None}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["avm_estimate"] == 1_300_000.0

    async def test_sqft_falls_back_to_rentcast_when_homeharvest_missing(self):
        """When homeharvest returns no sqft, RentCast squareFootage is used."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {"price": 1_250_000.0, "sqft": None, "source": "homeharvest"}
            mock_rc.return_value = {"avm": 1_300_000.0, "sqft": 1750}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["sqft"] == 1750

    async def test_sqft_from_homeharvest_preferred_over_rentcast(self):
        """homeharvest sqft wins when present; RentCast sqft is not used."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {"price": 1_250_000.0, "sqft": 1800, "source": "homeharvest"}
            mock_rc.return_value = {"avm": 1_300_000.0, "sqft": 1750}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["sqft"] == 1800


# ---------------------------------------------------------------------------
# Result structure tests
# ---------------------------------------------------------------------------

class TestResultStructure:
    async def test_result_has_required_keys(self):
        """Result dict always includes all required keys."""
        from agent.tools.property_lookup import lookup_property_by_address

        required_keys = {
            "address_input", "address_matched", "latitude", "longitude", "county", "state", "zip_code",
            "city", "neighborhoods",
            "price", "bedrooms", "bathrooms", "sqft", "year_built", "lot_size",
            "property_type", "hoa_fee", "days_on_market", "list_date", "price_history",
            "avm_estimate", "source", "listing_description", "description_signals",
        }

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

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

    async def test_result_includes_description_signals_when_listing_has_remarks(self):
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {
                "price": 1_250_000.0,
                "listing_description": "Contractor special, tenant occupied",
                "source": "homeharvest",
            }
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["listing_description"] == "Contractor special, tenant occupied"
        assert result["description_signals"]["net_adjustment_pct"] < 0

    async def test_result_has_stable_description_schema_when_missing(self):
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {"price": 1_250_000.0, "source": "homeharvest"}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["listing_description"] is None
        assert result["description_signals"]["detected_signals"] == []
        assert result["description_signals"]["net_adjustment_pct"] == 0.0

    async def test_result_includes_llm_metadata_when_llm_signal_available(self):
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc, \
             patch("agent.tools.property_lookup.evaluate_condition_with_llm", new_callable=AsyncMock) as mock_llm:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {
                "price": 1_250_000.0,
                "listing_description": "tenant occupied fixer",
                "source": "homeharvest",
            }
            mock_rc.return_value = None
            mock_llm.return_value = {
                "source": "llm",
                "confidence": 0.91,
                "model": "test-model",
                "detected_signals": [{"label": "Tenant Occupied", "weight_pct": -1.5}],
                "net_adjustment_pct": -1.5,
            }

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["description_signals"]["llm"]["used"] is True
        assert result["description_signals"]["llm"]["confidence"] == 0.91


# ---------------------------------------------------------------------------
# Internal helpers tests
# ---------------------------------------------------------------------------

class TestHomeharvestListingHelper:
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

    async def test_city_and_neighborhoods_included(self):
        """_homeharvest_listing includes city, county, and neighborhoods fields."""
        from agent.tools.property_lookup import _homeharvest_listing

        df = _make_homeharvest_df([{**HOMEHARVEST_ROW, "county": "San Francisco"}])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("450 SANCHEZ ST, SAN FRANCISCO, CA, 94114")

        assert result["city"] == "San Francisco"
        assert result["county"] == "San Francisco"
        assert result["neighborhoods"] == "Noe Valley, Castro"

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

    async def test_homeharvest_listing_prefers_matching_unit_row(self):
        """
        When multiple units are returned for the same building, select the row
        whose unit matches the requested address.
        """
        from agent.tools.property_lookup import _homeharvest_listing

        row_514 = {
            **HOMEHARVEST_ROW,
            "street": "821 Folsom St Unit 514",
            "list_price": 930_000.0,
            "sqft": 1090,
        }
        row_515 = {
            **HOMEHARVEST_ROW,
            "street": "821 Folsom St Unit 515",
            "list_price": 998_000.0,
            "sqft": 1105,
        }
        df = _make_homeharvest_df([row_514, row_515])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("821 Folsom St #515, San Francisco, CA 94107")

        assert result["price"] == 998_000.0
        assert result["sqft"] == 1105

    async def test_homeharvest_listing_uses_property_url_unit_token_when_street_lacks_unit(self):
        """
        Some rows omit unit in `street` but include it in property_url
        as `...-Unit-<n>...`; we should still select the matching unit row.
        """
        from agent.tools.property_lookup import _homeharvest_listing

        row_other = {
            **HOMEHARVEST_ROW,
            "street": "821 Folsom St",
            "property_url": "https://www.realtor.com/realestateandhomes-detail/821-Folsom-St-Unit-514_San-Francisco_CA_94107_M12345-67890",
            "list_price": 930_000.0,
            "sqft": 1090,
        }
        row_target = {
            **HOMEHARVEST_ROW,
            "street": "821 Folsom St",
            "property_url": "https://www.realtor.com/realestateandhomes-detail/821-Folsom-St-Unit-515_San-Francisco_CA_94107_M12345-67891",
            "list_price": 998_000.0,
            "sqft": 1105,
        }
        df = _make_homeharvest_df([row_other, row_target])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("821 Folsom St #515, San Francisco, CA 94107")

        assert result["price"] == 998_000.0
        assert result["sqft"] == 1105

    async def test_listing_description_extracted_from_text_column(self):
        """_homeharvest_listing reads the description from homeharvest's 'text' column."""
        from agent.tools.property_lookup import _homeharvest_listing

        row = {**HOMEHARVEST_ROW, "text": "Needs TLC. Fixer-upper in the Excelsior."}
        df = _make_homeharvest_df([row])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("450 SANCHEZ ST, SAN FRANCISCO, CA, 94114")

        assert result["listing_description"] == "Needs TLC. Fixer-upper in the Excelsior."

    async def test_listing_description_is_none_when_text_column_absent(self):
        """_homeharvest_listing returns listing_description=None when 'text' is missing."""
        from agent.tools.property_lookup import _homeharvest_listing

        row = {k: v for k, v in HOMEHARVEST_ROW.items() if k != "text"}
        df = _make_homeharvest_df([row])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("450 SANCHEZ ST, SAN FRANCISCO, CA, 94114")

        assert result["listing_description"] is None


class TestRentCastDataHelper:
    async def test_rentcast_data_returns_sqft_and_avm_when_key_set(self):
        """_rentcast_data returns sqft and avm when RENTCAST_API_KEY is set."""
        from agent.tools.property_lookup import _rentcast_data
        import os

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}), \
             patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_rentcast_mock()

            result = await _rentcast_data("450 Sanchez St, San Francisco, CA 94114")

        assert result["sqft"] == 1750
        assert result["avm"] == 1_300_000.0

    async def test_rentcast_data_returns_none_when_no_key(self):
        """_rentcast_data returns None when RENTCAST_API_KEY is not set."""
        from agent.tools.property_lookup import _rentcast_data
        import os

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("RENTCAST_API_KEY", None)
            result = await _rentcast_data("450 Sanchez St, San Francisco, CA 94114")

        assert result is None

    async def test_rentcast_data_returns_none_on_http_error(self):
        """_rentcast_data returns None when the RentCast API call fails."""
        from agent.tools.property_lookup import _rentcast_data
        import os
        import httpx

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}), \
             patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.HTTPError("connection error")

            result = await _rentcast_data("450 Sanchez St, San Francisco, CA 94114")

        assert result is None


# ---------------------------------------------------------------------------
# unit field in lookup_property_by_address result
# ---------------------------------------------------------------------------

class TestUnitField:
    async def test_unit_extracted_from_address_input_when_hash_present(self):
        """unit is derived from the user input when no homeharvest row is found."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address("66 Cleary Ct #1206, San Francisco, CA 94109")

        assert result["unit"] == "1206"

    async def test_unit_none_when_no_unit_in_address(self):
        """unit is None when address has no unit designator."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = None

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["unit"] is None

    async def test_unit_from_homeharvest_row_preferred_over_address_parse(self):
        """unit_number from homeharvest row takes precedence over parsing address_input."""
        from agent.tools.property_lookup import lookup_property_by_address

        import pandas as pd
        row_with_unit = {**HOMEHARVEST_ROW, "street": "66 Cleary Ct", "unit_number": "1206", "style": "CONDO"}
        df = pd.DataFrame([row_with_unit])

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_thread.return_value = df
            mock_rc.return_value = None

            result = await lookup_property_by_address("66 Cleary Ct #1206, San Francisco, CA 94109")

        assert result["unit"] == "1206"


# ---------------------------------------------------------------------------
# Homeharvest no-data row → treated as missing
# ---------------------------------------------------------------------------

class TestHomeharvest_NoDataRow:
    async def test_returns_empty_dict_when_all_key_fields_are_na(self):
        """
        When homeharvest returns a row with no price, beds, sqft, or year_built
        (e.g. a building-level APARTMENT record), treat it as no listing found.
        """
        import pandas as pd
        from agent.tools.property_lookup import _homeharvest_listing

        empty_row = {
            "street": "66 Cleary Ct",
            "unit": "Apt 369679",
            "style": "APARTMENT",
            "list_price": pd.NA,
            "beds": pd.NA,
            "full_baths": pd.NA,
            "half_baths": pd.NA,
            "sqft": pd.NA,
            "year_built": pd.NA,
            "lot_sqft": pd.NA,
            "hoa_fee": pd.NA,
            "days_on_mls": pd.NA,
            "list_date": pd.NA,
            "city": "San Francisco",
            "county": "San Francisco",
            "neighborhoods": pd.NA,
            "price_history": [],
            "property_url": "https://www.realtor.com/apartments/66-Cleary-Ct_San-Francisco_CA_94109",
        }
        df = _make_homeharvest_df([empty_row])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await _homeharvest_listing("66 Cleary Ct #1206, San Francisco, CA 94109")

        assert result == {}

    async def test_returns_data_when_at_least_one_key_field_is_present(self):
        """A row with only sqft (off-market but known) is still treated as found."""
        import pandas as pd
        from agent.tools.property_lookup import _homeharvest_listing

        partial_row = {
            **{k: pd.NA for k in ["list_price", "beds", "full_baths", "half_baths", "year_built", "lot_sqft", "hoa_fee", "days_on_mls", "list_date"]},
            "street": "450 Sanchez St",
            "sqft": 1800,
            "style": "CONDO",
            "city": "San Francisco",
            "county": "San Francisco",
            "neighborhoods": pd.NA,
            "price_history": [],
        }
        df = _make_homeharvest_df([partial_row])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await _homeharvest_listing("450 Sanchez St, San Francisco, CA 94114")

        assert result != {}
        assert result["sqft"] == 1800


# ---------------------------------------------------------------------------
# HomeHarvest unit fallback via nearby building search
# ---------------------------------------------------------------------------

class TestHomeharvestNearbyUnitFallback:
    async def test_homeharvest_nearby_unit_listing_picks_requested_unit(self):
        """
        Nearby building search should select the row whose unit matches the
        requested unit when direct address lookup misses.
        """
        from agent.tools.property_lookup import _homeharvest_nearby_unit_listing

        row_509 = {
            **HOMEHARVEST_ROW,
            "street": "66 Cleary Ct",
            "unit": "Apt 509",
            "style": "CONDOS",
            "list_price": 1_080_000.0,
            "sqft": 1100,
            "property_url": "https://www.realtor.com/realestateandhomes-detail/66-Cleary-Ct-Apt-509_San-Francisco_CA_94109_M19499-39329",
        }
        row_1206 = {
            **HOMEHARVEST_ROW,
            "street": "66 Cleary Ct",
            "unit": "Apt 1206",
            "style": "CONDOS",
            "list_price": 995_000.0,
            "sqft": 1099,
            "property_url": "https://www.realtor.com/realestateandhomes-detail/66-Cleary-Ct-Apt-1206_San-Francisco_CA_94109_M21113-00861",
        }
        df = _make_homeharvest_df([row_509, row_1206])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_nearby_unit_listing(
                "66 Cleary Ct, San Francisco, CA 94109",
                "66 Cleary Ct #1206, San Francisco, CA 94109",
            )

        assert result["price"] == 995_000.0
        assert result["sqft"] == 1099
        assert result["unit"] == "Apt 1206"

    async def test_lookup_uses_nearby_unit_fallback_when_direct_misses(self):
        """
        If direct candidate lookups return no usable HomeHarvest row, lookup
        should use nearby building search to recover the correct unit listing.
        """
        from agent.tools.property_lookup import lookup_property_by_address

        no_match_response = MagicMock()
        no_match_response.raise_for_status = MagicMock()
        no_match_response.json.return_value = {"result": {"addressMatches": []}}

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._homeharvest_nearby_unit_listing", new_callable=AsyncMock) as mock_nearby, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # First geocode call fails on full unit address; second succeeds on stripped.
            mock_client.get.side_effect = [no_match_response, _make_census_mock()]

            # Direct candidates miss.
            mock_hh.side_effect = [{}, {}]
            mock_nearby.return_value = {
                "price": 995_000.0,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "sqft": 1099,
                "year_built": 1963,
                "property_type": "CONDOS",
                "unit": "Apt 1206",
                "source": "homeharvest",
            }
            mock_rc.return_value = None

            result = await lookup_property_by_address(
                "66 Cleary Ct #1206, San Francisco, CA 94109"
            )

        assert result["source"] == "homeharvest"
        assert result["price"] == 995_000.0
        assert result["unit"] == "Apt 1206"
        assert mock_nearby.await_count == 1


# ---------------------------------------------------------------------------
# RentCast subjectProperty fallback for beds/baths/year_built
# ---------------------------------------------------------------------------

class TestRentCastSubjectPropertyFallback:
    async def test_rentcast_data_returns_beds_baths_year_built_from_subject_property(self):
        """_rentcast_data extracts bedrooms, bathrooms, and yearBuilt from subjectProperty."""
        from agent.tools.property_lookup import _rentcast_data
        import os

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}), \
             patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_rentcast_mock()

            result = await _rentcast_data("66 Cleary Ct Unit 1206, San Francisco, CA 94109")

        assert result["bedrooms"] == 3
        assert result["bathrooms"] == 2
        assert result["year_built"] == 1928

    async def test_lookup_uses_rentcast_beds_baths_year_built_as_fallback(self):
        """
        When homeharvest finds no listing data, beds/baths/year_built from
        RentCast subjectProperty are used to populate the result.
        """
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_rc.return_value = {
                "avm": 1_300_000.0,
                "sqft": 1100,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "year_built": 1962,
            }

            result = await lookup_property_by_address("66 Cleary Ct #1206, San Francisco, CA 94109")

        assert result["bedrooms"] == 3
        assert result["bathrooms"] == 2.0
        assert result["year_built"] == 1962

    async def test_homeharvest_beds_baths_year_built_preferred_over_rentcast(self):
        """homeharvest listing values win over RentCast subjectProperty values."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._rentcast_data", new_callable=AsyncMock) as mock_rc:

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
                "source": "homeharvest",
            }
            mock_rc.return_value = {
                "avm": 1_300_000.0,
                "sqft": 1750,
                "bedrooms": 2,
                "bathrooms": 1.0,
                "year_built": 1935,
            }

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["bedrooms"] == 3
        assert result["bathrooms"] == 2.0
        assert result["year_built"] == 1928


# ---------------------------------------------------------------------------
# _listing_lookup_candidates — unit address should not fall back to bare street
# ---------------------------------------------------------------------------

class TestListingLookupCandidates:
    def test_unit_address_excludes_bare_geocoder_matched(self):
        """
        When the user's address has a unit, the geocoder-matched address
        (which strips the unit) must NOT be included as a listing candidate.
        It would find the wrong building-level record.
        """
        from agent.tools.property_lookup import _listing_lookup_candidates

        candidates = _listing_lookup_candidates(
            "66 Cleary Ct #1206, San Francisco, CA 94109",
            "66 CLEARY CT, SAN FRANCISCO, CA, 94109",
        )
        # Must include the user's original and the Unit wording variant
        assert "66 Cleary Ct #1206, San Francisco, CA 94109" in candidates
        assert "66 Cleary Ct Unit 1206, San Francisco, CA 94109" in candidates
        # Must NOT include the bare (no-unit) geocoder address
        assert "66 CLEARY CT, SAN FRANCISCO, CA, 94109" not in candidates

    def test_non_unit_address_includes_geocoder_matched(self):
        """
        When the user's address has no unit, the geocoder-matched address
        is included as a candidate (normal SFH lookup).
        """
        from agent.tools.property_lookup import _listing_lookup_candidates

        candidates = _listing_lookup_candidates(
            "450 Sanchez St, San Francisco, CA 94114",
            "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
        )
        assert "450 Sanchez St, San Francisco, CA 94114" in candidates
        assert "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114" in candidates

    def test_unit_address_with_unit_in_geocoder_result_includes_it(self):
        """
        If the geocoder somehow preserves the unit in its matched address,
        include it — it contains unit-specific info.
        """
        from agent.tools.property_lookup import _listing_lookup_candidates

        candidates = _listing_lookup_candidates(
            "821 Folsom St #515, San Francisco, CA 94107",
            "821 FOLSOM ST UNIT 515, SAN FRANCISCO, CA, 94107",
        )
        assert "821 FOLSOM ST UNIT 515, SAN FRANCISCO, CA, 94107" in candidates
