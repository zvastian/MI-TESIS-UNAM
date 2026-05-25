import json
from pathlib import Path
import numpy as np

INPUT_CANDIDATES = [
    Path("static/nobel/nobel_atlas.json"),
    Path("nobel/nobel_atlas.json"),
    Path("nobel_atlas.json"),
]

CACHE_PATH = Path("outputs/nobel/nobel_motivation_translations_cache.json")
EMB_PATH = Path("outputs/nobel/nobel_embeddings_es.npy")

OUT_JSON = Path("outputs/nobel/nobel_atlas_es_ui.json")
OUT_STATIC = Path("static/nobel/nobel_atlas_es_ui.json")


def find_original():
    for p in INPUT_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("No encontré el nobel_atlas.json original.")


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


def build_embedding_text_es(node):
    return ". ".join(
        part for part in [
            safe_str(node.get("category")),
            safe_str(node.get("motivation_es")),
            safe_str(node.get("name")),
            safe_str(node.get("award_year")),
        ]
        if part
    )


original_path = find_original()

if not CACHE_PATH.exists():
    raise FileNotFoundError(
        f"No encontré el cache de traducciones: {CACHE_PATH}. "
        "No quiero traducir de nuevo."
    )

print("Loading original atlas:", original_path)
payload = json.loads(original_path.read_text(encoding="utf-8"))

print("Loading translation cache:", CACHE_PATH)
cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

nodes = payload.get("nodes", [])
print("Nodes:", len(nodes))

missing = 0

for node in nodes:
    motivation = safe_str(node.get("motivation")).strip()
    motivation_es = cache.get(motivation)

    if not motivation_es:
        missing += 1
        motivation_es = motivation

    node["motivation_es"] = motivation_es
    node["embedding_text_es"] = build_embedding_text_es(node)

payload.setdefault("meta", {})
payload["meta"]["language_ui"] = "es"
payload["meta"]["motivation_original_field"] = "motivation"
payload["meta"]["motivation_translated_field"] = "motivation_es"
payload["meta"]["embedding_text_es_field"] = "embedding_text_es"
payload["meta"]["layout_preserved"] = True
payload["meta"]["layout_preserved_note"] = (
    "Este archivo conserva x/y, semantic_x/y, semantic_neighbors, field_mix y area_mix "
    "del atlas original. Solo agrega motivation_es y embedding_text_es."
)

if EMB_PATH.exists():
    payload["meta"]["spanish_embedding_file"] = str(EMB_PATH)
else:
    payload["meta"]["spanish_embedding_file"] = None

OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_STATIC.parent.mkdir(parents=True, exist_ok=True)

text = json.dumps(json_sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False)

OUT_JSON.write_text(text, encoding="utf-8")
OUT_STATIC.write_text(text, encoding="utf-8")

print("DONE")
print("Missing translations:", missing)
print("Saved:", OUT_JSON)
print("Saved:", OUT_STATIC)
print("Embeddings already exist:", EMB_PATH.exists(), EMB_PATH)
