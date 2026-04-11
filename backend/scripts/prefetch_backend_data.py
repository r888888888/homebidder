"""
Prefetch large backend datasets so request handlers avoid heavy downloads.

Run manually or on a scheduler (cron/systemd) to refresh caches.
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.tools.ba_value_drivers import prefetch_bart_stations, prefetch_caltrain_stations, prefetch_muni_stops, prefetch_schools
from agent.tools.ca_hazards import prefetch_ca_hazard_geojson
from agent.tools.fhfa import prefetch_fhfa_hpi_dataset
from agent.tools.market_trends import prefetch_market_trends_dataset
from agent.tools.zillow_hpi import prefetch_zillow_zhvi


async def run_prefetch(force: bool = False) -> dict:
    market, fhfa, zillow, hazards, bart, caltrain, muni, schools = await asyncio.gather(
        prefetch_market_trends_dataset(force=force),
        prefetch_fhfa_hpi_dataset(force=force),
        prefetch_zillow_zhvi(force=force),
        prefetch_ca_hazard_geojson(force=force),
        prefetch_bart_stations(force=force),
        prefetch_caltrain_stations(force=force),
        prefetch_muni_stops(force=force),
        prefetch_schools(force=force),
    )
    return {
        "market_trends": market,
        "fhfa_hpi": fhfa,
        "zillow_zhvi": zillow,
        "ca_hazards": hazards,
        "bart_stations": bart,
        "caltrain_stations": caltrain,
        "muni_stops": muni,
        "schools": schools,
    }


async def _amain() -> int:
    parser = argparse.ArgumentParser(description="Prefetch large backend datasets")
    parser.add_argument("--force", action="store_true", help="Refresh all datasets even if cache exists")
    args = parser.parse_args()

    result = await run_prefetch(force=args.force)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
