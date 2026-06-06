from __future__ import annotations

from threading import RLock
from fastapi import APIRouter, HTTPException

from workshop_schema import AnalysisRequest, AnalysisResponse, ExactSearchRequest
from workshop_service import get_workshop_service


router = APIRouter(prefix="/api/workshop", tags=["workshop"])

WORKSHOP_TOOL_LOCK = RLock()


@router.get("/health")
def workshop_health():
    try:
        service = get_workshop_service()
        return {
            "ok": True,
            "source": str(service.dataset_path),
            "columns": service.columns,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/facets")
def workshop_facets():
    try:
        return get_workshop_service().facets()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/exact")
def workshop_exact(req: ExactSearchRequest):
    try:
        return get_workshop_service().exact_search(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/analyze", response_model=AnalysisResponse)
def analyze_workshop(req: AnalysisRequest):
    svc = get_workshop_service()
    return svc.analyze(req)


@router.get("/tools/bubbles")
def workshop_tool_bubbles(dimension: str = "advisor", limit: int = 50):
    try:
        with WORKSHOP_TOOL_LOCK:
            return get_workshop_service().tool_bubbles(dimension=dimension, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tools/ranking")
def workshop_tool_ranking(
    dimension: str = "program",
    limit: int = 25,
    year_min: int | None = None,
    year_max: int | None = None,
    areas: str | None = None,
    levels: str | None = None,
):
    try:
        area_values = [v.strip() for v in areas.split(",")] if areas else []
        level_values = [v.strip() for v in levels.split(",")] if levels else []
        with WORKSHOP_TOOL_LOCK:
            return get_workshop_service().tool_ranking(
                dimension=dimension,
                limit=limit,
                year_min=year_min,
                year_max=year_max,
                areas=area_values,
                levels=level_values,
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tools/heatmap")
def workshop_tool_heatmap(
    dimension: str = "area",
    limit: int = 25,
    year_min: int | None = None,
    year_max: int | None = None,
    areas: str | None = None,
    levels: str | None = None,
    scale: str = "absolute",
):
    try:
        area_values = [v.strip() for v in areas.split(",")] if areas else []
        level_values = [v.strip() for v in levels.split(",")] if levels else []
        with WORKSHOP_TOOL_LOCK:
            return get_workshop_service().tool_heatmap(
                dimension=dimension,
                limit=limit,
                year_min=year_min,
                year_max=year_max,
                areas=area_values,
                levels=level_values,
                scale=scale,
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))




# WCT HEATMAP MATRIX ROUTE START

@router.get("/tools/heatmap-matrix")
def workshop_tool_heatmap_matrix(
    matrix: str = "program_level",
    limit: int = 10,
    year_min: int | None = None,
    year_max: int | None = None,
    scale: str = "log",
):
    try:
        with WORKSHOP_TOOL_LOCK:
            return get_workshop_service().tool_heatmap_matrix(
                matrix=matrix,
                limit=limit,
                year_min=year_min,
                year_max=year_max,
                scale=scale,
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# WCT HEATMAP MATRIX ROUTE END


# WCT SERIES ROUTE START

@router.get("/tools/series")
def workshop_tool_series(
    dimension: str = "level",
    limit: int = 8,
    year_min: int | None = 2000,
    year_max: int | None = 2026,
):
    try:
        with WORKSHOP_TOOL_LOCK:
            return get_workshop_service().tool_series(
                dimension=dimension,
                limit=limit,
                year_min=year_min,
                year_max=year_max,
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# WCT SERIES ROUTE END

