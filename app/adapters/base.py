"""适配器协议：第三方重建引擎统一出入口。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol


@dataclass
class JobRequest:
    kind: str
    inputs: list[Path]
    workdir: Path
    options: dict = field(default_factory=dict)


@dataclass
class RawAsset:
    mesh_path: Path
    textures: list[Path] = field(default_factory=list)
    unit_hint: str = "auto"  # head | meter | auto
    quality: str = "standard"  # standard | fallback | preview
    source_meta: dict = field(default_factory=dict)


@dataclass
class Capability:
    available: bool
    detail: str = ""
    requires_gpu: bool = False
    version: str = ""


class Adapter(Protocol):
    id: str
    kind: str
    license: str
    commercial_ok: bool
    requires_gpu: bool

    def probe(self) -> Capability: ...

    def run(
        self,
        req: JobRequest,
        log: Callable[[str], None],
        cancel: Callable[[], bool] | None = None,
    ) -> RawAsset: ...


def write_result(workdir: Path, asset: RawAsset, extra: dict | None = None) -> Path:
    """把适配器结果落成 JSON，供 worker 读取。"""
    payload = {
        "mesh_path": str(asset.mesh_path),
        "textures": [str(t) for t in asset.textures],
        "unit_hint": asset.unit_hint,
        "quality": asset.quality,
        "source_meta": asset.source_meta,
    }
    if extra:
        payload.update(extra)
    out = workdir / "adapter_result.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
