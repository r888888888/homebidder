"""
Tests for zillow_hpi.py — fetch_zillow_hpi.
"""
import io
import os
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from agent.tools.zillow_hpi import (
    _compute_annual_changes,
    _parse_zhvi_csv,
    fetch_zillow_hpi,
    prefetch_zillow_zhvi,
)


def _make_csv_bytes(zip_code: str, yearly_values: dict[int, float]) -> bytes:
    """Build a minimal Zillow ZHVI CSV with one ZIP row and yearly Dec values."""
    date_cols = {f"{yr}-12-31": val for yr, val in yearly_values.items()}
    row = {
        "RegionID": "99999",
        "SizeRank": "100",
        "RegionName": zip_code,
        "RegionType": "zip",
        "StateName": "California",
        "State": "CA",
        "City": "San Francisco",
        "Metro": "San Francisco-Oakland-Berkeley, CA",
        "CountyName": "San Francisco County",
        **date_cols,
    }
    df = pd.DataFrame([row])
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


SAMPLE_VALUES = {
    2020: 800_000.0,
    2021: 840_000.0,   # +5.0%
    2022: 823_200.0,   # -2.0%
    2023: 847_896.0,   # +3.0%
    2024: 873_333.0,   # +3.0%
}


class TestComputeAnnualChanges:
    def test_annual_change_matches_year_over_year(self):
        changes = _compute_annual_changes(SAMPLE_VALUES)
        # Most recent year first; 2024 vs 2023 = ~3.0%
        assert changes[0]["year"] == "2024"
        assert changes[0]["annual_chg"] == pytest.approx(3.0, abs=0.1)

    def test_sorted_newest_first(self):
        changes = _compute_annual_changes(SAMPLE_VALUES)
        years = [int(c["year"]) for c in changes]
        assert years == sorted(years, reverse=True)

    def test_first_year_excluded(self):
        changes = _compute_annual_changes(SAMPLE_VALUES)
        # 2020 has no prior year so no change; 4 changes for 5 years
        assert len(changes) == 4

    def test_single_year_returns_empty(self):
        assert _compute_annual_changes({2024: 1_000_000.0}) == []


class TestParseZhviCsv:
    def test_returns_rows_for_matching_zip(self):
        csv_bytes = _make_csv_bytes("94109", SAMPLE_VALUES)
        rows = _parse_zhvi_csv(csv_bytes, "94109")
        assert len(rows) == 4  # 5 years → 4 annual changes

    def test_returns_empty_for_missing_zip(self):
        csv_bytes = _make_csv_bytes("94109", SAMPLE_VALUES)
        rows = _parse_zhvi_csv(csv_bytes, "94999")
        assert rows == []

    def test_rows_are_newest_first(self):
        csv_bytes = _make_csv_bytes("94109", SAMPLE_VALUES)
        rows = _parse_zhvi_csv(csv_bytes, "94109")
        assert rows[0]["year"] == "2024"


class TestFetchZillowHpi:
    async def test_returns_error_when_cache_missing(self, tmp_path):
        cache = str(tmp_path / "zillow.csv")
        with patch("agent.tools.zillow_hpi.CACHE_PATH", cache):
            result = await fetch_zillow_hpi("94109")
        assert "error" in result
        assert result["zip_code"] == "94109"

    async def test_returns_stats_for_known_zip(self, tmp_path):
        cache = str(tmp_path / "zillow.csv")
        csv_bytes = _make_csv_bytes("94109", SAMPLE_VALUES)
        with open(cache, "wb") as f:
            f.write(csv_bytes)
        with patch("agent.tools.zillow_hpi.CACHE_PATH", cache):
            result = await fetch_zillow_hpi("94109")
        assert "yoy_change_pct" in result
        assert "three_yr_avg_chg_pct" in result
        assert "five_yr_avg_chg_pct" in result
        assert "hpi_trend" in result
        assert result["source"] == "Zillow ZHVI"

    async def test_five_yr_avg_correct_value(self, tmp_path):
        """SAMPLE_VALUES has 4 annual changes (2021-2024); 5yr avg uses all 4."""
        cache = str(tmp_path / "zillow.csv")
        csv_bytes = _make_csv_bytes("94109", SAMPLE_VALUES)
        with open(cache, "wb") as f:
            f.write(csv_bytes)
        with patch("agent.tools.zillow_hpi.CACHE_PATH", cache):
            result = await fetch_zillow_hpi("94109")
        # 2021: +5.0, 2022: -2.0, 2023: +3.0, 2024: +3.0 → avg = 2.25
        assert result["five_yr_avg_chg_pct"] == pytest.approx(2.25, abs=0.1)

    async def test_returns_error_for_zip_not_in_dataset(self, tmp_path):
        cache = str(tmp_path / "zillow.csv")
        csv_bytes = _make_csv_bytes("94109", SAMPLE_VALUES)
        with open(cache, "wb") as f:
            f.write(csv_bytes)
        with patch("agent.tools.zillow_hpi.CACHE_PATH", cache):
            result = await fetch_zillow_hpi("99999")
        assert "error" in result

    async def test_trend_appreciating_when_yoy_above_threshold(self, tmp_path):
        cache = str(tmp_path / "zillow.csv")
        # Strong appreciation
        values = {2020: 500_000.0, 2021: 600_000.0, 2022: 720_000.0}
        csv_bytes = _make_csv_bytes("94109", values)
        with open(cache, "wb") as f:
            f.write(csv_bytes)
        with patch("agent.tools.zillow_hpi.CACHE_PATH", cache):
            result = await fetch_zillow_hpi("94109")
        assert result["hpi_trend"] == "appreciating"


class TestPrefetchZillow:
    async def test_downloads_and_writes_file(self, tmp_path):
        cache = str(tmp_path / "zillow.csv")
        csv_bytes = _make_csv_bytes("94109", SAMPLE_VALUES)
        dl = AsyncMock(return_value=csv_bytes)
        with patch("agent.tools.zillow_hpi.CACHE_PATH", cache), \
             patch("agent.tools.zillow_hpi._download_zhvi", dl):
            written = await prefetch_zillow_zhvi(force=True)
        assert written is True
        assert os.path.exists(cache)
        dl.assert_awaited_once()

    async def test_skips_download_when_cache_fresh(self, tmp_path):
        cache = str(tmp_path / "zillow.csv")
        csv_bytes = _make_csv_bytes("94109", SAMPLE_VALUES)
        with open(cache, "wb") as f:
            f.write(csv_bytes)
        dl = AsyncMock()
        with patch("agent.tools.zillow_hpi.CACHE_PATH", cache), \
             patch("agent.tools.zillow_hpi._cache_valid", return_value=True), \
             patch("agent.tools.zillow_hpi._download_zhvi", dl):
            written = await prefetch_zillow_zhvi(force=False)
        assert written is False
        dl.assert_not_awaited()
