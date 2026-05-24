import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


SAMPLE_PATH = Path("sample_50k_final_15d.parquet")
EMB_PATH = Path("sample_50k_embeddings.npy")
BIB_PATH = Path("semantic_bibliography_dataset.parquet")
OUT_DIR = Path("outputs")
DEFAULT_OUT = OUT_DIR / "graph_neighborhood.json"

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

DEFAULT_QUERY = (
    "sistema bancario de México y China desarrollo financiero "
    "banca estatal inversión productiva"
)

AREA_COLORS = {
    "Area 1": "#7A1E3A",
    "Area 2": "#5A9A7A",
    "Area 3": "#174EA6",
    "Area 4": "#9A6A8F",
    "Por Clasificar": "#999999",
    "": "#999999",
}


def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x)

def json_sanitize(obj):
    """
    Convert pandas/numpy NaN/NA/inf values into valid JSON nulls.
    Also converts numpy scalars into native Python values.
    """
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


def normalize_matrix(x):
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.clip(norms, 1e-9, None)


def thesis_label(title, max_len=120):
    title = safe_str(title)
    if len(title) <= max_len:
        return title
    return title[:max_len].rstrip() + "…"


def load_bib_docs():
    if not BIB_PATH.exists():
        return set()

    bib = pd.read_parquet(BIB_PATH, columns=["doc_number"])
    return set(
        bib["doc_number"]
        .dropna()
        .astype(str)
        .str.strip()
    )


def build_graph_from_query(query: str, top_k: int = 100):
    top_k = max(10, min(int(top_k), 300))

    df = pd.read_parquet(SAMPLE_PATH)
    emb = np.load(EMB_PATH, mmap_mode="r").astype("float32")

    if len(df) != emb.shape[0]:
        raise RuntimeError(f"Misalignment: df={len(df)} emb={emb.shape[0]}")

    bib_docs = load_bib_docs()

    model = SentenceTransformer(MODEL_NAME)
    q = model.encode([query], normalize_embeddings=True).astype("float32")[0]

    emb_norm = normalize_matrix(np.asarray(emb, dtype=np.float32))
    scores = emb_norm @ q

    idx = np.argsort(scores)[::-1][:top_k]

    top = df.iloc[idx].copy()
    top["similarity"] = scores[idx]

    top["has_bibliography"] = (
        top["doc_number_url"]
        .astype("string")
        .str.strip()
        .isin(bib_docs)
    )

    nodes = []
    edges = []

    nodes.append({
        "id": "PROJECT",
        "type": "project",
        "label": query,
        "title": query,
        "displayLabel": query.upper(),
        "size": 24,
        "color": "#6B4BB7",
    })

    for _, row in top.iterrows():
        thesis_id = safe_str(row.get("thesis_id"))
        area = safe_str(row.get("area"))
        title = safe_str(row.get("titulo_limpio") or row.get("título"))
        plantel = (
            safe_str(row.get("plantel_limpio_final"))
            or safe_str(row.get("plantel_estandarizado"))
            or safe_str(row.get("plantel_final"))
        )

        author = (
            safe_str(row.get("autor_limpio_v2"))
            or safe_str(row.get("autor_limpio"))
            or safe_str(row.get("autor(es)"))
        )

        nodes.append({
            "id": thesis_id,
            "type": "thesis",
            "label": thesis_label(title),
            "title": title,
            "displayLabel": title.upper(),
            "doc_number_url": safe_str(row.get("doc_number_url")),
            "year": None if pd.isna(row.get("Año")) else int(row.get("Año")),
            "program": safe_str(row.get("programa")),
            "plantel": plantel,
            "author": author,
            "area": area,
            "level": safe_str(row.get("nivel_estandar")),
            "advisor": safe_str(row.get("asesores_limpios_v2")),
            "similarity": round(float(row.get("similarity")), 6),
            "has_bibliography": bool(row.get("has_bibliography")),
            "size": round(9.2 + max(0, float(row.get("similarity")) - 0.72) * 26, 3),
            "color": AREA_COLORS.get(area, "#999999"),
        })

        edges.append({
            "source": "PROJECT",
            "target": thesis_id,
            "type": "semantic_similarity",
            "weight": round(float(row.get("similarity")), 6),
        })

    top_cols = [
        "thesis_id",
        "doc_number_url",
        "titulo_limpio",
        "programa",
        "plantel_limpio_final",
        "autor_limpio_v2",
        "autor_limpio",
        "autor(es)",
        "Año",
        "area",
        "nivel_estandar",
        "asesores_limpios_v2",
        "has_bibliography",
        "similarity",
    ]
    top_cols = [c for c in top_cols if c in top.columns]

    payload = {
        "meta": {
            "mode": "query",
            "center_id": "PROJECT",
            "query": query,
            "top_k": int(top_k),
            "dataset": "sample_50k_final_15d",
            "embedding_file": "sample_50k_embeddings.npy",
            "graph_type": "local_semantic_neighborhood_v2",
            "defaults": {
                "universe_count": 40,
                "analytic_count": 100,
                "max_display": 300,
                "color_follows_group_by": True,
            },
        },
        "nodes": nodes,
        "edges": edges,
        "top_theses": top[top_cols].to_dict("records"),
    }

    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = build_graph_from_query(args.query, args.top_k)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(json_sanitize(payload), f, ensure_ascii=False, indent=2, allow_nan=False)

    print("Saved:", out_path)
    print("nodes:", len(payload["nodes"]))
    print("edges:", len(payload["edges"]))
    print("top_k:", payload["meta"]["top_k"])

    print("\nTop 5:")
    for t in payload["top_theses"][:5]:
        print("-", t["titulo_limpio"], "|", t["programa"], "|", t["similarity"])


if __name__ == "__main__":
    main()
