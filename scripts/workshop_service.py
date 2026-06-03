from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb

from workshop_charts import bar_chart, horizontal_bar_chart, line_chart
from workshop_queries import (
    DIMENSIONS,
    ColumnMap,
    build_exact_condition,
    build_filter_conditions,
    normalize_text,
    resolve_columns,
    sql_ident,
)
from workshop_schema import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSummary,
    ExactSearchRequest,
    ExactSearchResponse,
    FacetsResponse,
    MethodMetadata,
    MethodStep,
    WorkshopSummary,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_CANDIDATES = [
    PROJECT_ROOT / "data" / "thesis_lookup.parquet",
    PROJECT_ROOT / "data" / "base.parquet",
    PROJECT_ROOT / "base.parquet",
    PROJECT_ROOT / "static" / "explore" / "thesis_lookup.parquet",
    PROJECT_ROOT / "static" / "explore" / "base.parquet",
]


STOPWORDS_ES = {
    "de", "la", "el", "los", "las", "y", "en", "del", "para", "por", "con",
    "un", "una", "unos", "unas", "al", "a", "e", "o", "su", "sus", "se",
    "que", "como", "sobre", "entre", "desde", "hacia", "analisis", "estudio",
    "caso", "propuesta", "modelo", "sistema", "sistemas"
}


MISSING_ANALYSIS_VALUES = {
    "",
    "-",
    "--",
    "—",
    "na",
    "n/a",
    "s/d",
    "sd",
    "sin dato",
    "sin datos",
    "no disponible",
    "no especificado",
    "no especificada",
    "no aplica",
    "null",
    "none",
    "nan",
}


def _is_missing_analysis_value(value: object) -> bool:
    if value is None:
        return True

    normalized = " ".join(str(value).strip().lower().split())
    return normalized in MISSING_ANALYSIS_VALUES


def _sql_non_missing_condition(column: str) -> str:
    ident = sql_ident(column)
    normalized = f"lower(trim(cast({ident} as varchar)))"
    return (
        f"{ident} IS NOT NULL "
        f"AND trim(cast({ident} as varchar)) <> '' "
        f"AND {normalized} NOT IN ("
        "'-', '--', '—', 'na', 'n/a', 's/d', 'sd', "
        "'sin dato', 'sin datos', 'no disponible', "
        "'no especificado', 'no especificada', 'no aplica', "
        "'null', 'none', 'nan'"
        ")"
    )


class WorkshopService:
    def __init__(self, dataset_path: Path | None = None):
        self.dataset_path = dataset_path or self.find_dataset()
        self.conn = duckdb.connect(database=":memory:")
        self.conn.create_function("unaccent_like", normalize_text, [str], str)
        self.table = "thesis_lookup"
        parquet_path = str(self.dataset_path).replace("'", "''")
        self.conn.execute(
            f"CREATE VIEW {self.table} AS SELECT * FROM read_parquet('{parquet_path}')"
            )
        self.columns = [r[1] for r in self.conn.execute(f"PRAGMA table_info('{self.table}')").fetchall()]
        self.colmap = resolve_columns(self.columns)

    @staticmethod
    def find_dataset() -> Path:
        for p in DATASET_CANDIDATES:
            if p.exists():
                return p

        found = []
        for pattern in ["**/thesis_lookup.parquet", "**/base.parquet"]:
            found.extend(PROJECT_ROOT.glob(pattern))

        # Evitar .venv y backups.
        found = [
            p for p in found
            if ".venv" not in p.parts
            and "site-packages" not in p.parts
            and ".git" not in p.parts
        ]

        if found:
            return sorted(found, key=lambda x: len(str(x)))[0]

        raise FileNotFoundError(
            "No encontré thesis_lookup.parquet ni base.parquet. "
            "Coloca un parquet en data/thesis_lookup.parquet o data/base.parquet."
        )

    def facets(self) -> FacetsResponse:
        total_rows = self.conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]

        year_min = year_max = None
        if self.colmap.year:
            row = self.conn.execute(
                f"""
                SELECT
                  min(try_cast({sql_ident(self.colmap.year)} AS INTEGER)),
                  max(try_cast({sql_ident(self.colmap.year)} AS INTEGER))
                FROM {self.table}
                """
            ).fetchone()
            year_min, year_max = row[0], row[1]

        def top_values(col: str | None, limit: int = 80) -> list[str]:
            if not col:
                return []
            rows = self.conn.execute(
                f"""
                SELECT {sql_ident(col)} AS value, COUNT(*) AS n
                FROM {self.table}
                WHERE {sql_ident(col)} IS NOT NULL
                  AND trim(CAST({sql_ident(col)} AS VARCHAR)) <> ''
                GROUP BY 1
                ORDER BY n DESC, value ASC
                LIMIT ?
                """,
                [limit]
            ).fetchall()
            return [str(r[0]) for r in rows if r[0] is not None]

        return FacetsResponse(
            source=str(self.dataset_path.relative_to(PROJECT_ROOT)),
            total_rows=total_rows,
            year_min=year_min,
            year_max=year_max,
            degrees=top_values(self.colmap.degree),
            programs=top_values(self.colmap.program),
            plantels=top_values(self.colmap.plantel),
            areas=top_values(self.colmap.area),
        )

    def exact_search(self, req: ExactSearchRequest) -> ExactSearchResponse:
        import time

        t0 = time.perf_counter()

        title_col = self.colmap.title_norm or self.colmap.title
        if not title_col:
            raise ValueError("El dataset no tiene columna de título/title_norm disponible.")

        exact_condition, exact_params = build_exact_condition(
            query=req.query,
            match_mode=req.match_mode,
            title_column=title_col,
        )

        filters, filter_params = build_filter_conditions(
            self.colmap,
            year_start=req.year.start if req.year else None,
            year_end=req.year.end if req.year else None,
            degree=req.degree,
            program=req.program,
            plantel=req.plantel,
            area=req.area,
        )

        where_parts = [exact_condition] + filters
        where_sql = " AND ".join(where_parts)
        params: list[Any] = exact_params + filter_params

        # Materializamos una sola vez el conjunto encontrado.
        # Antes cada gráfica re-ejecutaba el mismo WHERE sobre el parquet.
        self.conn.execute("DROP TABLE IF EXISTS workshop_matches")

        match_sql_for_table = f"""
            CREATE TEMP TABLE workshop_matches AS
            SELECT
              row_number() OVER () AS match_rank,
              *
            FROM {self.table}
            WHERE {where_sql}
        """
        self.conn.execute(match_sql_for_table, params)

        timings: dict[str, float] = {}
        timings["materialize_matches_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        match_sql = "SELECT * FROM workshop_matches"
        params = []

        t_summary = time.perf_counter()
        summary = self._summary(match_sql, params)
        timings["summary_ms"] = round((time.perf_counter() - t_summary) * 1000, 2)

        t_charts = time.perf_counter()
        charts = {
            "by_year": line_chart(
                "Evolución temporal",
                self._aggregate_dimension(match_sql, params, "year", limit=120, order_by_value=True),
                x="label",
                y="count",
            ),
            "by_program": horizontal_bar_chart(
                "Programas principales",
                self._aggregate_dimension(match_sql, params, "program", limit=15),
                x="count",
                y="label",
            ),
            "by_plantel": horizontal_bar_chart(
                "Planteles principales",
                self._aggregate_dimension(match_sql, params, "plantel", limit=15),
                x="count",
                y="label",
            ),
            "by_degree": bar_chart(
                "Nivel académico",
                self._aggregate_dimension(match_sql, params, "degree", limit=10),
                x="label",
                y="count",
            ),
            "by_area": horizontal_bar_chart(
                "Áreas académicas",
                self._aggregate_dimension(match_sql, params, "area", limit=10),
                x="count",
                y="label",
            ),
            "by_advisor": horizontal_bar_chart(
                "Asesores asociados al conjunto",
                self._aggregate_dimension(match_sql, params, "advisor", limit=15),
                x="count",
                y="label",
            ),
            "top_terms": horizontal_bar_chart(
                "Términos recurrentes",
                self._term_frequency(match_sql, params, top=20, exclude_terms=req.query),
                x="count",
                y="label",
            ),
        }
        timings["charts_ms"] = round((time.perf_counter() - t_charts) * 1000, 2)

        t_tables = time.perf_counter()
        tables = {
            "top_theses": self._top_theses(match_sql, params, limit=min(req.limit, 100)),
            "recent_theses": self._top_theses(match_sql, params, limit=min(req.limit, 100), recent=True),
        }
        timings["tables_ms"] = round((time.perf_counter() - t_tables) * 1000, 2)
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        editorial = self._build_editorial_layer(
            query=req.query,
            summary=summary,
            charts=charts,
        )

        method = MethodMetadata(
            mode="exact",
            source=str(self.dataset_path.relative_to(PROJECT_ROOT)),
            engine="DuckDB",
            steps=[
                MethodStep(label="Consulta", detail=f"Término buscado: {req.query}"),
                MethodStep(label="Normalización", detail="Se normalizó el texto para búsqueda en título."),
                MethodStep(label="Coincidencia exacta", detail=f"Modo: {req.match_mode}; columna: {title_col}"),
                MethodStep(label="Materialización", detail="Se creó una tabla temporal workshop_matches para no reescanear el parquet por cada gráfica."),
                MethodStep(label="Agregación", detail="Se agregaron resultados por año, programa, plantel, nivel, área y asesor."),
                MethodStep(label="Rendimiento", detail=str(timings)),
            ],
            generated_sql=" ".join(match_sql_for_table.split()),
        )

        return ExactSearchResponse(
            query=req.query,
            match_mode=req.match_mode,
            summary=summary,
            charts=charts,
            tables=tables,
            method=method,
            editorial=editorial,
        )


    def _summary(self, match_sql: str, params: list[Any]) -> WorkshopSummary:
        c = self.colmap

        year_expr = f"try_cast({sql_ident(c.year)} AS INTEGER)" if c.year else "NULL"
        program_expr = sql_ident(c.program) if c.program else "NULL"
        plantel_expr = sql_ident(c.plantel) if c.plantel else "NULL"
        degree_expr = sql_ident(c.degree) if c.degree else "NULL"

        row = self.conn.execute(
            f"""
            WITH matches AS ({match_sql})
            SELECT
              COUNT(*) AS total_matches,
              min({year_expr}) AS first_year,
              max({year_expr}) AS last_year,
              count(DISTINCT {program_expr}) AS distinct_programs,
              count(DISTINCT {plantel_expr}) AS distinct_plantels
            FROM matches
            """,
            params
        ).fetchone()

        dominant_program = self._dominant(match_sql, params, c.program)
        dominant_degree = self._dominant(match_sql, params, c.degree)

        return WorkshopSummary(
            total_matches=int(row[0] or 0),
            first_year=row[1],
            last_year=row[2],
            distinct_programs=int(row[3] or 0),
            distinct_plantels=int(row[4] or 0),
            dominant_program=dominant_program,
            dominant_degree=dominant_degree,
            avg_similarity=None,
        )

    def _dominant(self, match_sql: str, params: list[Any], col: str | None) -> str | None:
        if not col:
            return None

        row = self.conn.execute(
            f"""
            WITH matches AS ({match_sql})
            SELECT {sql_ident(col)} AS label, COUNT(*) AS n
            FROM matches
            WHERE {sql_ident(col)} IS NOT NULL
              AND trim(CAST({sql_ident(col)} AS VARCHAR)) <> ''
            GROUP BY 1
            ORDER BY n DESC, label ASC
            LIMIT 1
            """,
            params
        ).fetchone()

        return str(row[0]) if row and row[0] is not None else None

    def _aggregate_dimension(
        self,
        match_sql: str,
        params: list[Any],
        dim: str,
        limit: int = 15,
        order_by_value: bool = False,
    ) -> list[dict[str, Any]]:
        if dim not in DIMENSIONS:
            raise ValueError(f"Dimensión no permitida: {dim}")

        col = getattr(self.colmap, DIMENSIONS[dim])
        if not col:
            return []

        label_expr = (
            f"try_cast({sql_ident(col)} AS INTEGER)"
            if dim == "year"
            else f"CAST({sql_ident(col)} AS VARCHAR)"
        )

        order_sql = "label ASC" if order_by_value else "count DESC, label ASC"

        rows = self.conn.execute(
            f"""
            WITH matches AS ({match_sql})
            SELECT
              {label_expr} AS label,
              COUNT(*) AS count
            FROM matches
            WHERE {sql_ident(col)} IS NOT NULL
              AND trim(CAST({sql_ident(col)} AS VARCHAR)) <> ''
            GROUP BY 1
            ORDER BY {order_sql}
            LIMIT ?
            """,
            params + [limit]
        ).fetchall()

        return [
            {"label": str(r[0]), "count": int(r[1])}
            for r in rows
            if r[0] is not None
        ]

    def _top_theses(
        self,
        match_sql: str,
        params: list[Any],
        limit: int = 50,
        recent: bool = False,
    ) -> list[dict[str, Any]]:
        c = self.colmap

        select_parts = [
            f"{sql_ident(c.title)} AS title" if c.title else "NULL AS title",
            f"{sql_ident(c.year)} AS year" if c.year else "NULL AS year",
            f"{sql_ident(c.program)} AS program" if c.program else "NULL AS program",
            f"{sql_ident(c.degree)} AS degree" if c.degree else "NULL AS degree",
            f"{sql_ident(c.plantel)} AS plantel" if c.plantel else "NULL AS plantel",
            f"{sql_ident(c.advisor)} AS advisor" if c.advisor else "NULL AS advisor",
            f"{sql_ident(c.url)} AS url" if c.url else "NULL AS url",
        ]

        order_sql = (
            f"try_cast({sql_ident(c.year)} AS INTEGER) DESC NULLS LAST"
            if recent and c.year
            else "match_rank ASC"
        )

        rows = self.conn.execute(
            f"""
            WITH matches AS ({match_sql})
            SELECT {", ".join(select_parts)}
            FROM matches
            ORDER BY {order_sql}
            LIMIT ?
            """,
            params + [limit]
        ).fetchall()

        keys = ["title", "year", "program", "degree", "plantel", "advisor", "url"]
        return [
            {k: r[i] for i, k in enumerate(keys)}
            for r in rows
        ]






    def tool_heatmap(
        self,
        dimension: str = "area",
        limit: int = 25,
        year_min: int | None = None,
        year_max: int | None = None,
        areas: list[str] | None = None,
        levels: list[str] | None = None,
        scale: str = "absolute",
    ) -> dict[str, Any]:
        """Dataset curado para heatmap año × categoría."""
        summary_path = Path("data/workshop/ranking_summary.parquet")
        if not summary_path.exists():
            raise FileNotFoundError("No existe data/workshop/ranking_summary.parquet")

        dimension_map = {
            "program": "program",
            "programa": "program",
            "advisor": "advisor",
            "asesor": "advisor",
            "plantel": "plantel",
            "campus": "plantel",
            "level": "level",
            "nivel": "level",
            "area": "area",
            "degree": "degree",
            "grado": "degree",
        }

        dimension = (dimension or "area").lower().strip()
        dimension = dimension_map.get(dimension, dimension)
        if dimension not in {"program", "advisor", "plantel", "level", "area", "degree"}:
            raise ValueError(f"dimension no soportada: {dimension}")

        scale = (scale or "absolute").lower().strip()
        if scale not in {"absolute", "year_share", "log"}:
            raise ValueError(f"scale no soportada: {scale}")

        limit = max(1, min(int(limit or 25), 75))

        where_parts = ["dimension = ?"]
        params: list[Any] = [dimension]

        if year_min is not None:
            where_parts.append("year >= ?")
            params.append(int(year_min))

        if year_max is not None:
            where_parts.append("year <= ?")
            params.append(int(year_max))

        def add_in_filter(column: str, values: list[str] | None):
            clean = [
                str(v).strip().upper()
                for v in (values or [])
                if v is not None and str(v).strip()
            ]
            if not clean:
                return
            placeholders = ", ".join(["?"] * len(clean))
            where_parts.append(f"{column} IN ({placeholders})")
            params.extend(clean)

        add_in_filter("area", areas)

        clean_levels = []
        for value in levels or []:
            level = str(value).strip().upper()
            if level == "MAESTRIA":
                level = "MAESTRÍA"
            if level:
                clean_levels.append(level)

        if clean_levels:
            placeholders = ", ".join(["?"] * len(clean_levels))
            where_parts.append(f"level IN ({placeholders})")
            params.extend(clean_levels)

        where_sql = "WHERE " + " AND ".join(where_parts)

        top_labels = [
            row[0]
            for row in self.conn.execute(
                f"""
                SELECT label, SUM(count) AS total
                FROM read_parquet('{summary_path.as_posix()}')
                {where_sql}
                GROUP BY label
                ORDER BY total DESC, label ASC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()
        ]

        if not top_labels:
            return {
                "tool": "heatmap",
                "dimension": dimension,
                "scale": scale,
                "limit": limit,
                "years": [],
                "labels": [],
                "cells": [],
                "summary": {
                    "total_rows": 0,
                    "max_value": 0,
                    "top_label": None,
                },
            }

        label_placeholders = ", ".join(["?"] * len(top_labels))

        raw_rows = self.conn.execute(
            f"""
            WITH filtered AS (
              SELECT label, year, SUM(count) AS raw
              FROM read_parquet('{summary_path.as_posix()}')
              {where_sql}
                AND label IN ({label_placeholders})
              GROUP BY label, year
            ),
            year_totals AS (
              SELECT year, SUM(raw) AS year_total
              FROM filtered
              GROUP BY year
            )
            SELECT
              f.label,
              f.year,
              f.raw,
              CASE
                WHEN ? = 'log' THEN log10(f.raw + 1)
                WHEN ? = 'year_share' THEN f.raw / NULLIF(y.year_total, 0)
                ELSE f.raw
              END AS value
            FROM filtered f
            JOIN year_totals y USING(year)
            ORDER BY f.year ASC, f.label ASC
            """,
            params + top_labels + [scale, scale],
        ).fetchall()

        years = sorted({int(row[1]) for row in raw_rows})
        label_order = {label: index for index, label in enumerate(top_labels)}
        max_value = max((float(row[3] or 0) for row in raw_rows), default=0)
        total_rows = sum(int(row[2] or 0) for row in raw_rows)

        cells = [
            {
                "x": int(year),
                "y": label,
                "label_index": label_order.get(label, 0),
                "year_index": years.index(int(year)),
                "raw": int(raw or 0),
                "value": float(value or 0),
            }
            for label, year, raw, value in raw_rows
        ]

        return {
            "tool": "heatmap",
            "dimension": dimension,
            "scale": scale,
            "limit": limit,
            "years": years,
            "labels": top_labels,
            "cells": cells,
            "summary": {
                "total_rows": int(total_rows),
                "max_value": max_value,
                "top_label": top_labels[0] if top_labels else None,
            },
        }

    def tool_ranking(
        self,
        dimension: str = "program",
        limit: int = 25,
        year_min: int | None = None,
        year_max: int | None = None,
        areas: list[str] | None = None,
        levels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Dataset curado para rankings.

        Lee data/workshop/ranking_summary.parquet, un parquet preagregado.
        """
        ranking_path = Path("data/workshop/ranking_summary.parquet")
        if not ranking_path.exists():
            raise FileNotFoundError("No existe data/workshop/ranking_summary.parquet")

        dimension_map = {
            "program": "program",
            "programa": "program",
            "advisor": "advisor",
            "asesor": "advisor",
            "advisors": "advisor",
            "plantel": "plantel",
            "campus": "plantel",
            "level": "level",
            "nivel": "level",
            "area": "area",
            "degree": "degree",
            "grado": "degree",
        }

        dimension = (dimension or "program").lower().strip()
        dimension = dimension_map.get(dimension, dimension)
        if dimension not in {"program", "advisor", "plantel", "level", "area", "degree"}:
            raise ValueError(f"dimension no soportada: {dimension}")

        limit = max(1, min(int(limit or 25), 100))

        where_parts = ["dimension = ?"]
        params: list[Any] = [dimension]

        if year_min is not None:
            where_parts.append("year >= ?")
            params.append(int(year_min))

        if year_max is not None:
            where_parts.append("year <= ?")
            params.append(int(year_max))

        def add_in_filter(column: str, values: list[str] | None):
            clean = [
                str(v).strip().upper()
                for v in (values or [])
                if v is not None and str(v).strip()
            ]
            if not clean:
                return
            placeholders = ", ".join(["?"] * len(clean))
            where_parts.append(f"{column} IN ({placeholders})")
            params.extend(clean)

        add_in_filter("area", areas)

        clean_levels = []
        for value in levels or []:
            level = str(value).strip().upper()
            if level == "MAESTRIA":
                level = "MAESTRÍA"
            if level:
                clean_levels.append(level)

        if clean_levels:
            placeholders = ", ".join(["?"] * len(clean_levels))
            where_parts.append(f"level IN ({placeholders})")
            params.extend(clean_levels)

        where_sql = "WHERE " + " AND ".join(where_parts)

        total_rows = self.conn.execute(
            f"""
            SELECT COALESCE(SUM(count), 0)
            FROM read_parquet('{ranking_path.as_posix()}')
            {where_sql}
            """,
            params,
        ).fetchone()[0] or 0

        rows = self.conn.execute(
            f"""
            WITH ranked AS (
              SELECT
                label,
                SUM(count) AS count,
                MIN(first_year) AS first_year,
                MAX(last_year) AS last_year,
                mode(main_area) AS main_area,
                mode(main_level) AS main_level,
                mode(main_plantel) AS main_plantel,
                mode(main_program) AS main_program
              FROM read_parquet('{ranking_path.as_posix()}')
              {where_sql}
              GROUP BY label
            ),
            ordered AS (
              SELECT
                label,
                count,
                count / NULLIF(SUM(count) OVER (), 0) AS share,
                SUM(count) OVER (
                  ORDER BY count DESC, label ASC
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) / NULLIF(SUM(count) OVER (), 0) AS cumulative_share,
                first_year,
                last_year,
                main_area,
                main_level,
                main_plantel,
                main_program,
                ROW_NUMBER() OVER (ORDER BY count DESC, label ASC) AS rank
              FROM ranked
            )
            SELECT
              rank,
              label,
              count,
              share,
              cumulative_share,
              first_year,
              last_year,
              main_area,
              main_level,
              main_plantel,
              main_program
            FROM ordered
            ORDER BY rank
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()

        result_rows = [
            {
                "rank": int(rank),
                "label": label,
                "count": int(count or 0),
                "share": float(share or 0),
                "cumulative_share": float(cumulative_share or 0),
                "first_year": int(first_year) if first_year is not None else None,
                "last_year": int(last_year) if last_year is not None else None,
                "main_area": main_area or "",
                "main_level": main_level or "",
                "main_plantel": main_plantel or "",
                "main_program": main_program or "",
            }
            for (
                rank,
                label,
                count,
                share,
                cumulative_share,
                first_year,
                last_year,
                main_area,
                main_level,
                main_plantel,
                main_program,
            ) in rows
        ]

        concentration_80_count = None
        for row in result_rows:
            if row["cumulative_share"] >= 0.8:
                concentration_80_count = row["rank"]
                break

        top = result_rows[0] if result_rows else None

        return {
            "tool": "ranking",
            "dimension": dimension,
            "limit": limit,
            "filters": {
                "year_min": year_min,
                "year_max": year_max,
                "areas": areas or [],
                "levels": levels or [],
            },
            "summary": {
                "total_rows": int(total_rows),
                "returned_rows": len(result_rows),
                "top_label": top["label"] if top else None,
                "top_count": top["count"] if top else 0,
                "top_share": top["share"] if top else 0,
                "concentration_80_count": concentration_80_count,
            },
            "rows": result_rows,
        }

    def tool_bubbles(self, dimension: str = "advisor", limit: int = 50) -> dict[str, Any]:
        """Dataset curado para burbujas tipo Gapminder.

        Slider: year
        X: active_age = years since first appearance
        Y: cumulative production
        Size: cumulative production
        Color: main area
        """
        dimension_map = {
            "advisor": self.colmap.advisor or "asesor_limpio_v2",
            "advisors": self.colmap.advisor or "asesor_limpio_v2",
            "program": self.colmap.program or "programa",
            "programa": self.colmap.program or "programa",
            "plantel": self.colmap.plantel or "plantel_estandarizado",
            "campus": self.colmap.plantel or "plantel_estandarizado",
            "level": self.colmap.degree or "nivel_estandar",
            "nivel": self.colmap.degree or "nivel_estandar",
        }

        dimension = (dimension or "advisor").lower().strip()
        entity_col = dimension_map.get(dimension)
        if not entity_col:
            raise ValueError(f"dimension no soportada: {dimension}")

        year_col = self.colmap.year or "Año"
        area_col = self.colmap.area or "area"
        program_col = self.colmap.program or "programa"
        degree_col = getattr(self.colmap, "degree", None) or "nivel_estandar"
        plantel_col = self.colmap.plantel or "plantel_estandarizado"

        limit = max(1, min(int(limit or 50), 100))

        missing_values = (
            "sin dato", "s/d", "n/a", "na", "null", "none",
            "no aplica", "por clasificar", "-", "--"
        )

        missing_sql = ", ".join(["?"] * len(missing_values))
        params = [*missing_values, limit]

        rows = self.conn.execute(
            f"""
            WITH raw AS (
              SELECT
                try_cast({sql_ident(year_col)} AS INTEGER) AS year,
                upper(trim(CAST({sql_ident(entity_col)} AS VARCHAR))) AS entity,
                upper(trim(CAST({sql_ident(area_col)} AS VARCHAR))) AS area,
                upper(trim(CAST({sql_ident(program_col)} AS VARCHAR))) AS program,
                upper(trim(CAST({sql_ident(degree_col)} AS VARCHAR))) AS level,
                upper(trim(CAST({sql_ident(plantel_col)} AS VARCHAR))) AS plantel
              FROM {self.table}
            ),
            clean AS (
              SELECT *
              FROM raw
              WHERE year IS NOT NULL
                AND entity IS NOT NULL
                AND entity <> ''
                AND lower(entity) NOT IN ({missing_sql})
            ),
            top_entities AS (
              SELECT entity, COUNT(*) AS total
              FROM clean
              GROUP BY entity
              ORDER BY total DESC, entity ASC
              LIMIT ?
            ),
            yearly AS (
              SELECT
                c.entity,
                c.year,
                COUNT(*) AS year_count
              FROM clean c
              JOIN top_entities t USING(entity)
              GROUP BY c.entity, c.year
            ),
            cumulative AS (
              SELECT
                entity,
                year,
                year_count,
                SUM(year_count) OVER (
                  PARTITION BY entity
                  ORDER BY year
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS cumulative
              FROM yearly
            ),
            meta AS (
              SELECT
                c.entity,
                COUNT(*) AS total,
                MIN(c.year) AS first_year,
                MAX(c.year) AS last_year,
                mode(c.area) AS main_area,
                mode(c.program) AS main_program,
                mode(c.level) AS main_level,
                mode(c.plantel) AS main_plantel
              FROM clean c
              JOIN top_entities t USING(entity)
              GROUP BY c.entity
            )
            SELECT
              m.entity,
              m.total,
              m.first_year,
              m.last_year,
              m.main_area,
              m.main_program,
              m.main_level,
              m.main_plantel,
              c.year,
              c.year_count,
              c.cumulative,
              c.year - m.first_year + 1 AS active_age
            FROM meta m
            JOIN cumulative c USING(entity)
            ORDER BY m.total DESC, m.entity ASC, c.year ASC
            """,
            params,
        ).fetchall()

        entities: dict[str, dict[str, Any]] = {}
        years_set: set[int] = set()

        for (
            entity,
            total,
            first_year,
            last_year,
            main_area,
            main_program,
            main_level,
            main_plantel,
            year,
            year_count,
            cumulative,
            active_age,
        ) in rows:
            key = str(entity)

            if key not in entities:
                entities[key] = {
                    "id": key,
                    "label": key,
                    "total": int(total or 0),
                    "first_year": int(first_year) if first_year is not None else None,
                    "last_year": int(last_year) if last_year is not None else None,
                    "main_area": main_area or "",
                    "main_program": main_program or "",
                    "main_level": main_level or "",
                    "main_plantel": main_plantel or "",
                    "series": [],
                }

            years_set.add(int(year))
            entities[key]["series"].append({
                "year": int(year),
                "year_count": int(year_count or 0),
                "cumulative": int(cumulative or 0),
                "active_age": int(active_age or 0),
            })

        return {
            "tool": "bubbles",
            "dimension": dimension,
            "limit": limit,
            "years": sorted(years_set),
            "encoding": {
                "time": "year",
                "x": "active_age",
                "y": "cumulative",
                "size": "cumulative",
                "color": "main_area",
            },
            "entities": list(entities.values()),
        }

    def analyze(self, req: AnalysisRequest) -> AnalysisResponse:
        """Mesa de análisis: agrupaciones y cruces sobre thesis_lookup.

        MVP:
        - group_by simple
        - group_by + compare_by
        - filtros por año, área, nivel, programa, plantel y texto en título
        """

        allowed_dimensions = {
            "year": self.colmap.year,
            "area": self.colmap.area,
            "degree": self.colmap.degree,
            "program": self.colmap.program,
            "plantel": self.colmap.plantel,
            "advisor": self.colmap.advisor,
        }

        group_by = req.group_by
        compare_by = req.compare_by

        if group_by not in allowed_dimensions or not allowed_dimensions[group_by]:
            raise ValueError(f"group_by no soportado: {group_by}")

        if compare_by and (compare_by not in allowed_dimensions or not allowed_dimensions[compare_by]):
            raise ValueError(f"compare_by no soportado: {compare_by}")

        params: list[Any] = []
        where_parts: list[str] = []

        def add_in_filter(column: str | None, values: list[str] | None):
            if not column or not values:
                return
            clean_values = [v for v in values if v is not None and str(v).strip()]
            if not clean_values:
                return
            placeholders = ", ".join(["?"] * len(clean_values))
            where_parts.append(f'{sql_ident(column)} IN ({placeholders})')
            params.extend(clean_values)

        f = req.filters

        if f.year_min is not None and self.colmap.year:
            where_parts.append(f"{sql_ident(self.colmap.year)} >= ?")
            params.append(int(f.year_min))

        if f.year_max is not None and self.colmap.year:
            where_parts.append(f"{sql_ident(self.colmap.year)} <= ?")
            params.append(int(f.year_max))

        add_in_filter(self.colmap.area, f.areas)
        add_in_filter(self.colmap.degree, f.degrees)
        add_in_filter(self.colmap.program, f.programs)
        add_in_filter(self.colmap.plantel, f.plantels)

        if f.title_contains:
            q = normalize_text(f.title_contains)
            title_col = self.colmap.title_norm or self.colmap.title
            where_parts.append(f"{sql_ident(title_col)} LIKE ?")
            params.append(f"%{q}%")

        group_col = allowed_dimensions[group_by]
        compare_col = allowed_dimensions.get(compare_by) if compare_by else None

        where_parts.append(_sql_non_missing_condition(group_col))
        if compare_col:
            where_parts.append(_sql_non_missing_condition(compare_col))

        where_sql = ""
        if where_parts:
            where_sql = "WHERE " + " AND ".join(where_parts)

        # Total filtrado
        total_rows = self.conn.execute(
            f"SELECT COUNT(*) FROM {self.table} {where_sql}",
            params,
        ).fetchone()[0]

        # Rango de años filtrado
        year_min = None
        year_max = None
        if self.colmap.year:
            yr = self.conn.execute(
                f"""
                SELECT MIN({sql_ident(self.colmap.year)}), MAX({sql_ident(self.colmap.year)})
                FROM {self.table}
                {where_sql}
                """,
                params,
            ).fetchone()
            year_min, year_max = yr[0], yr[1]

        table_rows: list[dict[str, Any]] = []

        if compare_col:
            sql = f"""
                SELECT
                    CAST({sql_ident(group_col)} AS VARCHAR) AS group_value,
                    CAST({sql_ident(compare_col)} AS VARCHAR) AS compare_value,
                    COUNT(*) AS count
                FROM {self.table}
                {where_sql}
                GROUP BY 1, 2
                ORDER BY group_value ASC, count DESC
                LIMIT ?
            """
            rows = self.conn.execute(sql, params + [int(req.limit) * 20]).fetchall()

            for group_value, compare_value, count in rows:
                table_rows.append({
                    "group": group_value,
                    "compare": compare_value,
                    "count": int(count),
                })

            chart = {
                "type": "grouped_bar" if group_by != "year" else "stacked_time",
                "group_by": group_by,
                "compare_by": compare_by,
                "data": table_rows,
            }

            # Dominante por suma de group
            group_totals: dict[str, int] = {}
            for row in table_rows:
                group_totals[row["group"]] = group_totals.get(row["group"], 0) + row["count"]

            dominant_group = None
            dominant_group_count = None
            if group_totals:
                dominant_group, dominant_group_count = max(group_totals.items(), key=lambda kv: kv[1])

        else:
            sql = f"""
                SELECT
                    CAST({sql_ident(group_col)} AS VARCHAR) AS group_value,
                    COUNT(*) AS count
                FROM {self.table}
                {where_sql}
                GROUP BY 1
                ORDER BY count DESC, group_value ASC
                LIMIT ?
            """

            # Para year, ordenar cronológicamente.
            if group_by == "year":
                sql = f"""
                    SELECT
                        CAST({sql_ident(group_col)} AS VARCHAR) AS group_value,
                        COUNT(*) AS count
                    FROM {self.table}
                    {where_sql}
                    GROUP BY 1
                    ORDER BY group_value ASC
                    LIMIT ?
                """

            rows = self.conn.execute(sql, params + [int(req.limit)]).fetchall()

            for group_value, count in rows:
                table_rows.append({
                    "group": group_value,
                    "count": int(count),
                })

            chart = {
                "type": "bar" if group_by != "year" else "time_bar",
                "group_by": group_by,
                "compare_by": None,
                "data": table_rows,
            }

            dominant_group = None
            dominant_group_count = None
            if table_rows:
                dominant = max(table_rows, key=lambda row: row["count"])
                dominant_group = dominant["group"]
                dominant_group_count = dominant["count"]

        summary = AnalysisSummary(
            total_rows=int(total_rows or 0),
            group_by=group_by,
            compare_by=compare_by,
            groups_returned=len(table_rows),
            year_min=year_min,
            year_max=year_max,
            dominant_group=dominant_group,
            dominant_group_count=dominant_group_count,
        )

        editorial = {
            "summary": self._analysis_editorial_summary(req, summary),
            "findings": [
                {
                    "label": "Tesis filtradas",
                    "value": int(total_rows or 0),
                    "detail": "Registros que cumplen los filtros seleccionados.",
                },
                {
                    "label": "Agrupación",
                    "value": group_by,
                    "detail": "Variable principal usada para construir la visualización.",
                },
                {
                    "label": "Grupo dominante",
                    "value": dominant_group or "—",
                    "detail": f"{dominant_group_count or 0} tesis en el grupo con mayor frecuencia.",
                },
            ],
        }

        method = MethodMetadata(
            mode="analysis",
            source="workshop_analyze",
            steps=[
                MethodStep(
                    label="Selección de datos",
                    detail="Se consultó thesis_lookup.parquet mediante DuckDB.",
                ),
                MethodStep(
                    label="Filtros",
                    detail=str(req.filters.model_dump(exclude_none=True)),
                ),
                MethodStep(
                    label="Agrupación",
                    detail=f"group_by={group_by}; compare_by={compare_by or 'none'}",
                ),
                MethodStep(
                    label="SQL reproducible",
                    detail="La consulta agrupa registros y calcula COUNT(*) por las variables seleccionadas.",
                ),
            ],
            generated_sql="analysis query generated by WorkshopService.analyze",
        )

        return AnalysisResponse(
            ok=True,
            mode="analysis",
            request=req.model_dump(),
            summary=summary,
            chart=chart,
            table=table_rows,
            editorial=editorial,
            method=method,
        )

    def _analysis_editorial_summary(self, req: AnalysisRequest, summary: AnalysisSummary) -> str:
        period = "periodo no determinado"
        if summary.year_min and summary.year_max:
            period = f"{summary.year_min}–{summary.year_max}"

        parts = [
            f"La consulta analiza {summary.total_rows:,} tesis del acervo filtrado.".replace(",", " "),
            f"La agrupación principal es “{summary.group_by}”.",
            f"El periodo cubierto es {period}.",
        ]

        if summary.compare_by:
            parts.append(f"La visualización compara los resultados por “{summary.compare_by}”.")

        if summary.dominant_group:
            parts.append(
                f"El grupo con mayor frecuencia es “{summary.dominant_group}”, con {summary.dominant_group_count} registros."
            )

        return " ".join(parts)


    def _build_editorial_layer(
        self,
        query: str,
        summary: Any,
        charts: dict[str, Any],
    ) -> dict[str, Any]:
        """Construye una lectura editorial determinística, sin IA.

        La idea es que el Taller no sea solo una colección de gráficas,
        sino un pequeño reporte interpretativo basado en agregaciones.
        """

        def chart_data(key: str) -> list[dict[str, Any]]:
            chart = charts.get(key)
            data = getattr(chart, "data", None)
            if data is None and isinstance(chart, dict):
                data = chart.get("data")
            return data or []

        def top_item(key: str) -> dict[str, Any] | None:
            data = chart_data(key)
            return data[0] if data else None

        by_year = chart_data("by_year")
        by_area = chart_data("by_area")
        by_program = chart_data("by_program")
        by_degree = chart_data("by_degree")
        by_plantel = chart_data("by_plantel")
        by_advisor = chart_data("by_advisor")
        top_terms = chart_data("top_terms")

        total = getattr(summary, "total_matches", None)
        first_year = getattr(summary, "first_year", None)
        last_year = getattr(summary, "last_year", None)

        dominant_area = top_item("by_area")
        dominant_program = top_item("by_program")
        dominant_degree = top_item("by_degree")
        dominant_plantel = top_item("by_plantel")
        dominant_advisor = top_item("by_advisor")

        peak_year = None
        if by_year:
            peak_year = max(
                by_year,
                key=lambda row: int(row.get("count") or 0)
            )

        recent_window = []
        recent_total = 0
        recent_share = None

        if by_year:
            numeric_years = []
            for row in by_year:
                try:
                    numeric_years.append((int(row.get("label")), int(row.get("count") or 0)))
                except Exception:
                    pass

            if numeric_years:
                max_year = max(y for y, _ in numeric_years)
                recent_window = [
                    {"label": str(y), "count": c}
                    for y, c in numeric_years
                    if y >= max_year - 9
                ]
                recent_total = sum(row["count"] for row in recent_window)
                if total:
                    recent_share = round(recent_total / total * 100, 1)

        period = "periodo no determinado"
        if first_year and last_year:
            period = f"{first_year}–{last_year}"

        dominant_area_label = dominant_area.get("label") if dominant_area else None
        dominant_program_label = dominant_program.get("label") if dominant_program else None
        dominant_degree_label = dominant_degree.get("label") if dominant_degree else None
        dominant_plantel_label = dominant_plantel.get("label") if dominant_plantel else None

        summary_text_parts = [
            f'La búsqueda “{query}” aparece en {total:,} títulos del acervo analizado.'.replace(",", " "),
            f"El conjunto cubre {period}.",
        ]

        if peak_year:
            summary_text_parts.append(
                f"El año con más menciones es {peak_year.get('label')}, con {peak_year.get('count')} registros."
            )

        if recent_share is not None:
            summary_text_parts.append(
                f"En los últimos diez años del conjunto se concentra aproximadamente {recent_share}% de los resultados."
            )

        if dominant_program_label:
            summary_text_parts.append(
                f"El programa con mayor presencia es {dominant_program_label}."
            )

        if dominant_area_label:
            summary_text_parts.append(
                f"La distribución por área ayuda a leer si el tema está concentrado o circula entre campos disciplinares."
            )

        findings = []

        findings.append({
            "label": "Resultados",
            "value": total,
            "detail": f"Títulos que contienen la frase consultada en el título limpio.",
        })

        findings.append({
            "label": "Periodo",
            "value": period,
            "detail": "Rango temporal cubierto por los resultados encontrados.",
        })

        if peak_year:
            findings.append({
                "label": "Pico temporal",
                "value": peak_year.get("label"),
                "detail": f"{peak_year.get('count')} tesis encontradas en ese año.",
            })

        if recent_share is not None:
            findings.append({
                "label": "Peso reciente",
                "value": f"{recent_share}%",
                "detail": f"{recent_total} resultados en la ventana reciente.",
            })

        if dominant_area:
            findings.append({
                "label": "Área dominante",
                "value": dominant_area_label,
                "detail": f"{dominant_area.get('count')} resultados en esta área.",
            })

        if dominant_program:
            findings.append({
                "label": "Programa principal",
                "value": dominant_program_label,
                "detail": f"{dominant_program.get('count')} resultados.",
            })

        if dominant_degree:
            findings.append({
                "label": "Nivel principal",
                "value": dominant_degree_label,
                "detail": f"{dominant_degree.get('count')} resultados.",
            })

        if dominant_plantel:
            findings.append({
                "label": "Plantel principal",
                "value": dominant_plantel_label,
                "detail": f"{dominant_plantel.get('count')} resultados.",
            })

        story_cards = []

        if by_year:
            story_cards.append({
                "title": "Evolución temporal",
                "body": (
                    f"El tema aparece a lo largo de {len(by_year)} años con resultados. "
                    f"El punto más alto se observa en {peak_year.get('label') if peak_year else 'un año no determinado'}."
                ),
            })

        if by_area:
            area_count = len(by_area)
            story_cards.append({
                "title": "Distribución disciplinaria",
                "body": (
                    f"Los resultados se distribuyen en {area_count} áreas. "
                    f"La mayor concentración aparece en {dominant_area_label or 'un área no determinada'}, "
                    "pero la comparación por áreas permite evitar una lectura excesivamente centrada en programas aislados."
                ),
            })

        if by_program:
            story_cards.append({
                "title": "Programas",
                "body": (
                    f"El programa con más resultados es {dominant_program_label}. "
                    "Esta lectura debe interpretarse junto con el área, porque algunos campos están más fragmentados en varios programas."
                ),
            })

        if top_terms:
            top_labels = ", ".join(row.get("label", "") for row in top_terms[:5])
            story_cards.append({
                "title": "Lenguaje asociado",
                "body": (
                    f"Después de excluir los términos de la búsqueda, las palabras más frecuentes son: {top_labels}."
                ),
            })

        return {
            "summary": " ".join(summary_text_parts),
            "findings": findings,
            "story_cards": story_cards,
            "dominant_area": dominant_area,
            "dominant_program": dominant_program,
            "dominant_degree": dominant_degree,
            "dominant_plantel": dominant_plantel,
            "dominant_advisor": dominant_advisor,
            "peak_year": peak_year,
            "recent_window": recent_window,
            "recent_total": recent_total,
            "recent_share": recent_share,
        }


    def _term_frequency(
        self,
        match_sql: str,
        params: list[Any],
        top: int = 20,
        exclude_terms: str | list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Calcula términos recurrentes sobre el título limpio normalizado.

        Excluye dinámicamente los tokens de la consulta.
        Ejemplo: si el usuario busca "inteligencia artificial",
        no devuelve "inteligencia" ni "artificial" como términos recurrentes.
        """

        import re
        import unicodedata
        from collections import Counter

        def norm(value: Any) -> str:
            if value is None:
                return ""
            value = str(value)
            value = unicodedata.normalize("NFKD", value)
            value = "".join(ch for ch in value if not unicodedata.combining(ch))
            value = value.lower()
            value = re.sub(r"[^a-z0-9ñü\s]+", " ", value)
            value = re.sub(r"\s+", " ", value).strip()
            return value

        def tokens(value: Any) -> list[str]:
            return [
                token
                for token in norm(value).split()
                if len(token) >= 3
            ]

        base_stopwords = {
            "para", "por", "con", "sin", "del", "las", "los", "una", "uno",
            "como", "sobre", "entre", "desde", "hasta", "hacia", "contra",
            "ante", "bajo", "tras", "durante", "mediante", "segun", "según",
            "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
            "sus", "mas", "más", "menos", "muy", "ser", "son", "fue", "han",
            "que", "cual", "cuáles", "cuales", "donde", "cuando",

            # Stopwords catalográficas residuales.
            "tesis", "tesina", "titulo", "título", "grado", "obtener", "optar",
            "presenta", "presentacion", "presentación", "tutor", "tutora",
            "asesor", "asesora", "asesores", "director", "directora",
            "maestro", "maestra", "licenciado", "licenciada", "especialista",

            # Palabras demasiado genéricas para lectura temática.
            "analisis", "análisis", "estudio", "propuesta", "modelo",
            "sistema", "sistemas", "caso", "uso",
        }

        dynamic_stopwords: set[str] = set()

        if isinstance(exclude_terms, str):
            dynamic_stopwords.update(tokens(exclude_terms))
        elif isinstance(exclude_terms, list):
            for item in exclude_terms:
                dynamic_stopwords.update(tokens(item))

        stopwords = base_stopwords | dynamic_stopwords

        title_col = self.colmap.title_norm or self.colmap.title
        if not title_col:
            return []

        safe_col = '"' + title_col.replace('"', '""') + '"'

        rows = self.conn.execute(
            f"SELECT {safe_col} FROM ({match_sql}) AS matched_titles",
            params,
        ).fetchall()

        counter: Counter[str] = Counter()

        for (title_text,) in rows:
            for token in tokens(title_text):
                if token in stopwords:
                    continue
                counter[token] += 1

        return [
            {"label": token, "count": count}
            for token, count in counter.most_common(top)
        ]

@lru_cache(maxsize=1)
def get_workshop_service() -> WorkshopService:
    return WorkshopService()


# WCT HEATMAP MATRIX API START

def _workshop_tool_heatmap_matrix(self, matrix: str = "program_level", limit: int = 10,
                                  year_min: int | None = None, year_max: int | None = None,
                                  scale: str = "log"):
    """Matrices categóricas curadas para Heatmap.

    program_level: top programas x nivel
    area_level: áreas x nivel
    program_area: top programas x área
    """
    from pathlib import Path
    import math

    parquet = Path("data/workshop/ranking_summary.parquet")
    if not parquet.exists():
        raise FileNotFoundError("No encontré data/workshop/ranking_summary.parquet")

    matrix_specs = {
        "program_level": {
            "dimension": "program",
            "row_expr": "label",
            "col_expr": "level",
            "row_label": "Programa",
            "col_label": "Nivel",
        },
        "area_level": {
            "dimension": "area",
            "row_expr": "label",
            "col_expr": "level",
            "row_label": "Área",
            "col_label": "Nivel",
        },
        "program_area": {
            "dimension": "program",
            "row_expr": "label",
            "col_expr": "area",
            "row_label": "Programa",
            "col_label": "Área",
        },
    }

    if matrix not in matrix_specs:
        raise ValueError(f"matrix no soportada: {matrix}")

    if scale not in {"absolute", "log", "row_share"}:
        raise ValueError(f"scale no soportada: {scale}")

    spec = matrix_specs[matrix]
    limit = max(1, min(int(limit or 10), 50))

    where = ["dimension = ?"]
    params = [spec["dimension"]]

    if year_min is not None:
        where.append("year >= ?")
        params.append(int(year_min))

    if year_max is not None:
        where.append("year <= ?")
        params.append(int(year_max))

    where_sql = " AND ".join(where)

    top_rows = self.conn.execute(f"""
        SELECT {spec["row_expr"]} AS row_label, SUM(count) AS total
        FROM read_parquet('{parquet.as_posix()}')
        WHERE {where_sql}
          AND {spec["row_expr"]} IS NOT NULL
          AND {spec["col_expr"]} IS NOT NULL
        GROUP BY 1
        ORDER BY total DESC, row_label ASC
        LIMIT ?
    """, params + [limit]).fetchall()

    rows = [r[0] for r in top_rows]
    if not rows:
        return {
            "tool": "heatmap_matrix",
            "matrix": matrix,
            "scale": scale,
            "rows": [],
            "columns": [],
            "cells": [],
            "summary": {"total_rows": 0, "max_value": 0},
            "encoding": {"x": spec["col_label"], "y": spec["row_label"], "value": "tesis"},
        }

    placeholders = ", ".join(["?"] * len(rows))

    raw = self.conn.execute(f"""
        WITH base AS (
          SELECT
            {spec["row_expr"]} AS row_label,
            {spec["col_expr"]} AS col_label,
            SUM(count) AS raw
          FROM read_parquet('{parquet.as_posix()}')
          WHERE {where_sql}
            AND {spec["row_expr"]} IN ({placeholders})
            AND {spec["col_expr"]} IS NOT NULL
          GROUP BY 1, 2
        ),
        row_totals AS (
          SELECT row_label, SUM(raw) AS row_total
          FROM base
          GROUP BY 1
        )
        SELECT base.row_label, base.col_label, base.raw, row_totals.row_total
        FROM base
        JOIN row_totals USING (row_label)
        ORDER BY base.row_label ASC, base.col_label ASC
    """, params + rows).fetchall()

    columns = sorted({str(r[1]) for r in raw})
    row_index = {str(v): i for i, v in enumerate(rows)}
    col_index = {str(v): i for i, v in enumerate(columns)}

    cells = []
    values = []

    for row_label, col_label, count, row_total in raw:
        row_label = str(row_label)
        col_label = str(col_label)
        count = int(count or 0)
        row_total = int(row_total or 0)

        if scale == "log":
            value = math.log10(count + 1)
        elif scale == "row_share":
            value = (count / row_total) if row_total else 0
        else:
            value = float(count)

        values.append(value)
        cells.append({
            "x": col_label,
            "y": row_label,
            "column_index": col_index[col_label],
            "row_index": row_index[row_label],
            "raw": count,
            "value": value,
        })

    return {
        "tool": "heatmap_matrix",
        "matrix": matrix,
        "scale": scale,
        "limit": limit,
        "rows": [str(r) for r in rows],
        "columns": columns,
        "cells": cells,
        "summary": {
            "total_rows": sum(int(r[2] or 0) for r in raw),
            "max_value": max(values) if values else 0,
            "top_row": str(rows[0]) if rows else None,
        },
        "encoding": {
            "x": spec["col_label"],
            "y": spec["row_label"],
            "value": "tesis",
        },
    }

try:
    WorkshopService.tool_heatmap_matrix = _workshop_tool_heatmap_matrix
except NameError:
    pass

# WCT HEATMAP MATRIX API END


# WCT SERIES API START

def _workshop_tool_series(self, dimension: str = "level", limit: int = 8,
                          year_min: int | None = 2000, year_max: int | None = 2026):
    """Series temporales curadas para el Taller."""
    from pathlib import Path

    parquet = Path("data/workshop/series_summary.parquet")
    if not parquet.exists():
        raise FileNotFoundError("No encontré data/workshop/series_summary.parquet")

    allowed = {"area", "level", "program", "plantel", "advisor"}
    if dimension not in allowed:
        raise ValueError(f"dimension no soportada: {dimension}")

    limit = max(1, min(int(limit or 8), 30))

    where = ["dimension = ?"]
    params = [dimension]

    if year_min is not None:
        where.append("year >= ?")
        params.append(int(year_min))

    if year_max is not None:
        where.append("year <= ?")
        params.append(int(year_max))

    where_sql = " AND ".join(where)

    labels = self.conn.execute(f"""
        SELECT label, SUM(count) AS period_count, MIN(series_rank) AS series_rank
        FROM read_parquet('{parquet.as_posix()}')
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY
          CASE WHEN ? IN ('area', 'level') THEN MIN(series_rank) ELSE SUM(count) * -1 END ASC,
          label ASC
        LIMIT ?
    """, params + [dimension, limit]).fetchall()

    selected = [row[0] for row in labels]
    if not selected:
        return {
            "tool": "series",
            "dimension": dimension,
            "limit": limit,
            "years": [],
            "labels": [],
            "rows": [],
            "summary": {"total_rows": 0},
        }

    placeholders = ", ".join(["?"] * len(selected))

    rows = self.conn.execute(f"""
        SELECT
          dimension,
          label,
          year,
          count,
          share_of_year,
          index_base_100,
          series_rank,
          total_count,
          first_year,
          last_year
        FROM read_parquet('{parquet.as_posix()}')
        WHERE {where_sql}
          AND label IN ({placeholders})
        ORDER BY year ASC, series_rank ASC, label ASC
    """, params + selected).fetchall()

    years = [r[0] for r in self.conn.execute(f"""
        SELECT DISTINCT year
        FROM read_parquet('{parquet.as_posix()}')
        WHERE {where_sql}
        ORDER BY year ASC
    """, params).fetchall()]

    return {
        "tool": "series",
        "dimension": dimension,
        "limit": limit,
        "years": [int(y) for y in years],
        "labels": [str(v) for v in selected],
        "rows": [
            {
                "dimension": str(r[0]),
                "label": str(r[1]),
                "year": int(r[2]),
                "count": float(r[3] or 0),
                "share_of_year": float(r[4] or 0),
                "index_base_100": float(r[5]) if r[5] is not None else None,
                "series_rank": int(r[6] or 0),
                "total_count": float(r[7] or 0),
                "first_year": int(r[8]) if r[8] is not None else None,
                "last_year": int(r[9]) if r[9] is not None else None,
            }
            for r in rows
        ],
        "summary": {
            "total_rows": float(sum(r[3] or 0 for r in rows)),
            "label_count": len(selected),
            "min_year": min(years) if years else None,
            "max_year": max(years) if years else None,
        },
    }

try:
    WorkshopService.tool_series = _workshop_tool_series
except NameError:
    pass

# WCT SERIES API END

