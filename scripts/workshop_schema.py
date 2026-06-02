from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ExploreMode = Literal["exact", "semantic", "analysis"]
ChartType = Literal["line", "bar", "horizontal_bar", "stacked_bar", "heatmap", "table"]


class YearRange(BaseModel):
    start: int | None = None
    end: int | None = None


class ExactSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=240)
    match_mode: Literal["phrase", "all_words", "any_word"] = "phrase"
    year: YearRange | None = None
    degree: list[str] = Field(default_factory=list)
    program: list[str] = Field(default_factory=list)
    plantel: list[str] = Field(default_factory=list)
    area: list[str] = Field(default_factory=list)
    limit: int = Field(default=500, ge=50, le=5000)


class FacetsResponse(BaseModel):
    ok: bool = True
    source: str
    total_rows: int
    year_min: int | None = None
    year_max: int | None = None
    degrees: list[str] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)
    plantels: list[str] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)


class ChartSpec(BaseModel):
    type: ChartType
    title: str
    x: str | None = None
    y: str | None = None
    series: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class WorkshopSummary(BaseModel):
    total_matches: int
    first_year: int | None = None
    last_year: int | None = None
    distinct_programs: int | None = None
    distinct_plantels: int | None = None
    dominant_program: str | None = None
    dominant_degree: str | None = None
    avg_similarity: float | None = None


class MethodStep(BaseModel):
    label: str
    detail: str


class MethodMetadata(BaseModel):
    mode: ExploreMode
    source: str
    engine: str = "DuckDB"
    steps: list[MethodStep] = Field(default_factory=list)
    generated_sql: str | None = None


class ExactSearchResponse(BaseModel):
    ok: bool = True
    mode: Literal["exact"] = "exact"
    query: str
    match_mode: str
    summary: WorkshopSummary
    charts: dict[str, ChartSpec]
    tables: dict[str, list[dict[str, Any]]]
    method: MethodMetadata
    editorial: dict[str, Any] | None = None


# ============================================================
# Workshop analysis builder
# ============================================================

class AnalysisFilters(BaseModel):
    year_min: int | None = None
    year_max: int | None = None
    areas: list[str] | None = None
    degrees: list[str] | None = None
    programs: list[str] | None = None
    plantels: list[str] | None = None
    title_contains: str | None = None


class AnalysisRequest(BaseModel):
    group_by: str = Field(
        default="year",
        description="Variable principal de agrupación: year, area, degree, program, plantel, advisor.",
    )
    compare_by: str | None = Field(
        default=None,
        description="Variable secundaria opcional para cruce: area, degree, program, plantel.",
    )
    filters: AnalysisFilters = Field(default_factory=AnalysisFilters)
    limit: int = Field(default=30, ge=1, le=100)
    chart_type: str = Field(default="auto")


class AnalysisSummary(BaseModel):
    total_rows: int
    group_by: str
    compare_by: str | None = None
    groups_returned: int
    year_min: int | None = None
    year_max: int | None = None
    dominant_group: str | None = None
    dominant_group_count: int | None = None


class AnalysisResponse(BaseModel):
    ok: bool = True
    mode: str = "analysis"
    request: dict[str, Any]
    summary: AnalysisSummary
    chart: dict[str, Any]
    table: list[dict[str, Any]]
    editorial: dict[str, Any] | None = None
    method: MethodMetadata
