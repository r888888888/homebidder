"""
Tests for rentcast_avm.fetch_avm_estimate.
All HTTP calls are mocked — no real network requests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_avm_response(price: int | None = 1_250_000):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    body = {}
    if price is not None:
        body["price"] = price
    resp.json.return_value = body
    return resp


class TestFetchAvmEstimate:
    async def test_returns_price_when_api_call_succeeds(self):
        from agent.tools.rentcast_avm import fetch_avm_estimate

        with patch("agent.tools.rentcast_avm.settings") as mock_settings, \
             patch("agent.tools.rentcast_avm.httpx.AsyncClient") as mock_cls:

            mock_settings.enable_rentcast_avm = True
            mock_settings.rentcast_api_key = "test-key"

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_avm_response(1_250_000)

            result = await fetch_avm_estimate("450 Sanchez St, San Francisco, CA 94114")

        assert result == 1_250_000

    async def test_returns_none_when_feature_flag_disabled(self):
        from agent.tools.rentcast_avm import fetch_avm_estimate

        with patch("agent.tools.rentcast_avm.settings") as mock_settings, \
             patch("agent.tools.rentcast_avm.httpx.AsyncClient") as mock_cls:

            mock_settings.enable_rentcast_avm = False

            result = await fetch_avm_estimate("450 Sanchez St, San Francisco, CA 94114")

        assert result is None
        mock_cls.assert_not_called()

    async def test_returns_none_on_http_status_error(self):
        import httpx
        from agent.tools.rentcast_avm import fetch_avm_estimate

        with patch("agent.tools.rentcast_avm.settings") as mock_settings, \
             patch("agent.tools.rentcast_avm.httpx.AsyncClient") as mock_cls:

            mock_settings.enable_rentcast_avm = True
            mock_settings.rentcast_api_key = "test-key"

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "429 rate limited",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )

            result = await fetch_avm_estimate("450 Sanchez St, San Francisco, CA 94114")

        assert result is None

    async def test_returns_none_on_network_exception(self):
        from agent.tools.rentcast_avm import fetch_avm_estimate

        with patch("agent.tools.rentcast_avm.settings") as mock_settings, \
             patch("agent.tools.rentcast_avm.httpx.AsyncClient") as mock_cls:

            mock_settings.enable_rentcast_avm = True
            mock_settings.rentcast_api_key = "test-key"

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = Exception("connection refused")

            result = await fetch_avm_estimate("450 Sanchez St, San Francisco, CA 94114")

        assert result is None

    async def test_passes_address_and_api_key_to_api(self):
        from agent.tools.rentcast_avm import fetch_avm_estimate

        with patch("agent.tools.rentcast_avm.settings") as mock_settings, \
             patch("agent.tools.rentcast_avm.httpx.AsyncClient") as mock_cls:

            mock_settings.enable_rentcast_avm = True
            mock_settings.rentcast_api_key = "my-secret-key"

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_avm_response(900_000)

            await fetch_avm_estimate("123 Main St, Oakland, CA 94601")

        call_kwargs = mock_client.get.call_args
        url = call_kwargs[0][0]
        headers = call_kwargs[1]["headers"]

        assert "rentcast.io" in url
        assert "123+Main+St" in url or "123%20Main%20St" in url or "123 Main St" in url
        assert headers.get("X-Api-Key") == "my-secret-key"

    async def test_returns_none_when_response_missing_price_key(self):
        from agent.tools.rentcast_avm import fetch_avm_estimate

        with patch("agent.tools.rentcast_avm.settings") as mock_settings, \
             patch("agent.tools.rentcast_avm.httpx.AsyncClient") as mock_cls:

            mock_settings.enable_rentcast_avm = True
            mock_settings.rentcast_api_key = "test-key"

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_avm_response(price=None)

            result = await fetch_avm_estimate("450 Sanchez St, San Francisco, CA 94114")

        assert result is None

    async def test_returns_integer(self):
        from agent.tools.rentcast_avm import fetch_avm_estimate

        with patch("agent.tools.rentcast_avm.settings") as mock_settings, \
             patch("agent.tools.rentcast_avm.httpx.AsyncClient") as mock_cls:

            mock_settings.enable_rentcast_avm = True
            mock_settings.rentcast_api_key = "test-key"

            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # RentCast can return floats (e.g. 1250000.0)
            mock_client.get.return_value = _make_avm_response(1_250_000)

            result = await fetch_avm_estimate("450 Sanchez St, San Francisco, CA 94114")

        assert isinstance(result, int)
