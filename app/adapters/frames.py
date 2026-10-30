"""视频/图片目录 → 抽帧。"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _resize(frame: np.ndarray, long_side: int = 1280) -> np.ndarray:
    from PIL import Image

    h, w = frame.shape[:2]
    scale = long_side / max(h, w)
    if scale >= 1.0:
        return frame
    img = Image.fromarray(frame).resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return np.asarray(img)


def extract_images(src: Path, workdir: Path, log, max_frames: int = 60) -> Path:
    images = workdir / "images"
    images.mkdir(parents=True, exist_ok=True)
    src = Path(src)

    if src.suffix.lower() in VIDEO_SUFFIXES:
        import cv2
        import imageio.v2 as iio

        reader = iio.get_reader(str(src), "ffmpeg")
        meta = reader.get_meta_data()
        fps = float(meta.get("fps") or 30.0)
        step = max(1, int(round(fps / 3.0)))  # 约 3fps

        candidates: list[tuple[int, float, np.ndarray]] = []
        for idx, frame in enumerate(reader):
            if idx % step:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            candidates.append((idx, score, frame))
        reader.close()
        if not candidates:
            raise ValueError("视频里没有读到帧")

        scores = np.array([c[1] for c in candidates], dtype=np.float64)
        threshold = max(15.0, float(np.median(scores)) * 0.35)
        kept = [c for c in candidates if c[1] >= threshold]
        if len(kept) < 8:
            kept = sorted(candidates, key=lambda c: c[1], reverse=True)[: min(12, len(candidates))]
        kept = sorted(kept[:max_frames], key=lambda c: c[0])

        for j, (_, _, frame) in enumerate(kept):
            iio.imwrite(images / f"frame_{j:05d}.jpg", _resize(frame))
        log(f"抽取视频帧 {len(kept)} 张（候选 {len(candidates)}，模糊阈值 {threshold:.0f}）")
    elif src.is_dir():
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        for i, p in enumerate(files[:max_frames]):
            shutil.copy2(p, images / f"frame_{i:05d}{p.suffix.lower()}")
        log(f"复制图片 {min(len(files), max_frames)} 张")
    else:
        raise ValueError("扫描输入需要是视频文件或图片目录")

    n = len(list(images.glob("*.jpg"))) + len(list(images.glob("*.png")))
    if n < 8:
        raise ValueError(f"有效图片少于 8 张（{n}），无法重建")
    return images
