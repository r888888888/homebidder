"""Tests for scripts/build_hazard_pkl.py — geojson_to_pkl conversion."""
import json
import pickle

import pytest
from shapely.geometry import shape
from shapely.wkb import loads as wkb_loads

from scripts.build_hazard_pkl import geojson_to_pkl


def _make_geojson(*features: dict) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


def _feature(geom: dict, props: dict) -> dict:
    return {"type": "Feature", "geometry": geom, "properties": props}


def _square(cx: float = 0.0, cy: float = 0.0, r: float = 0.1) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [cx - r, cy - r], [cx + r, cy - r],
            [cx + r, cy + r], [cx - r, cy + r],
            [cx - r, cy - r],
        ]],
    }


class TestGeojsonToPkl:
    def test_returns_feature_count(self, tmp_path):
        path = tmp_path / "z.geojson"
        path.write_text(json.dumps(_make_geojson(
            _feature(_square(0, 0), {"HAZ_CLASS": "HIGH"}),
            _feature(_square(1, 1), {"HAZ_CLASS": "LOW"}),
        )))
        n = geojson_to_pkl(path, tmp_path / "z.pkl", "HAZ_CLASS")
        assert n == 2

    def test_parallel_wkb_and_props_lists(self, tmp_path):
        path = tmp_path / "z.geojson"
        path.write_text(json.dumps(_make_geojson(
            _feature(_square(0, 0), {"HAZ_CLASS": "HIGH"}),
            _feature(_square(1, 1), {"HAZ_CLASS": "LOW"}),
        )))
        geojson_to_pkl(path, tmp_path / "z.pkl", "HAZ_CLASS")
        payload = pickle.loads((tmp_path / "z.pkl").read_bytes())
        assert len(payload["wkb"]) == 2
        assert len(payload["props"]) == 2

    def test_props_uppercased_and_stripped(self, tmp_path):
        path = tmp_path / "z.geojson"
        path.write_text(json.dumps(_make_geojson(
            _feature(_square(), {"HAZ_CLASS": "  very high  "}),
        )))
        geojson_to_pkl(path, tmp_path / "z.pkl", "HAZ_CLASS")
        payload = pickle.loads((tmp_path / "z.pkl").read_bytes())
        assert payload["props"][0] == "VERY HIGH"

    def test_missing_prop_stored_as_none(self, tmp_path):
        path = tmp_path / "z.geojson"
        path.write_text(json.dumps(_make_geojson(
            _feature(_square(), {}),
        )))
        geojson_to_pkl(path, tmp_path / "z.pkl", "HAZ_CLASS")
        payload = pickle.loads((tmp_path / "z.pkl").read_bytes())
        assert payload["props"][0] is None

    def test_none_prop_key_stores_none_for_all(self, tmp_path):
        path = tmp_path / "z.geojson"
        path.write_text(json.dumps(_make_geojson(
            _feature(_square(), {"irrelevant": "x"}),
        )))
        geojson_to_pkl(path, tmp_path / "z.pkl", None)
        payload = pickle.loads((tmp_path / "z.pkl").read_bytes())
        assert payload["props"][0] is None

    def test_features_without_geometry_skipped(self, tmp_path):
        path = tmp_path / "z.geojson"
        path.write_text(json.dumps(_make_geojson(
            _feature(None, {"HAZ_CLASS": "HIGH"}),
            _feature(_square(), {"HAZ_CLASS": "LOW"}),
        )))
        n = geojson_to_pkl(path, tmp_path / "z.pkl", "HAZ_CLASS")
        assert n == 1
        payload = pickle.loads((tmp_path / "z.pkl").read_bytes())
        assert payload["props"][0] == "LOW"

    def test_wkb_round_trips_correctly(self, tmp_path):
        geom = _square(-122.4, 37.8)
        path = tmp_path / "z.geojson"
        path.write_text(json.dumps(_make_geojson(_feature(geom, {}))))
        geojson_to_pkl(path, tmp_path / "z.pkl", None)
        payload = pickle.loads((tmp_path / "z.pkl").read_bytes())
        loaded = wkb_loads(payload["wkb"][0])
        assert loaded.equals(shape(geom))
