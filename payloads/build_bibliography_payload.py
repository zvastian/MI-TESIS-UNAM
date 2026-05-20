import json
from pathlib import Path


CONTEXT_PATH = Path("context_minimal.json")
INITIAL_NOTE_PATH = Path("outputs/ai_conceptual_interpretation.json")
QUESTIONS_PATH = Path("outputs/ai_questions_groq_20b.json")
OUTPUT_PATH = Path("ai_bibliography_payload.json")


MAX_SOURCE_THESES = 5
MAX_TITLES_PER_THESIS = 4


def load_json_if_exists(path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def unwrap_output(data):
    if isinstance(data, dict) and isinstance(data.get("output"), dict):
        return data["output"]
    return data


def compact_initial_note(data):
    if not data:
        return None

    data = unwrap_output(data)

    note = data.get("initial_note", {})
    if not isinstance(note, dict) or not note:
        return None

    return {
        "scope_note": note.get("scope_note", ""),
        "one_sentence_reframe": note.get("one_sentence_reframe", "")
    }


def compact_questions(data):
    if not data:
        return None

    data = unwrap_output(data)

    rq = data.get("research_questions", {})
    if not isinstance(rq, dict) or not rq:
        return None

    questions = []

    for q in rq.get("questions", [])[:4]:
        if not isinstance(q, dict):
            continue

        questions.append({
            "type": q.get("type", ""),
            "question": q.get("question", "")
        })

    return {
        "questions": questions
    }


def get_bibliography_sources(ctx):
    if isinstance(ctx.get("bibliography_summaries"), list):
        return ctx["bibliography_summaries"]

    if isinstance(ctx.get("bibliography_pool"), list):
        return ctx["bibliography_pool"]

    return []


def get_source_title(source):
    return (
        source.get("thesis_title")
        or source.get("source_thesis_title")
        or source.get("titulo")
        or source.get("title")
        or source.get("matched_title")
        or ""
    )


def get_source_doc(source):
    return (
        source.get("doc_number")
        or source.get("bibliography_doc_number")
        or source.get("source_doc_number")
        or source.get("doc")
        or ""
    )


def get_clean_titles(source):
    titles = source.get("bibliography_titles_clean")

    if isinstance(titles, list) and titles:
        return [
            str(t).strip()
            for t in titles
            if t is not None and str(t).strip()
        ]

    detected = source.get("detected_titles")

    if isinstance(detected, list) and detected:
        clean = []

        for item in detected:
            if isinstance(item, dict):
                title = item.get("title")
            else:
                title = item

            if title is not None and str(title).strip():
                clean.append(str(title).strip())

        return clean

    titles = source.get("titles")

    if isinstance(titles, list):
        return [
            str(t).strip()
            for t in titles
            if t is not None and str(t).strip()
        ]

    return []


def main():
    if not CONTEXT_PATH.exists():
        raise FileNotFoundError(f"No encontré {CONTEXT_PATH}")

    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        ctx = json.load(f)

    user_project = ctx.get("user_project", {})

    initial_note = compact_initial_note(load_json_if_exists(INITIAL_NOTE_PATH))
    questions = compact_questions(load_json_if_exists(QUESTIONS_PATH))

    raw_sources = get_bibliography_sources(ctx)

    bibliography_candidates = []
    used_titles = set()
    source_count = 0

    for source in raw_sources:
        if source_count >= MAX_SOURCE_THESES:
            break

        source_title = get_source_title(source)
        source_doc = get_source_doc(source)
        clean_titles = get_clean_titles(source)

        if not clean_titles:
            continue

        source_count += 1
        source_id = f"S{source_count:02d}"

        titles_payload = []
        local_count = 0

        for title in clean_titles:
            title_key = title.lower().strip()

            if not title_key or title_key in used_titles:
                continue

            used_titles.add(title_key)
            local_count += 1

            bib_id = f"{source_id}_B{local_count:02d}"

            titles_payload.append({
                "bib_id": bib_id,
                "title": title
            })

            if local_count >= MAX_TITLES_PER_THESIS:
                break

        if not titles_payload:
            continue

        bibliography_candidates.append({
            "source_id": source_id,
            "source_doc_number": source_doc,
            "source_thesis_title": source_title,
            "titles": titles_payload
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
        "initial_note": initial_note,
        "research_questions": questions,
        "semantic_signals": {
            "keywords_detected": ctx.get("keywords_detected", [])[:8],
            "known_tensions": [
                "Puede haber más fuentes sobre un país, tema o enfoque que sobre otro.",
                "No deben inventarse fuentes externas.",
                "Prioriza fuentes útiles para antecedentes, comparación y marco conceptual.",
                "Detecta vacíos de cobertura respecto a entidades, periodos, países, sectores o enfoques centrales del proyecto."
            ]
        },
        "bibliography_candidates": bibliography_candidates
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    total_titles = sum(len(s["titles"]) for s in bibliography_candidates)

    print(f"Guardado {OUTPUT_PATH}")
    print("source theses:", len(bibliography_candidates))
    print("candidate titles:", total_titles)
    print("chars:", len(json.dumps(payload, ensure_ascii=False)))


if __name__ == "__main__":
    main()