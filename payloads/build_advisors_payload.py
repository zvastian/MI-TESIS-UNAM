import json
from pathlib import Path
from collections import Counter, defaultdict


CONTEXT_PATH = Path("context_minimal.json")
RERANK_PATH = Path("ai_rerank_groq_llama.json")
OUTPUT_PATH = Path("ai_advisors_payload.json")

MAX_ADVISORS = 12
MAX_EVIDENCE_TITLES = 4


def load_json_if_exists(path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(x):
    if x is None:
        return ""
    return str(x).strip()


def get_advisor_candidates(ctx):
    """
    Flexible extraction from context_minimal.
    Expected possible sources:
    - ctx["advisor_candidates"]
    - ctx["advisor_evidence"]
    """
    if isinstance(ctx.get("advisor_candidates"), list):
        return ctx["advisor_candidates"]

    if isinstance(ctx.get("advisor_evidence"), list):
        return ctx["advisor_evidence"]

    return []


def main():
    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        ctx = json.load(f)

    user_project = ctx.get("user_project", {})
    advisors_raw = get_advisor_candidates(ctx)

    advisor_map = {}

    for i, a in enumerate(advisors_raw, start=1):
        name = (
            a.get("advisor")
            or a.get("advisor_name")
            or a.get("asesor")
            or a.get("name")
            or ""
        )

        name = normalize_text(name)

        if not name:
            continue

        thesis_titles = []

        for key in ["titles", "theses", "evidence_titles", "top_titles", "related_theses"]:
            val = a.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        title = item.get("title") or item.get("titulo") or item.get("thesis_title")
                    else:
                        title = item

                    title = normalize_text(title)
                    if title:
                        thesis_titles.append(title)

        # Fallback if candidate has one direct title
        one_title = (
            a.get("title")
            or a.get("titulo")
            or a.get("thesis_title")
            or ""
        )
        one_title = normalize_text(one_title)
        if one_title:
            thesis_titles.append(one_title)

        # Deduplicate evidence titles
        seen = set()
        clean_titles = []
        for t in thesis_titles:
            k = t.lower()
            if k not in seen:
                seen.add(k)
                clean_titles.append(t)

        advisor_map[name] = {
            "name": name,
            "count": int(a.get("count") or a.get("thesis_count") or a.get("n") or len(clean_titles) or 1),
            "programs": a.get("programs", []) if isinstance(a.get("programs"), list) else [],
            "years": a.get("years", []) if isinstance(a.get("years"), list) else [],
            "keywords": a.get("keywords", []) if isinstance(a.get("keywords"), list) else [],
            "evidence_titles": clean_titles[:MAX_EVIDENCE_TITLES]
        }

    # Sort deterministically by count/evidence length
    advisors_sorted = sorted(
        advisor_map.values(),
        key=lambda x: (x.get("count", 0), len(x.get("evidence_titles", []))),
        reverse=True
    )[:MAX_ADVISORS]

    advisor_candidates = []

    for i, a in enumerate(advisors_sorted, start=1):
        advisor_candidates.append({
            "advisor_id": f"A{i:02d}",
            "name": a["name"],
            "evidence_count": a.get("count", 0),
            "programs": a.get("programs", [])[:4],
            "years": a.get("years", [])[:8],
            "keywords": a.get("keywords", [])[:8],
            "evidence_titles": a.get("evidence_titles", [])[:MAX_EVIDENCE_TITLES]
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
                "Sugerir asesores relacionados no implica disponibilidad actual.",
                "Prioriza afinidad temática con tesis asesoradas, no prestigio personal.",
                "La recomendación debe basarse solo en evidencia histórica del acervo."
            ]
        },
        "advisor_candidates": advisor_candidates
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH}")
    print("advisor candidates:", len(advisor_candidates))
    print("chars:", len(json.dumps(payload, ensure_ascii=False)))


if __name__ == "__main__":
    main()