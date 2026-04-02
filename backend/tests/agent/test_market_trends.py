"""
Tests for market_trends.py — fetch_market_trends.
"""
import gzip
import io
import os
import time
from unittest.mock import AsyncMock, patch

import pytest

from agent.tools.market_trends import (
    _compute_trend,
    _parse_tsv_for_zip,
    fetch_market_trends,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gzipped_tsv(rows: list[dict]) -> bytes:
    """Build an in-memory gzip TSV matching Redfin's market tracker format."""
    header = (
        "region_type\tregion\tperiod_end"
        "\tmedian_sale_price\thomes_sold\tmedian_dom"
        "\tmonths_of_supply\tsold_above_list\tprice_drops"
    )
    lines = [header]
    for r in rows:
        lines.append(
            f"{r.get('region_type','zip code')}\t{r['region']}\t{r['period_end']}"
            f"\t{r.get('median_sale_price','')}\t{r.get('homes_sold','')}"
            f"\t{r.get('median_dom','')}\t{r.get('months_of_supply','')}"
            f"\t{r.get('sold_above_list','')}\t{r.get('price_drops','')}"
        )
    content = "\n".join(lines).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(content)
    return buf.getvalue()


SAMPLE_ROWS = [
    {"region": "94114", "period_end": "2025-10-31", "median_sale_price": "1250000",
     "homes_sold": "45", "median_dom": "12", "months_of_supply": "1.2",
     "sold_above_list": "78.5", "price_drops": "5.2"},
    {"region": "94114", "period_end": "2025-09-30", "median_sale_price": "1200000",
     "homes_sold": "50", "median_dom": "14", "months_of_supply": "1.3",
     "sold_above_list": "72.1", "price_drops": "4.8"},
    {"region": "94114", "period_end": "2025-08-31", "median_sale_price": "1180000",
     "homes_sold": "52", "median_dom": "16", "months_of_supply": "1.4",
     "sold_above_list": "68.9", "price_drops": "5.1"},
    # Different ZIP — must be filtered out
    {"region": "94110", "period_end": "2025-10-31", "median_sale_price": "980000",
     "homes_sold": "60", "median_dom": "20", "months_of_supply": "1.8",
     "sold_above_list": "55.0", "price_drops": "3.1"},
]


# ---------------------------------------------------------------------------
# _parse_tsv_for_zip
# ---------------------------------------------------------------------------

class TestParseTsvForZip:
    def test_returns_matching_rows_only(self):
        raw = _make_gzipped_tsv(SAMPLE_ROWS)
        result = _parse_tsv_for_zip(raw, "94114")
        assert all(True for _ in result)  # no assertion yet — just non-empty
        assert len(result) == 3

    def test_filters_out_other_zips(self):
        raw = _make_gzipped_tsv(SAMPLE_ROWS)
        result = _parse_tsv_for_zip(raw, "94110")
        assert len(result) == 1

    def test_returns_empty_for_unknown_zip(self):
        raw = _make_gzipped_tsv(SAMPLE_ROWS)
        result = _parse_tsv_for_zip(raw, "99999")
        assert result == []

    def test_rows_sorted_newest_first(self):
        raw = _make_gzipped_tsv(SAMPLE_ROWS)
        result = _parse_tsv_for_zip(raw, "94114")
        dates = [r["period_end"] for r in result]
        assert dates == sorted(dates, reverse=True)

    def test_limits_to_six_months(self):
        rows = [
            {"region": "94114", "period_end": f"2025-{str(m).zfill(2)}-28",
             "median_sale_price": str(1_000_000 + m * 10_000),
             "homes_sold": "40", "median_dom": "15", "months_of_supply": "1.5",
             "sold_above_list": "70", "price_drops": "4"}
            for m in range(1, 10)  # 9 months
        ]
        raw = _make_gzipped_tsv(rows)
        result = _parse_tsv_for_zip(raw, "94114")
        assert len(result) == 6

    def test_numeric_fields_are_floats(self):
        raw = _make_gzipped_tsv(SAMPLE_ROWS)
        result = _parse_tsv_for_zip(raw, "94114")
        row = result[0]
        assert isinstance(row["median_sale_price"], float)
        assert isinstance(row["homes_sold"], float)
        assert isinstance(row["median_dom"], float)

    def test_missing_optional_field_is_none(self):
        rows = [{"region": "94114", "period_end": "2025-10-31",
                 "median_sale_price": "1200000", "homes_sold": "",
                 "median_dom": "", "months_of_supply": "",
                 "sold_above_list": "", "price_drops": ""}]
        raw = _make_gzipped_tsv(rows)
        result = _parse_tsv_for_zip(raw, "94114")
        assert result[0]["homes_sold"] is None


# ---------------------------------------------------------------------------
# _compute_trend
# ---------------------------------------------------------------------------

class TestComputeTrend:
    def test_appreciating_when_prices_rise_significantly(self):
        months = [
            {"median_sale_price": 1_300_000},  # newest
            {"median_sale_price": 1_200_000},
            {"median_sale_price": 1_100_000},  # oldest
        ]
        assert _compute_trend(months) == "appreciating"

    def test_depreciating_when_prices_fall_significantly(self):
        months = [
            {"median_sale_price": 900_000},
            {"median_sale_price": 1_000_000},
            {"median_sale_price": 1_100_000},
        ]
        assert _compute_trend(months) == "depreciating"

    def test_flat_when_minimal_change(self):
        months = [{"median_sale_price": 1_010_000}, {"median_sale_price": 1_000_000}]
        assert _compute_trend(months) == "flat"

    def test_unknown_when_fewer_than_two_prices(self):
        assert _compute_trend([{"median_sale_price": None}]) == "unknown"
        assert _compute_trend([]) == "unknown"


# ---------------------------------------------------------------------------
# fetch_market_trends (integration, mocked HTTP + cache)
# ---------------------------------------------------------------------------

class TestFetchMarketTrends:
    @pytest.fixture()
    def mock_tsv_bytes(self):
        return _make_gzipped_tsv(SAMPLE_ROWS)

    async def test_returns_months_and_trend(self, mock_tsv_bytes, tmp_path):
        cache = str(tmp_path / "redfin.tsv.gz")
        with patch("agent.tools.market_trends.CACHE_PATH", cache), \
             patch("agent.tools.market_trends._download_tsv", AsyncMock(return_value=mock_tsv_bytes)):
            result = await fetch_market_trends("94114")

        assert "months" in result
        assert "trend" in result
        assert len(result["months"]) == 3
        assert result["trend"] in ("appreciating", "depreciating", "flat", "unknown")

    async def test_returns_error_for_unknown_zip(self, mock_tsv_bytes, tmp_path):
        cache = str(tmp_path / "redfin.tsv.gz")
        with patch("agent.tools.market_trends.CACHE_PATH", cache), \
             patch("agent.tools.market_trends._download_tsv", AsyncMock(return_value=mock_tsv_bytes)):
            result = await fetch_market_trends("00000")

        assert "error" in result

    async def test_uses_cache_on_second_call(self, mock_tsv_bytes, tmp_path):
        cache = str(tmp_path / "redfin.tsv.gz")
        download_mock = AsyncMock(return_value=mock_tsv_bytes)
        with patch("agent.tools.market_trends.CACHE_PATH", cache), \
             patch("agent.tools.market_trends._download_tsv", download_mock):
            await fetch_market_trends("94114")
            await fetch_market_trends("94114")

        assert download_mock.call_count == 1  # only downloaded once

    async def test_re_downloads_when_cache_stale(self, mock_tsv_bytes, tmp_path):
        cache = str(tmp_path / "redfin.tsv.gz")
        # Write stale cache (mtime > 24h ago)
        with open(cache, "wb") as f:
            f.write(mock_tsv_bytes)
        stale_mtime = time.time() - 90_000  # 25 hours ago
        os.utime(cache, (stale_mtime, stale_mtime))

        download_mock = AsyncMock(return_value=mock_tsv_bytes)
        with patch("agent.tools.market_trends.CACHE_PATH", cache), \
             patch("agent.tools.market_trends._download_tsv", download_mock):
            await fetch_market_trends("94114")

        assert download_mock.call_count == 1
