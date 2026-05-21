import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


SAMPLE_PATH = Path("sample_50k_final_15d.parquet")
EMB_PATH = Path("sample_50k_embeddings.npy")
BIB_PATH = Path("semantic_bibliography_dataset.parquet")

OUT_DIR = Path("outputs")
OUT_PATH = OUT_DIR / "visuals_global_50k.json"

SCATTER_N = 3000
RANDOM_STATE = 42


def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x)


def value_counts_payload(series, top=None):
    vc = series.astype("string").fillna("desconocido").value_counts(dropna=False)
    if top:
        vc = vc.head(top)

    total = int(vc.sum())

    return [
        {
            "label": safe_str(idx),
            "count": int(count),
            "share": round(float(count / total), 6) if total else 0,
        }
        for idx, count in vc.items()
    ]


def build_year_bucket(year):
    if pd.isna(year):
        return "desconocido"

    year = int(year)

    if year < 1980:
        return "antes_1980"
    if year <= 1990:
        return "1981_1990"
    if year <= 2000:
        return "1991_2000"
    if year <= 2010:
        return "2001_2010"
    if year <= 2020:
        return "2011_2020"
    return "2021_2030"


def minmax_scale(values):
    values = np.asarray(values, dtype=np.float32)
    mn = float(np.nanmin(values))
    mx = float(np.nanmax(values))

    if mx - mn < 1e-9:
        return np.zeros_like(values)

    return (values - mn) / (mx - mn)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading sample...")
    df = pd.read_parquet(SAMPLE_PATH)

    print("Loading embeddings...")
    emb = np.load(EMB_PATH, mmap_mode="r")

    if len(df) != emb.shape[0]:
        raise RuntimeError(
            f"Sample and embeddings are misaligned: df={len(df)}, emb={emb.shape[0]}"
        )

    print("Sample shape:", df.shape)
    print("Embedding shape:", emb.shape)

    df["Año"] = pd.to_numeric(df["Año"], errors="coerce")
    df["year_bucket"] = df["Año"].apply(build_year_bucket)

    # Bibliography coverage
    print("Loading bibliography doc ids...")
    bib = pd.read_parquet(BIB_PATH, columns=["doc_number", "bibliography_ref_count", "ready_for_ai"])

    bib_docs = set(
        bib["doc_number"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    df["has_bibliography"] = (
        df["doc_number_url"]
        .astype("string")
        .str.strip()
        .isin(bib_docs)
    )

    # Scatter preliminar
    print("Building PCA scatter sample...")
    scatter_df = df.sample(
        min(SCATTER_N, len(df)),
        random_state=RANDOM_STATE
    ).copy()

    scatter_idx = scatter_df.index.to_numpy()
    scatter_emb = np.asarray(emb[scatter_idx], dtype=np.float32)

    # Normalizar antes de PCA para consistencia
    norms = np.linalg.norm(scatter_emb, axis=1, keepdims=True)
    scatter_emb = scatter_emb / np.clip(norms, 1e-9, None)

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    xy = pca.fit_transform(scatter_emb)

    x = minmax_scale(xy[:, 0])
    y = minmax_scale(xy[:, 1])

    scatter_df["x"] = x
    scatter_df["y"] = y

    scatter_payload = []

    for _, row in scatter_df.iterrows():
        scatter_payload.append({
            "thesis_id": safe_str(row.get("thesis_id")),
            "doc_number_url": safe_str(row.get("doc_number_url")),
            "title": safe_str(row.get("titulo_limpio") or row.get("título"))[:180],
            "year": None if pd.isna(row.get("Año")) else int(row.get("Año")),
            "program": safe_str(row.get("programa")),
            "area": safe_str(row.get("area")),
            "level": safe_str(row.get("nivel_estandar")),
            "has_bibliography": bool(row.get("has_bibliography")),
            "x": round(float(row["x"]), 6),
            "y": round(float(row["y"]), 6),
        })

    # Contexto tipo cluster preliminar por área/nivel, no cluster semántico real todavía
    cluster_like_context = {
        "note": (
            "Preliminary context only. This is not final clustering. "
            "It summarizes the 50k sample by institutional area, level and time bucket."
        ),
        "area_by_level": (
            df.groupby(["area", "nivel_estandar"], dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(30)
            .to_dict("records")
        ),
        "area_by_time": (
            df.groupby(["area", "year_bucket"], dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values(["area", "year_bucket"])
            .to_dict("records")
        ),
    }

    payload = {
        "meta": {
            "dataset": "sample_50k_final_15d",
            "rows": int(len(df)),
            "embedding_shape": [int(emb.shape[0]), int(emb.shape[1])],
            "scatter_method": "PCA_2D_preliminary",
            "scatter_points": len(scatter_payload),
            "warning": (
                "semantic_scatter_sample is a lightweight PCA preview, "
                "not the final UMAP atlas."
            ),
        },
        "area_distribution": value_counts_payload(df["area"]),
        "level_distribution": value_counts_payload(df["nivel_estandar"]),
        "timeline_distribution": value_counts_payload(df["year_bucket"]),
        "program_distribution": value_counts_payload(df["programa"], top=30),
        "bibliography_coverage": {
            "sample_rows": int(len(df)),
            "with_bibliography": int(df["has_bibliography"].sum()),
            "coverage": round(float(df["has_bibliography"].mean()), 6),
            "by_area": (
                df.groupby("area", dropna=False)["has_bibliography"]
                .mean()
                .sort_values(ascending=False)
                .round(6)
                .to_dict()
            ),
            "by_level": (
                df.groupby("nivel_estandar", dropna=False)["has_bibliography"]
                .mean()
                .sort_values(ascending=False)
                .round(6)
                .to_dict()
            ),
        },
        "semantic_scatter_sample": scatter_payload,
        "cluster_like_context": cluster_like_context,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Saved:", OUT_PATH)
    print("Scatter points:", len(scatter_payload))
    print("Bibliography coverage:", payload["bibliography_coverage"]["coverage"])


if __name__ == "__main__":
    main()