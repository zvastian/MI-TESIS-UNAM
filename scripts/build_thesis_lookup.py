from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]

INPUT_CANDIDATES = [
    ROOT / "base.parquet",
    ROOT / "data" / "base.parquet",
    ROOT / "static" / "explore" / "base.parquet",
]

OUTPUT_PATH = ROOT / "data" / "thesis_lookup.parquet"

BATCH_SIZE = 10_000


COLUMN_CANDIDATES = {
    "thesis_id": ["thesis_id", "ID_Limpio", "ID_Aleph", "doc_number_url", "doc_number"],
    "title": ["title", "titulo", "título", "source_thesis_title"],
    "title_norm_existing": ["title_norm", "titulo_normalizado", "titulo_norm"],
    "year": ["year", "anio", "año", "Año"],
    "degree": ["degree_norm", "degree", "nivel_estandar", "nivel", "grado"],
    "program": ["program_norm", "program", "programa"],
    "plantel": ["plantel_norm", "plantel", "plantel_estandarizado"],
    "area": ["area_norm", "area", "área", "materia_general", "materia general"],
    "advisor": ["advisor_norm", "advisor_name", "asesor_limpio_v2", "asesor"],
    "author": ["author", "autor_limpio_v2", "autor"],
    "url": ["url", "pdf_url", "link_extraido_regex"],
}


OUTPUT_SCHEMA = pa.schema([
    ("thesis_id", pa.string()),
    ("title", pa.string()),
    ("title_norm", pa.string()),
    ("year", pa.int64()),
    ("degree", pa.string()),
    ("degree_norm", pa.string()),
    ("program", pa.string()),
    ("program_norm", pa.string()),
    ("plantel", pa.string()),
    ("plantel_norm", pa.string()),
    ("area", pa.string()),
    ("area_norm", pa.string()),
    ("advisor", pa.string()),
    ("advisor_norm", pa.string()),
    ("author", pa.string()),
    ("url", pa.string()),
    ("title_raw", pa.string()),
])


def find_input() -> Path:
    for p in INPUT_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("No encontré base.parquet en rutas esperadas.")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    value = str(value)
    if value.lower() in {"nan", "none", "null"}:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9ñü\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    if value.lower() in {"nan", "none", "null"}:
        return ""
    return value


def clean_title(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""

    # Corta nota catalográfica común para que el Taller muestre títulos limpios.
    text = re.split(
        r"\s*/\s*(tesis\s+que\s+para\s+obtener|que\s+para\s+obtener)",
        text,
        flags=re.I
    )[0].strip()

    return text


def parse_year(value: Any) -> int | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    m = re.search(r"(18|19|20)\d{2}", text)
    if not m:
        return None

    try:
        return int(m.group(0))
    except Exception:
        return None


def pick_column(columns: list[str], candidates: list[str]) -> str | None:
    lower_to_actual = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_to_actual:
            return lower_to_actual[cand.lower()]
    return None


def list_from_batch(batch: pa.RecordBatch, col: str | None, n: int) -> list[Any]:
    if not col:
        return [""] * n
    if col not in batch.schema.names:
        return [""] * n
    return batch.column(batch.schema.get_field_index(col)).to_pylist()


def main() -> None:
    input_path = find_input()
    output_path = OUTPUT_PATH
    output_path.parent.mkdir(exist_ok=True)

    if output_path.exists():
        output_path.unlink()

    pf = pq.ParquetFile(input_path)
    columns = pf.schema.names

    source = {}
    for canonical, candidates in COLUMN_CANDIDATES.items():
        source[canonical] = pick_column(columns, candidates)

    read_columns = sorted({
        col for col in source.values()
        if col is not None
    })

    print(f"Input: {input_path}")
    print(f"Rows metadata: {pf.metadata.num_rows:,}")
    print(f"Read columns ({len(read_columns)}): {read_columns}")
    print("Column mapping:")
    for k, v in source.items():
        print(f"  {k}: {v}")

    writer: pq.ParquetWriter | None = None
    total_seen = 0
    total_written = 0
    fallback_id_counter = 0

    try:
        for batch_idx, batch in enumerate(
            pf.iter_batches(
                batch_size=BATCH_SIZE,
                columns=read_columns,
                use_threads=False
            ),
            start=1
        ):
            n = batch.num_rows
            total_seen += n

            raw_ids = list_from_batch(batch, source["thesis_id"], n)
            raw_titles = list_from_batch(batch, source["title"], n)

            if source["title_norm_existing"]:
                raw_title_norms = list_from_batch(batch, source["title_norm_existing"], n)
            else:
                raw_title_norms = [""] * n

            raw_years = list_from_batch(batch, source["year"], n)
            raw_degree = list_from_batch(batch, source["degree"], n)
            raw_program = list_from_batch(batch, source["program"], n)
            raw_plantel = list_from_batch(batch, source["plantel"], n)
            raw_area = list_from_batch(batch, source["area"], n)
            raw_advisor = list_from_batch(batch, source["advisor"], n)
            raw_author = list_from_batch(batch, source["author"], n)
            raw_url = list_from_batch(batch, source["url"], n)

            rows = {name: [] for name in OUTPUT_SCHEMA.names}

            for i in range(n):
                title_raw = clean_text(raw_titles[i])
                title = clean_title(title_raw)

                title_norm = normalize_text(raw_title_norms[i]) if raw_title_norms[i] else normalize_text(title)
                if not title_norm:
                    continue

                thesis_id = clean_text(raw_ids[i])
                if not thesis_id:
                    fallback_id_counter += 1
                    thesis_id = f"TH_{fallback_id_counter:07d}"

                degree = clean_text(raw_degree[i])
                program = clean_text(raw_program[i])
                plantel = clean_text(raw_plantel[i])
                area = clean_text(raw_area[i])
                advisor = clean_text(raw_advisor[i])

                rows["thesis_id"].append(thesis_id)
                rows["title"].append(title)
                rows["title_norm"].append(title_norm)
                rows["year"].append(parse_year(raw_years[i]))
                rows["degree"].append(degree)
                rows["degree_norm"].append(normalize_text(degree))
                rows["program"].append(program)
                rows["program_norm"].append(normalize_text(program))
                rows["plantel"].append(plantel)
                rows["plantel_norm"].append(normalize_text(plantel))
                rows["area"].append(area)
                rows["area_norm"].append(normalize_text(area))
                rows["advisor"].append(advisor)
                rows["advisor_norm"].append(normalize_text(advisor))
                rows["author"].append(clean_text(raw_author[i]))
                rows["url"].append(clean_text(raw_url[i]))
                rows["title_raw"].append(title_raw)

            if not rows["thesis_id"]:
                continue

            table = pa.Table.from_pydict(rows, schema=OUTPUT_SCHEMA)

            if writer is None:
                writer = pq.ParquetWriter(
                    output_path,
                    OUTPUT_SCHEMA,
                    compression="zstd",
                    use_dictionary=True,
                    write_statistics=True
                )

            writer.write_table(table)
            total_written += table.num_rows

            if batch_idx == 1 or batch_idx % 10 == 0:
                print(
                    f"Batch {batch_idx:,} | seen {total_seen:,} | written {total_written:,}",
                    flush=True
                )

    finally:
        if writer is not None:
            writer.close()

    if not output_path.exists():
        raise RuntimeError("No se creó thesis_lookup.parquet.")

    size_mb = output_path.stat().st_size / 1024 / 1024

    print("")
    print(f"Output: {output_path}")
    print(f"Rows seen: {total_seen:,}")
    print(f"Rows output: {total_written:,}")
    print(f"Size MB: {size_mb:.2f}")


if __name__ == "__main__":
    main()
