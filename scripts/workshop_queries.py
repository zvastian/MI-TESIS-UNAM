from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


# Columnas canónicas internas. Los valores se resuelven dinámicamente
# contra el parquet real mediante resolve_columns().
CANDIDATE_COLUMNS = {
    "thesis_id": ["thesis_id", "ID_Limpio", "ID_Aleph", "doc_number_url", "doc_number"],
    "title": ["title", "titulo", "título", "source_thesis_title"],
    "title_norm": ["title_norm", "titulo_normalizado", "titulo_norm", "titulo", "título"],
    "year": ["year", "anio", "año", "Año"],
    "degree": ["degree_norm", "degree", "nivel_estandar", "nivel", "grado"],
    "program": ["program_norm", "program", "programa"],
    "plantel": ["plantel_norm", "plantel", "plantel_estandarizado"],
    "area": ["area_norm", "area", "área", "materia_general", "materia general"],
    "advisor": ["advisor_norm", "advisor_name", "asesor_limpio_v2", "asesor"],
    "author": ["author", "autor_limpio_v2", "autor"],
    "url": ["url", "pdf_url", "link_extraido_regex"],
}


DIMENSIONS = {
    "year": "year",
    "program": "program",
    "plantel": "plantel",
    "degree": "degree",
    "area": "area",
    "advisor": "advisor",
}


@dataclass(frozen=True)
class ColumnMap:
    thesis_id: str | None
    title: str | None
    title_norm: str | None
    year: str | None
    degree: str | None
    program: str | None
    plantel: str | None
    area: str | None
    advisor: str | None
    author: str | None
    url: str | None

    def require(self, key: str) -> str:
        value = getattr(self, key)
        if not value:
            raise ValueError(f"Missing required column mapping for {key}")
        return value


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9ñü\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def sql_ident(name: str) -> str:
    # Quoting seguro para nombres ya elegidos por whitelist interna.
    return '"' + name.replace('"', '""') + '"'


def resolve_columns(actual_columns: list[str]) -> ColumnMap:
    lower_to_actual = {c.lower(): c for c in actual_columns}

    resolved = {}
    for canonical, candidates in CANDIDATE_COLUMNS.items():
        found = None
        for cand in candidates:
            if cand.lower() in lower_to_actual:
                found = lower_to_actual[cand.lower()]
                break
        resolved[canonical] = found

    return ColumnMap(**resolved)


def build_exact_condition(
    query: str,
    match_mode: str,
    title_column: str,
) -> tuple[str, list[str]]:
    q = normalize_text(query)
    col = f"lower(unaccent_like({sql_ident(title_column)}))"

    if match_mode == "phrase":
        return f"{col} LIKE ?", [f"%{q}%"]

    words = [w for w in q.split() if len(w) > 1]
    if not words:
        return f"{col} LIKE ?", [f"%{q}%"]

    op = " AND " if match_mode == "all_words" else " OR "
    parts = [f"{col} LIKE ?" for _ in words]
    params = [f"%{w}%" for w in words]
    return "(" + op.join(parts) + ")", params


def build_filter_conditions(
    colmap: ColumnMap,
    year_start: int | None = None,
    year_end: int | None = None,
    degree: list[str] | None = None,
    program: list[str] | None = None,
    plantel: list[str] | None = None,
    area: list[str] | None = None,
) -> tuple[list[str], list[object]]:
    conditions: list[str] = []
    params: list[object] = []

    if colmap.year and year_start is not None:
        conditions.append(f"try_cast({sql_ident(colmap.year)} AS INTEGER) >= ?")
        params.append(year_start)

    if colmap.year and year_end is not None:
        conditions.append(f"try_cast({sql_ident(colmap.year)} AS INTEGER) <= ?")
        params.append(year_end)

    for values, col in [
        (degree or [], colmap.degree),
        (program or [], colmap.program),
        (plantel or [], colmap.plantel),
        (area or [], colmap.area),
    ]:
        values = [v for v in values if v]
        if values and col:
            placeholders = ",".join(["?"] * len(values))
            conditions.append(f"{sql_ident(col)} IN ({placeholders})")
            params.extend(values)

    return conditions, params
