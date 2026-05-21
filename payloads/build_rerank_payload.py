import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
from pathlib import Path


CONTEXT_PATH = BASE_DIR / "payloads" / "context_minimal.json"
OUTPUT_PATH = Path("ai_rerank_payload.json")


def main():
    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        ctx = json.load(f)

    user_project = ctx.get("user_project", {})

    candidates = []

    for i, t in enumerate(ctx.get("top_similar_theses", [])[:10], start=1):
        candidates.append({
            "candidate_id": f"T{i:02d}",
            "title": t.get("title"),
            "year": t.get("year"),
            "program": t.get("program")
        })

    payload = {
        "user_project": {
            "title": user_project.get("title"),
            "keywords": user_project.get("keywords", []),
            "objectives": user_project.get("objectives", []),
            "program": user_project.get("program"),
            "degree": user_project.get("degree"),
            "study_period": user_project.get("study_period")
        },
        "semantic_signals": {
            "keywords_detected": ctx.get("keywords_detected", [])[:8],
            "known_tensions": [
                "La idea compara México y China.",
                "Los antecedentes cercanos están más cargados hacia México.",
                "Prioriza tesis útiles para delimitar banca, Estado, regulación o desarrollo financiero."
            ]
        },
        "candidates": candidates
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH}")
    print("candidates:", len(candidates))
    print("chars:", len(json.dumps(payload, ensure_ascii=False)))


if __name__ == "__main__":
    main()
# Ensure output is stored under payloads/
_src = BASE_DIR / "ai_rerank_payload.json"
_dst = BASE_DIR / "payloads/ai_rerank_payload.json"
if _src.exists():
    _dst.parent.mkdir(parents=True, exist_ok=True)
    _src.replace(_dst)
