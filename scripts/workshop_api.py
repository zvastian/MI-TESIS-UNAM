from __future__ import annotations

from fastapi import APIRouter, HTTPException

from workshop_schema import AnalysisRequest, AnalysisResponse, ExactSearchRequest
from workshop_service import get_workshop_service


router = APIRouter(prefix="/api/workshop", tags=["workshop"])


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
        return get_workshop_service().tool_bubbles(dimension=dimension, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

