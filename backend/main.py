"""FastAPI backend: upload audio/video -> faster-whisper transcription.

Run:  ../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
(or just use ../run.sh from the project root)
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import transcribe as engine

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# docs_url=None: free up /docs for our own model documentation page.
app = FastAPI(title="NEUROSCRIBE", docs_url=None, redoc_url=None)

# In-memory job store: job_id -> {status, progress, result, error}
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _set_job(job_id: str, **fields) -> None:
    with _jobs_lock:
        _jobs.setdefault(job_id, {}).update(fields)


def _run_job(job_id: str, audio_path: str, opts: dict) -> None:
    def progress(done: float, total: float) -> None:
        pct = 0 if not total else min(0.99, done / total)
        _set_job(job_id, progress=round(pct, 4))

    try:
        _set_job(job_id, status="transcribing", progress=0.0)
        result = engine.transcribe(audio_path, progress=progress, **opts)
        _set_job(job_id, status="done", progress=1.0, result=result)
    except Exception as exc:  # noqa: BLE001
        _set_job(job_id, status="error", error=str(exc))
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass


@app.post("/api/transcribe")
async def start_transcribe(
    file: UploadFile = File(...),
    model_size: str = Form(engine.DEFAULT_MODEL),
    compute_type: str = Form(engine.DEFAULT_COMPUTE_TYPE),
    language: str = Form(engine.DEFAULT_LANGUAGE),
    beam_size: int = Form(engine.DEFAULT_BEAM_SIZE),
    vad: bool = Form(engine.DEFAULT_VAD),
):
    suffix = Path(file.filename or "audio").suffix or ".mp4"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as out:
        shutil.copyfileobj(file.file, out)

    opts = {
        "model_size": model_size,
        "compute_type": compute_type,
        "language": language,
        "beam_size": beam_size,
        "vad": vad,
    }
    job_id = uuid.uuid4().hex
    _set_job(job_id, status="queued", progress=0.0, filename=file.filename)
    threading.Thread(target=_run_job, args=(job_id, tmp_path, opts), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/options")
async def options():
    """Selectable options + metadata, consumed by the UI and docs page."""
    return {
        "models": engine.MODELS,
        "compute_types": engine.COMPUTE_TYPES,
        "languages": engine.LANGUAGES,
        "defaults": {
            "model_size": engine.DEFAULT_MODEL,
            "compute_type": engine.DEFAULT_COMPUTE_TYPE,
            "language": engine.DEFAULT_LANGUAGE,
            "beam_size": engine.DEFAULT_BEAM_SIZE,
            "vad": engine.DEFAULT_VAD,
        },
    }


@app.get("/api/progress/{job_id}")
async def get_progress(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(job)


@app.get("/api/health")
async def health():
    return {"ok": True, "model": engine.DEFAULT_MODEL, "compute_type": engine.DEFAULT_COMPUTE_TYPE}


# --- Serve the frontend ------------------------------------------------------
@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/docs")
async def docs_page():
    return FileResponse(FRONTEND_DIR / "docs.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="static")
