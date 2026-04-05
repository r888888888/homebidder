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
import datetime as dt
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


# ---------------------------------------------------------------------------
# Adaptive radius
# ---------------------------------------------------------------------------

class TestAdaptiveRadius:
    @pytest.mark.parametrize("zip_code,expected_radius", [
        ("94110", 0.3),   # Dense SF Mission
        ("94612", 0.3),   # Dense Oakland
        ("94025", 0.75),  # Suburban Menlo Park
        ("10001", 1.0),   # Unknown / non-Bay-Area default
    ])
    def test_adaptive_radius_by_zip(self, zip_code, expected_radius):
        from agent.tools.comps import _adaptive_radius
        assert _adaptive_radius(zip_code) == pytest.approx(expected_radius)


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
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert len(comps) == 1
        assert comps[0]["pct_over_asking"] == pytest.approx(10.0, abs=0.1)

    async def test_pct_over_asking_null_when_no_list_price(self):
        """pct_over_asking is None when list_price is missing."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "list_price": None}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert comps[0]["pct_over_asking"] is None

    async def test_pct_over_asking_negative_when_sold_below_list(self):
        """Negative pct_over_asking when sold below list price."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "sold_price": 900_000, "list_price": 1_000_000}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert comps[0]["pct_over_asking"] == pytest.approx(-10.0, abs=0.1)

    async def test_unit_number_is_included_when_available(self):
        """Comp includes unit field when source row has a unit identifier."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "unit_number": "515"}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="821 Folsom St #515", city="San Francisco", state="CA",
                zip_code="94107", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert comps[0]["unit"] == "515"


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
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

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
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

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
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
                subject_sqft=subject_sqft,
            )
        comps = result["comps"]

        assert len(comps) == 1


# ---------------------------------------------------------------------------
# property type filter
# ---------------------------------------------------------------------------

class TestPropertyTypeFilter:
    async def test_filters_comps_by_subject_property_type(self):
        """When subject type is condo, non-condo comps are excluded."""
        from agent.tools.comps import fetch_comps

        condo = {**BASE_COMP_ROW, "street": "1 Condo Way", "style": "CONDO"}
        sfh = {**BASE_COMP_ROW, "street": "2 House Way", "style": "SINGLE_FAMILY"}
        df = _make_df([condo, sfh])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="450 Sanchez St",
                city="San Francisco",
                state="CA",
                zip_code="94114",
                subject_lat=SF_LAT,
                subject_lon=SF_LON,
                subject_property_type="CONDO",
            )
        comps = result["comps"]

        assert len(comps) == 1
        assert comps[0]["address"] == "1 Condo Way"

    async def test_no_property_type_filter_when_subject_type_missing(self):
        """When no subject property type is provided, both condo and SFH remain."""
        from agent.tools.comps import fetch_comps

        condo = {**BASE_COMP_ROW, "street": "1 Condo Way", "style": "CONDO"}
        sfh = {**BASE_COMP_ROW, "street": "2 House Way", "style": "SINGLE_FAMILY"}
        df = _make_df([condo, sfh])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="450 Sanchez St",
                city="San Francisco",
                state="CA",
                zip_code="94114",
                subject_lat=SF_LAT,
                subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert len(comps) == 2


class TestSubjectResaleFilter:
    async def test_excludes_same_address_and_unit_sold_within_last_30_days(self):
        """Ignore comp when it is the same unit and sold within the past month."""
        from agent.tools.comps import fetch_comps

        recent_sale_date = dt.date.today() - dt.timedelta(days=10)
        same_unit_recent = {
            **BASE_COMP_ROW,
            "street": "821 Folsom St",
            "unit_number": "515",
            "last_sold_date": recent_sale_date,
        }
        different_unit_recent = {
            **BASE_COMP_ROW,
            "street": "821 Folsom St",
            "unit_number": "516",
            "last_sold_date": recent_sale_date,
        }
        df = _make_df([same_unit_recent, different_unit_recent])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="821 Folsom St #515",
                city="San Francisco",
                state="CA",
                zip_code="94107",
                subject_lat=SF_LAT,
                subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert len(comps) == 1
        assert comps[0]["unit"] == "516"

    async def test_excludes_same_address_without_unit_sold_within_last_30_days(self):
        """Ignore comp when same address has no unit and sold within the past month."""
        from agent.tools.comps import fetch_comps

        recent_sale_date = dt.date.today() - dt.timedelta(days=7)
        same_house_recent = {
            **BASE_COMP_ROW,
            "street": "400 Hearst Ave",
            "unit_number": None,
            "last_sold_date": recent_sale_date,
        }
        other_house_recent = {
            **BASE_COMP_ROW,
            "street": "402 Hearst Ave",
            "unit_number": None,
            "last_sold_date": recent_sale_date,
        }
        df = _make_df([same_house_recent, other_house_recent])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="400 Hearst Ave, San Francisco, CA 94112",
                city="San Francisco",
                state="CA",
                zip_code="94112",
                subject_lat=SF_LAT,
                subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert len(comps) == 1
        assert comps[0]["address"] == "402 Hearst Ave"

    async def test_comps_outside_25pct_sqft_excluded(self):
        """Comp outside ±25% of subject sqft is filtered out."""
        from agent.tools.comps import fetch_comps

        subject_sqft = 1000
        row = {**BASE_COMP_ROW, "sqft": 2000}  # +100% — outside 25%
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
                subject_sqft=subject_sqft,
            )
        comps = result["comps"]

        assert len(comps) == 0

    async def test_sqft_filter_skipped_when_subject_sqft_none(self):
        """If subject_sqft is not provided, sqft filter is not applied."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "sqft": 9999}
        df = _make_df([row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
                subject_sqft=None,
            )
        comps = result["comps"]

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

            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert len(comps) == 1
        assert comps[0]["sqft"] == 1650


# ---------------------------------------------------------------------------
# Validation mode: subject sale detection
# ---------------------------------------------------------------------------

class TestSubjectSaleDetection:
    async def test_returns_dict_shape(self):
        """fetch_comps returns a dict with 'comps' and 'subject_sale' keys."""
        from agent.tools.comps import fetch_comps

        df = _make_df([BASE_COMP_ROW])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert isinstance(result, dict)
        assert set(result.keys()) == {"comps", "subject_sale"}

    async def test_subject_sale_captured_within_180_days(self):
        """When the subject property appears in comps with a sale within 180 days,
        subject_sale is populated with sold_price and sold_date."""
        from agent.tools.comps import fetch_comps

        sale_date = dt.date.today() - dt.timedelta(days=90)
        subject_row = {
            **BASE_COMP_ROW,
            "street": "400 Hearst Ave",
            "unit_number": None,
            "sold_price": 1_350_000,
            "list_price": 1_200_000,
            "last_sold_date": sale_date,
        }
        other_comp = {**BASE_COMP_ROW, "street": "402 Hearst Ave", "unit_number": None}
        df = _make_df([subject_row, other_comp])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="400 Hearst Ave, San Francisco, CA",
                city="San Francisco", state="CA",
                zip_code="94112", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert result["subject_sale"] is not None
        assert result["subject_sale"]["sold_price"] == pytest.approx(1_350_000)
        assert result["subject_sale"]["sold_date"] == sale_date.isoformat()

    async def test_subject_sale_excluded_from_comps_list(self):
        """The subject property's own sale row must NOT appear in the comps list."""
        from agent.tools.comps import fetch_comps

        sale_date = dt.date.today() - dt.timedelta(days=90)
        subject_row = {
            **BASE_COMP_ROW,
            "street": "400 Hearst Ave",
            "unit_number": None,
            "last_sold_date": sale_date,
        }
        other_comp = {**BASE_COMP_ROW, "street": "402 Hearst Ave", "unit_number": None}
        df = _make_df([subject_row, other_comp])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="400 Hearst Ave, San Francisco, CA",
                city="San Francisco", state="CA",
                zip_code="94112", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        addresses = [c["address"] for c in result["comps"]]
        assert "400 Hearst Ave" not in addresses
        assert "402 Hearst Ave" in addresses

    async def test_subject_sale_none_when_beyond_180_days(self):
        """When the subject property sold more than 180 days ago, subject_sale is None."""
        from agent.tools.comps import fetch_comps

        old_sale_date = dt.date.today() - dt.timedelta(days=181)
        subject_row = {
            **BASE_COMP_ROW,
            "street": "400 Hearst Ave",
            "unit_number": None,
            "last_sold_date": old_sale_date,
        }
        df = _make_df([subject_row])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="400 Hearst Ave, San Francisco, CA",
                city="San Francisco", state="CA",
                zip_code="94112", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert result["subject_sale"] is None

    async def test_subject_sale_none_when_no_self_sale_in_comps(self):
        """When no comp matches the subject address, subject_sale is None."""
        from agent.tools.comps import fetch_comps

        df = _make_df([BASE_COMP_ROW])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )

        assert result["subject_sale"] is None

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

            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

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

            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert mock_client.get.call_count == 2
        assert all(c["sqft"] == 1500 for c in comps)

    async def test_price_per_sqft_computed_after_rentcast_sqft_fill(self):
        """price_per_sqft is computed when sqft comes from RentCast."""
        from agent.tools.comps import fetch_comps

        row = {**BASE_COMP_ROW, "sqft": None}  # sold_price=1_100_000
        df = _make_df([row])

        with patch.dict(os.environ, {"RENTCAST_API_KEY": "test-key"}), \
             patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
             patch("agent.tools.comps.httpx.AsyncClient") as mock_cls:

            mock_thread.return_value = df
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_rentcast_avm_mock(sqft=1100)

            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert comps[0]["sqft"] == 1100
        assert comps[0]["price_per_sqft"] == pytest.approx(1000.0)

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

            result = await fetch_comps(
                address="450 Sanchez St", city="San Francisco", state="CA",
                zip_code="94114", subject_lat=SF_LAT, subject_lon=SF_LON,
            )
        comps = result["comps"]

        assert comps[0]["sqft"] is None
