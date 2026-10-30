"""扫描件导入：OBJ/GLB/GLTF/PLY 直接进编译器。"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from app.adapters.base import Adapter, Capability, JobRequest, RawAsset

MESH_SUFFIXES = {".obj", ".glb", ".gltf", ".ply", ".stl"}


class ScanUpload(Adapter):
    def __init__(self, entry: dict):
        self.id = entry["id"]
        self.kind = entry["kind"]
        self.license = entry.get("license", "MIT")
        self.commercial_ok = bool(entry.get("commercial_ok", True))
        self.requires_gpu = False

    def probe(self) -> Capability:
        try:
            import trimesh  # noqa: F401
        except Exception as exc:
            return Capability(False, f"trimesh 不可用: {exc}")
        return Capability(True, "支持 OBJ/GLB/GLTF/PLY/STL 及 ZIP")

    def _resolve_mesh(self, src: Path, workdir: Path) -> Path:
        if src.suffix.lower() == ".zip":
            extract = workdir / "unzipped"
            extract.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(src) as zf:
                zf.extractall(extract)
            candidates = [p for p in extract.rglob("*") if p.suffix.lower() in MESH_SUFFIXES]
            if not candidates:
                raise ValueError("ZIP 内没有找到网格文件")
            candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
            return candidates[0]
        if src.suffix.lower() not in MESH_SUFFIXES:
            raise ValueError(f"不支持的格式: {src.suffix}（支持 OBJ/GLB/GLTF/PLY/STL）")
        return src

    def run(self, req: JobRequest, log, cancel=None) -> RawAsset:
        src = self._resolve_mesh(Path(req.inputs[0]), req.workdir)
        log(f"读取网格: {src}")
        dst = req.workdir / ("input" + src.suffix.lower())
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        return RawAsset(
            mesh_path=dst,
            unit_hint="head",
            quality="standard",
            source_meta={"kind": "scan_upload", "engine": "trimesh", "inputs": [str(src)]},
        )
