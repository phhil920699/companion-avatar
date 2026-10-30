"""视频/多图扫描：COLMAP SfM+MVS → Open3D Poisson。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from app import config
from app.adapters.base import Adapter, Capability, JobRequest, RawAsset
from app.adapters.frames import extract_images

ENGINE = config.ENGINES / "colmap"


def find_colmap() -> str | None:
    env = os.environ.get("COLMAP_BIN")
    if env and Path(env).exists():
        return env
    candidates = [
        ENGINE / "colmap.exe",
        ENGINE / "bin" / "colmap.exe",
        *ENGINE.glob("*/bin/colmap.exe"),
        *ENGINE.glob("*/colmap.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("colmap")


class ScanColmap(Adapter):
    def __init__(self, entry: dict):
        self.id = entry["id"]
        self.kind = entry["kind"]
        self.license = entry.get("license", "BSD-3-Clause")
        self.commercial_ok = bool(entry.get("commercial_ok", True))
        self.requires_gpu = False

    def probe(self) -> Capability:
        binary = find_colmap()
        if not binary:
            return Capability(False, "未找到 COLMAP 可执行文件（设置 COLMAP_BIN 或放入 engines/colmap/）")
        try:
            import open3d  # noqa: F401
        except Exception as exc:
            return Capability(False, f"Open3D 不可用: {exc}")
        return Capability(True, f"COLMAP 可用: {binary}")

    def _run(self, cmd: list[str], log, cancel) -> None:
        log("$ " + " ".join(cmd))
        env = os.environ.copy()
        binary = Path(cmd[0])
        if binary.suffix.lower() == ".exe":
            # COLMAP.bat 会设置这两个变量，否则 Qt 找不到 windows 平台插件
            env["PATH"] = str(binary.parent) + os.pathsep + env.get("PATH", "")
            root = binary.parent.parent
            env["QT_PLUGIN_PATH"] = str(root / "plugins") + os.pathsep + env.get("QT_PLUGIN_PATH", "")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env=env)
        assert proc.stdout is not None
        for line in proc.stdout:
            log(line.rstrip())
            if cancel and cancel():
                proc.terminate()
                raise RuntimeError("任务已取消")
        if proc.wait() != 0:
            raise RuntimeError(f"命令失败: {cmd[1]}")

    def run(self, req: JobRequest, log, cancel=None) -> RawAsset:
        binary = find_colmap()
        if not binary:
            raise RuntimeError("COLMAP 未安装")
        work = req.workdir
        images = extract_images(Path(req.inputs[0]), work, log)
        db = work / "database.db"
        sparse = work / "sparse"
        dense = work / "dense"
        sparse.mkdir(exist_ok=True)

        self._run([binary, "feature_extractor", "--database_path", str(db),
                   "--image_path", str(images), "--ImageReader.single_camera", "1"], log, cancel)
        self._run([binary, "exhaustive_matcher", "--database_path", str(db)], log, cancel)
        self._run([binary, "mapper", "--database_path", str(db),
                   "--image_path", str(images), "--output_path", str(sparse)], log, cancel)
        model = sparse / "0"
        if not model.exists():
            raise RuntimeError("COLMAP 稀疏重建失败（注册帧不足，建议补拍）")

        dense.mkdir(exist_ok=True)
        if req.options.get("fast", True):
            # 快速模式：稀疏点云直接 Poisson，跳过 CPU 很慢的 MVS
            sparse_ply = sparse / "points.ply"
            self._run([binary, "model_converter", "--input_path", str(model),
                       "--output_path", str(sparse_ply), "--output_type", "PLY"], log, cancel)
            points_src = sparse_ply
            poisson_depth = 8
        else:
            self._run([binary, "image_undistorter", "--image_path", str(images),
                       "--input_path", str(model), "--output_path", str(dense)], log, cancel)
            self._run([binary, "patch_match_stereo", "--workspace_path", str(dense),
                       "--workspace_format", "COLMAP", "--PatchMatchStereo.geom_consistency", "true"], log, cancel)
            fused = dense / "fused.ply"
            self._run([binary, "stereo_fusion", "--workspace_path", str(dense),
                       "--workspace_format", "COLMAP", "--input_type", "geometric",
                       "--output_path", str(fused)], log, cancel)
            points_src = fused
            poisson_depth = 9

        log(f"Poisson 重建（depth={poisson_depth}, 来源 {points_src.name}）…")
        import numpy as np
        import open3d as o3d

        pcd = o3d.io.read_point_cloud(str(points_src))
        if len(pcd.points) < 200:
            raise RuntimeError(f"点云过少（{len(pcd.points)} 点），无法重建；建议补拍或改用完整模式")
        pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.02, max_nn=30))
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=poisson_depth)
        densities = np.asarray(densities)
        if len(densities):
            mesh.remove_vertices_by_mask(densities < np.quantile(densities, 0.05))
        mesh.compute_vertex_normals()
        out = work / "scan_mesh.ply"
        o3d.io.write_triangle_mesh(str(out), mesh)
        return RawAsset(
            mesh_path=out,
            unit_hint="head",
            quality="preview",
            source_meta={"kind": "scan_video", "engine": "colmap+open3d", "inputs": [str(p) for p in req.inputs]},
        )
