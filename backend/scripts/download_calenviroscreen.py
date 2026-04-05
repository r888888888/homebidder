#!/usr/bin/env python3
"""
Download CalEnviroScreen 4.0 shapefile from OEHHA and convert to GeoJSON.

Output: backend/data/calenviroscreen.geojson

Usage:
    python3 backend/scripts/download_calenviroscreen.py
    python3 backend/scripts/download_calenviroscreen.py --force   # re-download even if file exists
"""

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DOWNLOAD_URL = (
    "https://oehha.ca.gov/media/downloads/calenviroscreen/document/"
    "calenviroscreen40shpf2021shp.zip"
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT_FILE = DATA_DIR / "calenviroscreen.geojson"

# CalEnviroScreen 4.0 shapefile field names (10-char DBF truncation).
# These are printed after download so you can verify them if anything looks off.
EXPECTED_FIELDS = {
    "TrafficP",    # Traffic proximity percentile
    "DieselPM_P",  # Diesel PM percentile
    "PM2_5_P",     # PM2.5 percentile
    "CIscoreP",    # CalEnviroScreen 4.0 score percentile
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_pyshp():
    try:
        import shapefile  # noqa: F401
    except ImportError:
        print("Installing pyshp...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "pyshp",
            "--break-system-packages", "--quiet",
        ])


def _download(url: str, dest: Path) -> None:
    print(f"Downloading {url} ...")
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=120) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            print(f"\r  {downloaded / 1_048_576:.1f} / {total / 1_048_576:.1f} MB ({pct:.0f}%)", end="", flush=True)
    except Exception as exc:
        print(f"\nDownload failed: {exc}")
        print(f"\nManual download: {url}")
        print(f"Place the extracted shapefile in a temp directory, then re-run.")
        sys.exit(1)
    print()


def _find_shp(directory: Path) -> Path:
    matches = list(directory.rglob("*.shp"))
    if not matches:
        raise FileNotFoundError(f"No .shp file found under {directory}")
    if len(matches) > 1:
        # Prefer the one whose name contains 'CES' or 'results'
        for m in matches:
            if any(k in m.stem.lower() for k in ("ces", "result", "final")):
                return m
    return matches[0]


def _convert(shp_path: Path, out_path: Path) -> None:
    import shapefile  # pyshp

    print(f"Converting {shp_path.name} → {out_path.name} ...")
    with shapefile.Reader(str(shp_path)) as sf:
        fields = [f[0] for f in sf.fields[1:]]  # skip DeletionFlag

        # Print available fields for verification
        print(f"  Fields in shapefile ({len(fields)} total):")
        for i in range(0, len(fields), 6):
            print("    " + "  ".join(fields[i:i+6]))

        missing = EXPECTED_FIELDS - set(fields)
        if missing:
            print(f"\n  WARNING: expected fields not found: {missing}")
            print("  The calenviroscreen.py field names may need updating.")
            print("  Edit backend/agent/tools/calenviroscreen.py to match the actual field names above.\n")

        features = []
        for shape_rec in sf.shapeRecords():
            geom = shape_rec.shape.__geo_interface__
            props = dict(zip(fields, shape_rec.record))
            # Convert any non-serialisable types (e.g. Decimal) to float/None
            clean_props = {}
            for k, v in props.items():
                if v is None or v == "":
                    clean_props[k] = None
                else:
                    try:
                        clean_props[k] = float(v) if isinstance(v, (int, float)) else v
                    except (TypeError, ValueError):
                        clean_props[k] = str(v)
            features.append({"type": "Feature", "geometry": geom, "properties": clean_props})

    geojson = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f)

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"  Written {len(features)} census tracts → {out_path} ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Download CalEnviroScreen 4.0 → GeoJSON")
    parser.add_argument("--force", action="store_true", help="Re-download even if output exists")
    args = parser.parse_args()

    if OUT_FILE.exists() and not args.force:
        size_mb = OUT_FILE.stat().st_size / 1_048_576
        print(f"Already exists: {OUT_FILE} ({size_mb:.1f} MB). Use --force to re-download.")
        return

    _ensure_pyshp()
    DATA_DIR.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "calenviroscreen.zip"

        _download(DOWNLOAD_URL, zip_path)

        print("Extracting zip...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)

        shp_path = _find_shp(tmp_path)
        print(f"Found shapefile: {shp_path.name}")

        _convert(shp_path, OUT_FILE)

    print("Done.")


if __name__ == "__main__":
    main()
