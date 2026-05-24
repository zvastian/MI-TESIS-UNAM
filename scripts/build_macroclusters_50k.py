import argparse
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


DEFAULT_MICRO_DIR = Path("outputs/microclusters")
DEFAULT_NODES = DEFAULT_MICRO_DIR / "cluster_nodes_final_50k.parquet"
DEFAULT_SUMMARY = DEFAULT_MICRO_DIR / "cluster_summary_50k.parquet"
DEFAULT_EMB = Path("sample_50k_embeddings.npy")

OUT_DIR = Path("outputs/macroclusters")
OUT_NODES = OUT_DIR / "macrocluster_nodes_50k.parquet"
OUT_SUMMARY = OUT_DIR / "macrocluster_summary_50k.parquet"
OUT_MAP = OUT_DIR / "micro_to_macro_map_50k.parquet"
OUT_JSON = OUT_DIR / "macrocluster_summary_50k.json"

STOPWORDS_ES = {
    "de", "del", "la", "las", "el", "los", "en", "y", "a", "un", "una", "para",
    "por", "con", "sin", "sobre", "entre", "al", "como", "su", "sus", "se",
    "que", "e", "o", "u", "lo", "es", "son", "esta", "este", "estos", "estas",
    "the", "of", "and", "in", "for", "to", "on", "from", "by", "an"
}


def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x)


def json_sanitize(obj):
    if obj is None:
        return None

    if isinstance(obj, (str, bool, int)):
        return obj

    if isinstance(obj, (float, np.floating)):
        if not np.isfinite(obj):
            return None
        return float(obj)

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, (list, tuple)):
        return [json_sanitize(x) for x in obj]

    if isinstance(obj, dict):
        return {str(k): json_sanitize(v) for k, v in obj.items()}

    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass

    return obj


def top_counts(series, n=8):
    if series is None:
        return []

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


def parse_maybe_list(x):
    if isinstance(x, list):
        return x

    if isinstance(x, np.ndarray):
        return x.tolist()

    if pd.isna(x):
        return []

    if isinstance(x, str):
        s = x.strip()
        if not s:
            return []
        try:
            parsed = ast.literal_eval(s)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    return []


def extract_top_terms(texts, n_terms=14):
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
        max_features=7000,
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


def make_macro_label(top_terms, max_terms=4):
    terms = []

    for item in top_terms:
        if isinstance(item, dict):
            term = safe_str(item.get("term"))
        else:
            term = safe_str(item)

        term = term.strip()
        if term:
            terms.append(term)

    if not terms:
        return "TERRITORIO SEMÁNTICO"

    return " · ".join(terms[:max_terms]).upper()


def get_title_col(df):
    for col in ["titulo_limpio", "título", "title"]:
        if col in df.columns:
            return col
    return None


def agglomerative_fit_predict(X, n_clusters):
    """
    Compatible with sklearn versions that use either metric= or affinity=.
    """
    try:
        model = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric="cosine",
            linkage="average",
        )
        return model.fit_predict(X)
    except TypeError:
        model = AgglomerativeClustering(
            n_clusters=n_clusters,
            affinity="cosine",
            linkage="average",
        )
        return model.fit_predict(X)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--micro-nodes", default=str(DEFAULT_NODES))
    parser.add_argument("--micro-summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--embeddings", default=str(DEFAULT_EMB))
    parser.add_argument("--n-macroclusters", type=int, default=40)
    args = parser.parse_args()

    micro_nodes_path = Path(args.micro_nodes)
    micro_summary_path = Path(args.micro_summary)
    emb_path = Path(args.embeddings)

    if not micro_nodes_path.exists():
        raise FileNotFoundError(f"No existe micro-nodes: {micro_nodes_path}")

    if not emb_path.exists():
        raise FileNotFoundError(f"No existe embeddings: {emb_path}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading microcluster nodes:", micro_nodes_path)
    nodes = pd.read_parquet(micro_nodes_path)

    print("Loading embeddings:", emb_path)
    emb = np.load(emb_path, mmap_mode="r").astype("float32")

    if len(nodes) != emb.shape[0]:
        raise RuntimeError(
            f"Embeddings y nodes no están alineados: nodes={len(nodes)}, emb={emb.shape[0]}"
        )

    if "cluster_id" not in nodes.columns:
        raise RuntimeError("micro_nodes debe tener columna cluster_id")

    print("Normalizing embeddings...")
    emb_norm = normalize(np.asarray(emb, dtype=np.float32), norm="l2", axis=1).astype("float32")

    nodes = nodes.copy()
    nodes["microcluster_id"] = nodes["cluster_id"].astype(int)

    valid_micro_ids = sorted([
        int(c) for c in nodes["microcluster_id"].unique()
        if int(c) != -1
    ])

    if not valid_micro_ids:
        raise RuntimeError("No hay microclusters válidos. Todo parece ruido (-1).")

    n_macro = min(max(2, int(args.n_macroclusters)), len(valid_micro_ids))

    print("Microclusters válidos:", len(valid_micro_ids))
    print("Requested macroclusters:", args.n_macroclusters)
    print("Using macroclusters:", n_macro)

    print("Computing microcluster centroids...")
    centroid_rows = []

    for micro_id in valid_micro_ids:
        idx = nodes.index[nodes["microcluster_id"] == micro_id].to_numpy()
        centroid = emb_norm[idx].mean(axis=0)
        centroid = normalize(centroid.reshape(1, -1), norm="l2", axis=1)[0]

        sub = nodes.loc[idx]

        centroid_rows.append({
            "microcluster_id": int(micro_id),
            "size": int(len(idx)),
            "centroid": centroid.astype("float32"),
            "x": float(sub["x"].mean()) if "x" in sub.columns else None,
            "y": float(sub["y"].mean()) if "y" in sub.columns else None,
        })

    micro_df = pd.DataFrame(centroid_rows)
    centroid_matrix = np.vstack(micro_df["centroid"].to_numpy()).astype("float32")

    print("Clustering microcluster centroids into macroclusters...")
    macro_labels = agglomerative_fit_predict(centroid_matrix, n_macro)

    micro_df["macrocluster_id"] = macro_labels.astype(int)

    # Make macro IDs stable by largest macrocluster first.
    macro_sizes = (
        micro_df.groupby("macrocluster_id")["size"]
        .sum()
        .sort_values(ascending=False)
    )

    remap = {old: new for new, old in enumerate(macro_sizes.index.tolist())}
    micro_df["macrocluster_id"] = micro_df["macrocluster_id"].map(remap).astype(int)

    micro_to_macro = dict(zip(
        micro_df["microcluster_id"].astype(int),
        micro_df["macrocluster_id"].astype(int),
    ))

    nodes["macrocluster_id"] = nodes["microcluster_id"].map(micro_to_macro).fillna(-1).astype(int)

    print("Loading microcluster summary if available...")
    micro_summary = None

    if micro_summary_path.exists():
        micro_summary = pd.read_parquet(micro_summary_path)
        if "cluster_id" in micro_summary.columns:
            micro_summary["microcluster_id"] = micro_summary["cluster_id"].astype(int)
        elif "microcluster_id" in micro_summary.columns:
            micro_summary["microcluster_id"] = micro_summary["microcluster_id"].astype(int)
        else:
            micro_summary = None
    else:
        print("No existe micro-summary:", micro_summary_path)

    print("Building macrocluster summaries...")

    title_col = get_title_col(nodes)
    summaries = []

    for macro_id in sorted([c for c in nodes["macrocluster_id"].unique() if c != -1]):
        cdf = nodes[nodes["macrocluster_id"] == macro_id].copy()
        micro_ids = sorted(cdf["microcluster_id"].dropna().astype(int).unique().tolist())

        titles = cdf[title_col].tolist() if title_col else []
        top_terms = extract_top_terms(titles, n_terms=16)

        # If TF-IDF terms are weak, collect terms from microcluster summary.
        micro_terms = []

        if micro_summary is not None and "top_terms" in micro_summary.columns:
            ms = micro_summary[micro_summary["microcluster_id"].isin(micro_ids)]

            for raw in ms["top_terms"].tolist():
                for item in parse_maybe_list(raw):
                    if isinstance(item, dict) and item.get("term"):
                        micro_terms.append(item["term"])
                    elif isinstance(item, str):
                        micro_terms.append(item)

        if len(top_terms) < 4 and micro_terms:
            vc = pd.Series(micro_terms).value_counts().head(16)
            top_terms = [
                {"term": str(k), "score": round(float(v), 6)}
                for k, v in vc.items()
            ]

        macro_label = make_macro_label(top_terms, max_terms=4)

        if title_col:
            rep_cols = [c for c in [
                "thesis_id",
                title_col,
                "programa",
                "Año",
                "microcluster_id",
                "cluster_strength",
            ] if c in cdf.columns]

            representative_titles = (
                cdf.sort_values(
                    "cluster_strength",
                    ascending=False
                ).head(10)[rep_cols].to_dict("records")
                if "cluster_strength" in cdf.columns
                else cdf.head(10)[rep_cols].to_dict("records")
            )
        else:
            representative_titles = []

        micro_for_macro = micro_df[micro_df["macrocluster_id"] == macro_id].copy()

        summaries.append({
            "macrocluster_id": int(macro_id),
            "macro_label": macro_label,
            "size": int(len(cdf)),
            "microcluster_count": int(len(micro_ids)),
            "microcluster_ids": micro_ids,
            "x": float(cdf["x"].mean()) if "x" in cdf.columns else None,
            "y": float(cdf["y"].mean()) if "y" in cdf.columns else None,
            "year_min": None if "Año" not in cdf.columns or cdf["Año"].isna().all() else int(pd.to_numeric(cdf["Año"], errors="coerce").min()),
            "year_max": None if "Año" not in cdf.columns or cdf["Año"].isna().all() else int(pd.to_numeric(cdf["Año"], errors="coerce").max()),
            "top_terms": top_terms,
            "top_programs": top_counts(cdf["programa"], 8) if "programa" in cdf.columns else [],
            "top_areas": top_counts(cdf["area"], 6) if "area" in cdf.columns else [],
            "top_levels": top_counts(cdf["nivel_estandar"], 6) if "nivel_estandar" in cdf.columns else top_counts(cdf["level"], 6) if "level" in cdf.columns else [],
            "top_planteles": top_counts(cdf["plantel"], 8) if "plantel" in cdf.columns else top_counts(cdf["plantel_limpio_final"], 8) if "plantel_limpio_final" in cdf.columns else [],
            "representative_microclusters": (
                micro_for_macro.sort_values("size", ascending=False)
                .head(8)[["microcluster_id", "size"]]
                .to_dict("records")
            ),
            "representative_titles": representative_titles,
        })

    summary = pd.DataFrame(summaries)

    # Add macro labels back to node rows.
    macro_label_map = dict(zip(summary["macrocluster_id"], summary["macro_label"]))
    nodes["macro_label"] = nodes["macrocluster_id"].map(macro_label_map).fillna("NO ASIGNADO")

    print("Saving:", OUT_NODES)
    nodes.to_parquet(OUT_NODES, index=False)

    print("Saving:", OUT_SUMMARY)
    summary.to_parquet(OUT_SUMMARY, index=False)

    print("Saving:", OUT_MAP)
    micro_df_out = micro_df.drop(columns=["centroid"])
    micro_df_out.to_parquet(OUT_MAP, index=False)

    payload = {
        "meta": {
            "name": "macroclusters_50k",
            "description": "Macroclusters creados agrupando centroides de microclusters semánticos.",
            "source_micro_nodes": str(micro_nodes_path),
            "source_micro_summary": str(micro_summary_path),
            "source_embeddings": str(emb_path),
            "rows": int(len(nodes)),
            "microclusters": int(len(valid_micro_ids)),
            "macroclusters": int(summary["macrocluster_id"].nunique()),
            "noise_rows": int((nodes["macrocluster_id"] == -1).sum()),
            "method": "microcluster_centroids + AgglomerativeClustering(metric=cosine, linkage=average)",
        },
        "macroclusters": summaries,
    }

    print("Saving:", OUT_JSON)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(json_sanitize(payload), f, ensure_ascii=False, indent=2, allow_nan=False)

    print("\nDONE")
    print("Macroclusters:", summary["macrocluster_id"].nunique())
    print("Rows:", len(nodes))
    print("\nTop macroclusters:")
    print(summary[["macrocluster_id", "macro_label", "size", "microcluster_count"]].sort_values("size", ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
