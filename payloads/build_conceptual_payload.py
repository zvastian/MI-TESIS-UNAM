import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

CONTEXT_PATH = BASE_DIR / "payloads" / "context_minimal.json"
OUTPUT_PATH = BASE_DIR / "payloads" / "ai_conceptual_payload.json"


def main():
    if not CONTEXT_PATH.exists():
        raise FileNotFoundError(f"No encontré {CONTEXT_PATH}")

    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        ctx = json.load(f)

    payload = {
        "user_project": ctx.get("user_project", {}),
        "semantic_position": ctx.get("semantic_position", {}),
        "keywords_detected": ctx.get("keywords_detected", []),
        "temporal_patterns": ctx.get("temporal_patterns", {}),
        "top_similar_theses": ctx.get("top_similar_theses", [])[:8],
        "novelty_signals": ctx.get("novelty_signals", {}),
        "bridge_clusters": ctx.get("bridge_clusters", []),
        "bibliography_status": ctx.get("bibliography_status", {}),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH.relative_to(BASE_DIR)}")
    print("chars:", len(json.dumps(payload, ensure_ascii=False)))


if __name__ == "__main__":
    main()
