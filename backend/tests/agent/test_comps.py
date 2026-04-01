"""
Tests for fetch_comps Phase 4 enhancements.
- Haversine distance calculation
- Bay Area adaptive radius selection
- sqft similarity filter (±25%)
- pct_over_asking field
- distance_miles field on each comp
All homeharvest / HTTP calls are mocked.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# SF Mission District coords (dense)
SF_LAT, SF_LON = 37.7599, -122.4148
# San Jose suburb coords (low-density)
SJ_LAT, SJ_LON = 37.3382, -121.8863

BASE_COMP_ROW = {
    "street": "100 Comp St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94110",
    "sold_price": 1_100_000,
    "list_price": 1_050_000,
    "sold_date": "2026-02-01",
    "beds": 3,
    "full_baths": 2,
    "half_baths": None,
    "sqft": 1700,
    "latitude": 37.7605,
    "longitude": -122.4152,
    "property_url": "https://redfin.com/comp",
}


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_is_zero(self):
        from agent.tools.comps import _haversine
        assert _haversine(SF_LAT, SF_LON, SF_LAT, SF_LON) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance(self):
        """Golden Gate Bridge to Coit Tower ≈ 4.1 miles (haversine)."""
        from agent.tools.comps import _haversine
        gg_lat, gg_lon = 37.8199, -122.4783
        ct_lat, ct_lon = 37.8024, -122.4058
        dist = _haversine(gg_lat, gg_lon, ct_lat, ct_lon)
        assert dist == pytest.approx(4.1, abs=0.3)

    def test_distance_is_symmetric(self):
        from agent.tools.comps import _haversine
        d1 = _haversine(SF_LAT, SF_LON, SJ_LAT, SJ_LON)
        d2 = _haversine(SJ_LAT, SJ_LON, SF_LAT, SF_LON)
        assert d1 == pytest.approx(d2, rel=1e-6)


# ---------------------------------------------------------------------------
# Adaptive radius
# ---------------------------------------------------------------------------

class TestAdaptiveRadius:
    def test_dense_sf_zip_returns_small_radius(self):
        """Dense SF ZIPs (e.g. 94110 Mission) → 0.3 mile radius."""
        from agent.tools.comps import _adaptive_radius
        assert _adaptive_radius("94110") == pytest.approx(0.3)

    def test_dense_oakland_zip_returns_small_radius(self):
        """Dense Oakland ZIP → 0.3 mile radius."""
        from agent.tools.comps import _adaptive_radius
        assert _adaptive_radius("94612") == pytest.approx(0.3)

    def test_suburban_zip_returns_medium_radius(self):
        """Suburban Bay Area ZIP → 0.75 mile radius."""
        from agent.tools.comps import _adaptive_radius
        assert _adaptive_radius("94025") == pytest.approx(0.75)  # Menlo Park

    def test_unknown_zip_returns_default_radius(self):
        """Non-Bay-Area ZIP → 1.0 mile default."""
        from agent.tools.comps import _adaptive_radius
        assert _adaptive_radius("10001") == pytest.approx(1.0)  # NYC


# ---------------------------------------------------------------------------
# pct_over_asking
# ---------------------------------------------------------------------------

class TestPctOverAsking:
    async def test_pct_over_asking_computed_when_list_price_known(self):
        """pct_over_asking = (sold - list) / list * 100."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "sold_price": 1_100_000, "list_price": 1_000_000}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert len(comps) == 1
        assert comps[0]["pct_over_asking"] == pytest.approx(10.0, abs=0.1)

    async def test_pct_over_asking_null_when_no_list_price(self):
        """pct_over_asking is None when list_price is missing."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "list_price": None}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert comps[0]["pct_over_asking"] is None

    async def test_pct_over_asking_negative_when_sold_below_list(self):
        """Negative pct_over_asking when sold below list price."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "sold_price": 900_000, "list_price": 1_000_000}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert comps[0]["pct_over_asking"] == pytest.approx(-10.0, abs=0.1)


# ---------------------------------------------------------------------------
# distance_miles
# ---------------------------------------------------------------------------

class TestDistanceMiles:
    async def test_distance_miles_computed_for_each_comp(self):
        """Each comp has a distance_miles value computed via haversine."""
        from agent.tools.comps import fetch_comps

        df = _make_df([BASE_COMP_ROW])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert "distance_miles" in comps[0]
        # Comp at (37.7605, -122.4152) is very close to subject (37.7599, -122.4148)
        assert comps[0]["distance_miles"] == pytest.approx(0.05, abs=0.05)

    async def test_distance_miles_null_when_comp_has_no_coords(self):
        """distance_miles is None when the comp has no lat/lon."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "latitude": None, "longitude": None}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert comps[0]["distance_miles"] is None


# ---------------------------------------------------------------------------
# sqft similarity filter
# ---------------------------------------------------------------------------

class TestSqftFilter:
    async def test_comps_within_25pct_sqft_included(self):
        """Comp within ±25% of subject sqft passes the filter."""
        from agent.tools.comps import fetch_comps

        subject_sqft = 1800
        row = {**BASE_COMP_ROW, "sqft": 2000}  # +11% — within 25%
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
                subject_sqft=subject_sqft,
            )

        assert len(comps) == 1

    async def test_comps_outside_25pct_sqft_excluded(self):
        """Comp outside ±25% of subject sqft is filtered out."""
        from agent.tools.comps import fetch_comps

        subject_sqft = 1000
        row = {**BASE_COMP_ROW, "sqft": 2000}  # +100% — outside 25%
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
                subject_sqft=subject_sqft,
            )

        assert len(comps) == 0

    async def test_sqft_filter_skipped_when_subject_sqft_none(self):
        """If subject_sqft is not provided, sqft filter is not applied."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "sqft": 9999}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
                subject_sqft=None,
            )

        assert len(comps) == 1

# ---------------------------------------------------------------------------
# RentCast sqft fallback for comps
# ---------------------------------------------------------------------------

def _make_rentcast_avm_mock(sqft: int | None):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "price": 1_100_000,
        "subjectProperty": {"squareFootage": sqft} if sqft is not None else {},
    }
    return resp


class TestCompsRentCastSqftFallback:
    async def test_rentcast_sqft_used_when_homeharvest_sqft_missing(self):
        """When a comp has no sqft, RentCast fills it in."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "sqft": None}
        df = _make_df([row])

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}), \
             patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
             patch("agent.tools.comps.httpx.AsyncClient") as mock_cls:

            mock_thread.return_value = df
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_rentcast_avm_mock(sqft=1650)

            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert len(comps) == 1
        assert comps[0]["sqft"] == 1650

    async def test_rentcast_sqft_not_called_when_homeharvest_has_sqft(self):
        """RentCast is not called when homeharvest already provides sqft."""
        from agent.tools.comps import fetch_comps

        df = _make_df([BASE_COMP_ROW])  # sqft=1700

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
             patch("agent.tools.comps.httpx.AsyncClient") as mock_cls:

            mock_thread.return_value = df
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        mock_client.get.assert_not_called()
        assert comps[0]["sqft"] == 1700

    async def test_rentcast_calls_made_in_parallel_for_multiple_missing(self):
        """RentCast is called once per comp with missing sqft, all in parallel."""
        from agent.tools.comps import fetch_comps

        row1 = {**BASE_COMP_ROW, "street": "1 A St", "sqft": None}
        row2 = {**BASE_COMP_ROW, "street": "2 B St", "sqft": None}
        df = _make_df([row1, row2])

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}), \
             patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
             patch("agent.tools.comps.httpx.AsyncClient") as mock_cls:

            mock_thread.return_value = df
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_rentcast_avm_mock(sqft=1500)

            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert mock_client.get.call_count == 2
        assert all(c["sqft"] == 1500 for c in comps)

    async def test_sqft_remains_none_when_rentcast_fails(self):
        """sqft stays None if RentCast raises for a comp."""
        from agent.tools.comps import fetch_comps
        import httpx

        row = {**BASE_COMP_ROW, "sqft": None}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
             patch("agent.tools.comps.httpx.AsyncClient") as mock_cls:

            mock_thread.return_value = df
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.HTTPError("timeout")

            comps = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert comps[0]["sqft"] is None
