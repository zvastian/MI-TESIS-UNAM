import json
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = BASE_DIR / os.getenv(
    "BIBLIOGRAPHY_INPUT_PATH",
    "semantic_bibliography_dataset.parquet"
)

OUTPUT_DB = BASE_DIR / os.getenv(
    "BIBLIOGRAPHY_INDEX_PATH",
    "bibliography_title_index.sqlite"
)

BATCH_SIZE = int(os.getenv("PARQUET_BATCH_SIZE", "1000"))

# Índice ligero: NO meter bibliography_embedding_text ni ai_context_chunk.
WANTED_COLUMNS = [
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
    "bibliography_ref_count",
    "ready_for_ai",
]


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


def safe_text(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value)


def safe_int(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    try:
        return int(value)
    except Exception:
        return None


def safe_bool(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, bool):
        return int(value)

    s = str(value).strip().lower()

    if s in {"true", "1", "yes", "sí", "si"}:
        return 1

    if s in {"false", "0", "no"}:
        return 0

    return None

def safe_detected_titles(value):
    """
    Guarda detected_titles como JSON string robusto.
    Soporta listas, tuplas, numpy arrays, pandas/pyarrow objects y strings JSON.
    """
    if value is None:
        return "[]"

    if isinstance(value, str):
        s = value.strip()
        return s if s else "[]"

    # numpy array / pyarrow-ish / pandas object arrays
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except Exception:
            pass

    # pyarrow scalar-ish
    if hasattr(value, "as_py"):
        try:
            value = value.as_py()
        except Exception:
            pass

    try:
        if pd.isna(value):
            return "[]"
    except Exception:
        pass

    if isinstance(value, dict):
        value = [value]

    if isinstance(value, tuple):
        value = list(value)

    if isinstance(value, list):
        clean = []
        for item in value:
            if hasattr(item, "as_py"):
                try:
                    item = item.as_py()
                except Exception:
                    pass

            if isinstance(item, dict):
                clean.append(item)
            elif item is not None:
                clean.append({"title": str(item), "score": None})

        return json.dumps(clean, ensure_ascii=False)

    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return json.dumps([{"title": str(value), "score": None}], ensure_ascii=False)

def init_db(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS bibliography")

    cur.execute("""
        CREATE TABLE bibliography (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo_key TEXT NOT NULL,
            doc_number TEXT,
            titulo TEXT,
            titulo_normalizado TEXT,
            anio INTEGER,
            autor TEXT,
            asesor TEXT,
            programa TEXT,
            nivel TEXT,
            area TEXT,
            plantel TEXT,
            detected_titles_json TEXT,
            bibliography_ref_count INTEGER,
            ready_for_ai INTEGER
        )
    """)

    conn.commit()


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"No encontré parquet bibliográfico: {INPUT_PATH}")

    if OUTPUT_DB.exists():
        print(f"Eliminando índice previo: {OUTPUT_DB}")
        OUTPUT_DB.unlink()

    dataset = ds.dataset(str(INPUT_PATH), format="parquet")
    available = set(dataset.schema.names)

    if "titulo_normalizado" not in available:
        raise RuntimeError(
            "El parquet bibliográfico no tiene columna titulo_normalizado. "
            f"Columnas disponibles: {dataset.schema.names}"
        )

    columns = [c for c in WANTED_COLUMNS if c in available]

    print(f"Input parquet: {INPUT_PATH}")
    print(f"Output SQLite: {OUTPUT_DB}")
    print(f"Batch size: {BATCH_SIZE}")
    print("Columnas leídas:")
    for c in columns:
        print("-", c)

    conn = sqlite3.connect(str(OUTPUT_DB))

    # PRAGMAs seguros para Codespaces: no usar temp_store MEMORY grande.
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA cache_size = -20000")

    init_db(conn)

    insert_sql = """
        INSERT INTO bibliography (
            titulo_key,
            doc_number,
            titulo,
            titulo_normalizado,
            anio,
            autor,
            asesor,
            programa,
            nivel,
            area,
            plantel,
            detected_titles_json,
            bibliography_ref_count,
            ready_for_ai
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    total = 0
    inserted = 0
    skipped_empty_key = 0

    scanner = dataset.scanner(
        columns=columns,
        batch_size=BATCH_SIZE,
    )

    try:
        for batch_i, batch in enumerate(scanner.to_batches(), start=1):
            df = batch.to_pandas()
            rows = []

            for _, r in df.iterrows():
                titulo_normalizado = safe_text(r.get("titulo_normalizado"))
                titulo_key = normalize_title_key(titulo_normalizado)

                total += 1

                if not titulo_key:
                    skipped_empty_key += 1
                    continue

                rows.append((
                    titulo_key,
                    safe_text(r.get("doc_number")),
                    safe_text(r.get("titulo")),
                    titulo_normalizado,
                    safe_int(r.get("anio")),
                    safe_text(r.get("autor")),
                    safe_text(r.get("asesor")),
                    safe_text(r.get("programa")),
                    safe_text(r.get("nivel")),
                    safe_text(r.get("area")),
                    safe_text(r.get("plantel")),
                    safe_detected_titles(r.get("detected_titles")),
                    safe_int(r.get("bibliography_ref_count")),
                    safe_bool(r.get("ready_for_ai")),
                ))

            if rows:
                conn.executemany(insert_sql, rows)
                inserted += len(rows)

            conn.commit()

            if batch_i % 10 == 0:
                print(
                    f"Batch {batch_i} | procesadas: {total:,} | "
                    f"insertadas: {inserted:,} | sin key: {skipped_empty_key:,}",
                    flush=True
                )

            del df
            del rows

        print("Creando índice por titulo_key...")
        conn.execute(
            "CREATE INDEX idx_bibliography_titulo_key ON bibliography(titulo_key)"
        )
        conn.commit()

    finally:
        conn.close()

    print("\nOK")
    print("Procesadas:", total)
    print("Insertadas:", inserted)
    print("Sin titulo_key:", skipped_empty_key)
    print("DB:", OUTPUT_DB)
    print("\nAgrega a .env:")
    print(f"BIBLIOGRAPHY_INDEX_PATH={OUTPUT_DB.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()