"""照片链路回退：3DDFA_V2（ONNX）。需要 FaceBoxes 权重，缺失时不可用。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from app import config
from app.adapters.base import Adapter, Capability, JobRequest, RawAsset

ENGINE = config.ENGINES / "3ddfa_v2"


def _faceboxes_ready() -> bool:
    w = ENGINE / "weights"
    return (w / "FaceBoxesProd.pth").exists() or (w / "FaceBoxes.onnx").exists()


class Photo3DDFAV2(Adapter):
    def __init__(self, entry: dict):
        self.id = entry["id"]
        self.kind = entry["kind"]
        self.license = entry.get("license", "MIT")
        self.commercial_ok = bool(entry.get("commercial_ok", True))
        self.requires_gpu = False
        self.repo = entry.get("repo", "")

    def probe(self) -> Capability:
        if not (ENGINE / "demo.py").exists():
            return Capability(False, f"引擎未安装: {ENGINE}")
        if not (ENGINE / "weights" / "mb1_120x120.pth").exists():
            return Capability(False, "缺少 3DDFA_V2 主干权重")
        if not _faceboxes_ready():
            return Capability(False, "缺少 FaceBoxes 检测器权重（weights/FaceBoxesProd.pth）")
        return Capability(True, "3DDFA_V2 ONNX 可用")

    def run(self, req: JobRequest, log, cancel=None) -> RawAsset:
        work = req.workdir
        results = ENGINE / "examples" / "results"
        results.mkdir(parents=True, exist_ok=True)
        src = Path(req.inputs[0]).resolve()
        # demo.py 用 split('/') 取文件名，传正斜杠路径
        img_arg = str(src).replace("\\", "/")

        cmd = [
            sys.executable, "demo.py",
            "-f", img_arg,
            "--onnx",
            "--opt", "obj",
            "-o", "obj",
        ]
        log("$ " + " ".join(cmd))
        env = dict(os.environ, PYTHONIOENCODING="utf-8", KMP_DUPLICATE_LIB_OK="TRUE")
        proc = subprocess.run(
            cmd, cwd=str(ENGINE), capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env, timeout=300,
        )
        for line in (proc.stdout or "").splitlines():
            log(line)
        for line in (proc.stderr or "").splitlines():
            log("[stderr] " + line)
        if proc.returncode != 0:
            raise RuntimeError("3DDFA_V2 执行失败，请查看日志")

        objs = sorted(results.glob("*.obj"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not objs:
            raise RuntimeError("3DDFA_V2 未产出 OBJ（可能未检测到人脸）")
        return RawAsset(
            mesh_path=objs[0],
            unit_hint="head",
            quality="fallback",
            source_meta={"kind": "photo", "engine": "3ddfa_v2", "inputs": [str(src)], "license": self.license},
        )
