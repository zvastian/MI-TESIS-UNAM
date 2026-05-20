import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from sentence_transformers import SentenceTransformer
from sklearn.cluster import MiniBatchKMeans


BASE_DIR = Path(__file__).resolve().parents[1]

SOURCE_PATH = BASE_DIR / os.getenv("SOURCE_PATH", "Base.parquet")

OUTPUT_META_PATH = BASE_DIR / "sample_50k_final_15d.parquet"
OUTPUT_EMBEDDINGS_PATH = BASE_DIR / "sample_50k_embeddings.npy"

SAMPLE_SIZE = int(os.getenv("SAMPLE_SIZE", "2000"))
RANDOM_STATE = int(os.getenv("RANDOM_STATE", "42"))

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
PARQUET_BATCH_SIZE = int(os.getenv("PARQUET_BATCH_SIZE", "25000"))
N_CLUSTERS = int(os.getenv("N_CLUSTERS", "80"))


COLUMN_ALIASES = {
    "ID_Limpio": ["ID_Limpio", "doc_number", "id", "ID", "ID_global"],
    "titulo_normalizado": ["titulo_normalizado", "titulo", "title", "Título", "Titulo"],
    "Año": ["Año", "anio", "year", "año"],
    "programa": ["programa", "program", "Programa"],
    "nivel_estandar": ["nivel_estandar", "nivel", "degree", "grado"],
    "area": ["area", "area_conocimiento", "Área"],
    "asesor_limpio_v2": ["asesor_limpio_v2", "asesor", "advisor"],
    "asesores_limpios_v2": ["asesores_limpios_v2", "asesores", "advisors"],
    "plantel_estandarizado": ["plantel_estandarizado", "plantel", "entidad", "Plantel"],
    "periodo": ["periodo", "period"],
}


def resolve_columns(available_columns: list[str]) -> dict[str, str | None]:
    available = set(available_columns)
    resolved = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        found = None

        for alias in aliases:
            if alias in available:
                found = alias
                break

        resolved[canonical] = found

    return resolved


def build_period(y):
    try:
        y = int(y)
    except Exception:
        return "sin_fecha"

    if y < 1980:
        return "antes_1980"
    if y < 1991:
        return "1981_1990"
    if y < 2001:
        return "1991_2000"
    if y < 2011:
        return "2001_2010"
    if y < 2021:
        return "2011_2020"

    return "2021_2030"


def normalize_sample_columns(df: pd.DataFrame, resolved: dict[str, str | None]) -> pd.DataFrame:
    out = pd.DataFrame()

    defaults = {
        "ID_Limpio": None,
        "titulo_normalizado": "",
        "Año": None,
        "programa": "",
        "nivel_estandar": "",
        "area": "",
        "asesor_limpio_v2": "",
        "asesores_limpios_v2": "",
        "plantel_estandarizado": "",
        "periodo": "",
    }

    for canonical, default in defaults.items():
        source_col = resolved.get(canonical)

        if source_col and source_col in df.columns:
            out[canonical] = df[source_col]
        else:
            out[canonical] = default

    out = out[out["titulo_normalizado"].notna()].copy()
    out["titulo_normalizado"] = out["titulo_normalizado"].astype(str).str.strip()
    out = out[out["titulo_normalizado"] != ""].copy()

    if "periodo" not in out.columns or out["periodo"].isna().all() or (out["periodo"].astype(str).str.strip() == "").all():
        out["periodo"] = out["Año"].apply(build_period)
    else:
        mask = out["periodo"].isna() | (out["periodo"].astype(str).str.strip() == "")
        out.loc[mask, "periodo"] = out.loc[mask, "Año"].apply(build_period)

    return out


def reservoir_sample_parquet(path: Path, sample_size: int, random_state: int) -> pd.DataFrame:
    dataset = ds.dataset(str(path), format="parquet")
    available_columns = dataset.schema.names

    resolved = resolve_columns(available_columns)

    read_columns = sorted({
        col for col in resolved.values()
        if col is not None
    })

    if not read_columns:
        raise RuntimeError("No pude resolver columnas útiles del parquet.")

    print("Columnas disponibles:", len(available_columns))
    print("Columnas leídas:", read_columns)
    print("Columnas resueltas:", resolved)

    rng = np.random.default_rng(random_state)

    reservoir = []
    seen = 0

    scanner = dataset.scanner(
        columns=read_columns,
        batch_size=PARQUET_BATCH_SIZE,
    )

    for batch_i, batch in enumerate(scanner.to_batches(), start=1):
        df_batch = batch.to_pandas()
        df_batch = normalize_sample_columns(df_batch, resolved)

        if df_batch.empty:
            continue

        for row in df_batch.itertuples(index=False):
            seen += 1

            if len(reservoir) < sample_size:
                reservoir.append(row)
            else:
                j = rng.integers(0, seen)
                if j < sample_size:
                    reservoir[j] = row

        if batch_i % 10 == 0:
            print(f"Batches: {batch_i} | vistos válidos: {seen:,} | muestra: {len(reservoir):,}")

    if not reservoir:
        raise RuntimeError("No se obtuvo ninguna fila válida del parquet.")

    columns = [
        "ID_Limpio",
        "titulo_normalizado",
        "Año",
        "programa",
        "nivel_estandar",
        "area",
        "asesor_limpio_v2",
        "asesores_limpios_v2",
        "plantel_estandarizado",
        "periodo",
    ]

    sample = pd.DataFrame(reservoir, columns=columns)
    sample = sample.reset_index(drop=True)

    return sample


def build_embedding_text(row: pd.Series) -> str:
    parts = [
        row.get("titulo_normalizado", ""),
        row.get("programa", ""),
        row.get("nivel_estandar", ""),
        row.get("area", ""),
        row.get("plantel_estandarizado", ""),
    ]

    return " | ".join(
        str(x).strip()
        for x in parts
        if x is not None and str(x).strip()
    )


def main():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"No encontré fuente: {SOURCE_PATH}")

    print(f"Leyendo muestra desde {SOURCE_PATH}")
    print(f"SAMPLE_SIZE={SAMPLE_SIZE:,}")

    df_sample = reservoir_sample_parquet(
        path=SOURCE_PATH,
        sample_size=SAMPLE_SIZE,
        random_state=RANDOM_STATE,
    )

    print("Muestra obtenida:", df_sample.shape)

    texts = [
        build_embedding_text(row)
        for _, row in df_sample.iterrows()
    ]

    print(f"Cargando modelo: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Generando embeddings...")
    X = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32")

    print("Embeddings:", X.shape)

    n_clusters = min(N_CLUSTERS, len(df_sample))

    print(f"Creando clusters con MiniBatchKMeans: {n_clusters}")

    kmeans = MiniBatchKMeans(
        n_clusters=n_clusters,
        random_state=RANDOM_STATE,
        batch_size=2048,
        n_init="auto",
    )

    labels = kmeans.fit_predict(X)

    df_sample["cluster"] = labels.astype(int)

    print(f"Guardando {OUTPUT_META_PATH}")
    df_sample.to_parquet(OUTPUT_META_PATH, index=False)

    print(f"Guardando {OUTPUT_EMBEDDINGS_PATH}")
    np.save(OUTPUT_EMBEDDINGS_PATH, X)

    print("\nOK")
    print("meta:", df_sample.shape)
    print("embeddings:", X.shape)
    print("clusters:", df_sample["cluster"].nunique())


if __name__ == "__main__":
    main()