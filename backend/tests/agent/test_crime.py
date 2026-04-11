"""
Tests for fetch_crime_data tool.
All external HTTP calls are mocked — no real network requests.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _http_mock(json_data):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = json_data
    return resp


# Sample DataSF incidents (2 Assault, 1 Robbery, 3 Larceny Theft, 1 Motor Vehicle Theft, 1 Burglary)
DATASF_INCIDENTS = [
    {"incident_category": "Assault",             "incident_subcategory": "Aggravated Assault"},
    {"incident_category": "Assault",             "incident_subcategory": "Simple Assault"},
    {"incident_category": "Robbery",             "incident_subcategory": "Street Robbery"},
    {"incident_category": "Larceny Theft",       "incident_subcategory": "Theft From Vehicle"},
    {"incident_category": "Larceny Theft",       "incident_subcategory": "Pickpocket"},
    {"incident_category": "Larceny Theft",       "incident_subcategory": "Grand Theft"},
    {"incident_category": "Motor Vehicle Theft", "incident_subcategory": "Car Theft"},
    {"incident_category": "Burglary",            "incident_subcategory": "Residential Burglary"},
]

# Sample SpotCrime response (1 Assault, 2 Theft, 1 Burglary — all recent)
_RECENT = (datetime.utcnow() - timedelta(days=10)).strftime("%m/%d/%Y")
SPOTCRIME_RESPONSE = {
    "crimes": [
        {"type": "Assault",  "date": f"{_RECENT} 08:00 pm"},
        {"type": "Theft",    "date": f"{_RECENT} 09:00 am"},
        {"type": "Theft",    "date": f"{_RECENT} 10:00 am"},
        {"type": "Burglary", "date": f"{_RECENT} 11:00 pm"},
    ]
}


# ---------------------------------------------------------------------------
# DataSF (San Francisco county) tests
# ---------------------------------------------------------------------------

class TestDataSF:
    async def test_sf_county_calls_datasf_endpoint(self):
        """SF county triggers the DataSF Socrata API, not SpotCrime."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(DATASF_INCIDENTS)

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="San Francisco"
            )

        url = mock_client.get.call_args[0][0]
        assert "sfgov.org" in url
        assert result["source"] == "SFPD / DataSF"

    async def test_sf_county_case_insensitive(self):
        """County match is case-insensitive (e.g. 'san francisco' works)."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(DATASF_INCIDENTS)

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="san francisco"
            )

        assert result["source"] == "SFPD / DataSF"

    async def test_datasf_violent_count(self):
        """Assault + Robbery incidents are counted as violent crimes."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(DATASF_INCIDENTS)

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="San Francisco"
            )

        # 2 Assault + 1 Robbery = 3 violent
        assert result["violent_count"] == 3

    async def test_datasf_property_count(self):
        """Larceny, auto theft, burglary are counted as property crimes."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(DATASF_INCIDENTS)

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="San Francisco"
            )

        # 3 Larceny Theft + 1 Motor Vehicle Theft + 1 Burglary = 5 property
        assert result["property_count"] == 5

    async def test_datasf_top_types_ordered_by_frequency(self):
        """Top types are returned in descending frequency order."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(DATASF_INCIDENTS)

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="San Francisco"
            )

        # Assault (2) ranks before Robbery (1) for violent
        assert result["top_violent_types"][0] == "Assault"
        # Larceny Theft (3) ranks first for property
        assert result["top_property_types"][0] == "Larceny Theft"

    async def test_datasf_http_error_returns_null_result(self):
        """DataSF HTTP error returns null result without raising."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = Exception("Connection refused")

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="San Francisco"
            )

        assert result["violent_count"] is None
        assert result["property_count"] is None


# ---------------------------------------------------------------------------
# SpotCrime (non-SF) tests
# ---------------------------------------------------------------------------

class TestSpotCrime:
    async def test_non_sf_county_calls_spotcrime(self):
        """Non-SF county triggers SpotCrime API."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.crime.settings") as mock_settings:
            mock_settings.spotcrime_api_key = "test-key"
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(SPOTCRIME_RESPONSE)

            result = await fetch_crime_data(
                latitude=37.8044, longitude=-122.2712, county="Alameda"
            )

        url = mock_client.get.call_args[0][0]
        assert "spotcrime.com" in url
        assert result["source"] == "SpotCrime"

    async def test_spotcrime_violent_and_property_counts(self):
        """Assault counts as violent; Theft + Burglary count as property."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.crime.settings") as mock_settings:
            mock_settings.spotcrime_api_key = "test-key"
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(SPOTCRIME_RESPONSE)

            result = await fetch_crime_data(
                latitude=37.8044, longitude=-122.2712, county="Alameda"
            )

        assert result["violent_count"] == 1   # 1 Assault
        assert result["property_count"] == 3  # 2 Theft + 1 Burglary

    async def test_spotcrime_no_api_key_returns_nulls(self):
        """Without SpotCrime API key, non-SF returns null result."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.settings") as mock_settings:
            mock_settings.spotcrime_api_key = None

            result = await fetch_crime_data(
                latitude=37.8044, longitude=-122.2712, county="Alameda"
            )

        assert result["violent_count"] is None
        assert result["property_count"] is None
        assert result["source"] is None

    async def test_spotcrime_http_error_returns_nulls(self):
        """SpotCrime HTTP error returns null result without raising."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.crime.settings") as mock_settings:
            mock_settings.spotcrime_api_key = "test-key"
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = Exception("Connection timeout")

            result = await fetch_crime_data(
                latitude=37.8044, longitude=-122.2712, county="Alameda"
            )

        assert result["violent_count"] is None
        assert result["property_count"] is None

    async def test_spotcrime_filters_out_old_crimes(self):
        """Incidents older than 90 days are excluded from counts."""
        from agent.tools.crime import fetch_crime_data

        old_date = (datetime.utcnow() - timedelta(days=120)).strftime("%m/%d/%Y")
        recent_date = (datetime.utcnow() - timedelta(days=5)).strftime("%m/%d/%Y")

        response = {
            "crimes": [
                {"type": "Assault", "date": f"{old_date} 08:00 pm"},   # old — excluded
                {"type": "Theft",   "date": f"{recent_date} 09:00 am"},  # recent — included
            ]
        }

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls, \
             patch("agent.tools.crime.settings") as mock_settings:
            mock_settings.spotcrime_api_key = "test-key"
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(response)

            result = await fetch_crime_data(
                latitude=37.8044, longitude=-122.2712, county="Alameda"
            )

        assert result["violent_count"] == 0
        assert result["property_count"] == 1


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    _REQUIRED_KEYS = {
        "violent_count", "property_count", "total_count",
        "radius_miles", "period_days", "source",
        "top_violent_types", "top_property_types",
    }

    async def test_null_result_has_all_required_keys(self):
        """Null result (no key) still has all required keys."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.settings") as mock_settings:
            mock_settings.spotcrime_api_key = None

            result = await fetch_crime_data(
                latitude=37.8044, longitude=-122.2712, county="Alameda"
            )

        missing = self._REQUIRED_KEYS - result.keys()
        assert not missing, f"Missing keys: {missing}"

    async def test_sf_success_result_has_all_required_keys(self):
        """Successful SF result has all required keys."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(DATASF_INCIDENTS)

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="San Francisco"
            )

        missing = self._REQUIRED_KEYS - result.keys()
        assert not missing, f"Missing keys: {missing}"

    async def test_total_count_equals_violent_plus_property(self):
        """total_count equals violent_count + property_count."""
        from agent.tools.crime import fetch_crime_data

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(DATASF_INCIDENTS)

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="San Francisco"
            )

        assert result["total_count"] == result["violent_count"] + result["property_count"]

    async def test_top_types_capped_at_three(self):
        """top_violent_types and top_property_types are at most 3 entries."""
        from agent.tools.crime import fetch_crime_data

        # Create 5 distinct violent categories to test the cap
        many_incidents = [
            {"incident_category": cat, "incident_subcategory": "sub"}
            for cat in ["Assault", "Robbery", "Homicide", "Rape", "Human Trafficking"]
        ]

        with patch("agent.tools.crime.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _http_mock(many_incidents)

            result = await fetch_crime_data(
                latitude=37.7749, longitude=-122.4194, county="San Francisco"
            )

        assert len(result["top_violent_types"]) <= 3
