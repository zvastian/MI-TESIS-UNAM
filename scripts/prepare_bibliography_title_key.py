import os
import re
import unicodedata
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = BASE_DIR / os.getenv(
    "BIBLIOGRAPHY_INPUT_PATH",
    "semantic_bibliography_dataset.parquet"
)

OUTPUT_PATH = BASE_DIR / os.getenv(
    "BIBLIOGRAPHY_OUTPUT_PATH",
    "semantic_bibliography_dataset_with_title_key.parquet"
)

BATCH_SIZE = int(os.getenv("PARQUET_BATCH_SIZE", "5000"))


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


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"No encontré parquet bibliográfico: {INPUT_PATH}")

    if OUTPUT_PATH.exists():
        print(f"Eliminando output previo: {OUTPUT_PATH}")
        OUTPUT_PATH.unlink()

    print(f"Leyendo por batches: {INPUT_PATH}")
    print(f"Batch size: {BATCH_SIZE}")

    dataset = ds.dataset(str(INPUT_PATH), format="parquet")
    columns = dataset.schema.names

    if "titulo_normalizado" not in columns:
        raise RuntimeError(
            "El parquet bibliográfico no tiene columna 'titulo_normalizado'. "
            f"Columnas disponibles: {columns}"
        )

    writer = None
    total = 0
    non_empty = 0

    scanner = dataset.scanner(
        columns=columns,
        batch_size=BATCH_SIZE,
    )

    try:
        for i, batch in enumerate(scanner.to_batches(), start=1):
            df = batch.to_pandas()

            df["titulo_key"] = df["titulo_normalizado"].apply(normalize_title_key)

            total += len(df)
            non_empty += int((df["titulo_key"].astype(str).str.strip() != "").sum())

            table = pa.Table.from_pandas(df, preserve_index=False)

            if writer is None:
                OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
                writer = pq.ParquetWriter(
                    where=str(OUTPUT_PATH),
                    schema=table.schema,
                    compression="zstd",
                )

            writer.write_table(table)

            if i % 10 == 0:
                print(
                    f"Batches: {i} | filas procesadas: {total:,} | "
                    f"titulo_key no vacío: {non_empty:,}"
                )

            del df
            del table

    finally:
        if writer is not None:
            writer.close()

    if total == 0:
        raise RuntimeError("No se procesó ninguna fila del parquet bibliográfico.")

    print("\nOK")
    print("Filas procesadas:", total)
    print("titulo_key no vacío:", non_empty)
    print(f"Guardado: {OUTPUT_PATH}")
    print("\nAgrega a .env:")
    print(f"BIBLIOGRAPHY_PATH={OUTPUT_PATH.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()