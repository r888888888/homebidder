"""
Tests for fetch_neighborhood_context tool.
All external HTTP calls are mocked — no real network requests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _http_mock(json_data):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = json_data
    return resp


SF_ASSESSOR_ROWS = [
    {
        "parcel_number": "3582008",
        "assessed_land_value": "250000",
        "assessed_improvement_value": "950000",
        "closed_roll_year": "2019",
        "property_location": "0000 0450 SANCHEZ              ST0000",
    }
]

CENSUS_ACS_RESPONSE = [
    ["B25077_001E", "B25001_001E", "B25004_002E", "B25004_001E", "B25035_001E", "NAME"],
    ["950000",      "12000",       "300",          "300",          "1965",         "ZCTA5 94114"],
]

ALAMEDA_ARCGIS_RESPONSE = {
    "features": [
        {
            "attributes": {
                "APN": "123-456-789",
                "ASSESSED_LAND": 180000,
                "ASSESSED_IMPR": 620000,
                "YEAR_BUILT": 1952,
                "TAX_YEAR": 2018,
            }
        }
    ]
}

SANTA_CLARA_RESPONSE = [
    {
        "apn": "123-45-678",
        "assessed_land_value": "200000",
        "assessed_improvement_value": "750000",
        "year_built": "1960",
        "tax_year": "2020",
    }
]


# ---------------------------------------------------------------------------
# _sf_search_term — street suffix stripping
# ---------------------------------------------------------------------------

class TestSfSearchTerm:
    def test_strips_ave_suffix(self):
        from agent.tools.neighborhood import _sf_search_term
        assert _sf_search_term("319 PLYMOUTH AVE") == "319 PLYMOUTH"

    def test_strips_st_suffix(self):
        from agent.tools.neighborhood import _sf_search_term
        assert _sf_search_term("450 SANCHEZ ST") == "450 SANCHEZ"

    def test_preserves_multi_word_name_without_suffix(self):
        from agent.tools.neighborhood import _sf_search_term
        # "123 VAN NESS AVE" → strips "AVE" → "123 VAN NESS"
        assert _sf_search_term("123 VAN NESS AVE") == "123 VAN NESS"

    def test_no_suffix_returned_unchanged(self):
        from agent.tools.neighborhood import _sf_search_term
        # Only 2 tokens — don't strip (could be "1 MARKET" with no type)
        assert _sf_search_term("1 MARKET") == "1 MARKET"

    def test_unknown_suffix_not_stripped(self):
        from agent.tools.neighborhood import _sf_search_term
        assert _sf_search_term("100 MAIN XYZ") == "100 MAIN XYZ"


# ---------------------------------------------------------------------------
# SF assessor (primary path)
# ---------------------------------------------------------------------------

class TestSFAssessor:
    async def test_sf_county_returns_prop13_data(self):
        """For San Francisco county, Prop 13 assessed value is returned."""
        from agent.tools.neighborhood import fetch_neighborhood_context

        with patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(SF_ASSESSOR_ROWS)

            result = await fetch_neighborhood_context(
                county="San Francisco", state="CA",
                zip_code="94114", address_matched="450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
            )

        assert result["prop13_assessed_value"] == 1_200_000.0  # 250k + 950k

    async def test_sf_county_returns_prop13_base_year(self):
        """Base year extracted from DataSF rollyr field."""
        from agent.tools.neighborhood import fetch_neighborhood_context

        with patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(SF_ASSESSOR_ROWS)

            result = await fetch_neighborhood_context(
                county="San Francisco", state="CA",
                zip_code="94114", address_matched="450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
            )

        assert result["prop13_base_year"] == 2019

    async def test_sf_county_computes_annual_tax(self):
        """Annual tax ≈ assessed_value × 1.25%."""
        from agent.tools.neighborhood import fetch_neighborhood_context

        with patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(SF_ASSESSOR_ROWS)

            result = await fetch_neighborhood_context(
                county="San Francisco", state="CA",
                zip_code="94114", address_matched="450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
            )

        expected_tax = 1_200_000.0 * 0.0125
        assert abs(result["prop13_annual_tax"] - expected_tax) < 1.0

    async def test_sf_assessor_no_match_returns_null_prop13(self):
        """If the DataSF assessor API returns no rows, Prop 13 fields are null."""
        from agent.tools.neighborhood import fetch_neighborhood_context

        with patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock([])

            result = await fetch_neighborhood_context(
                county="San Francisco", state="CA",
                zip_code="94114", address_matched="450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
            )

        assert result["prop13_assessed_value"] is None
        assert result["prop13_base_year"] is None
        assert result["prop13_annual_tax"] is None


# ---------------------------------------------------------------------------
# Alameda County (primary path)
# ---------------------------------------------------------------------------

class TestAlamedaAssessor:
    async def test_alameda_county_returns_prop13_data(self):
        """For Alameda county, Prop 13 data is pulled from ArcGIS REST."""
        from agent.tools.neighborhood import fetch_neighborhood_context

        with patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(ALAMEDA_ARCGIS_RESPONSE)

            result = await fetch_neighborhood_context(
                county="Alameda", state="CA",
                zip_code="94610", address_matched="123 GRAND AVE, OAKLAND, CA, 94610",
            )

        assert result["prop13_assessed_value"] == 800_000.0  # 180k + 620k
        assert result["prop13_base_year"] == 2018


# ---------------------------------------------------------------------------
# Santa Clara County (primary path)
# ---------------------------------------------------------------------------

class TestSantaClaraAssessor:
    async def test_santa_clara_county_returns_prop13_data(self):
        """For Santa Clara county, Prop 13 data is returned."""
        from agent.tools.neighborhood import fetch_neighborhood_context

        with patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(SANTA_CLARA_RESPONSE)

            result = await fetch_neighborhood_context(
                county="Santa Clara", state="CA",
                zip_code="95014", address_matched="1 INFINITE LOOP, CUPERTINO, CA, 95014",
            )

        assert result["prop13_assessed_value"] == 950_000.0  # 200k + 750k
        assert result["prop13_base_year"] == 2020


# ---------------------------------------------------------------------------
# Census ACS fallback
# ---------------------------------------------------------------------------

class TestCensusACSFallback:
    async def test_unsupported_county_uses_census_acs(self):
        """San Mateo (unsupported) falls back to Census ACS; prop13 fields are null."""
        from agent.tools.neighborhood import fetch_neighborhood_context
        import os

        with patch.dict(os.environ, {"CENSUS_API_KEY": "test-key"}), \
             patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(CENSUS_ACS_RESPONSE)

            result = await fetch_neighborhood_context(
                county="San Mateo", state="CA",
                zip_code="94402", address_matched="100 MAIN ST, SAN MATEO, CA, 94402",
            )

        assert result["prop13_assessed_value"] is None
        assert result["median_home_value"] == 950_000.0

    async def test_census_acs_returns_housing_units(self):
        """Census ACS fallback populates housing_units."""
        from agent.tools.neighborhood import fetch_neighborhood_context
        import os

        with patch.dict(os.environ, {"CENSUS_API_KEY": "test-key"}), \
             patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(CENSUS_ACS_RESPONSE)

            result = await fetch_neighborhood_context(
                county="San Mateo", state="CA",
                zip_code="94402", address_matched="100 MAIN ST, SAN MATEO, CA, 94402",
            )

        assert result["housing_units"] == 12_000

    async def test_census_acs_returns_vacancy_rate(self):
        """Census ACS fallback computes vacancy_rate = vacant / total."""
        from agent.tools.neighborhood import fetch_neighborhood_context
        import os

        with patch.dict(os.environ, {"CENSUS_API_KEY": "test-key"}), \
             patch("agent.tools.neighborhood.httpx.AsyncClient") as mock_cls:

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(CENSUS_ACS_RESPONSE)

            result = await fetch_neighborhood_context(
                county="San Mateo", state="CA",
                zip_code="94402", address_matched="100 MAIN ST, SAN MATEO, CA, 94402",
            )

        # 300 vacant / 12000 total = 2.5%
        assert abs(result["vacancy_rate"] - 2.5) < 0.1

    async def test_no_census_key_returns_nulls(self):
        """Without CENSUS_API_KEY, fallback returns all-null result rather than raising."""
        from agent.tools.neighborhood import fetch_neighborhood_context
        import os

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CENSUS_API_KEY", None)
            result = await fetch_neighborhood_context(
                county="Marin", state="CA",
                zip_code="94941", address_matched="1 MAIN ST, MILL VALLEY, CA, 94941",
            )

        assert result["median_home_value"] is None
        assert result["prop13_assessed_value"] is None


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    async def test_result_always_has_required_keys(self):
        """Result dict always contains all required keys regardless of data source."""
        from agent.tools.neighborhood import fetch_neighborhood_context
        import os

        required_keys = {
            "median_home_value", "housing_units", "vacancy_rate", "median_year_built",
            "prop13_assessed_value", "prop13_base_year", "prop13_annual_tax",
        }

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CENSUS_API_KEY", None)
            result = await fetch_neighborhood_context(
                county="Contra Costa", state="CA",
                zip_code="94523", address_matched="100 MAIN ST, PLEASANT HILL, CA, 94523",
            )

        assert required_keys.issubset(result.keys()), \
            f"Missing keys: {required_keys - result.keys()}"

    async def test_non_ca_address_returns_null_prop13(self):
        """Non-CA address has no Prop 13 data."""
        from agent.tools.neighborhood import fetch_neighborhood_context
        import os

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CENSUS_API_KEY", None)
            result = await fetch_neighborhood_context(
                county="King", state="WA",
                zip_code="98101", address_matched="100 MAIN ST, SEATTLE, WA, 98101",
            )

        assert result["prop13_assessed_value"] is None
