import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.adapters import registry  # noqa: E402


def test_manifest_entries_valid():
    entries = registry._entries()
    assert entries
    for entry in entries:
        assert entry["id"]
        assert entry["kind"] in ("photo", "scan_upload", "scan_video")
        assert entry["module"].startswith("app.adapters.")
        assert entry["class"]
        assert "license" in entry


def test_all_adapters_load():
    adapters = registry.all_adapters()
    assert adapters
    for adapter in adapters:
        assert adapter.id
        assert isinstance(adapter.commercial_ok, bool)


def test_commercial_profile_filters_noncommercial(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "PROFILE", "commercial")
    adapters = registry.all_adapters(include_noncommercial=False)
    assert all(a.commercial_ok for a in adapters)
