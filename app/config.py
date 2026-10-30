"""全局路径与运行配置。"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"
DATA = ROOT / "data"
MODELS = DATA / "models"
UPLOADS = DATA / "uploads"
AVATARS = DATA / "avatars"
TMP = DATA / "tmp"
FIXTURES = ROOT / "fixtures"
WEB_DIST = ROOT / "web" / "dist"
DB_PATH = DATA / "jobs.db"

for _p in (MODELS, UPLOADS, AVATARS, TMP):
    _p.mkdir(parents=True, exist_ok=True)

# prototype: 允许非商用引擎；commercial: 仅 MIT/BSD/Apache 等可商用组件
PROFILE = os.environ.get("COMPANION_PROFILE", "prototype").lower()

# 头部归一化后的高度（米）
HEAD_HEIGHT_M = 0.24
MIN_FREE_GB = 5.0


def free_gb(path: Path = ROOT) -> float:
    import shutil

    return shutil.disk_usage(path).free / (1024 ** 3)
