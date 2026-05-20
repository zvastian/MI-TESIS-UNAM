import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity


BASE_DIR = Path(__file__).resolve().parents[1]

META_PATH = BASE_DIR / os.getenv("META_PATH", "sample_50k_final_15d.parquet")
EMBEDDINGS_PATH = BASE_DIR / os.getenv("EMBEDDINGS_PATH", "sample_50k_embeddings.npy")

OUTPUT_NODES_PATH = BASE_DIR / "cluster_nodes_final_50k.parquet"
OUTPUT_EDGES_PATH = BASE_DIR / "cluster_edges_mutual_knn_50k.parquet"

CLUSTER_COL = os.getenv("CLUSTER_COL", "cluster")
TOP_NEIGHBORS = int(os.getenv("TOP_NEIGHBORS", "6"))


def safe_mode(series: pd.Series):
    series = series.dropna().astype(str)
    series = series[series.str.strip() != ""]

    if series.empty:
        return ""

    return series.value_counts().index[0]


def build_cluster_label(group: pd.DataFrame) -> str:
    keywords = []

    for col in ["programa", "area", "nivel_estandar"]:
        if col in group.columns:
            value = safe_mode(group[col])
            if value:
                keywords.append(value)

    if keywords:
        return " · ".join(keywords[:3])

    return "Cluster académico"


def main():
    if not META_PATH.exists():
        raise FileNotFoundError(f"No encontré meta: {META_PATH}")

    if not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(f"No encontré embeddings: {EMBEDDINGS_PATH}")

    print("Leyendo meta...")
    meta = pd.read_parquet(META_PATH)

    print("Leyendo embeddings...")
    X = np.load(EMBEDDINGS_PATH)

    if len(meta) != len(X):
        raise ValueError(f"meta y X no coinciden: meta={len(meta)}, X={len(X)}")

    if CLUSTER_COL not in meta.columns:
        raise ValueError(f"No existe columna cluster: {CLUSTER_COL}")

    print("meta:", meta.shape)
    print("X:", X.shape)

    clusters = sorted([
        int(c)
        for c in meta[CLUSTER_COL].dropna().unique().tolist()
        if int(c) != -1
    ])

    print("clusters:", len(clusters))

    centroids = []
    node_rows = []

    for cid in clusters:
        idx = meta.index[meta[CLUSTER_COL] == cid].to_numpy()
        group = meta.iloc[idx].copy()

        centroid = X[idx].mean(axis=0)
        norm = np.linalg.norm(centroid)

        if norm > 0:
            centroid = centroid / norm

        centroids.append(centroid)

        node_rows.append({
            "id": cid,
            "label": build_cluster_label(group),
            "macro_domain": safe_mode(group["area"]) if "area" in group.columns else "",
            "main_area": safe_mode(group["area"]) if "area" in group.columns else "",
            "size": int(len(group)),
            "program_top": safe_mode(group["programa"]) if "programa" in group.columns else "",
            "degree_top": safe_mode(group["nivel_estandar"]) if "nivel_estandar" in group.columns else "",
            "year_min": int(group["Año"].dropna().min()) if "Año" in group.columns and group["Año"].notna().any() else None,
            "year_max": int(group["Año"].dropna().max()) if "Año" in group.columns and group["Año"].notna().any() else None,
        })

    C = np.vstack(centroids).astype("float32")

    print("Calculando layout PCA...")
    if len(C) >= 2:
        coords = PCA(n_components=2, random_state=42).fit_transform(C)
    else:
        coords = np.zeros((len(C), 2), dtype="float32")

    nodes = pd.DataFrame(node_rows)
    nodes["x"] = coords[:, 0]
    nodes["y"] = coords[:, 1]

    print("Calculando similitud entre clusters...")
    S = cosine_similarity(C)

    edge_rows = []

    for i, source_id in enumerate(clusters):
        order = np.argsort(S[i])[::-1]

        neighbors = []

        for j in order:
            if i == j:
                continue

            neighbors.append(j)

            if len(neighbors) >= TOP_NEIGHBORS:
                break

        for j in neighbors:
            target_id = clusters[j]

            # Evitar duplicados no dirigidos
            if source_id < target_id:
                edge_rows.append({
                    "source": int(source_id),
                    "target": int(target_id),
                    "weight": float(S[i, j]),
                })

    edges = pd.DataFrame(edge_rows)

    if edges.empty:
        edges = pd.DataFrame(columns=["source", "target", "weight"])

    # Centralidades simples compatibles con thesis.py
    degree_counts = {}

    for _, row in edges.iterrows():
        degree_counts[int(row["source"])] = degree_counts.get(int(row["source"]), 0) + 1
        degree_counts[int(row["target"])] = degree_counts.get(int(row["target"]), 0) + 1

    max_degree = max(degree_counts.values()) if degree_counts else 1

    nodes["degree_centrality"] = nodes["id"].map(lambda x: degree_counts.get(int(x), 0) / max_degree)
    nodes["betweenness_centrality"] = 0.0
    nodes["pagerank"] = nodes["degree_centrality"]

    print(f"Guardando {OUTPUT_NODES_PATH}")
    nodes.to_parquet(OUTPUT_NODES_PATH, index=False)

    print(f"Guardando {OUTPUT_EDGES_PATH}")
    edges.to_parquet(OUTPUT_EDGES_PATH, index=False)

    print("\nOK")
    print("nodes:", nodes.shape)
    print("edges:", edges.shape)
    print(nodes.head())
    print(edges.head())


if __name__ == "__main__":
    main()