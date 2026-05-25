from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lab_orchestrator import LabBusyError, LabOrchestrator
from build_graph_neighborhood import build_graph_from_query, json_sanitize


BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"

orch = LabOrchestrator(BASE_DIR)

app = FastAPI(
    title="MiTesis UNAM API",
    version="0.1.0",
    description="API local para Laboratorio de Tesis UNAM",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StudyPeriod(BaseModel):
    applies: bool = False
    start_year: int | None = None
    end_year: int | None = None
    label: str | None = None


class LabInput(BaseModel):
    title: str = Field(..., min_length=3)
    keywords: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    program: str | None = ""
    degree: str | None = ""
    plantel: str | None = ""
    study_period: StudyPeriod | dict[str, Any] | None = None


class ProjectRequest(BaseModel):
    project_id: str = Field(..., min_length=3)


def error_response(exc: Exception):
    return {
        "ok": False,
        "error": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "MiTesis UNAM API",
        "base_dir": str(BASE_DIR),
        "static_dir_exists": STATIC_DIR.exists(),
    }


@app.get("/api/explore/neighborhood/{thesis_id}")
def get_explore_neighborhood(thesis_id: str, top_k: int = 100):
    """
    Construye el vecindario semántico local de una tesis existente
    para visualizarla como centro del modo Universo / Analítico.
    """
    try:
        thesis_id = str(thesis_id or "").strip()

        if not thesis_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "error": "InvalidThesisId",
                    "message": "Debe proporcionar thesis_id.",
                },
            )

        graph = build_graph_from_query(
            query="",
            top_k=top_k,
            thesis_id=thesis_id,
        )

        return {
            "ok": True,
            "data": json_sanitize(graph),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "error": "ThesisNotFound",
                "message": str(exc),
            },
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=error_response(exc),
        )


@app.post("/api/lab/run-basic")
def run_basic(payload: LabInput):
    try:
        data = payload.model_dump()
        result = orch.run_basic(data)

        return {
            "ok": True,
            "data": result,
        }

    except LabBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "ok": False,
                "error": "LabBusyError",
                "message": str(exc),
            },
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=error_response(exc),
        )


@app.post("/api/lab/run-bibliography")
def run_bibliography(payload: ProjectRequest):
    try:
        result = orch.run_bibliography(payload.project_id)

        return {
            "ok": True,
            "data": result,
        }

    except LabBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "ok": False,
                "error": "LabBusyError",
                "message": str(exc),
            },
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "error": "FileNotFoundError",
                "message": str(exc),
            },
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=error_response(exc),
        )


@app.post("/api/lab/run-advisors")
def run_advisors(payload: ProjectRequest):
    try:
        result = orch.run_advisors(payload.project_id)

        return {
            "ok": True,
            "data": result,
        }

    except LabBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "ok": False,
                "error": "LabBusyError",
                "message": str(exc),
            },
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "error": "FileNotFoundError",
                "message": str(exc),
            },
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=error_response(exc),
        )


@app.get("/api/lab/project/{project_id}")
def get_project(project_id: str):
    try:
        result = orch.consolidate_project(project_id)

        return {
            "ok": True,
            "data": result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "error": "FileNotFoundError",
                "message": str(exc),
            },
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=error_response(exc),
        )


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
