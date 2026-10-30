"""MediaPipe Face Landmarker → 细分规范人脸网格 + 投影顶点色。

独立子进程运行。输入一张照片，输出带顶点色的 OBJ。
用法: python -m app.adapters._mediapipe_runner <image> <out_obj>
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "engines" / "mediapipe_assets"
CANONICAL = ASSETS / "canonical_face_model.obj"
TASK = ASSETS / "face_landmarker.task"


def load_canonical():
    verts, faces = [], []
    for line in CANONICAL.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:4]])
    return np.asarray(verts, np.float64), np.asarray(faces, np.int32)


def detect_landmarks(image_bgr: np.ndarray) -> np.ndarray:
    import mediapipe as mp
    from mediapipe.tasks import python as mpp
    from mediapipe.tasks.python import vision

    options = vision.FaceLandmarkerOptions(
        base_options=mpp.BaseOptions(model_asset_path=str(TASK)),
        num_faces=1,
        output_face_blendshapes=False,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)
    if not result.face_landmarks:
        raise RuntimeError("MediaPipe 未检测到人脸")
    return np.array([[lm.x, lm.y] for lm in result.face_landmarks[0][:468]], np.float64)


def bilinear(img: np.ndarray, xy: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    x = np.clip(xy[:, 0], 0, w - 1.001)
    y = np.clip(xy[:, 1], 0, h - 1.001)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    dx = (x - x0)[:, None]
    dy = (y - y0)[:, None]
    c00 = img[y0, x0].astype(np.float64)
    c01 = img[y0, x0 + 1].astype(np.float64)
    c10 = img[y0 + 1, x0].astype(np.float64)
    c11 = img[y0 + 1, x0 + 1].astype(np.float64)
    return (c00 * (1 - dx) * (1 - dy) + c01 * dx * (1 - dy)
            + c10 * (1 - dx) * dy + c11 * dx * dy)


def main() -> int:
    image_path = Path(sys.argv[1])
    out_obj = Path(sys.argv[2])

    img = cv2.imread(str(image_path))
    if img is None:
        raise SystemExit(f"读不到图片: {image_path}")
    h, w = img.shape[:2]

    verts, faces = load_canonical()
    lms = detect_landmarks(img)
    if len(lms) != len(verts):
        raise SystemExit(f"关键点数量不匹配: {len(lms)} vs {len(verts)}")

    # 规范网格确认 Y 轴向上
    eye_y = verts[[33, 133, 362, 263], 1].mean()
    mouth_y = verts[[61, 291, 13, 14], 1].mean()
    if eye_y < mouth_y:
        verts[:, 1] *= -1
        faces = faces[:, ::-1]

    img_pts = np.stack([lms[:, 0] * w, lms[:, 1] * h], axis=1).astype(np.float32)
    f = float(max(w, h)) * 1.15
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]], np.float64)
    ok, rvec, tvec = cv2.solvePnP(verts.astype(np.float32), img_pts, K, None, flags=cv2.SOLVEPNP_EPNP)
    if not ok:
        raise SystemExit("solvePnP 失败")
    rvec, tvec = cv2.solvePnPRefineLM(verts.astype(np.float32), img_pts, K, None, rvec, tvec)

    # 细分两次，让眼/嘴区域有足够顶点承载颜色
    import trimesh

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    mesh = mesh.subdivide()
    mesh = mesh.subdivide()

    proj, _ = cv2.projectPoints(np.asarray(mesh.vertices, np.float32), rvec, tvec, K, None)
    colors = bilinear(img, proj.reshape(-1, 2))[:, ::-1] / 255.0  # BGR -> RGB, 0..1

    out_obj.parent.mkdir(parents=True, exist_ok=True)
    with out_obj.open("w", encoding="utf-8") as fh:
        fh.write("# MediaPipe canonical face mesh (subdivided) with projected vertex colors\n")
        for (x, y, z), (r, g, b) in zip(mesh.vertices, colors):
            fh.write(f"v {x:.5f} {y:.5f} {z:.5f} {r:.5f} {g:.5f} {b:.5f}\n")
        for a, b, c in mesh.faces:
            fh.write(f"f {a + 1} {b + 1} {c + 1}\n")
    print(f"[mediapipe] wrote {out_obj} ({len(mesh.vertices)} verts, {len(mesh.faces)} faces)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
