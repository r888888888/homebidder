"""
Tests for market_trends.py — fetch_market_trends.
"""
import gzip
import io
import os
from unittest.mock import AsyncMock, patch

import pytest

from agent.tools.market_trends import (
    _compute_trend,
    _parse_tsv_for_zip,
    fetch_market_trends,
    prefetch_market_trends_dataset,
)


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
    {"region": "94110", "period_end": "2025-10-31", "median_sale_price": "980000",
     "homes_sold": "60", "median_dom": "20", "months_of_supply": "1.8",
     "sold_above_list": "55.0", "price_drops": "3.1"},
]


class TestParseTsvForZip:
    def test_returns_matching_rows_only(self):
        raw = _make_gzipped_tsv(SAMPLE_ROWS)
        result = _parse_tsv_for_zip(raw, "94114")
        assert len(result) == 3


class TestComputeTrend:
    def test_appreciating_when_prices_rise_significantly(self):
        months = [
            {"median_sale_price": 1_300_000},
            {"median_sale_price": 1_200_000},
            {"median_sale_price": 1_100_000},
        ]
        assert _compute_trend(months) == "appreciating"


class TestFetchMarketTrends:
    @pytest.fixture()
    def mock_tsv_bytes(self):
        return _make_gzipped_tsv(SAMPLE_ROWS)

    async def test_returns_error_when_cache_missing_and_never_downloads_in_request_path(self, tmp_path):
        cache = str(tmp_path / "redfin.tsv.gz")
        with patch("agent.tools.market_trends.CACHE_PATH", cache), \
             patch("agent.tools.market_trends._download_tsv", AsyncMock(side_effect=AssertionError("should not download"))):
            result = await fetch_market_trends("94114")

        assert result == {
            "zip_code": "94114",
            "error": "Market data cache missing. Run prefetch_backend_data.py to download datasets.",
        }

    async def test_reads_prefetched_cache(self, mock_tsv_bytes, tmp_path):
        cache = str(tmp_path / "redfin.tsv.gz")
        with open(cache, "wb") as f:
            f.write(mock_tsv_bytes)

        with patch("agent.tools.market_trends.CACHE_PATH", cache):
            result = await fetch_market_trends("94114")

        assert len(result["months"]) == 3


class TestPrefetchMarketTrends:
    async def test_prefetch_downloads_and_writes_file(self, tmp_path):
        mock_tsv_bytes = _make_gzipped_tsv(SAMPLE_ROWS)
        cache = str(tmp_path / "redfin.tsv.gz")
        dl = AsyncMock(return_value=mock_tsv_bytes)
        with patch("agent.tools.market_trends.CACHE_PATH", cache), \
             patch("agent.tools.market_trends._download_tsv", dl):
            written = await prefetch_market_trends_dataset(force=True)

        assert written is True
        assert os.path.exists(cache)
        dl.assert_awaited_once()
