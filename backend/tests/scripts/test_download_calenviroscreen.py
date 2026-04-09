"""
Tests for download_calenviroscreen._convert — verifies that the shapefile
conversion reprojects coordinates from California Albers (EPSG:3310) to
WGS84 (EPSG:4326) as required by the GeoJSON spec.
"""

import json
import pytest
import shapefile as pyshp


def _make_ces_shapefile(tmp_path, epsg3310_x: float, epsg3310_y: float, size: float = 200.0):
    """
    Write a minimal one-polygon CalEnviroScreen shapefile at the given EPSG:3310
    coordinates (x, y) with a square footprint of `size` metres.
    Returns the path to the .shp file.
    """
    shp_stem = str(tmp_path / "test_ces")
    with pyshp.Writer(shp_stem) as w:
        w.field("TrafficP",  "N", decimal=2)
        w.field("DieselPM_P", "N", decimal=2)
        w.field("PM2_5_P",   "N", decimal=2)
        w.field("CIscoreP",  "N", decimal=2)
        cx, cy = epsg3310_x, epsg3310_y
        ring = [
            (cx,        cy),
            (cx + size, cy),
            (cx + size, cy + size),
            (cx,        cy + size),
            (cx,        cy),
        ]
        w.poly([ring])
        w.record(85.3, 72.1, 64.8, 78.5)
    return tmp_path / "test_ces.shp"


class TestConvertReprojectsToWGS84:
    def test_output_coordinates_are_in_wgs84_range(self, tmp_path):
        """
        _convert must write GeoJSON with WGS84 coordinates (lon -180..180, lat -90..90).
        CalEnviroScreen 4.0 shapefiles use EPSG:3310; their raw coordinates are in
        metres and far outside the WGS84 degree range, so any output outside ±180/±90
        proves reprojection was skipped.
        """
        # SF City Hall in EPSG:3310 ≈ (-212792, -24128)
        shp_path = _make_ces_shapefile(tmp_path, epsg3310_x=-212792.0, epsg3310_y=-24128.0)
        out_path = tmp_path / "output.geojson"

        from scripts.download_calenviroscreen import _convert
        _convert(shp_path, out_path)

        with open(out_path) as f:
            data = json.load(f)

        assert data["features"], "Output GeoJSON has no features"
        coords = data["features"][0]["geometry"]["coordinates"][0]

        for lon, lat in coords:
            assert -180 <= lon <= 180, f"Longitude {lon:.2f} is outside WGS84 range — not reprojected"
            assert -90  <= lat <= 90,  f"Latitude  {lat:.2f} is outside WGS84 range — not reprojected"

    def test_sf_location_reprojects_near_sf(self, tmp_path):
        """
        An EPSG:3310 coordinate corresponding to SF City Hall must round-trip to
        WGS84 coordinates within the San Francisco bounding box.
        """
        shp_path = _make_ces_shapefile(tmp_path, epsg3310_x=-212792.0, epsg3310_y=-24128.0)
        out_path = tmp_path / "output.geojson"

        from scripts.download_calenviroscreen import _convert
        _convert(shp_path, out_path)

        with open(out_path) as f:
            data = json.load(f)

        coords = data["features"][0]["geometry"]["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        centroid_lon = sum(lons) / len(lons)
        centroid_lat = sum(lats) / len(lats)

        # SF bounding box: roughly -122.53 to -122.35 lon, 37.70 to 37.83 lat
        assert -122.6 < centroid_lon < -122.3, f"Centroid lon {centroid_lon:.5f} not in SF area"
        assert  37.6  < centroid_lat <  37.9,  f"Centroid lat {centroid_lat:.5f} not in SF area"

    def test_properties_preserved_after_reprojection(self, tmp_path):
        """Reprojection must not drop or alter feature properties."""
        shp_path = _make_ces_shapefile(tmp_path, epsg3310_x=-212792.0, epsg3310_y=-24128.0)
        out_path = tmp_path / "output.geojson"

        from scripts.download_calenviroscreen import _convert
        _convert(shp_path, out_path)

        with open(out_path) as f:
            data = json.load(f)

        props = data["features"][0]["properties"]
        assert props["TrafficP"]  == pytest.approx(85.3)
        assert props["DieselPM_P"] == pytest.approx(72.1)
        assert props["PM2_5_P"]   == pytest.approx(64.8)
        assert props["CIscoreP"]  == pytest.approx(78.5)
