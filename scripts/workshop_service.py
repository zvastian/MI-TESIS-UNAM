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
                self._term_frequency(match_sql, params, top=20),
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

    def _term_frequency(self, match_sql: str, params: list[Any], top: int = 20) -> list[dict[str, Any]]:
        col = self.colmap.title_norm or self.colmap.title
        if not col:
            return []

        rows = self.conn.execute(
            f"""
            WITH matches AS ({match_sql})
            SELECT {sql_ident(col)} AS title_value
            FROM matches
            WHERE {sql_ident(col)} IS NOT NULL
            LIMIT 5000
            """,
            params
        ).fetchall()

        freq: dict[str, int] = {}
        for (title,) in rows:
            text = normalize_text(str(title or ""))
            for token in text.split():
                if len(token) < 4 or token in STOPWORDS_ES:
                    continue
                freq[token] = freq.get(token, 0) + 1

        return [
            {"label": term, "count": count}
            for term, count in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:top]
        ]


@lru_cache(maxsize=1)
def get_workshop_service() -> WorkshopService:
    return WorkshopService()
