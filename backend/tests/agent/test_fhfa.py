"""
Tests for fhfa.py — fetch_fhfa_hpi.
"""
import io
import os
from unittest.mock import AsyncMock, patch

import openpyxl
import pytest

from agent.tools.fhfa import (
    _compute_hpi_stats,
    _parse_hpi_xlsx,
    fetch_fhfa_hpi,
    prefetch_fhfa_hpi_dataset,
)


def _make_xlsx_bytes(rows: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(5):
        ws.append([""])
    ws.append(["Five-Digit ZIP Code", "Year", "Annual Change (%)"])
    for r in rows:
        ws.append([int(r["zip_code"]), int(r["year"]), float(r["annual_chg"])])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


SAMPLE_ROWS = [
    {"zip_code": "94114", "year": "2024", "annual_chg": "4.2"},
    {"zip_code": "94114", "year": "2023", "annual_chg": "-1.1"},
    {"zip_code": "94114", "year": "2022", "annual_chg": "8.5"},
    {"zip_code": "94110", "year": "2024", "annual_chg": "3.0"},
]


class TestParseHpiXlsx:
    def test_returns_rows_for_matching_zip(self, tmp_path):
        cache = tmp_path / "fhfa.xlsx"
        cache.write_bytes(_make_xlsx_bytes(SAMPLE_ROWS))
        rows = _parse_hpi_xlsx(str(cache), "94114")
        assert len(rows) == 3


class TestComputeHpiStats:
    def test_yoy_is_most_recent_years_change(self):
        rows = [
            {"zip_code": "94114", "year": "2024", "annual_chg": 4.2},
            {"zip_code": "94114", "year": "2023", "annual_chg": -1.1},
            {"zip_code": "94114", "year": "2022", "annual_chg": 8.5},
        ]
        stats = _compute_hpi_stats(rows)
        assert stats["yoy_change_pct"] == pytest.approx(4.2)

    def test_five_yr_avg_averages_up_to_five_rows(self):
        rows = [
            {"zip_code": "94114", "year": "2024", "annual_chg": 4.0},
            {"zip_code": "94114", "year": "2023", "annual_chg": 2.0},
            {"zip_code": "94114", "year": "2022", "annual_chg": 6.0},
            {"zip_code": "94114", "year": "2021", "annual_chg": 8.0},
            {"zip_code": "94114", "year": "2020", "annual_chg": 5.0},
            {"zip_code": "94114", "year": "2019", "annual_chg": 1.0},  # should be excluded
        ]
        stats = _compute_hpi_stats(rows)
        assert stats["five_yr_avg_chg_pct"] == pytest.approx((4.0 + 2.0 + 6.0 + 8.0 + 5.0) / 5, abs=0.01)

    def test_five_yr_avg_uses_all_rows_when_fewer_than_five(self):
        rows = [
            {"zip_code": "94114", "year": "2024", "annual_chg": 4.2},
            {"zip_code": "94114", "year": "2023", "annual_chg": -1.1},
            {"zip_code": "94114", "year": "2022", "annual_chg": 8.5},
        ]
        stats = _compute_hpi_stats(rows)
        assert stats["five_yr_avg_chg_pct"] == pytest.approx((4.2 + -1.1 + 8.5) / 3, abs=0.01)


class TestFetchFhfaHpi:
    @pytest.fixture()
    def mock_xlsx_bytes(self):
        return _make_xlsx_bytes(SAMPLE_ROWS)

    async def test_returns_error_when_cache_missing_and_never_downloads_in_request_path(self, tmp_path):
        cache = str(tmp_path / "fhfa.xlsx")
        with patch("agent.tools.fhfa.CACHE_PATH", cache), \
             patch("agent.tools.fhfa._download_hpi", AsyncMock(side_effect=AssertionError("should not download"))):
            result = await fetch_fhfa_hpi("94114")

        assert result == {
            "zip_code": "94114",
            "error": "FHFA HPI cache missing. Run prefetch_backend_data.py to download datasets.",
        }

    async def test_reads_prefetched_cache(self, mock_xlsx_bytes, tmp_path):
        cache = str(tmp_path / "fhfa.xlsx")
        with open(cache, "wb") as f:
            f.write(mock_xlsx_bytes)

        with patch("agent.tools.fhfa.CACHE_PATH", cache):
            result = await fetch_fhfa_hpi("94114")

        assert "yoy_change_pct" in result


    async def test_falls_back_to_zillow_when_zip_not_in_fhfa(self, mock_xlsx_bytes, tmp_path):
        cache = str(tmp_path / "fhfa.xlsx")
        with open(cache, "wb") as f:
            f.write(mock_xlsx_bytes)

        zillow_result = {
            "zip_code": "94109",
            "yoy_change_pct": 3.5,
            "three_yr_avg_chg_pct": 2.8,
            "hpi_trend": "appreciating",
            "as_of_year": 2024,
            "source": "Zillow ZHVI",
        }
        with patch("agent.tools.fhfa.CACHE_PATH", cache), \
             patch("agent.tools.fhfa.fetch_zillow_hpi", AsyncMock(return_value=zillow_result)) as mock_zillow:
            result = await fetch_fhfa_hpi("94109")

        mock_zillow.assert_awaited_once_with("94109")
        assert result == zillow_result

    async def test_no_zillow_fallback_when_fhfa_data_found(self, mock_xlsx_bytes, tmp_path):
        cache = str(tmp_path / "fhfa.xlsx")
        with open(cache, "wb") as f:
            f.write(mock_xlsx_bytes)

        with patch("agent.tools.fhfa.CACHE_PATH", cache), \
             patch("agent.tools.fhfa.fetch_zillow_hpi", AsyncMock()) as mock_zillow:
            result = await fetch_fhfa_hpi("94114")

        mock_zillow.assert_not_awaited()
        assert "yoy_change_pct" in result


class TestPrefetchFhfa:
    async def test_prefetch_downloads_and_writes_file(self, tmp_path):
        mock_xlsx_bytes = _make_xlsx_bytes(SAMPLE_ROWS)
        cache = str(tmp_path / "fhfa.xlsx")
        dl = AsyncMock(return_value=mock_xlsx_bytes)
        with patch("agent.tools.fhfa.CACHE_PATH", cache), \
             patch("agent.tools.fhfa._download_hpi", dl):
            written = await prefetch_fhfa_hpi_dataset(force=True)

        assert written is True
        assert os.path.exists(cache)
        dl.assert_awaited_once()
