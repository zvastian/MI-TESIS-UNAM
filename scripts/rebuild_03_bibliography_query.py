import json
import os
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parents[1]

SOURCE_PATH = BASE_DIR / os.getenv("SOURCE_PATH", "Base.parquet")
SAMPLE_META_PATH = BASE_DIR / os.getenv("SAMPLE_META_PATH", "sample_50k_final_15d.parquet")

OUTPUT_BIB_PATH = BASE_DIR / "semantic_bibliography_dataset.parquet"
OUTPUT_QUERY_VECTOR_PATH = BASE_DIR / "payloads" / "query_vector.json"

INPUT_PATH_CANDIDATES = [
    BASE_DIR / "payloads" / "input.json",
    BASE_DIR / "payloads" / "lab_input.json",
    BASE_DIR / "input.json",
    BASE_DIR / "lab_input.json",
]

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

PARQUET_BATCH_SIZE = int(os.getenv("PARQUET_BATCH_SIZE", "25000"))
MAX_BIB_RECORDS = int(os.getenv("MAX_BIB_RECORDS", "20000"))


def normalize_title_key(s):
    if pd.isna(s):
        return ""

    s = str(s).lower().strip()

    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))

    s = s.replace(":", " ")
    s = s.replace("/", " ")
    s = s.replace("-", " ")
    s = s.replace("–", " ")
    s = s.replace("—", " ")

    s = re.sub(r"[^a-z0-9ñ\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s


def first_existing_input():
    for path in INPUT_PATH_CANDIDATES:
        if path.exists():
            return path
    return None


def load_lab_input() -> dict:
    path = first_existing_input()

    if path:
        print(f"Leyendo input: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    print("AVISO: no encontré input.json/lab_input.json. Usando input de prueba.")

    return {
        "title": "Analisis del sistema bancario de Mexico y China 1850-2009",
        "keywords": [
            "México",
            "China",
            "banco",
            "sistema bancario",
            "economía"
        ],
        "objectives": [
            "Analizar las diferencias entre ambos sistemas bancarios",
            "Reconocer diferencias en los procesos históricos",
            "Sugerir mejoras para el sistema bancario mexicano"
        ],
        "program": "Economía",
        "degree": "Licenciatura",
        "plantel": "Facultad de Economía",
        "study_period": {
            "applies": True,
            "start_year": 1850,
            "end_year": 2009,
            "label": "1850-2009"
        },
    }


def build_query_text(user_input: dict) -> str:
    title = user_input.get("title", "")

    keywords = user_input.get("keywords", [])
    if isinstance(keywords, list):
        keywords_text = " ".join(str(k) for k in keywords)
    else:
        keywords_text = str(keywords)

    objectives = user_input.get("objectives", [])
    if isinstance(objectives, list):
        objectives_text = " ".join(str(o) for o in objectives)
    else:
        objectives_text = str(objectives)

    program = user_input.get("program", "")
    degree = user_input.get("degree", "")
    plantel = user_input.get("plantel", "")

    return " | ".join(
        x.strip()
        for x in [
            str(title),
            str(keywords_text),
            str(objectives_text),
            str(program),
            str(degree),
            str(plantel),
        ]
        if x and str(x).strip()
    )


def resolve_columns(available_columns: list[str]) -> dict[str, str | None]:
    aliases = {
        "doc_number": ["doc_number", "ID_Limpio", "id", "ID", "ID_global"],
        "titulo": ["titulo", "titulo_normalizado", "title", "Título", "Titulo"],
        "titulo_normalizado": ["titulo_normalizado", "titulo", "title", "Título", "Titulo"],
        "anio": ["anio", "Año", "year", "año"],
        "autor": ["autor", "author"],
        "asesor": ["asesor", "asesor_limpio_v2", "advisor"],
        "programa": ["programa", "program", "Programa"],
        "nivel": ["nivel", "nivel_estandar", "degree", "grado"],
        "area": ["area", "area_conocimiento", "Área"],
        "plantel": ["plantel", "plantel_estandarizado", "entidad", "Plantel"],
        "detected_titles": ["detected_titles", "bibliography_titles_clean", "bibliografia", "bibliography"],
        "bibliography_embedding_text": ["bibliography_embedding_text", "bibliography_text", "bibliografia_texto"],
        "bibliography_ref_count": ["bibliography_ref_count", "ref_count", "num_refs"],
        "ai_context_chunk": ["ai_context_chunk", "bibliography_context", "context_chunk"],
    }

    available = set(available_columns)
    resolved = {}

    for canonical, candidates in aliases.items():
        found = None

        for candidate in candidates:
            if candidate in available:
                found = candidate
                break

        resolved[canonical] = found

    return resolved


def safe_get(row: pd.Series, col: str | None, default=""):
    if col and col in row.index:
        value = row[col]
        if pd.isna(value):
            return default
        return value
    return default


def clean_bibliography_line(s):
    if s is None:
        return ""

    s = str(s)
    s = re.sub(r"^\s*\d+[\.\-\)]\s*", "", s)
    s = re.sub(r"^\s*[•\-]\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("lllBLIOGRAFÍA", "Bibliografía")
    s = s.replace("BIBLIOGRAFIA", "")
    s = s.replace("Bibliografía", "")
    s = s.strip(" .;:-")

    return s


def parse_detected_titles(value, fallback_text="", max_titles=15):
    titles = []

    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                title = item.get("title", "")
            else:
                title = item
            title = clean_bibliography_line(title)
            if title:
                titles.append(title)

    elif isinstance(value, str) and value.strip():
        raw = value.strip()

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        title = item.get("title", "")
                    else:
                        title = item
                    title = clean_bibliography_line(title)
                    if title:
                        titles.append(title)
        except Exception:
            parts = re.split(r"\n|(?=\s*\d+[\.\)])|;", raw)
            for part in parts:
                title = clean_bibliography_line(part)
                if len(title) >= 20:
                    titles.append(title)

    if len(titles) < 3 and fallback_text:
        parts = re.split(
            r"\n|(?=\s*\d+[\.\)])|(?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+,\s)",
            str(fallback_text)
        )

        for part in parts:
            title = clean_bibliography_line(part)
            if 25 <= len(title) <= 220:
                titles.append(title)

    seen = set()
    clean = []

    for title in titles:
        key = normalize_title_key(title)

        if not key:
            continue

        if key in seen:
            continue

        if len(title) < 12:
            continue

        seen.add(key)
        clean.append(title)

        if len(clean) >= max_titles:
            break

    return clean


def load_sample_title_keys() -> set[str]:
    if not SAMPLE_META_PATH.exists():
        print(f"AVISO: no encontré sample meta: {SAMPLE_META_PATH}")
        return set()

    sample = pd.read_parquet(SAMPLE_META_PATH, columns=["titulo_normalizado"])
    keys = set(sample["titulo_normalizado"].dropna().apply(normalize_title_key).tolist())

    print("Títulos en sample:", len(keys))

    return keys


def build_bibliography_dataset():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"No encontré fuente: {SOURCE_PATH}")

    sample_title_keys = load_sample_title_keys()

    dataset = ds.dataset(str(SOURCE_PATH), format="parquet")
    available_columns = dataset.schema.names
    resolved = resolve_columns(available_columns)

    read_columns = sorted({
        col for col in resolved.values()
        if col is not None
    })

    if not read_columns:
        raise RuntimeError("No pude resolver columnas útiles para bibliografía.")

    print("Columnas leídas para bibliografía:", read_columns)
    print("Columnas resueltas:", resolved)

    rows = []

    scanner = dataset.scanner(
        columns=read_columns,
        batch_size=PARQUET_BATCH_SIZE,
    )

    for batch_i, batch in enumerate(scanner.to_batches(), start=1):
        df = batch.to_pandas()

        for _, row in df.iterrows():
            titulo_norm = safe_get(row, resolved["titulo_normalizado"], "")
            title_key = normalize_title_key(titulo_norm)

            if not title_key:
                continue

            # Si tenemos sample, priorizar solo tesis que podrían matchear por título exacto.
            if sample_title_keys and title_key not in sample_title_keys:
                continue

            detected_raw = safe_get(row, resolved["detected_titles"], "")
            embedding_text = safe_get(row, resolved["bibliography_embedding_text"], "")
            ai_chunk = safe_get(row, resolved["ai_context_chunk"], "")

            detected_titles = parse_detected_titles(
                detected_raw,
                fallback_text=embedding_text or ai_chunk,
                max_titles=15,
            )

            # Si no hay bibliografía real, crea placeholder mínimo para no romper pipeline,
            # pero build_bibliography_payload ignorará fuentes sin títulos útiles.
            if not detected_titles:
                continue

            rows.append({
                "doc_number": str(safe_get(row, resolved["doc_number"], "")),
                "titulo": str(safe_get(row, resolved["titulo"], "")),
                "titulo_normalizado": str(titulo_norm),
                "anio": safe_get(row, resolved["anio"], None),
                "autor": str(safe_get(row, resolved["autor"], "")),
                "asesor": str(safe_get(row, resolved["asesor"], "")),
                "programa": str(safe_get(row, resolved["programa"], "")),
                "nivel": str(safe_get(row, resolved["nivel"], "")),
                "area": str(safe_get(row, resolved["area"], "")),
                "plantel": str(safe_get(row, resolved["plantel"], "")),
                "detected_titles": detected_titles,
                "average_title_score": None,
                "bibliography_embedding_text": str(embedding_text),
                "bibliography_ref_count": len(detected_titles),
                "ready_for_ai": True,
                "ai_context_chunk": str(ai_chunk),
            })

            if len(rows) >= MAX_BIB_RECORDS:
                break

        if batch_i % 10 == 0:
            print(f"Batches: {batch_i} | bib rows: {len(rows):,}")

        if len(rows) >= MAX_BIB_RECORDS:
            break

    if rows:
        out = pd.DataFrame(rows)
    else:
        print("AVISO: no se encontraron registros con bibliografía detectada.")
        out = pd.DataFrame(columns=[
            "doc_number",
            "titulo",
            "titulo_normalizado",
            "anio",
            "autor",
            "asesor",
            "programa",
            "nivel",
            "area",
            "plantel",
            "detected_titles",
            "average_title_score",
            "bibliography_embedding_text",
            "bibliography_ref_count",
            "ready_for_ai",
            "ai_context_chunk",
        ])

    print(f"Guardando {OUTPUT_BIB_PATH}")
    out.to_parquet(OUTPUT_BIB_PATH, index=False)

    print("semantic bibliography:", out.shape)


def build_query_vector():
    user_input = load_lab_input()
    query_text = build_query_text(user_input)

    if not query_text.strip():
        raise RuntimeError("query_text vacío; revisa payloads/input.json")

    print("Query text:")
    print(query_text[:500])

    print(f"Cargando modelo: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    vector = model.encode(
        [query_text],
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0].astype("float32")

    OUTPUT_QUERY_VECTOR_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_QUERY_VECTOR_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "embedding": vector.tolist(),
            "model": EMBEDDING_MODEL,
            "dimensions": int(vector.shape[0]),
            "query_text": query_text,
        }, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_QUERY_VECTOR_PATH}")
    print("query vector shape:", vector.shape)


def main():
    build_bibliography_dataset()
    build_query_vector()

    print("\nOK")
    print(f"- {OUTPUT_BIB_PATH}")
    print(f"- {OUTPUT_QUERY_VECTOR_PATH}")


if __name__ == "__main__":
    main()