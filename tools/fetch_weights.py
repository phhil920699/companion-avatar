"""下载 3DDFA-V3 权重（优先 hf-mirror，支持断点续传）。

用法:
    python tools/fetch_weights.py
"""
from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "engines" / "3ddfa_v3" / "assets"
BASE = "https://hf-mirror.com/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets"

FILES = {
    "face_model.npy": 103_918_535,
    "net_recon.pth": 96_464_581,
    "large_base_net.pth": 27_795_941,
    "retinaface_resnet50_2020-07-20_old_torch.pth": 109_477_455,
    "similarity_Lm3D_all.mat": 994,
}


def download(name: str, expected: int) -> None:
    target = ASSETS / name
    if target.exists() and target.stat().st_size == expected:
        print(f"[skip] {name}")
        return
    ASSETS.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{name}"
    print(f"[get ] {name} -> {target}")
    # curl 支持断点续传，比 urllib 更适合国内网络
    subprocess.run(["curl.exe", "-L", "-C", "-", "--retry", "3", "--max-time", "1800",
                    "-o", str(target), url], check=True)
    size = target.stat().st_size
    if size != expected:
        print(f"[warn] {name} 大小 {size} != {expected}，请重跑本脚本续传", file=sys.stderr)


def main() -> None:
    if not (ROOT / "engines" / "3ddfa_v3").exists():
        print("请先克隆引擎: git clone --depth 1 https://github.com/wang-zidu/3DDFA-V3 engines/3ddfa_v3",
              file=sys.stderr)
        raise SystemExit(1)
    for name, size in FILES.items():
        download(name, size)
    print("完成。若 CPU 渲染器未编译，请进入 engines/3ddfa_v3/util/cython_renderer 执行 python setup.py build_ext -i")


if __name__ == "__main__":
    main()
