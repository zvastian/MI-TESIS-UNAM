import json
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.preprocessing import normalize
from sklearn.feature_extraction.text import TfidfVectorizer

import umap
import hdbscan


SAMPLE_PATH = Path("sample_50k_final_15d.parquet")
EMB_PATH = Path("sample_50k_embeddings.npy")

OUT_NODES = Path("cluster_nodes_final_50k.parquet")
OUT_SUMMARY = Path("cluster_summary_50k.parquet")
OUT_JSON = Path("outputs/cluster_summary_50k.json")

RANDOM_STATE = 42


STOPWORDS_ES = {
    "de", "del", "la", "las", "el", "los", "en", "y", "a", "un", "una", "para",
    "por", "con", "sin", "sobre", "entre", "al", "como", "su", "sus", "se",
    "que", "e", "o", "u", "lo", "es", "son", "the", "of", "and", "in", "for",
    "to", "on", "from", "by", "an", "a"
}


def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x)


def top_counts(series, n=8):
    vc = (
        series.astype("string")
        .fillna("desconocido")
        .value_counts()
        .head(n)
    )

    return [
        {"label": str(k), "count": int(v)}
        for k, v in vc.items()
    ]


def extract_top_terms(texts, n_terms=12):
    texts = [safe_str(t) for t in texts if safe_str(t).strip()]

    if len(texts) < 3:
        return []

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        stop_words=list(STOPWORDS_ES),
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.65,
        max_features=5000,
    )

    try:
        X = vectorizer.fit_transform(texts)
    except ValueError:
        return []

    scores = np.asarray(X.mean(axis=0)).ravel()
    terms = np.array(vectorizer.get_feature_names_out())

    idx = scores.argsort()[::-1][:n_terms]

    return [
        {"term": str(terms[i]), "score": round(float(scores[i]), 6)}
        for i in idx
        if scores[i] > 0
    ]


def main():
    print("Loading sample...")
    df = pd.read_parquet(SAMPLE_PATH)

    print("Loading embeddings...")
    emb = np.load(EMB_PATH).astype("float32")

    if len(df) != emb.shape[0]:
        raise RuntimeError(f"Misalignment: df={len(df)} emb={emb.shape[0]}")

    print("Normalizing embeddings...")
    emb_norm = normalize(emb, norm="l2", axis=1).astype("float32")

    print("Building UMAP 2D projection...")
    reducer_2d = umap.UMAP(
        n_components=2,
        n_neighbors=30,
        min_dist=0.08,
        metric="cosine",
        random_state=RANDOM_STATE,
        low_memory=True,
        verbose=True,
    )

    xy = reducer_2d.fit_transform(emb_norm).astype("float32")

    print("Building UMAP 15D for clustering...")
    reducer_cluster = umap.UMAP(
        n_components=15,
        n_neighbors=30,
        min_dist=0.0,
        metric="cosine",
        random_state=RANDOM_STATE,
        low_memory=True,
        verbose=True,
    )

    emb_15d = reducer_cluster.fit_transform(emb_norm).astype("float32")

    print("Running HDBSCAN...")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=45,
        min_samples=12,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=False,
    )

    labels = clusterer.fit_predict(emb_15d)
    strengths = clusterer.probabilities_

    nodes = df.copy()

    nodes["x"] = xy[:, 0]
    nodes["y"] = xy[:, 1]
    nodes["cluster_id"] = labels.astype(int)
    nodes["cluster_strength"] = strengths.astype("float32")

    # Normalize useful aliases for frontend.
    if "plantel_limpio_final" in nodes.columns:
        nodes["plantel"] = nodes["plantel_limpio_final"]
    elif "plantel_final" in nodes.columns:
        nodes["plantel"] = nodes["plantel_final"]
    else:
        nodes["plantel"] = ""

    if "nivel_estandar" in nodes.columns:
        nodes["level"] = nodes["nivel_estandar"]
    else:
        nodes["level"] = ""

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    noise = int((labels == -1).sum())

    print("Clusters:", n_clusters)
    print("Noise:", noise)
    print("Noise share:", round(noise / len(labels), 4))

    print("Building cluster summaries...")

    summaries = []

    for cluster_id in sorted([c for c in set(labels) if c != -1]):
        cdf = nodes[nodes["cluster_id"] == cluster_id].copy()

        titles = cdf["titulo_limpio"] if "titulo_limpio" in cdf.columns else cdf["título"]

        top_terms = extract_top_terms(titles.tolist(), n_terms=14)

        sample_titles = (
            cdf.sort_values("cluster_strength", ascending=False)
            .head(8)
            [["thesis_id", "titulo_limpio", "programa", "Año"]]
            .to_dict("records")
            if "titulo_limpio" in cdf.columns
            else []
        )

        summaries.append({
            "cluster_id": int(cluster_id),
            "size": int(len(cdf)),
            "year_min": None if cdf["Año"].isna().all() else int(pd.to_numeric(cdf["Año"], errors="coerce").min()),
            "year_max": None if cdf["Año"].isna().all() else int(pd.to_numeric(cdf["Año"], errors="coerce").max()),
            "top_terms": top_terms,
            "top_programs": top_counts(cdf["programa"], 8) if "programa" in cdf.columns else [],
            "top_areas": top_counts(cdf["area"], 6) if "area" in cdf.columns else [],
            "top_levels": top_counts(cdf["nivel_estandar"], 6) if "nivel_estandar" in cdf.columns else [],
            "top_planteles": top_counts(cdf["plantel"], 8),
            "sample_titles": sample_titles,
        })

    summary = pd.DataFrame(summaries)

    print("Saving nodes:", OUT_NODES)
    nodes.to_parquet(OUT_NODES, index=False)

    print("Saving summary:", OUT_SUMMARY)
    summary.to_parquet(OUT_SUMMARY, index=False)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "dataset": "sample_50k_final_15d",
                    "rows": int(len(nodes)),
                    "clusters": int(n_clusters),
                    "noise": int(noise),
                    "noise_share": round(float(noise / len(nodes)), 6),
                    "method": "UMAP_15D_HDBSCAN",
                },
                "clusters": summaries,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("Done.")
    print("Wrote:")
    print("-", OUT_NODES)
    print("-", OUT_SUMMARY)
    print("-", OUT_JSON)


if __name__ == "__main__":
    main()