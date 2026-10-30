"""从 manifest 加载适配器，并按 profile 做许可证闸门。"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

from app import config
from app.adapters.base import Adapter, Capability

MANIFEST = Path(__file__).with_name("manifest.json")


def _entries() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _instantiate(entry: dict) -> Adapter:
    mod = importlib.import_module(entry["module"])
    cls = getattr(mod, entry["class"])
    return cls(entry)


def all_adapters(kind: str | None = None, include_noncommercial: bool | None = None) -> list[Adapter]:
    if include_noncommercial is None:
        include_noncommercial = config.PROFILE != "commercial"
    result: list[Adapter] = []
    for entry in sorted(_entries(), key=lambda e: e.get("priority", 100)):
        if kind and entry["kind"] != kind:
            continue
        if not include_noncommercial and not entry.get("commercial_ok", False):
            continue
        try:
            result.append(_instantiate(entry))
        except Exception as exc:  # 引擎缺失不应拖垮服务
            result.append(_BrokenAdapter(entry, str(exc)))
    return result


class _BrokenAdapter:
    """占位：适配器模块导入失败时仍能在 doctor 中报错。"""

    def __init__(self, entry: dict, error: str):
        self.id = entry["id"]
        self.kind = entry["kind"]
        self.license = entry.get("license", "unknown")
        self.commercial_ok = bool(entry.get("commercial_ok"))
        self.requires_gpu = bool(entry.get("requires_gpu"))
        self._error = error

    def probe(self) -> Capability:
        return Capability(False, f"适配器加载失败: {self._error}")

    def run(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError(self._error)


def pick(kind: str) -> Adapter | None:
    """按优先级返回第一个 probe 通过的适配器。"""
    for adapter in all_adapters(kind):
        try:
            if adapter.probe().available:
                return adapter
        except Exception:
            continue
    return None
