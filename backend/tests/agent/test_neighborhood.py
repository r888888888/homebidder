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


CENSUS_ACS_RESPONSE = [
    ["B25077_001E", "B25001_001E", "B25004_002E", "B25004_001E", "B25035_001E", "NAME"],
    ["950000",      "12000",       "300",          "300",          "1965",         "ZCTA5 94114"],
]


# ---------------------------------------------------------------------------
# Census ACS fallback
# ---------------------------------------------------------------------------

class TestCensusACSFallback:
    async def test_census_acs_returns_median_home_value(self):
        """Census ACS returns median home value."""
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
        }

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CENSUS_API_KEY", None)
            result = await fetch_neighborhood_context(
                county="Contra Costa", state="CA",
                zip_code="94523", address_matched="100 MAIN ST, PLEASANT HILL, CA, 94523",
            )

        assert required_keys.issubset(result.keys()), \
            f"Missing keys: {required_keys - result.keys()}"
