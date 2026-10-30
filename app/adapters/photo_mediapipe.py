"""照片链路：MediaPipe 468 点规范人脸网格 + 照片投影贴色。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app import config
from app.adapters.base import Adapter, Capability, JobRequest, RawAsset

ASSETS = config.ENGINES / "mediapipe_assets"


class PhotoMediaPipe(Adapter):
    def __init__(self, entry: dict):
        self.id = entry["id"]
        self.kind = entry["kind"]
        self.license = entry.get("license", "Apache-2.0")
        self.commercial_ok = bool(entry.get("commercial_ok", True))
        self.requires_gpu = False

    def probe(self) -> Capability:
        if not (ASSETS / "canonical_face_model.obj").exists():
            return Capability(False, "缺少 canonical_face_model.obj")
        if not (ASSETS / "face_landmarker.task").exists():
            return Capability(False, "缺少 face_landmarker.task")
        try:
            import mediapipe  # noqa: F401
            import cv2  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            return Capability(False, f"mediapipe/opencv 不可用: {exc}")
        return Capability(True, "MediaPipe 人脸网格（468 点，投影贴色）")

    def run(self, req: JobRequest, log, cancel=None) -> RawAsset:
        work = req.workdir
        out = work / "mediapipe_face.obj"
        cmd = [sys.executable, "-m", "app.adapters._mediapipe_runner", str(req.inputs[0]), str(out)]
        log("$ " + " ".join(cmd))
        env = dict(os.environ, PYTHONPATH=str(config.ROOT), PYTHONIOENCODING="utf-8")
        proc = subprocess.run(cmd, cwd=str(config.ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, timeout=300)
        for line in (proc.stdout or "").splitlines():
            log(line)
        for line in (proc.stderr or "").splitlines():
            if "WARNING" in line or "INFO" in line:
                continue
            log("[stderr] " + line)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError("MediaPipe 人脸网格生成失败，请查看日志")
        return RawAsset(
            mesh_path=out,
            unit_hint="head",
            quality="standard",
            source_meta={"kind": "photo", "engine": "mediapipe", "inputs": [str(p) for p in req.inputs],
                         "license": self.license},
        )
