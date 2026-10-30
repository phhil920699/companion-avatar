"""减面：优先 pymeshlab，失败回退 trimesh/Open3D。"""
from __future__ import annotations

import numpy as np
import trimesh


def _vertex_colors(mesh: trimesh.Trimesh) -> np.ndarray | None:
    try:
        if mesh.visual.kind == "vertex":
            return np.asarray(mesh.visual.vertex_colors)
    except Exception:
        pass
    return None


def _transfer_colors(src: trimesh.Trimesh, dst: trimesh.Trimesh) -> trimesh.Trimesh:
    colors = _vertex_colors(src)
    if colors is None:
        return dst
    from scipy.spatial import cKDTree

    tree = cKDTree(src.vertices)
    _, idx = tree.query(dst.vertices, k=1)
    dst.visual = trimesh.visual.ColorVisuals(dst, vertex_colors=colors[idx])
    return dst


def _decimate_pymeshlab(mesh: trimesh.Trimesh, target: int) -> trimesh.Trimesh:
    import pymeshlab

    ms = pymeshlab.MeshSet()
    ms.add_mesh(
        pymeshlab.Mesh(
            vertex_matrix=np.asarray(mesh.vertices, dtype=np.float64),
            face_matrix=np.asarray(mesh.faces, dtype=np.int32),
        )
    )
    ms.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=int(target),
        preservenormal=True,
        optimalplacement=True,
        preserveboundary=True,
    )
    cur = ms.current_mesh()
    out = trimesh.Trimesh(
        vertices=cur.vertex_matrix(),
        faces=cur.face_matrix(),
        process=False,
    )
    return _transfer_colors(mesh, out)


def decimate(mesh: trimesh.Trimesh, target_faces: int) -> trimesh.Trimesh:
    if len(mesh.faces) <= target_faces:
        return mesh.copy()
    try:
        return _decimate_pymeshlab(mesh, target_faces)
    except Exception:
        pass
    try:
        out = mesh.simplify_quadric_decimation(face_count=int(target_faces))
        return _transfer_colors(mesh, out)
    except Exception:
        return mesh.copy()
