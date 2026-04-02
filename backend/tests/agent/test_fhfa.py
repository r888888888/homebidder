"""
Tests for fhfa.py — fetch_fhfa_hpi.
"""
import io
import os
import time
import zipfile
from unittest.mock import AsyncMock, patch

import pytest

from agent.tools.fhfa import (
    _compute_hpi_stats,
    _parse_hpi_csv,
    fetch_fhfa_hpi,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hpi_csv(rows: list[dict]) -> str:
    """Build a minimal CSV matching the FHFA ZIP-level HPI format."""
    lines = ["zip_code,year,annual_chg"]
    for r in rows:
        lines.append(f"{r['zip_code']},{r['year']},{r['annual_chg']}")
    return "\n".join(lines)


def _make_zipped_csv(csv_text: str, filename: str = "HPI_AT_BDL_ZIP5.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, csv_text)
    return buf.getvalue()


SAMPLE_ROWS = [
    {"zip_code": "94114", "year": "2024", "annual_chg": "4.2"},
    {"zip_code": "94114", "year": "2023", "annual_chg": "-1.1"},
    {"zip_code": "94114", "year": "2022", "annual_chg": "8.5"},
    {"zip_code": "94114", "year": "2021", "annual_chg": "12.3"},
    # Different ZIP
    {"zip_code": "94110", "year": "2024", "annual_chg": "3.0"},
]


# ---------------------------------------------------------------------------
# _parse_hpi_csv
# ---------------------------------------------------------------------------

class TestParseHpiCsv:
    def test_returns_rows_for_matching_zip(self):
        csv_text = _make_hpi_csv(SAMPLE_ROWS)
        rows = _parse_hpi_csv(csv_text, "94114")
        assert len(rows) == 4
        assert all(r["zip_code"] == "94114" for r in rows)

    def test_returns_empty_for_unknown_zip(self):
        csv_text = _make_hpi_csv(SAMPLE_ROWS)
        rows = _parse_hpi_csv(csv_text, "99999")
        assert rows == []

    def test_rows_sorted_newest_first(self):
        csv_text = _make_hpi_csv(SAMPLE_ROWS)
        rows = _parse_hpi_csv(csv_text, "94114")
        years = [r["year"] for r in rows]
        assert years == sorted(years, reverse=True)

    def test_annual_chg_is_float(self):
        csv_text = _make_hpi_csv(SAMPLE_ROWS)
        rows = _parse_hpi_csv(csv_text, "94114")
        assert isinstance(rows[0]["annual_chg"], float)


# ---------------------------------------------------------------------------
# _compute_hpi_stats
# ---------------------------------------------------------------------------

class TestComputeHpiStats:
    def test_yoy_is_most_recent_years_change(self):
        rows = [
            {"zip_code": "94114", "year": "2024", "annual_chg": 4.2},
            {"zip_code": "94114", "year": "2023", "annual_chg": -1.1},
            {"zip_code": "94114", "year": "2022", "annual_chg": 8.5},
        ]
        stats = _compute_hpi_stats(rows)
        assert stats["yoy_change_pct"] == pytest.approx(4.2)

    def test_three_yr_is_average_of_last_three_years(self):
        rows = [
            {"zip_code": "94114", "year": "2024", "annual_chg": 4.2},
            {"zip_code": "94114", "year": "2023", "annual_chg": -1.1},
            {"zip_code": "94114", "year": "2022", "annual_chg": 8.5},
        ]
        stats = _compute_hpi_stats(rows)
        expected = (4.2 + -1.1 + 8.5) / 3
        assert stats["three_yr_avg_chg_pct"] == pytest.approx(expected, rel=0.01)

    def test_trend_appreciating_when_yoy_positive(self):
        rows = [{"zip_code": "94114", "year": "2024", "annual_chg": 5.0}]
        stats = _compute_hpi_stats(rows)
        assert stats["hpi_trend"] == "appreciating"

    def test_trend_depreciating_when_yoy_negative(self):
        rows = [{"zip_code": "94114", "year": "2024", "annual_chg": -3.0}]
        stats = _compute_hpi_stats(rows)
        assert stats["hpi_trend"] == "depreciating"

    def test_trend_flat_when_near_zero(self):
        rows = [{"zip_code": "94114", "year": "2024", "annual_chg": 0.8}]
        stats = _compute_hpi_stats(rows)
        assert stats["hpi_trend"] == "flat"

    def test_as_of_year_is_most_recent(self):
        rows = [
            {"zip_code": "94114", "year": "2024", "annual_chg": 4.0},
            {"zip_code": "94114", "year": "2023", "annual_chg": 2.0},
        ]
        stats = _compute_hpi_stats(rows)
        assert stats["as_of_year"] == 2024


# ---------------------------------------------------------------------------
# fetch_fhfa_hpi (integration, mocked HTTP + cache)
# ---------------------------------------------------------------------------

class TestFetchFhfaHpi:
    @pytest.fixture()
    def mock_zip_bytes(self):
        csv_text = _make_hpi_csv(SAMPLE_ROWS)
        return _make_zipped_csv(csv_text)

    async def test_returns_hpi_stats_for_zip(self, mock_zip_bytes, tmp_path):
        cache = str(tmp_path / "fhfa.zip")
        with patch("agent.tools.fhfa.CACHE_PATH", cache), \
             patch("agent.tools.fhfa._download_hpi", AsyncMock(return_value=mock_zip_bytes)):
            result = await fetch_fhfa_hpi("94114")

        assert "yoy_change_pct" in result
        assert "hpi_trend" in result
        assert "as_of_year" in result

    async def test_returns_error_for_unknown_zip(self, mock_zip_bytes, tmp_path):
        cache = str(tmp_path / "fhfa.zip")
        with patch("agent.tools.fhfa.CACHE_PATH", cache), \
             patch("agent.tools.fhfa._download_hpi", AsyncMock(return_value=mock_zip_bytes)):
            result = await fetch_fhfa_hpi("00000")

        assert "error" in result

    async def test_uses_cache_on_second_call(self, mock_zip_bytes, tmp_path):
        cache = str(tmp_path / "fhfa.zip")
        download_mock = AsyncMock(return_value=mock_zip_bytes)
        with patch("agent.tools.fhfa.CACHE_PATH", cache), \
             patch("agent.tools.fhfa._download_hpi", download_mock):
            await fetch_fhfa_hpi("94114")
            await fetch_fhfa_hpi("94114")

        assert download_mock.call_count == 1

    async def test_re_downloads_when_cache_stale(self, mock_zip_bytes, tmp_path):
        cache = str(tmp_path / "fhfa.zip")
        with open(cache, "wb") as f:
            f.write(mock_zip_bytes)
        stale_mtime = time.time() - 8 * 86400  # 8 days ago
        os.utime(cache, (stale_mtime, stale_mtime))

        download_mock = AsyncMock(return_value=mock_zip_bytes)
        with patch("agent.tools.fhfa.CACHE_PATH", cache), \
             patch("agent.tools.fhfa._download_hpi", download_mock):
            await fetch_fhfa_hpi("94114")

        assert download_mock.call_count == 1
