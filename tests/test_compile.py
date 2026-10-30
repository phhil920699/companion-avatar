import json
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.adapters.base import RawAsset  # noqa: E402
from app.compile import compile_asset  # noqa: E402
from app.compile.normalize import normalize  # noqa: E402


def _sphere() -> trimesh.Trimesh:
    mesh = trimesh.creation.uv_sphere(radius=1.0, count=[32, 32])
    colors = np.tile(np.array([180, 120, 90, 255], dtype=np.uint8), (len(mesh.vertices), 1))
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=colors)
    return mesh


def test_normalize_head_height(tmp_path: Path):
    mesh = _sphere()
    out, meta = normalize(mesh, unit_hint="head")
    assert meta["units"] == "meter"
    assert meta["up_axis"] == "Y"
    assert abs(out.extents[1] - 0.24) < 1e-6
    assert abs(out.bounds[0][1]) < 1e-6  # 底部落地


def test_normalize_millimeter_scan():
    mesh = trimesh.creation.box(extents=[100, 200, 90])  # 单位毫米
    out, meta = normalize(mesh, unit_hint="auto")
    assert meta["scale_applied"] == 0.001
    assert abs(out.extents[1] - 0.2) < 1e-6


def test_compile_asset_tiers(tmp_path: Path):
    src = tmp_path / "src.obj"
    _sphere().export(src)
    raw = RawAsset(mesh_path=src, unit_hint="head", quality="standard",
                   source_meta={"kind": "photo", "engine": "test"})
    outdir = tmp_path / "av_test"
    meta = compile_asset(raw, outdir, tiers=("low", "standard"), licenses=["MIT"])

    assert (outdir / "low.glb").exists()
    assert (outdir / "standard.glb").exists()
    assert meta["tiers"]["low"]["tris"] > 0
    assert meta["licenses"] == ["MIT"]
    saved = json.loads((outdir / "meta.json").read_text(encoding="utf-8"))
    assert saved["avatar_id"] == "av_test"

    loaded = trimesh.load(outdir / "low.glb", force="mesh")
    assert len(loaded.faces) > 0
