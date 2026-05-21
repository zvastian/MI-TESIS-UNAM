import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
from pathlib import Path


CONTEXT_PATH = BASE_DIR / "payloads" / "context_minimal.json"
INITIAL_NOTE_PATH = Path("outputs/ai_conceptual_interpretation.json")
BLOOM_PATH = Path("outputs/ai_bloom_groq_20b.json")
OUTPUT_PATH = Path("ai_questions_payload.json")


def load_json_if_exists(path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compact_initial_note(data):
    if not data:
        return None

    note = data.get("output", {}).get("initial_note", {})

    if not note:
        return None

    return {
        "paragraph": note.get("paragraph", ""),
        "possible_angles": [
            {
                "title": a.get("title", ""),
                "description": a.get("description", "")
            }
            for a in note.get("possible_angles", [])[:4]
        ],
        "scope_note": note.get("scope_note", ""),
        "one_sentence_reframe": note.get("one_sentence_reframe", "")
    }


def compact_bloom(data):
    if not data:
        return None

    bloom = data.get("output", {}).get("bloom_analysis", {})

    if not bloom:
        return None

    return {
        "cognitive_profile": bloom.get("cognitive_profile", ""),
        "main_risk": bloom.get("main_risk", ""),
        "missing_cognitive_step": bloom.get("missing_cognitive_step", ""),
        "revised_objectives": bloom.get("revised_objectives", [])
    }


def main():
    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        ctx = json.load(f)

    initial_data = load_json_if_exists(INITIAL_NOTE_PATH)
    bloom_data = load_json_if_exists(BLOOM_PATH)

    initial_note = compact_initial_note(initial_data)
    bloom_summary = compact_bloom(bloom_data)

    user_project = ctx.get("user_project", {})
    semantic = ctx.get("semantic_position", {})

    top_titles = []

    for t in ctx.get("top_similar_theses", [])[:5]:
        title = t.get("title")
        if title:
            top_titles.append({
                "title": title,
                "year": t.get("year"),
                "program": t.get("program")
            })

    keywords = ctx.get("keywords_detected", [])[:12]

    payload = {
        "user_project": {
            "title": user_project.get("title"),
            "keywords": user_project.get("keywords", []),
            "objectives": user_project.get("objectives", []),
            "program": user_project.get("program"),
            "degree": user_project.get("degree"),
            "study_period": user_project.get("study_period")
        },

        "initial_note": initial_note,

        "semantic_signals": {
            "main_cluster": semantic.get("main_cluster", {}),
            "keywords_detected": keywords,
            "top_similar_titles": top_titles,
            "temporal_patterns": ctx.get("temporal_patterns", {}),
            "novelty_signals": ctx.get("novelty_signals", {}),
            "bridge_clusters": ctx.get("bridge_clusters", []),
            "known_gaps_or_tensions": [
                "La comparación México-China debe cuidar la comparabilidad entre contextos históricos distintos.",
                "La dimensión china puede requerir mayor explicitación frente a los antecedentes más cargados hacia México.",
                "Antes de proponer mejoras para México, conviene formular criterios de evaluación."
            ]
        },

        "bloom_summary": bloom_summary
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH}")
    print("chars:", len(json.dumps(payload, ensure_ascii=False)))
    print("keys:", payload.keys())


if __name__ == "__main__":
    main()
# Ensure output is stored under payloads/
_src = BASE_DIR / "ai_questions_payload.json"
_dst = BASE_DIR / "payloads/ai_questions_payload.json"
if _src.exists():
    _dst.parent.mkdir(parents=True, exist_ok=True)
    _src.replace(_dst)
