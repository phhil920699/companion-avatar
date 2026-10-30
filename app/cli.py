"""命令行入口：serve / photo / scan / doctor。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import config


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("app.serve:app", host=args.host, port=args.port, reload=False)


def _run(kind: str, inputs: list[Path], options: dict | None = None) -> None:
    from app.jobs import JobLogger, JobStore
    from app.runner import run_pipeline

    options = options or {}
    store = JobStore()
    # 直接标记 running，避免同机运行的服务端 worker 再次领取同一任务
    job_id = store.create(kind, [str(p) for p in inputs], options, status="running")
    log = JobLogger(job_id)
    log(f"CLI 任务 {job_id}，kind={kind}")

    def echo(line: str) -> None:
        log(line)
        print(line, flush=True)

    try:
        avatar_id, meta = run_pipeline(job_id, kind, inputs, options, echo)
    except Exception as exc:  # noqa: BLE001
        store.update(job_id, status="failed", stage="failed", error=str(exc))
        print(f"失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
    store.update(job_id, status="succeeded", stage="done", avatar_id=avatar_id)
    print(f"\n完成: {config.AVATARS / avatar_id}")
    print(f"档位: {', '.join(meta['tiers'])}")
    print(f"质量: {meta['quality']}")


def cmd_photo(args: argparse.Namespace) -> None:
    options = {}
    if getattr(args, "engine", None):
        options["engine"] = args.engine
    if getattr(args, "backbone", None):
        options["backbone"] = args.backbone
    _run("photo", [Path(args.image)], options)


def cmd_scan(args: argparse.Namespace) -> None:
    src = Path(args.path)
    video_suffixes = (".mp4", ".mov", ".avi", ".mkv")
    kind = "scan_video" if (src.is_dir() or src.suffix.lower() in video_suffixes) else "scan_upload"
    options = {"fast": False} if getattr(args, "full", False) else {}
    _run(kind, [src], options)


def cmd_doctor(_: argparse.Namespace) -> None:
    import platform

    print(f"Python: {platform.python_version()}  ({sys.executable})")
    print(f"Profile: {config.PROFILE}   Free disk: {config.free_gb():.1f} GB")
    try:
        import torch

        print(f"Torch: {torch.__version__}  CUDA: {torch.cuda.is_available()}")
    except Exception as exc:
        print(f"Torch: 不可用 ({exc})")

    from app.adapters import registry

    print("\n适配器：")
    for adapter in registry.all_adapters():
        try:
            cap = adapter.probe()
            status = "OK " if cap.available else "NO "
            print(f"  [{status}] {adapter.id:18s} {adapter.license:14s} {cap.detail}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERR] {adapter.id:18s} probe 异常: {exc}")


def main(argv: list[str] | None = None) -> None:
    try:  # Windows 控制台默认 GBK，统一成 UTF-8 输出
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(prog="companion")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="启动本地服务与预览页")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    p_photo = sub.add_parser("photo", help="单张照片生成头像")
    p_photo.add_argument("image")
    p_photo.add_argument("--engine", help="指定引擎: photo_3ddfa_v3 / photo_mediapipe")
    p_photo.add_argument("--backbone", choices=["resnet50", "mbnetv3"], help="3DDFA-V3 主干")
    p_photo.set_defaults(func=cmd_photo)

    p_scan = sub.add_parser("scan", help="扫描件或环绕视频生成头像")
    p_scan.add_argument("path")
    p_scan.add_argument("--full", action="store_true", help="COLMAP 完整 MVS（慢，但几何更完整）")
    p_scan.set_defaults(func=cmd_scan)

    p_doc = sub.add_parser("doctor", help="自检")
    p_doc.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
