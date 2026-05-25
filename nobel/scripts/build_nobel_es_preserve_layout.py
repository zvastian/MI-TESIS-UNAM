import argparse
import json
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

INPUT_CANDIDATES = [
    Path("static/nobel/nobel_atlas.json"),
    Path("nobel/nobel_atlas.json"),
    Path("nobel_atlas.json"),
]

OUT_JSON = Path("outputs/nobel/nobel_atlas_es_ui.json")
OUT_STATIC_JSON = Path("static/nobel/nobel_atlas_es_ui.json")
OUT_EMB = Path("outputs/nobel/nobel_embeddings_es.npy")
OUT_CACHE = Path("outputs/nobel/nobel_motivation_translations_cache.json")


def find_input():
    for p in INPUT_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("No encontré nobel_atlas.json original.")


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


def translate_text(text, cache, sleep=0.05):
    from deep_translator import GoogleTranslator

    text = safe_str(text).strip()
    if not text:
        return ""

    if text in cache:
        return cache[text]

    translated = GoogleTranslator(source="en", target="es").translate(text)
    translated = safe_str(translated).strip()

    cache[text] = translated
    save_cache(cache)

    time.sleep(sleep)
    return translated


def build_embedding_text_es(node):
    category = safe_str(node.get("category"))
    motivation_es = safe_str(node.get("motivation_es"))
    name = safe_str(node.get("name"))
    year = safe_str(node.get("award_year"))

    return ". ".join(
        part for part in [category, motivation_es, name, year]
        if part
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="")
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--translator", choices=["deep", "passthrough"], default="deep")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else find_input()

    print("Loading original atlas:", input_path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    nodes = payload.get("nodes", [])

    if not nodes:
        raise RuntimeError("El atlas no trae nodes.")

    # Guardar coordenadas originales para validar que NO cambian.
    original_positions = {
        n["id"]: {
            "x": n.get("x"),
            "y": n.get("y"),
            "semantic_x": n.get("semantic_x"),
            "semantic_y": n.get("semantic_y"),
            "layout_anchor_x": n.get("layout_anchor_x"),
            "layout_anchor_y": n.get("layout_anchor_y"),
        }
        for n in nodes
    }

    cache = load_cache()

    print("Translating motivations without touching coordinates...")
    for i, node in enumerate(nodes, start=1):
        motivation = safe_str(node.get("motivation"))

        if args.translator == "passthrough":
            motivation_es = motivation
        else:
            motivation_es = translate_text(motivation, cache, sleep=args.sleep)

        node["motivation_es"] = motivation_es
        node["embedding_text_es"] = build_embedding_text_es(node)

        if i % 50 == 0:
            print(f"Processed {i}/{len(nodes)}")

    print("Encoding Spanish texts...")
    model = SentenceTransformer(MODEL_NAME)
    texts = [node["embedding_text_es"] for node in nodes]

    emb = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
    ).astype("float32")

    OUT_EMB.parent.mkdir(parents=True, exist_ok=True)
    np.save(OUT_EMB, emb)

    # Validar que no cambiamos coordenadas.
    changed = 0
    for node in nodes:
        old = original_positions[node["id"]]
        for key, old_value in old.items():
            if node.get(key) != old_value:
                changed += 1
                break

    if changed:
        raise RuntimeError(f"ERROR: se alteraron coordenadas en {changed} nodos.")

    payload.setdefault("meta", {})
    payload["meta"]["language_ui"] = "es"
    payload["meta"]["motivation_original_field"] = "motivation"
    payload["meta"]["motivation_translated_field"] = "motivation_es"
    payload["meta"]["embedding_text_es_field"] = "embedding_text_es"
    payload["meta"]["spanish_embedding_file"] = str(OUT_EMB)
    payload["meta"]["layout_preserved"] = True
    payload["meta"]["layout_preserved_note"] = (
        "Se conservaron las coordenadas y vecinos semánticos originales. "
        "Los embeddings en español se guardan aparte para cruces con tesis UNAM."
    )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(json_sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    OUT_STATIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_STATIC_JSON.write_text(
        json.dumps(json_sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    print("DONE")
    print("Saved:", OUT_JSON)
    print("Saved:", OUT_STATIC_JSON)
    print("Saved embeddings:", OUT_EMB, emb.shape)
    print("Coordinates changed:", changed)


if __name__ == "__main__":
    main()
