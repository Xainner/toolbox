"""App3 Toolbox — API FastAPI."""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.registry import load_all, get, list_metas, REGISTRY
from tools.common import ToolError

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WORK_ROOT = DATA_DIR / "jobs"
DB_PATH = DATA_DIR / "app3.db"

load_all()

app = FastAPI(title="App3 Toolbox API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_MB = 200


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            tool_id TEXT,
            files INTEGER,
            status TEXT,
            detail TEXT,
            output_name TEXT,
            duration_ms INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )"""
    )
    return conn


def log_job(job_id: str, tool_id: str, files: int, status: str, detail: str = "",
            output_name: str = "", duration_ms: int | None = None):
    with closing(db()) as conn:
        conn.execute(
            "INSERT INTO jobs (id, tool_id, files, status, detail, output_name, duration_ms) VALUES (?,?,?,?,?,?,?)",
            (job_id, tool_id, files, status, detail[:500], output_name, duration_ms),
        )
        conn.commit()


@app.get("/api/health")
def health():
    return {"status": "ok", "tools": len(REGISTRY)}


@app.get("/api/tools")
def tools():
    return {"tools": list_metas()}


@app.post("/api/tools/{tool_id}/run")
async def run_tool(tool_id: str, files: list[UploadFile] = File(...), options: str = Form("{}")):
    reg = get(tool_id)
    if not reg:
        raise HTTPException(404, f"Herramienta desconocida: {tool_id}")

    try:
        opts = json.loads(options or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Opciones inválidas")

    job_id = uuid.uuid4().hex[:12]
    workdir = WORK_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    total_bytes = 0
    try:
        for f in files:
            dest = workdir / Path(f.filename or "file").name
            size = 0
            with open(dest, "wb") as out:
                while chunk := await f.read(1024 * 1024):
                    size += len(chunk)
                    if total_bytes + size > MAX_UPLOAD_MB * 1024 * 1024:
                        raise ToolError(f"Límite de {MAX_UPLOAD_MB} MB por trabajo excedido")
                    out.write(chunk)
            total_bytes += size
            saved.append(dest)

        t0 = time.monotonic()
        outputs = reg.handler(saved, opts, workdir)
        duration_ms = int((time.monotonic() - t0) * 1000)
        if not outputs:
            raise ToolError("La herramienta no produjo salida")

        # Empaquetar: si hay varios outputs, zip; si uno, tal cual
        final = outputs[0]
        input_size = sum(p.stat().st_size for p in saved)
        result = {
            "job_id": job_id,
            "download_url": f"/api/download/{job_id}",
            "output_name": final.name,
            "output_size": final.stat().st_size,
            "input_size": input_size,
            "duration_ms": duration_ms,
        }
        log_job(job_id, tool_id, len(files), "ok", "", final.name, duration_ms)
        return JSONResponse(result)
    except ToolError as e:
        log_job(job_id, tool_id, len(files), "error", str(e))
        raise HTTPException(422, str(e))
    except HTTPException:
        raise
    except Exception as e:
        log_job(job_id, tool_id, len(files), "error", repr(e))
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Error interno: {e}")
    finally:
        # limpiar archivos subidos que no son el resultado final
        if saved:
            keep = set()
            try:
                keep = {p.resolve() for p in [final]}
            except Exception:
                pass
            for p in saved:
                try:
                    if p.resolve() not in keep:
                        p.unlink(missing_ok=True)
                except Exception:
                    pass


@app.get("/api/download/{job_id}")
def download(job_id: str):
    workdir = WORK_ROOT / job_id
    if not workdir.is_dir():
        raise HTTPException(404, "Trabajo no encontrado o expirado")
    files = [p for p in workdir.iterdir() if p.is_file()]
    if not files:
        raise HTTPException(404, "Sin resultado")
    f = max(files, key=lambda p: p.stat().st_mtime)
    return FileResponse(f, filename=f.name)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    workdir = WORK_ROOT / job_id
    if workdir.is_dir():
        shutil.rmtree(workdir, ignore_errors=True)
    return {"deleted": job_id}


@app.get("/api/stats")
def stats(limit: int = 100):
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT id, tool_id, files, status, duration_ms, created_at FROM jobs ORDER BY created_at DESC LIMIT ?",
            (min(limit, 1000),),
        ).fetchall()
    keys = ["id", "tool_id", "files", "status", "duration_ms", "created_at"]
    return {"jobs": [dict(zip(keys, r)) for r in rows]}


@app.on_event("startup")
def startup():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    with closing(db()) as _:
        pass
