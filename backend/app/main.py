"""Toolbox API: catálogo, ejecución síncrona compatible y cola local."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image
from pypdf import PdfReader

from app.registry import load_all, get, list_metas, REGISTRY
from tools.common import ToolError

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WORK_ROOT = DATA_DIR / "jobs"
DB_PATH = DATA_DIR / "app3.db"
MAX_UPLOAD_MB = int(os.getenv("TOOLBOX_MAX_UPLOAD_MB", "200"))
JOB_TTL_HOURS = int(os.getenv("TOOLBOX_JOB_TTL_HOURS", "24"))
WORKERS = max(1, int(os.getenv("TOOLBOX_WORKERS", "2")))
AI_WORKERS = max(1, int(os.getenv("TOOLBOX_AI_WORKERS", "1")))

load_all()
app = FastAPI(title="Toolbox API", version="0.2.0")
executor = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="toolbox")
ai_executor = ThreadPoolExecutor(max_workers=AI_WORKERS, thread_name_prefix="toolbox-ai")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, tool_id TEXT, files INTEGER, status TEXT,
            detail TEXT, output_name TEXT, duration_ms INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            progress INTEGER DEFAULT 0, stage TEXT DEFAULT '',
            input_size INTEGER DEFAULT 0, output_size INTEGER DEFAULT 0,
            artifacts TEXT DEFAULT '[]'
        )"""
    )
    columns = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    migrations = {
        "progress": "INTEGER DEFAULT 0", "stage": "TEXT DEFAULT ''",
        "input_size": "INTEGER DEFAULT 0", "output_size": "INTEGER DEFAULT 0",
        "artifacts": "TEXT DEFAULT '[]'",
    }
    for name, spec in migrations.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {spec}")
    conn.commit()
    return conn


def update_job(job_id: str, **values):
    allowed = {"status", "detail", "output_name", "duration_ms", "progress", "stage",
               "input_size", "output_size", "artifacts"}
    values = {k: v for k, v in values.items() if k in allowed}
    if not values:
        return
    if isinstance(values.get("artifacts"), list):
        values["artifacts"] = json.dumps(values["artifacts"], ensure_ascii=False)
    with closing(db()) as conn:
        assigns = ", ".join(f"{k}=?" for k in values)
        conn.execute(f"UPDATE jobs SET {assigns} WHERE id=?", [*values.values(), job_id])
        conn.commit()


def create_job(job_id: str, tool_id: str, count: int, input_size: int):
    with closing(db()) as conn:
        conn.execute(
            "INSERT INTO jobs (id,tool_id,files,status,progress,stage,input_size) VALUES (?,?,?,?,?,?,?)",
            (job_id, tool_id, count, "queued", 5, "En cola", input_size),
        )
        conn.commit()


def _mime(path: Path) -> str:
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".pdf": "application/pdf", ".zip": "application/zip",
            ".txt": "text/plain"}.get(path.suffix.lower(), "application/octet-stream")


def classify_artifacts(workdir: Path, outputs: list[Path]) -> list[dict]:
    primary = {p.resolve() for p in outputs}
    artifacts = []
    for path in sorted((p for p in workdir.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime):
        if path.name.startswith("_source"):
            continue
        kind = "result" if path.resolve() in primary else "preview"
        low = path.name.lower()
        if "mask" in low or "mascara" in low:
            kind = "mask"
        elif path.suffix.lower() == ".txt":
            kind = "sidecar"
        artifacts.append({"id": path.name, "name": path.name, "kind": kind,
                          "mime": _mime(path), "size": path.stat().st_size,
                          "url": f"/api/jobs/{workdir.name}/artifacts/{path.name}"})
    return artifacts


def validate_saved(paths: list[Path], accept: list[str]):
    for path in paths:
        if path.suffix.lower() not in accept:
            raise ToolError(f"Formato no permitido: {path.suffix or path.name}")
        if path.suffix.lower() == ".pdf":
            try:
                PdfReader(path, strict=False)
            except Exception as exc:
                raise ToolError(f"PDF inválido o dañado: {path.name}") from exc
        elif path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}:
            try:
                with Image.open(path) as image:
                    if image.width * image.height > 120_000_000:
                        raise ToolError(f"Imagen demasiado grande: {path.name}")
                    image.verify()
            except ToolError:
                raise
            except Exception as exc:
                raise ToolError(f"Imagen inválida o dañada: {path.name}") from exc


async def save_uploads(files: list[UploadFile], workdir: Path, accept: list[str]) -> tuple[list[Path], int]:
    saved, total = [], 0
    input_dir = workdir / "_inputs"
    input_dir.mkdir(exist_ok=True)
    for index, upload in enumerate(files):
        clean_name = Path(upload.filename or f"archivo-{index}").name
        dest = input_dir / clean_name
        if dest.exists():
            dest = input_dir / f"{index:03d}-{clean_name}"
        with open(dest, "wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_MB * 1024 * 1024:
                    raise ToolError(f"Límite de {MAX_UPLOAD_MB} MB por trabajo excedido")
                output.write(chunk)
        saved.append(dest)
    validate_saved(saved, accept)
    return saved, total


def _run_handler(job_id: str, tool_id: str, paths: list[Path], opts: dict, async_job: bool = True):
    reg = get(tool_id)
    if not reg:
        raise ToolError(f"Herramienta desconocida: {tool_id}")
    workdir = WORK_ROOT / job_id
    started = time.monotonic()
    if async_job:
        update_job(job_id, status="running", progress=20, stage="Preparando archivos")
    try:
        if async_job:
            update_job(job_id, progress=45, stage="Procesando")
        outputs = reg.handler(paths, opts, workdir)
        if not outputs:
            raise ToolError("La herramienta no produjo salida")
        if async_job:
            update_job(job_id, progress=90, stage="Preparando resultado")
        duration = int((time.monotonic() - started) * 1000)
        artifacts = classify_artifacts(workdir, outputs)
        primary = outputs[0]
        result = {"job_id": job_id, "status": "succeeded",
                  "download_url": f"/api/download/{job_id}", "output_name": primary.name,
                  "output_size": primary.stat().st_size,
                  "input_size": sum(p.stat().st_size for p in paths if p.exists()),
                  "duration_ms": duration, "artifacts": artifacts}
        if async_job:
            update_job(job_id, status="succeeded", progress=100, stage="Listo", detail="",
                       output_name=primary.name, output_size=primary.stat().st_size,
                       duration_ms=duration, artifacts=artifacts)
        return result
    except Exception as exc:
        if async_job:
            update_job(job_id, status="failed", progress=100, stage="Error", detail=str(exc)[:500])
        raise


def execute_background(job_id: str, tool_id: str, paths: list[Path], opts: dict):
    try:
        _run_handler(job_id, tool_id, paths, opts, True)
    except Exception:
        import traceback
        traceback.print_exc()


def job_payload(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["artifacts"] = json.loads(data.get("artifacts") or "[]")
    data["error"] = data.get("detail") if data.get("status") == "failed" else None
    data["download_url"] = f"/api/download/{data['id']}" if data.get("status") == "succeeded" else None
    data["job_id"] = data.pop("id")
    return data


@app.get("/api/health")
def health():
    providers = ["CPUExecutionProvider"]
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
    except Exception:
        pass
    return {"status": "ok", "tools": len(REGISTRY), "workers": WORKERS, "ai_workers": AI_WORKERS,
            "providers": providers, "models_dir": os.getenv("U2NET_HOME", str(BASE_DIR / "models"))}


@app.get("/api/tools")
def tools():
    return {"tools": list_metas()}


@app.post("/api/tools/{tool_id}/jobs", status_code=202)
async def enqueue_tool(tool_id: str, files: list[UploadFile] = File(...), options: str = Form("{}")):
    reg = get(tool_id)
    if not reg:
        raise HTTPException(404, f"Herramienta desconocida: {tool_id}")
    try:
        opts = json.loads(options or "{}")
        job_id = uuid.uuid4().hex[:12]
        workdir = WORK_ROOT / job_id
        workdir.mkdir(parents=True, exist_ok=True)
        saved, total = await save_uploads(files, workdir, reg.meta.accept)
        create_job(job_id, tool_id, len(saved), total)
        cleanup_expired()
        (ai_executor if reg.meta.ai else executor).submit(execute_background, job_id, tool_id, saved, opts)
        return {"job_id": job_id, "status": "queued", "progress": 5, "stage": "En cola"}
    except ToolError as exc:
        raise HTTPException(422, str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Opciones inválidas") from exc


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with closing(db()) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Trabajo no encontrado")
    return job_payload(row)


@app.get("/api/jobs/{job_id}/artifacts/{artifact_id}")
def artifact(job_id: str, artifact_id: str):
    workdir = WORK_ROOT / job_id
    target = workdir / Path(artifact_id).name
    if not target.is_file() or target.parent.resolve() != workdir.resolve():
        raise HTTPException(404, "Artefacto no encontrado")
    return FileResponse(target, filename=target.name, media_type=_mime(target))


@app.post("/api/jobs/{job_id}/compose")
async def compose_cutout(job_id: str, mask: UploadFile = File(...),
                         background: str = Form("transparent"), color: str = Form("#ffffff")):
    workdir = WORK_ROOT / job_id
    sources = list(workdir.glob("_source*.png"))
    if not sources:
        raise HTTPException(404, "Este trabajo no tiene una fuente editable")
    mask_path = workdir / "mascara-editada.png"
    with open(mask_path, "wb") as output:
        while chunk := await mask.read(1024 * 1024):
            output.write(chunk)
    try:
        source = Image.open(sources[0]).convert("RGBA")
        alpha = Image.open(mask_path).convert("L").resize(source.size, Image.Resampling.LANCZOS)
        source.putalpha(alpha)
        if background == "transparent":
            final = source
        else:
            bg_color = "white" if background == "white" else color
            final = Image.new("RGBA", source.size, bg_color)
            final.alpha_composite(source)
        out = workdir / "recorte-editado.png"
        final.save(out)
        return {"artifact": {"id": out.name, "name": out.name, "kind": "result",
                "mime": "image/png", "size": out.stat().st_size,
                "url": f"/api/jobs/{job_id}/artifacts/{out.name}"}}
    except Exception as exc:
        raise HTTPException(422, f"Máscara inválida: {exc}") from exc


@app.post("/api/tools/{tool_id}/run")
async def run_tool(tool_id: str, files: list[UploadFile] = File(...), options: str = Form("{}")):
    reg = get(tool_id)
    if not reg:
        raise HTTPException(404, f"Herramienta desconocida: {tool_id}")
    job_id = uuid.uuid4().hex[:12]
    workdir = WORK_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        opts = json.loads(options or "{}")
        saved, total = await save_uploads(files, workdir, reg.meta.accept)
        create_job(job_id, tool_id, len(saved), total)
        result = _run_handler(job_id, tool_id, saved, opts, False)
        update_job(job_id, status="succeeded", progress=100, stage="Listo", detail="",
                   output_name=result["output_name"], output_size=result["output_size"],
                   duration_ms=result["duration_ms"], artifacts=result["artifacts"])
        return JSONResponse(result)
    except ToolError as exc:
        update_job(job_id, status="failed", progress=100, stage="Error", detail=str(exc))
        raise HTTPException(422, str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Opciones inválidas") from exc
    except Exception as exc:
        update_job(job_id, status="failed", progress=100, stage="Error", detail=str(exc))
        raise HTTPException(500, f"Error interno: {exc}") from exc


@app.get("/api/download/{job_id}")
def download(job_id: str):
    with closing(db()) as conn:
        row = conn.execute("SELECT output_name FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row or not row["output_name"]:
        raise HTTPException(404, "Trabajo no encontrado o sin resultado")
    target = WORK_ROOT / job_id / Path(row["output_name"]).name
    if not target.is_file():
        raise HTTPException(404, "Resultado expirado")
    return FileResponse(target, filename=target.name, media_type=_mime(target))


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    shutil.rmtree(WORK_ROOT / Path(job_id).name, ignore_errors=True)
    return {"deleted": job_id}


@app.get("/api/stats")
def stats(limit: int = 100):
    with closing(db()) as conn:
        rows = conn.execute("SELECT id,tool_id,files,status,duration_ms,created_at FROM jobs ORDER BY created_at DESC LIMIT ?",
                            (min(limit, 1000),)).fetchall()
    return {"jobs": [dict(r) for r in rows]}


def cleanup_expired():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=JOB_TTL_HOURS)
    with closing(db()) as conn:
        rows = conn.execute("SELECT id,created_at FROM jobs").fetchall()
        for row in rows:
            try:
                created = datetime.fromisoformat(row["created_at"]).replace(tzinfo=timezone.utc)
                if created < cutoff:
                    shutil.rmtree(WORK_ROOT / row["id"], ignore_errors=True)
            except (TypeError, ValueError):
                continue


@app.on_event("startup")
def startup():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    with closing(db()) as conn:
        conn.execute("UPDATE jobs SET status='failed',stage='Interrumpido',detail='Servidor reiniciado',progress=100 WHERE status IN ('queued','running')")
        conn.commit()
    cleanup_expired()


@app.on_event("shutdown")
def shutdown():
    executor.shutdown(wait=False, cancel_futures=True)
    ai_executor.shutdown(wait=False, cancel_futures=True)
