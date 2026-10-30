"""独立子进程：pycolmap SfM + Open3D Poisson。

崩溃（C++ abort）不会拖垮主服务。
用法: python -m app.adapters._pycolmap_runner <images_dir> <work_dir> <out_ply>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("GLOG_minloglevel", "2")  # 只保留 warning/error，避免日志刷屏


def main() -> int:
    images = Path(sys.argv[1])
    work = Path(sys.argv[2])
    out = Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    db = work / "pycolmap.db"
    sparse = work / "sparse"
    sparse.mkdir(exist_ok=True)

    import numpy as np
    import open3d as o3d
    import pycolmap

    print(f"[sfm] {images}", flush=True)
    pycolmap.extract_features(str(db), str(images), device=pycolmap.Device.cpu)
    pycolmap.match_exhaustive(str(db))
    recs = pycolmap.incremental_mapping(str(db), str(images), str(sparse))
    if not recs:
        print("[sfm] no reconstruction", flush=True)
        return 2
    rec = max(recs.values(), key=lambda r: len(r.images))
    print(f"[sfm] registered={len(rec.images)} points={len(rec.points3D)}", flush=True)
    if len(rec.points3D) < 500:
        return 3

    pts = np.array([p.xyz for p in rec.points3D.values()], dtype=np.float64)
    cols = np.array([np.asarray(p.color) / 255.0 for p in rec.points3D.values()], dtype=np.float64)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)
    pcd.colors = o3d.utility.Vector3dVector(cols)
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.02, max_nn=30))

    print("[poisson] depth=8", flush=True)
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=8)
    densities = np.asarray(densities)
    if len(densities):
        mesh.remove_vertices_by_mask(densities < np.quantile(densities, 0.05))
    mesh.compute_vertex_normals()
    o3d.io.write_triangle_mesh(str(out), mesh)
    print(f"[done] {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
