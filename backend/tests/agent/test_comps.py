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
# Bedroom filter fallback
# ---------------------------------------------------------------------------

class TestBedroomFilterFallback:
    async def test_falls_back_without_bedrooms_when_strict_filter_returns_zero(self):
        """Subject with anomalous BR/sqft (e.g. 6 BR / 1988 sqft) — every comp at the
        same BR count exceeds the sqft tolerance. Should retry without the bedroom
        filter and return sqft-matching comps."""
        from agent.tools.comps import fetch_comps

        # Subject: 6 BR, 1988 sqft, SFH. ±25% sqft → 1491–2485.
        # Within ±1 BR (5–7): only one row, but it's 2658 sqft (over the tolerance).
        too_large_same_br = {
            **BASE_COMP_ROW, "street": "2479 31st Ave", "beds": 5, "sqft": 2658,
            "style": "SINGLE_FAMILY",
        }
        # Lower BR but sqft-matching SFH.
        sqft_match_lower_br = {
            **BASE_COMP_ROW, "street": "2100 34th Ave", "beds": 4, "sqft": 1900,
            "style": "SINGLE_FAMILY",
        }
        df = _make_df([too_large_same_br, sqft_match_lower_br])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="1950 45TH AVE",
                city="San Francisco",
                state="CA",
                zip_code="94116",
                subject_lat=SF_LAT,
                subject_lon=SF_LON,
                subject_sqft=1988,
                subject_property_type="SINGLE_FAMILY",
                bedrooms=6,
            )
        comps = result["comps"]

        assert any(c["address"] == "2100 34th Ave" for c in comps), (
            f"Expected 2100 34th Ave (sqft-match, lower BR) to be returned via fallback, got {[c['address'] for c in comps]}"
        )

    async def test_strict_filter_kept_when_it_returns_results(self):
        """When the strict bedroom filter returns at least one comp, the fallback is
        not triggered and lower-BR rows are still excluded."""
        from agent.tools.comps import fetch_comps

        same_br_match = {
            **BASE_COMP_ROW, "street": "100 Same BR Way", "beds": 6, "sqft": 1900,
            "style": "SINGLE_FAMILY",
        }
        lower_br_match = {
            **BASE_COMP_ROW, "street": "200 Lower BR Way", "beds": 3, "sqft": 1800,
            "style": "SINGLE_FAMILY",
        }
        df = _make_df([same_br_match, lower_br_match])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="1950 45TH AVE",
                city="San Francisco",
                state="CA",
                zip_code="94116",
                subject_lat=SF_LAT,
                subject_lon=SF_LON,
                subject_sqft=1988,
                subject_property_type="SINGLE_FAMILY",
                bedrooms=6,
            )
        comps = result["comps"]

        addresses = [c["address"] for c in comps]
        assert "100 Same BR Way" in addresses
        assert "200 Lower BR Way" not in addresses


# ---------------------------------------------------------------------------
# Multi-family "multi" bucket normalization
# ---------------------------------------------------------------------------

class TestNormalizePropertyTypeMulti:
    @pytest.mark.parametrize("raw_type,expected", [
        ("DUPLEX",       "multi"),
        ("TRIPLEX",      "multi"),
        ("MULTI_FAMILY", "multi"),
        ("multi-family", "multi"),
        ("2_FAMILY",     "multi"),
        ("3_FAMILY",     "multi"),
    ])
    def test_multifamily_types_normalize_to_multi(self, raw_type, expected):
        from agent.tools.comps import _normalize_property_type
        assert _normalize_property_type(raw_type) == expected

    def test_sfh_unaffected_by_multi_bucket_addition(self):
        from agent.tools.comps import _normalize_property_type
        assert _normalize_property_type("SINGLE_FAMILY") == "sfh"

    def test_condo_unaffected_by_multi_bucket_addition(self):
        from agent.tools.comps import _normalize_property_type
        assert _normalize_property_type("CONDO") == "condo"

    def test_redfin_filter_returns_code_6_for_multi(self):
        from agent.tools.comps import _redfin_sf_filter_value
        assert _redfin_sf_filter_value("multi") == "6"

    def test_redfin_filter_all_types_when_unrecognized(self):
        from agent.tools.comps import _redfin_sf_filter_value
        assert _redfin_sf_filter_value(None) == "1,2,3,6,13"


class TestMultiPropertyTypeFilter:
    async def test_duplex_subject_only_gets_duplex_comps(self):
        """When subject type is DUPLEX, non-multi comps are filtered out."""
        from agent.tools.comps import fetch_comps

        duplex_comp = {**BASE_COMP_ROW, "street": "1 Duplex St", "style": "DUPLEX"}
        sfh_comp = {**BASE_COMP_ROW, "street": "2 House St", "style": "SINGLE_FAMILY"}
        df = _make_df([duplex_comp, sfh_comp])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="300 Multi Ave",
                city="San Francisco",
                state="CA",
                zip_code="94110",
                subject_lat=SF_LAT,
                subject_lon=SF_LON,
                subject_property_type="DUPLEX",
            )
        comps = result["comps"]
        assert len(comps) == 1
        assert comps[0]["address"] == "1 Duplex St"

    async def test_triplex_comps_match_duplex_subject(self):
        """TRIPLEX comps (also normalized to 'multi') are included for a DUPLEX subject."""
        from agent.tools.comps import fetch_comps

        triplex_comp = {**BASE_COMP_ROW, "street": "5 Triplex Rd", "style": "TRIPLEX"}
        df = _make_df([triplex_comp])

        with patch("agent.tools.comps.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = df
            result = await fetch_comps(
                address="300 Multi Ave",
                city="San Francisco",
                state="CA",
                zip_code="94110",
                subject_lat=SF_LAT,
                subject_lon=SF_LON,
                subject_property_type="DUPLEX",
            )
        comps = result["comps"]
        assert len(comps) == 1
        assert comps[0]["address"] == "5 Triplex Rd"

# ---------------------------------------------------------------------------