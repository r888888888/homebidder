#!/usr/bin/env python3
"""
Convert CA hazard GeoJSON files to compact pickle format for memory-efficient
runtime loading.

Run this locally before uploading data to Fly via scripts/upload_fly_data.sh.
Loading the raw 257MB fire_hazard_zones.geojson requires ~1.2 GB peak memory;
loading the equivalent .pkl uses ~108 MB.

Usage:
    python3 backend/scripts/build_hazard_pkl.py
    python3 backend/scripts/build_hazard_pkl.py --force   # overwrite existing pkls
"""

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from shapely.geometry import shape
from shapely.wkb import dumps as wkb_dumps

log = logging.getLogger(__name__)

DATA_DIR = BACKEND_DIR / "data"

# (geojson_stem, prop_key_or_None)
# prop_key is the GeoJSON properties field needed at query time.
# None means no property is needed (fault zones — containment check only).
HAZARD_FILES: list[tuple[str, str | None]] = [
    ("ap_fault_zones",     None),
    ("liquefaction_zones", "LIQSUSCEP"),
    ("fire_hazard_zones",  "HAZ_CLASS"),
]


def geojson_to_pkl(geojson_path: Path, pkl_path: Path, prop_key: str | None) -> int:
    """
    Convert a GeoJSON FeatureCollection to a compact pickle.

    Stores:
        {
            "wkb":   list[bytes],       # WKB-encoded shapely geometry per feature
            "props": list[str | None],  # normalized property value (or None)
        }

    Features without geometry are skipped. wkb and props are parallel lists —
    index i in props corresponds to index i in wkb (and to the STRtree index).
    Property values are upper-cased and stripped at conversion time.

    Returns the number of features written.
    """
    size_mb = geojson_path.stat().st_size // 1_048_576
    log.info("Loading %s (%d MB)...", geojson_path.name, size_mb)

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    wkb_list: list[bytes] = []
    props_list: list[str | None] = []

    for feature in data.get("features", []):
        geom_data = feature.get("geometry")
        if not geom_data:
            continue

        wkb_list.append(wkb_dumps(shape(geom_data)))

        if prop_key is not None:
            raw = (feature.get("properties", {}).get(prop_key) or "").upper().strip()
            props_list.append(raw or None)
        else:
            props_list.append(None)

    payload = {"wkb": wkb_list, "props": props_list}
    with open(pkl_path, "wb") as f:
        pickle.dump(payload, f, protocol=5)

    size_kb = pkl_path.stat().st_size // 1024
    log.info(
        "Wrote %d features → %s (%d KB, was %d MB)",
        len(wkb_list), pkl_path.name, size_kb, size_mb,
    )
    return len(wkb_list)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Convert CA hazard GeoJSON files to compact pkl format"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing pkl files")
    args = parser.parse_args()

    for stem, prop_key in HAZARD_FILES:
        geojson_path = DATA_DIR / f"{stem}.geojson"
        pkl_path = DATA_DIR / f"{stem}.pkl"

        if not geojson_path.exists():
            log.warning("Skipping %s: not found at %s", stem, geojson_path)
            continue

        if pkl_path.exists() and not args.force:
            log.info("Skipping %s: already exists (--force to overwrite)", pkl_path.name)
            continue

        geojson_to_pkl(geojson_path, pkl_path, prop_key)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
