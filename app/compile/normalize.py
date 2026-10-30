"""网格归一化：统一 Y-up、-Z 前、米制、底部落地。"""
from __future__ import annotations

import numpy as np
import trimesh

from app import config


def load_mesh(path) -> trimesh.Trimesh:
    obj = trimesh.load(str(path), force="mesh", process=False)
    if isinstance(obj, trimesh.Scene):
        obj = trimesh.util.concatenate(tuple(obj.geometry.values()))
    if not isinstance(obj, trimesh.Trimesh) or len(obj.faces) == 0:
        raise ValueError(f"无法从文件中读出三角网格: {path}")
    return obj


def _to_y_up(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    ext = mesh.extents
    # Z 明显最长 → 视为 Z-up 扫描件，绕 X 轴转 90°
    if ext[2] > ext[1] * 1.2 and ext[2] > ext[0] * 1.2:
        mesh = mesh.copy()
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return mesh


def normalize(mesh: trimesh.Trimesh, unit_hint: str = "auto") -> tuple[trimesh.Trimesh, dict]:
    mesh = mesh.copy()
    mesh = _to_y_up(mesh)
    mesh.remove_unreferenced_vertices()

    ext = mesh.extents
    height = float(ext[1]) if ext[1] > 1e-9 else float(max(ext))
    if unit_hint == "head":
        scale = config.HEAD_HEIGHT_M / height
    elif height > 5.0:  # 毫米
        scale = 0.001
    elif height < 0.01:  # 厘米
        scale = 0.01
    else:
        scale = 1.0

    mesh.apply_scale(scale)
    bounds = mesh.bounds
    center = (bounds[0] + bounds[1]) / 2.0
    mesh.apply_translation([-center[0], -bounds[0][1], -center[2]])

    meta = {
        "bounds": {
            "min": [round(float(v), 5) for v in mesh.bounds[0]],
            "max": [round(float(v), 5) for v in mesh.bounds[1]],
        },
        "up_axis": "Y",
        "forward": "-Z",
        "units": "meter",
        "height_m": round(float(mesh.extents[1]), 4),
        "scale_applied": round(float(scale), 6),
    }
    return mesh, meta
