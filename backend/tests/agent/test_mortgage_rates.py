"""
Tests for mortgage_rates.py.
All external HTTP calls are mocked.
"""

from unittest.mock import AsyncMock, Mock, patch


class TestFetchMortgageRates:
    async def test_fetches_latest_30_and_15_year_rates(self):
        from agent.tools.mortgage_rates import fetch_mortgage_rates

        def _resp(series_id: str, value: str, date: str):
            return {
                "observations": [
                    {"date": date, "value": value, "series_id": series_id},
                ]
            }

        with patch.dict("os.environ", {"FRED_API_KEY": "fred"}, clear=False), \
             patch("agent.tools.mortgage_rates.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                Mock(json=Mock(return_value=_resp("MORTGAGE30US", "6.71", "2026-03-26")), raise_for_status=Mock()),
                Mock(json=Mock(return_value=_resp("MORTGAGE15US", "5.98", "2026-03-26")), raise_for_status=Mock()),
            ]

            result = await fetch_mortgage_rates()

        assert result["rate_30yr_fixed"] == 6.71
        assert result["rate_15yr_fixed"] == 5.98
        assert result["as_of_date"] == "2026-03-26"
        assert result["source"] == "Freddie Mac PMMS via FRED"

    async def test_uses_24h_cache(self):
        from agent.tools.mortgage_rates import _cache, fetch_mortgage_rates

        _cache["value"] = {
            "rate_30yr_fixed": 6.88,
            "rate_15yr_fixed": 6.07,
            "as_of_date": "2026-03-19",
            "source": "Freddie Mac PMMS via FRED",
        }
        _cache["fetched_at_epoch"] = 1_000_000_000

        with patch("agent.tools.mortgage_rates.time.time", return_value=1_000_000_000 + 60), \
             patch("agent.tools.mortgage_rates.httpx.AsyncClient", side_effect=AssertionError("should not call network")):
            result = await fetch_mortgage_rates()

        assert result["rate_30yr_fixed"] == 6.88
        assert result["rate_15yr_fixed"] == 6.07

    async def test_refreshes_cache_after_ttl(self):
        from agent.tools.mortgage_rates import _cache, fetch_mortgage_rates

        _cache["value"] = {
            "rate_30yr_fixed": 6.4,
            "rate_15yr_fixed": 5.8,
            "as_of_date": "2026-03-12",
            "source": "Freddie Mac PMMS via FRED",
        }
        _cache["fetched_at_epoch"] = 1_000_000_000

        new_30 = {"observations": [{"date": "2026-03-26", "value": "6.73"}]}
        new_15 = {"observations": [{"date": "2026-03-26", "value": "5.99"}]}

        with patch.dict("os.environ", {"FRED_API_KEY": "fred"}, clear=False), \
             patch("agent.tools.mortgage_rates.time.time", return_value=1_000_000_000 + 86_401), \
             patch("agent.tools.mortgage_rates.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                Mock(json=Mock(return_value=new_30), raise_for_status=Mock()),
                Mock(json=Mock(return_value=new_15), raise_for_status=Mock()),
            ]

            result = await fetch_mortgage_rates()

        assert result["rate_30yr_fixed"] == 6.73
        assert result["rate_15yr_fixed"] == 5.99
