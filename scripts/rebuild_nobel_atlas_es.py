import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize
from sentence_transformers import SentenceTransformer
import umap


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

DEFAULT_INPUTS = [
    Path("nobel/nobel_atlas.json"),
    Path("static/nobel/nobel_atlas.json"),
    Path("nobel_atlas.json"),
]

OUT_JSON = Path("outputs/nobel/nobel_atlas_es.json")
OUT_EMB = Path("outputs/nobel/nobel_embeddings_es.npy")
OUT_CACHE = Path("outputs/nobel/nobel_motivation_translations_cache.json")

FIELD_TEXTS_ES = {
    "matter": "materia universo física química partículas energía estructura molecular naturaleza cósmica",
    "life": "vida salud medicina fisiología biología enfermedad cuerpo organismo tratamiento",
    "society": "sociedad economía paz política instituciones derechos mercados cooperación desarrollo",
    "culture": "cultura literatura lenguaje memoria experiencia humana creación artística pensamiento",
}

FIELD_POLES = {
    "matter": (-4.0, 2.6),
    "life": (4.0, 2.6),
    "society": (4.0, -2.6),
    "culture": (-4.0, -2.6),
}

AREA_FROM_FIELD = {
    "matter": "Area 1",
    "life": "Area 2",
    "society": "Area 3",
    "culture": "Area 4",
}


def find_input():
    for p in DEFAULT_INPUTS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "No encontré nobel_atlas.json en nobel/, static/nobel/ ni raíz."
    )


def safe_str(x):
    if x is None:
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
    if isinstance(obj, list):
        return [json_sanitize(x) for x in obj]
    if isinstance(obj, tuple):
        return [json_sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): json_sanitize(v) for k, v in obj.items()}
    return obj


def load_cache():
    if OUT_CACHE.exists():
        return json.loads(OUT_CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache):
    OUT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    OUT_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def translate_with_deep_translator(text, cache, sleep=0.07):
    from deep_translator import GoogleTranslator

    clean = safe_str(text).strip()
    if not clean:
        return ""

    if clean in cache:
        return cache[clean]

    translated = GoogleTranslator(source="en", target="es").translate(clean)
    translated = safe_str(translated).strip()

    cache[clean] = translated
    save_cache(cache)

    time.sleep(sleep)
    return translated


def build_embedding_text_es(node):
    category = safe_str(node.get("category") or node.get("category_es"))
    motivation_es = safe_str(node.get("motivation_es"))
    name = safe_str(node.get("name"))
    year = safe_str(node.get("award_year"))

    parts = [
        category,
        motivation_es,
        name,
        year,
    ]

    return ". ".join([p for p in parts if p]).strip()


def softmax_from_similarities(scores, temperature=0.08):
    scores = np.asarray(scores, dtype=np.float32)
    scores = scores / max(temperature, 1e-6)
    scores = scores - scores.max()
    exp = np.exp(scores)
    total = exp.sum()
    if total <= 0:
        return np.ones_like(exp) / len(exp)
    return exp / total


def normalize_xy(xy, scale_x=3.4, scale_y=2.6):
    xy = np.asarray(xy, dtype=np.float32)
    x = xy[:, 0]
    y = xy[:, 1]

    x = (x - x.mean()) / max(x.std(), 1e-6)
    y = (y - y.mean()) / max(y.std(), 1e-6)

    x = np.clip(x, -2.5, 2.5) / 2.5 * scale_x
    y = np.clip(y, -2.5, 2.5) / 2.5 * scale_y

    return np.column_stack([x, y]).astype(np.float32)


def compute_field_layout(field_mix, semantic_xy):
    x = 0.0
    y = 0.0
    total = 0.0

    for field, weight in field_mix.items():
        px, py = FIELD_POLES.get(field, (0, 0))
        weight = float(weight)
        x += px * weight
        y += py * weight
        total += weight

    if total > 0:
        x /= total
        y /= total

    # small semantic displacement inside the conceptual field
    x += float(semantic_xy[0]) * 0.38
    y += float(semantic_xy[1]) * 0.38

    return x, y


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="")
    parser.add_argument("--translator", choices=["deep", "passthrough"], default="deep")
    parser.add_argument("--neighbors", type=int, default=12)
    parser.add_argument("--sleep", type=float, default=0.07)
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else find_input()

    print("Loading:", input_path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    nodes = payload.get("nodes", [])

    if not nodes:
        raise RuntimeError("El JSON no trae nodes.")

    print("Nodes:", len(nodes))

    cache = load_cache()

    print("Translating motivations...")
    for i, node in enumerate(nodes, start=1):
        motivation = safe_str(node.get("motivation")).strip()

        if args.translator == "passthrough":
            motivation_es = motivation
        else:
            motivation_es = translate_with_deep_translator(
                motivation,
                cache=cache,
                sleep=args.sleep,
            )

        node["motivation_es"] = motivation_es
        node["embedding_text_es"] = build_embedding_text_es(node)

        if i % 50 == 0:
            print(f"Translated/processed {i}/{len(nodes)}")

    print("Loading embedding model:", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)

    texts = [node["embedding_text_es"] for node in nodes]

    print("Encoding Spanish embedding texts...")
    emb = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
    ).astype("float32")

    OUT_EMB.parent.mkdir(parents=True, exist_ok=True)
    np.save(OUT_EMB, emb)
    print("Saved embeddings:", OUT_EMB, emb.shape)

    print("Computing semantic neighbors...")
    sim = emb @ emb.T
    np.fill_diagonal(sim, -1.0)

    for i, node in enumerate(nodes):
        idx = np.argsort(sim[i])[::-1][: args.neighbors]
        node["semantic_neighbors"] = [
            {
                "id": nodes[j]["id"],
                "similarity": round(float(sim[i, j]), 6),
            }
            for j in idx
        ]

    print("Computing UMAP 2D...")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=24,
        min_dist=0.08,
        metric="cosine",
        random_state=42,
        low_memory=True,
    )
    xy_raw = reducer.fit_transform(emb).astype("float32")
    semantic_xy = normalize_xy(xy_raw)

    print("Computing category affinities...")
    categories = payload.get("categories", [])
    category_texts = [
        f"{c.get('es', '')}. {c.get('en', '')}".strip()
        for c in categories
    ]
    category_codes = [c.get("code") for c in categories]

    cat_emb = model.encode(
        category_texts,
        batch_size=32,
        normalize_embeddings=True,
    ).astype("float32")

    cat_sim = emb @ cat_emb.T

    print("Computing field affinities...")
    field_keys = list(FIELD_TEXTS_ES.keys())
    field_texts = [FIELD_TEXTS_ES[k] for k in field_keys]

    field_emb = model.encode(
        field_texts,
        batch_size=32,
        normalize_embeddings=True,
    ).astype("float32")

    field_sim = emb @ field_emb.T

    for i, node in enumerate(nodes):
        node["semantic_x"] = round(float(semantic_xy[i, 0]), 6)
        node["semantic_y"] = round(float(semantic_xy[i, 1]), 6)

        cat_weights = softmax_from_similarities(cat_sim[i], temperature=0.08)
        category_affinity = {
            str(code): round(float(weight), 6)
            for code, weight in zip(category_codes, cat_weights)
        }
        node["category_affinity"] = category_affinity

        field_weights = softmax_from_similarities(field_sim[i], temperature=0.08)
        field_mix = {
            field: round(float(weight), 6)
            for field, weight in zip(field_keys, field_weights)
        }
        node["field_mix"] = field_mix
        node["primary_field"] = max(field_mix, key=field_mix.get)

        area_mix = {
            "Area 1": round(float(field_mix.get("matter", 0)), 6),
            "Area 2": round(float(field_mix.get("life", 0)), 6),
            "Area 3": round(float(field_mix.get("society", 0)), 6),
            "Area 4": round(float(field_mix.get("culture", 0)), 6),
        }
        node["area_mix"] = area_mix
        node["primary_area"] = max(area_mix, key=area_mix.get)

        x, y = compute_field_layout(field_mix, semantic_xy[i])
        node["layout_anchor_x"] = round(float(x), 6)
        node["layout_anchor_y"] = round(float(y), 6)
        node["x"] = round(float(x), 6)
        node["y"] = round(float(y), 6)
        node["collision_spaced"] = False

    payload["meta"]["language"] = "es"
    payload["meta"]["translation_source_field"] = "motivation"
    payload["meta"]["translation_target_field"] = "motivation_es"
    payload["meta"]["embedding_text_field"] = "embedding_text_es"
    payload["meta"]["spanish_embedding_file"] = str(OUT_EMB)
    payload["meta"]["model"] = MODEL_NAME
    payload["meta"]["semantic_neighbors_per_node"] = args.neighbors
    payload["meta"]["layout"] = "spanish_motivation_embeddings_four_fields_v1"
    payload["meta"]["layout_note"] = (
        "Motivaciones traducidas a español; embeddings y vecinos semánticos "
        "recalculados con el mismo modelo multilingüe usado por el proyecto."
    )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(json_sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    print("Saved JSON:", OUT_JSON)

    static_out = Path("static/nobel/nobel_atlas_es.json")
    static_out.parent.mkdir(parents=True, exist_ok=True)
    static_out.write_text(
        json.dumps(json_sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print("Saved static JSON:", static_out)

    print("\nDONE")
    print("Embeddings:", OUT_EMB)
    print("JSON:", OUT_JSON)
    print("Static JSON:", static_out)


if __name__ == "__main__":
    main()
