"""照片链路：3DDFA-V3（CPU）。子进程调用，避免污染主进程。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from app import config
from app.adapters.base import Adapter, Capability, JobRequest, RawAsset

ENGINE = config.ENGINES / "3ddfa_v3"
REQUIRED_ASSETS = ("face_model.npy", "net_recon.pth", "large_base_net.pth", "similarity_Lm3D_all.mat")


def _renderer_built() -> bool:
    return any((ENGINE / "util" / "cython_renderer").glob("mesh_core_cython*.pyd"))


class Photo3DDFAV3(Adapter):
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
        missing = [a for a in REQUIRED_ASSETS if not (ENGINE / "assets" / a).exists()]
        if missing:
            return Capability(False, "缺少权重: " + ", ".join(missing))
        if not _renderer_built():
            return Capability(False, "CPU 渲染器未编译（util/cython_renderer）")
        return Capability(True, "3DDFA-V3 CPU 可用", requires_gpu=False)

    def run(self, req: JobRequest, log, cancel=None) -> RawAsset:
        work = req.workdir
        indir = work / "in"
        outdir = work / "out"
        indir.mkdir(parents=True, exist_ok=True)
        outdir.mkdir(parents=True, exist_ok=True)

        inputs: list[str] = []
        for i, src in enumerate(req.inputs):
            suffix = Path(src).suffix.lower() or ".jpg"
            dst = indir / f"input_{i}{suffix}"
            shutil.copy2(src, dst)
            inputs.append(str(src))

        backbone = req.options.get("backbone", "resnet50")
        cmd = [
            sys.executable, "demo.py",
            "--inputpath", str(indir),
            "--savepath", str(outdir),
            "--device", "cpu",
            "--iscrop", "1",
            "--detector", "retinaface",
            "--extractTex", "1",
            "--useTex", "0",
            "--ldm68", "0",
            "--ldm106", "0",
            "--ldm106_2d", "0",
            "--ldm134", "0",
            "--seg", "0",
            "--seg_visible", "0",
            "--backbone", backbone,
        ]
        log("$ " + " ".join(cmd))
        env = dict(**__import__("os").environ, PYTHONIOENCODING="utf-8", KMP_DUPLICATE_LIB_OK="TRUE")
        if req.options.get("neutral_expr", True):
            env["DFA_NEUTRAL_EXPR"] = "1"  # 基础模型默认中性表情
        proc = subprocess.Popen(
            cmd, cwd=str(ENGINE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
        )
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                log(line.rstrip())
                if cancel and cancel():
                    proc.terminate()
                    raise RuntimeError("任务已取消")
            proc.wait(timeout=600)
        finally:
            if proc.poll() is None:
                proc.kill()

        objs = sorted(outdir.rglob("*_extractTex.obj")) or sorted(outdir.rglob("*_pcaTex.obj"))
        if not objs:
            raise RuntimeError(
                "3DDFA-V3 未产出 OBJ：可能未检测到人脸，或渲染器/权重不完整。请查看任务日志。"
            )
        if proc.returncode != 0:
            log(f"[warn] demo.py 退出码 {proc.returncode}，但已找到产物，继续")

        return RawAsset(
            mesh_path=objs[0],
            textures=[],
            unit_hint="head",
            quality="standard",
            source_meta={
                "kind": "photo",
                "engine": "3ddfa_v3",
                "inputs": inputs,
                "license": self.license,
            },
        )
