"""GLB 导出：保留顶点色或贴图。"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh


def ensure_visual(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    try:
        kind = mesh.visual.kind
    except Exception:
        kind = None
    if kind in ("vertex", "texture"):
        return mesh
    # 无颜色时给中性灰，避免 GLB 全黑
    gray = np.tile(np.array([200, 190, 180, 255], dtype=np.uint8), (len(mesh.vertices), 1))
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=gray)
    return mesh


def _srgb_to_linear(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """glTF 的 COLOR_0 按线性空间解释，顶点色来自图片时需要转换。"""
    try:
        if mesh.visual.kind != "vertex":
            return mesh
    except Exception:
        return mesh
    colors = np.array(mesh.visual.vertex_colors, dtype=np.uint8).copy()
    rgb = colors[:, :3].astype(np.float32) / 255.0
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    colors[:, :3] = np.clip(np.round(linear * 255), 0, 255).astype(np.uint8)
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=colors)
    return mesh


def export_glb(mesh: trimesh.Trimesh, path: Path) -> int:
    mesh = ensure_visual(mesh.copy())
    mesh = _srgb_to_linear(mesh)
    try:
        _ = mesh.vertex_normals  # 触发计算，确保 GLB 写入 NORMAL
    except Exception:
        pass
    mesh.export(str(path), file_type="glb")
    return path.stat().st_size
