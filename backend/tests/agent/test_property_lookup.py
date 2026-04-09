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

def _make_census_mock():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = CENSUS_RESPONSE
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
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["address_matched"] == "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114"

    async def test_result_includes_original_address_input(self):
        """Result includes the user-entered address for UI display."""
        from agent.tools.property_lookup import lookup_property_by_address

        query = "821 Folsom St #515, San Francisco, CA 94107"
        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}

            result = await lookup_property_by_address(query)

        assert result["address_input"] == query

    async def test_geocode_returns_geo_fields(self):
        """Geocoded result includes lat/lon, county, state, and zip_code."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}

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
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = [no_match_response, _make_census_mock()]
            mock_hh.return_value = {}

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
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

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

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["price"] == 1_250_000.0
        assert result["bedrooms"] == 3
        assert result["sqft"] == 1800
        assert result["year_built"] == 1928
        assert result["source"] == "homeharvest"

    async def test_listing_url_passed_through_from_homeharvest(self):
        """listing_url is included in the result when homeharvest provides property_url."""
        from agent.tools.property_lookup import lookup_property_by_address

        realtor_url = "https://www.realtor.com/realestateandhomes-detail/450-Sanchez-St_San-Francisco_CA_94114_M89012-34567/"
        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

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
                "property_url": realtor_url,
                "source": "homeharvest",
            }

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["listing_url"] == realtor_url

    async def test_listing_url_is_none_when_no_homeharvest_data(self):
        """listing_url is None when no homeharvest listing was found."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["listing_url"] is None

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
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # First geocode call fails on full unit address; second succeeds on stripped.
            mock_client.get.side_effect = [no_match_response, _make_census_mock()]
            mock_hh.return_value = {"price": 1_050_000.0, "source": "homeharvest"}

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
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = [no_match_response, _make_census_mock()]

            # first candidate misses, second candidate (Unit wording) hits
            mock_hh.side_effect = [{}, {"price": 995_000.0, "source": "homeharvest"}]

            result = await lookup_property_by_address(
                "821 Folsom St #515, San Francisco, CA 94107"
            )

        assert result["source"] == "homeharvest"
        assert mock_hh.call_args_list[0].args[0] == "821 Folsom St #515, San Francisco, CA 94107"
        assert mock_hh.call_args_list[1].args[0] == "821 Folsom St Unit 515, San Francisco, CA 94107"


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
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )

    async def test_result_includes_description_signals_when_listing_has_remarks(self):
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {
                "price": 1_250_000.0,
                "listing_description": "Contractor special, tenant occupied",
                "source": "homeharvest",
            }

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["listing_description"] == "Contractor special, tenant occupied"
        assert result["description_signals"]["net_adjustment_pct"] < 0

    async def test_result_has_stable_description_schema_when_missing(self):
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {"price": 1_250_000.0, "source": "homeharvest"}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["listing_description"] is None
        assert result["description_signals"]["detected_signals"] == []
        assert result["description_signals"]["net_adjustment_pct"] == 0.0

    async def test_result_includes_llm_metadata_when_llm_signal_available(self):
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
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

    async def test_homeharvest_listing_uses_unit_number_structured_field_when_street_and_url_lack_unit(self):
        """
        Some rows store the unit only in the unit_number structured field with a
        bare street (e.g., street='88 Hoff St', unit_number='104') and a URL
        that contains no recognisable unit token.  _select_best_homeharvest_row
        should still select the row whose unit_number matches the query.
        """
        from agent.tools.property_lookup import _homeharvest_listing

        row_other = {
            **HOMEHARVEST_ROW,
            "street": "88 Hoff St",
            "unit_number": "101",
            "property_url": "https://www.realtor.com/some-opaque-id-abc",
            "list_price": 750_000.0,
            "sqft": 850,
        }
        row_target = {
            **HOMEHARVEST_ROW,
            "street": "88 Hoff St",
            "unit_number": "104",
            "property_url": "https://www.realtor.com/some-opaque-id-def",
            "list_price": 849_000.0,
            "sqft": 920,
        }
        df = _make_homeharvest_df([row_other, row_target])

        with patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df

            result = await _homeharvest_listing("88 Hoff St #104, San Francisco, CA 94110")

        assert result["price"] == 849_000.0
        assert result["sqft"] == 920

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


# ---------------------------------------------------------------------------
# unit field in lookup_property_by_address result
# ---------------------------------------------------------------------------

class TestUnitField:
    async def test_unit_extracted_from_address_input_when_hash_present(self):
        """unit is derived from the user input when no homeharvest row is found."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh, \
             patch("agent.tools.property_lookup._homeharvest_nearby_unit_listing", new_callable=AsyncMock) as mock_nearby:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}
            mock_nearby.return_value = {}

            result = await lookup_property_by_address("66 Cleary Ct #1206, San Francisco, CA 94109")

        assert result["unit"] == "1206"

    async def test_unit_none_when_no_unit_in_address(self):
        """unit is None when address has no unit designator."""
        from agent.tools.property_lookup import lookup_property_by_address

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup._homeharvest_listing", new_callable=AsyncMock) as mock_hh:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_hh.return_value = {}

            result = await lookup_property_by_address("450 Sanchez St, San Francisco, CA 94114")

        assert result["unit"] is None

    async def test_unit_from_homeharvest_row_preferred_over_address_parse(self):
        """unit_number from homeharvest row takes precedence over parsing address_input."""
        from agent.tools.property_lookup import lookup_property_by_address

        import pandas as pd
        row_with_unit = {**HOMEHARVEST_ROW, "street": "66 Cleary Ct", "unit_number": "1206", "style": "CONDO"}
        df = pd.DataFrame([row_with_unit])

        with patch("agent.tools.property_lookup.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.property_lookup.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_census_mock()
            mock_thread.return_value = df

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
             patch("agent.tools.property_lookup._homeharvest_nearby_unit_listing", new_callable=AsyncMock) as mock_nearby:

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

            result = await lookup_property_by_address(
                "66 Cleary Ct #1206, San Francisco, CA 94109"
            )

        assert result["source"] == "homeharvest"
        assert result["price"] == 995_000.0
        assert result["unit"] == "Apt 1206"
        assert mock_nearby.await_count == 1


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
