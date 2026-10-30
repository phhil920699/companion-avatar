"""视频/多图扫描（pip 版）：pycolmap SfM → Open3D Poisson。

SfM 在独立子进程里跑，避免 C++ abort 拖垮服务。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app import config
from app.adapters.base import Adapter, Capability, JobRequest, RawAsset
from app.adapters.frames import extract_images


class ScanPycolmap(Adapter):
    def __init__(self, entry: dict):
        self.id = entry["id"]
        self.kind = entry["kind"]
        self.license = entry.get("license", "BSD-3-Clause")
        self.commercial_ok = bool(entry.get("commercial_ok", True))
        self.requires_gpu = False

    def probe(self) -> Capability:
        try:
            import pycolmap  # noqa: F401
            import open3d  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            return Capability(False, f"pycolmap/Open3D 不可用: {exc}")
        return Capability(True, "pycolmap SfM + Open3D Poisson（无需 COLMAP 二进制）")

    def run(self, req: JobRequest, log, cancel=None) -> RawAsset:
        work = req.workdir
        images = extract_images(Path(req.inputs[0]), work, log)
        out = work / "scan_mesh.ply"

        cmd = [sys.executable, "-m", "app.adapters._pycolmap_runner", str(images), str(work), str(out)]
        log("$ " + " ".join(cmd))
        env = dict(os.environ, PYTHONPATH=str(config.ROOT), PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(config.ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log(line)
            if cancel and cancel():
                proc.terminate()
                raise RuntimeError("任务已取消")
        code = proc.wait()
        if code != 0 or not out.exists():
            raise RuntimeError(f"pycolmap 重建失败（退出码 {code}），建议补拍或改用完整模式")

        return RawAsset(
            mesh_path=out,
            unit_hint="head",
            quality="preview",
            source_meta={"kind": "scan_video", "engine": "pycolmap+open3d", "inputs": [str(p) for p in req.inputs]},
        )
