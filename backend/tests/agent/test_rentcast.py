"""
Tests for rentcast.py — fetch_rental_estimate.
"""

from unittest.mock import AsyncMock, Mock, patch


class TestFetchRentalEstimate:
    async def test_uses_rentcast_when_available(self):
        from agent.tools.rentcast import fetch_rental_estimate

        rc_payload = {
            "rent": 4850,
            "rentRangeLow": 4550,
            "rentRangeHigh": 5150,
            "confidence": 0.78,
        }

        with patch.dict("os.environ", {"RENTCAST_API_KEY": "x"}, clear=False), \
             patch("agent.tools.rentcast.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = Mock(
                raise_for_status=Mock(),
                json=Mock(return_value=rc_payload),
                status_code=200,
            )

            result = await fetch_rental_estimate("450 SANCHEZ ST, SAN FRANCISCO, CA, 94114", "94114")

        assert result["rent_estimate"] == 4850
        assert result["rent_low"] == 4550
        assert result["rent_high"] == 5150
        assert result["confidence"] == 0.78
        assert result["source"] == "rentcast"

    async def test_falls_back_to_acs_when_rentcast_unavailable(self):
        from agent.tools.rentcast import fetch_rental_estimate

        acs_data = [
            ["B25064_001E", "zip code tabulation area"],
            ["3100", "94114"],
        ]

        with patch.dict("os.environ", {"RENTCAST_API_KEY": "x", "CENSUS_API_KEY": "census"}, clear=False), \
             patch("agent.tools.rentcast.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client

            rentcast_resp = Mock(status_code=429)
            rentcast_resp.raise_for_status.side_effect = Exception("quota")
            rentcast_resp.json = Mock(return_value={})

            census_resp = Mock(status_code=200)
            census_resp.raise_for_status = Mock()
            census_resp.json = Mock(return_value=acs_data)

            mock_client.get.side_effect = [rentcast_resp, census_resp]

            result = await fetch_rental_estimate("450 SANCHEZ ST, SAN FRANCISCO, CA, 94114", "94114")

        assert result["rent_estimate"] == 3100
        assert result["rent_low"] is None
        assert result["rent_high"] is None
        assert result["confidence"] == "low"
        assert result["source"] == "census_acs_b25064"
