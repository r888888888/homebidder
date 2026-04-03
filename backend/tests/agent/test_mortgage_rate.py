"""
Tests for mortgage_rate.py.
All external HTTP calls are mocked — no real network requests.
"""

from unittest.mock import AsyncMock, patch

import httpx


class TestFetchFreddieMacMortgageRate:
    async def test_parses_latest_rate_and_date_from_fred_csv(self):
        from agent.tools.mortgage_rate import fetch_freddie_mac_mortgage_rate

        csv_text = (
            "DATE,MORTGAGE30US\n"
            "2026-03-19,6.62\n"
            "2026-03-26,6.64\n"
        )

        with patch("agent.tools.mortgage_rate.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = AsyncMock(text=csv_text)

            result = await fetch_freddie_mac_mortgage_rate()

        assert result["rate_pct"] == 6.64
        assert result["as_of"] == "2026-03-26"
        assert result["series"] == "MORTGAGE30US"

    async def test_raises_value_error_when_csv_has_no_numeric_values(self):
        from agent.tools.mortgage_rate import fetch_freddie_mac_mortgage_rate

        csv_text = "DATE,MORTGAGE30US\n2026-03-26,.\n"
        with patch("agent.tools.mortgage_rate.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = AsyncMock(text=csv_text)

            try:
                await fetch_freddie_mac_mortgage_rate()
                assert False, "Expected ValueError"
            except ValueError:
                pass


class TestGetCurrentMortgageRatePct:
    async def test_returns_fallback_when_http_fails(self):
        from agent.tools.mortgage_rate import get_current_mortgage_rate_pct

        with patch(
            "agent.tools.mortgage_rate.fetch_freddie_mac_mortgage_rate",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPError("network error"),
        ):
            rate = await get_current_mortgage_rate_pct(fallback_rate_pct=6.5)

        assert rate == 6.5
