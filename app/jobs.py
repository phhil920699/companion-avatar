"""SQLite 任务队列 + 单线程 worker。"""
from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.runner import run_pipeline

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT DEFAULT '',
    progress REAL DEFAULT 0,
    error TEXT DEFAULT '',
    avatar_id TEXT DEFAULT '',
    payload TEXT DEFAULT '{}',
    cancel_requested INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def __init__(self, path: Path = config.DB_PATH):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def create(self, kind: str, inputs: list[str], options: dict | None = None, status: str = "queued") -> str:
        job_id = "av_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        payload = json.dumps({"inputs": inputs, "options": options or {}}, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT INTO jobs (id, kind, status, payload, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?)",
                (job_id, kind, status, payload, _now(), _now()),
            )
            self._conn.commit()
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row(row) if row else None

    def list(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["payload"] = json.loads(d.get("payload") or "{}")
        except Exception:
            d["payload"] = {}
        return d

    def update(self, job_id: str, **fields) -> None:
        fields["updated_at"] = _now()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self._conn.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))
            self._conn.commit()

    def update_payload(self, job_id: str, payload: dict) -> None:
        self.update(job_id, payload=json.dumps(payload, ensure_ascii=False))

    def request_cancel(self, job_id: str) -> None:
        self.update(job_id, cancel_requested=1)

    def cancel_requested(self, job_id: str) -> bool:
        job = self.get(job_id)
        return bool(job and job.get("cancel_requested"))

    def claim_next(self) -> dict | None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                self._conn.commit()
                return None
            self._conn.execute(
                "UPDATE jobs SET status='running', updated_at=? WHERE id=?",
                (_now(), row["id"]),
            )
            self._conn.commit()
        return self._row(row)


class JobLogger:
    def __init__(self, job_id: str):
        self.path = config.TMP / job_id / "log.txt"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def __call__(self, line: str) -> None:
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line.rstrip() + "\n")

    def tail(self, n: int = 400) -> str:
        if not self.path.exists():
            return ""
        lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])


class Worker(threading.Thread):
    def __init__(self, store: JobStore):
        super().__init__(daemon=True, name="companion-worker")
        self.store = store
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            job = self.store.claim_next()
            if job is None:
                time.sleep(0.5)
                continue
            self._execute(job)

    def _execute(self, job: dict) -> None:
        job_id = job["id"]
        logger = JobLogger(job_id)
        try:
            self.store.update(job_id, stage="starting", progress=0.05)
            inputs = job["payload"].get("inputs", [])
            options = job["payload"].get("options", {})
            avatar_id, meta = run_pipeline(
                job_id,
                job["kind"],
                inputs,
                options,
                logger,
                cancel=lambda: self.store.cancel_requested(job_id),
            )
            if self.store.cancel_requested(job_id):
                self.store.update(job_id, status="canceled", stage="canceled", progress=0)
                return
            self.store.update(
                job_id, status="succeeded", stage="done", progress=1.0,
                avatar_id=avatar_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger(f"[error] {exc}")
            status = "canceled" if self.store.cancel_requested(job_id) else "failed"
            self.store.update(job_id, status=status, stage=status, error=str(exc))
        finally:
            # 任务结束后不再保留上传的人脸原图；只保留 log.txt 便于排查
            shutil.rmtree(config.UPLOADS / job_id, ignore_errors=True)
            workdir = config.TMP / job_id
            if workdir.exists():
                for child in workdir.iterdir():
                    if child.name == "log.txt":
                        continue
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
