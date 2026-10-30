"""FastAPI 服务：任务 API + 资产 API + 预览页托管。"""
from __future__ import annotations

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.adapters import registry
from app.jobs import JobLogger, JobStore, Worker

MAX_UPLOAD_MB = 300


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = JobStore()
    worker = Worker(store)
    worker.start()
    app.state.store = store
    app.state.worker = worker
    yield
    worker.stop()


app = FastAPI(title="Digital Companion · 本地原型", lifespan=lifespan)


def store() -> JobStore:
    return app.state.store


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "profile": config.PROFILE}


@app.get("/api/capabilities")
def capabilities() -> dict:
    items = []
    for adapter in registry.all_adapters():
        try:
            cap = adapter.probe()
        except Exception as exc:  # noqa: BLE001
            cap = None
            detail = f"probe 失败: {exc}"
        else:
            detail = cap.detail
        items.append({
            "id": adapter.id,
            "kind": adapter.kind,
            "license": adapter.license,
            "commercial_ok": adapter.commercial_ok,
            "available": bool(cap and cap.available),
            "detail": detail,
        })
    return {
        "profile": config.PROFILE,
        "free_gb": round(config.free_gb(), 1),
        "adapters": items,
    }


@app.post("/api/jobs")
async def create_job(
    kind: str = Form(...),
    files: list[UploadFile] = File(...),
    options: str = Form("{}"),
):
    if kind not in ("photo", "scan_upload", "scan_video"):
        raise HTTPException(400, f"未知任务类型: {kind}")
    try:
        opts = json.loads(options or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "options 不是合法 JSON")

    job_id = store().create(kind, [], opts)
    job_dir = config.UPLOADS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    total = 0
    try:
        for i, upload in enumerate(files):
            suffix = Path(upload.filename or "").suffix or ".bin"
            target = job_dir / f"{i:02d}{suffix}"
            with target.open("wb") as f:
                while chunk := await upload.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD_MB * 1024 * 1024:
                        raise HTTPException(413, f"上传超过 {MAX_UPLOAD_MB}MB")
                    f.write(chunk)
            saved.append(str(target))
        if not saved:
            raise HTTPException(400, "没有收到文件")
    except Exception as exc:
        store().update(job_id, status="failed", stage="failed", error=str(exc))
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    store().update_payload(job_id, {"inputs": saved, "options": opts})
    return {"id": job_id}


@app.get("/api/jobs")
def list_jobs(limit: int = 50) -> list[dict]:
    return store().list(limit)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = store().get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job


@app.get("/api/jobs/{job_id}/log", response_class=PlainTextResponse)
def job_log(job_id: str) -> str:
    return JobLogger(job_id).tail(400)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if not store().get(job_id):
        raise HTTPException(404, "任务不存在")
    store().request_cancel(job_id)
    return {"ok": True}


def _avatar_meta(avatar_id: str) -> dict:
    meta_path = config.AVATARS / avatar_id / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, "资产不存在")
    return json.loads(meta_path.read_text(encoding="utf-8"))


@app.get("/api/avatars")
def list_avatars() -> list[dict]:
    items = []
    for d in sorted(config.AVATARS.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.append({
            "avatar_id": d.name,
            "source_kind": meta.get("source", {}).get("kind"),
            "engine": meta.get("source", {}).get("engine"),
            "tiers": meta.get("tiers", {}),
            "quality": meta.get("quality"),
            "created_at": d.stat().st_mtime,
        })
    return items


@app.get("/api/avatars/{avatar_id}")
def avatar_meta(avatar_id: str) -> dict:
    return _avatar_meta(avatar_id)


@app.get("/api/avatars/{avatar_id}/files/{name}")
def avatar_file(avatar_id: str, name: str):
    if "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "非法文件名")
    path = config.AVATARS / avatar_id / name
    if not path.exists():
        raise HTTPException(404, "文件不存在")
    media = "model/gltf-binary" if name.endswith(".glb") else None
    return FileResponse(path, media_type=media, filename=name)


@app.delete("/api/avatars/{avatar_id}")
def delete_avatar(avatar_id: str) -> dict:
    target = config.AVATARS / avatar_id
    if not target.exists():
        raise HTTPException(404, "资产不存在")
    shutil.rmtree(target, ignore_errors=True)
    shutil.rmtree(config.TMP / avatar_id, ignore_errors=True)
    shutil.rmtree(config.UPLOADS / avatar_id, ignore_errors=True)
    return {"ok": True}


# 预览页：有构建产物就托管，没有则给提示
if (config.WEB_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(config.WEB_DIST), html=True), name="web")
else:
    @app.get("/", response_class=HTMLResponse)
    def placeholder() -> str:
        return (
            "<h1>预览页尚未构建</h1>"
            "<p>在 <code>web/</code> 下执行 <code>npm install &amp;&amp; npm run build</code>，"
            "或开发时执行 <code>npm run dev</code>。</p>"
        )
