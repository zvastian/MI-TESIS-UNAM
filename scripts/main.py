from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lab_orchestrator import LabOrchestrator, LabBusyError


BASE_DIR = Path(__file__).resolve().parents[1]

app = FastAPI(
    title="Laboratorio de Tesis API",
    version="0.1.0"
)

orchestrator = LabOrchestrator(BASE_DIR)


# ─── STATIC FRONTEND ──────────────────────────────────────────────────────────

STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    index_path = STATIC_DIR / "index.html"

    if not index_path.exists():
        return {
            "ok": True,
            "message": "Laboratorio de Tesis API activa. Falta static/index.html."
        }

    return FileResponse(index_path)


# ─── MODELS ───────────────────────────────────────────────────────────────────

class StudyPeriod(BaseModel):
    applies: bool = False
    start_year: int | None = None
    end_year: int | None = None
    label: str | None = None


class LabInput(BaseModel):
    title: str = Field(..., min_length=3)
    keywords: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    program: str | None = None
    degree: str | None = None
    plantel: str | None = None
    study_period: StudyPeriod | str | None = None


class ProjectRequest(BaseModel):
    project_id: str


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def handle_error(exc: Exception):
    if isinstance(exc, LabBusyError):
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        )

    if isinstance(exc, FileNotFoundError):
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

    raise HTTPException(
        status_code=500,
        detail=str(exc)
    )


# ─── API ENDPOINTS ────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "laboratorio-tesis",
    }


@app.post("/api/lab/run-basic")
def run_basic(lab_input: LabInput):
    try:
        result = orchestrator.run_basic(lab_input.model_dump())
        return {
            "ok": True,
            "project_id": result["project_id"],
            "data": result,
        }
    except Exception as exc:
        handle_error(exc)


@app.post("/api/lab/run-bibliography")
def run_bibliography(req: ProjectRequest):
    try:
        result = orchestrator.run_bibliography(req.project_id)
        return {
            "ok": True,
            "project_id": result["project_id"],
            "data": result,
        }
    except Exception as exc:
        handle_error(exc)


@app.post("/api/lab/run-advisors")
def run_advisors(req: ProjectRequest):
    try:
        result = orchestrator.run_advisors(req.project_id)
        return {
            "ok": True,
            "project_id": result["project_id"],
            "data": result,
        }
    except Exception as exc:
        handle_error(exc)


@app.get("/api/lab/{project_id}")
def get_project(project_id: str):
    try:
        result = orchestrator.consolidate_project(project_id)
        return {
            "ok": True,
            "project_id": result["project_id"],
            "data": result,
        }
    except Exception as exc:
        handle_error(exc)