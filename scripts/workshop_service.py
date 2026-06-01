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
