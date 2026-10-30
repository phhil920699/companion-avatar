"""把一次任务跑完：选择适配器 → 重建 → 编译资产。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import trimesh

from app import config
from app.adapters import registry
from app.adapters.base import JobRequest, RawAsset
from app.compile import compile_asset


class Cancelled(RuntimeError):
    pass


def _available(kind: str, log) -> list[object]:
    adapters = []
    for adapter in registry.all_adapters(kind):
        try:
            if adapter.probe().available:
                adapters.append(adapter)
        except Exception:
            continue
    if not adapters:
        names = ", ".join(a.id for a in registry.all_adapters(kind))
        raise RuntimeError(f"没有可用的 {kind} 引擎（已注册: {names}）")
    log(f"可用 {kind} 引擎: " + " → ".join(a.id for a in adapters))
    return adapters


def run_pipeline(
    job_id: str,
    kind: str,
    inputs: list[Path],
    options: dict,
    log: Callable[[str], None],
    cancel: Callable[[], bool] | None = None,
) -> tuple[str, dict]:
    workdir = config.TMP / job_id
    workdir.mkdir(parents=True, exist_ok=True)

    if kind in ("photo", "scan_upload", "scan_video"):
        adapters = _available(kind, log)
    else:
        raise ValueError(f"未知任务类型: {kind}")

    wanted = options.get("engine")
    if wanted:
        adapters = [a for a in adapters if a.id == wanted]
        if not adapters:
            raise RuntimeError(f"指定引擎 {wanted} 不可用")

    raw: RawAsset | None = None
    used = None
    last_error: Exception | None = None
    for candidate in adapters:
        req = JobRequest(kind=kind, inputs=[Path(p) for p in inputs], workdir=workdir, options=options)
        try:
            log(f"尝试引擎: {candidate.id}")
            raw = candidate.run(req, log, cancel)
            used = candidate
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log(f"[warn] {candidate.id} 失败: {exc}")
    if raw is None or used is None:
        raise RuntimeError(f"所有 {kind} 引擎都失败，最后一个错误: {last_error}")

    tiers = ("low", "standard") if kind == "photo" else ("low", "standard", "high")
    outdir = config.AVATARS / job_id
    log(f"编译资产: {', '.join(tiers)}")
    meta = compile_asset(raw, outdir, tiers=tiers, licenses=[used.license])
    meta["source"]["kind"] = kind
    meta["source"]["engine"] = raw.source_meta.get("engine", used.id)
    (outdir / "meta.json").write_text(
        __import__("json").dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return job_id, meta


def mesh_stats(path: Path) -> dict:
    m = trimesh.load(str(path), force="mesh", process=False)
    return {"vertices": int(len(m.vertices)), "faces": int(len(m.faces))}
