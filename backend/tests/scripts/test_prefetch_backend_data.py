from unittest.mock import AsyncMock, patch
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.asyncio
async def test_prefetch_script_runs_all_prefetchers():
    from scripts.prefetch_backend_data import run_prefetch

    with patch("scripts.prefetch_backend_data.prefetch_market_trends_dataset", AsyncMock(return_value=True)) as market_mock, \
         patch("scripts.prefetch_backend_data.prefetch_fhfa_hpi_dataset", AsyncMock(return_value=True)) as fhfa_mock, \
         patch("scripts.prefetch_backend_data.prefetch_ca_hazard_geojson", AsyncMock(return_value={
             "ap_fault_zones.geojson": True,
             "liquefaction_zones.geojson": True,
             "fire_hazard_zones.geojson": True,
         })) as hazard_mock, \
         patch("scripts.prefetch_backend_data.prefetch_bart_stations", AsyncMock(return_value=False)) as bart_mock, \
         patch("scripts.prefetch_backend_data.prefetch_caltrain_stations", AsyncMock(return_value=True)) as caltrain_mock:
        result = await run_prefetch(force=True)

    assert result["market_trends"] is True
    assert result["fhfa_hpi"] is True
    assert result["ca_hazards"]["ap_fault_zones.geojson"] is True
    assert result["bart_stations"] is False
    assert result["caltrain_stations"] is True
    market_mock.assert_awaited_once_with(force=True)
    fhfa_mock.assert_awaited_once_with(force=True)
    hazard_mock.assert_awaited_once_with(force=True)
    bart_mock.assert_awaited_once_with(force=True)
    caltrain_mock.assert_awaited_once_with(force=True)


def test_prefetch_script_is_importable_when_run_by_path_from_repo_root():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "backend" / "scripts" / "prefetch_backend_data.py"

    proc = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
