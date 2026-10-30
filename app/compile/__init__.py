"""资产编译：RawAsset → 多档 GLB + meta.json。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.adapters.base import RawAsset
from app.compile.glb import export_glb
from app.compile.normalize import load_mesh, normalize
from app.compile.simplify import decimate

TIER_FACES = {"low": 20_000, "standard": 80_000, "high": 250_000}


def compile_asset(
    raw: RawAsset,
    outdir: Path,
    tiers: tuple[str, ...] = ("low", "standard"),
    licenses: list[str] | None = None,
) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    mesh = load_mesh(raw.mesh_path)
    mesh, norm_meta = normalize(mesh, raw.unit_hint)

    tier_meta: dict[str, dict] = {}
    for name in tiers:
        target = TIER_FACES[name]
        simplified = decimate(mesh, target)
        path = outdir / f"{name}.glb"
        size = export_glb(simplified, path)
        tier_meta[name] = {
            "file": path.name,
            "tris": int(len(simplified.faces)),
            "vertices": int(len(simplified.vertices)),
            "bytes": int(size),
        }

    meta = {
        "schema_version": 1,
        "avatar_id": outdir.name,
        "source": {
            "kind": raw.source_meta.get("kind", "unknown"),
            "engine": raw.source_meta.get("engine", "unknown"),
            "inputs": raw.source_meta.get("inputs", []),
        },
        "tiers": tier_meta,
        "quality": raw.quality,
        "licenses": licenses or [],
        **norm_meta,
    }
    (outdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 保留原始网格，方便后续重编译
    try:
        shutil.copy2(raw.mesh_path, outdir / ("source" + Path(raw.mesh_path).suffix))
    except Exception:
        pass
    return meta
