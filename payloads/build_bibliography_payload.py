import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

CONTEXT_PATH = BASE_DIR / "payloads" / "context_minimal.json"
OUTPUT_PATH = BASE_DIR / "payloads" / "ai_bibliography_payload.json"


def load_json(path: Path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if not CONTEXT_PATH.exists():
        raise FileNotFoundError(f"No encontré contexto: {CONTEXT_PATH}")

    ctx = load_json(CONTEXT_PATH)

    bibliography_summaries = ctx.get("bibliography_summaries", [])

    source_theses = []
    bibliography_candidates = []

    seen_titles = set()

    for source_idx, source in enumerate(bibliography_summaries, start=1):
        source_id = f"S{source_idx:02d}"

        source_thesis = {
            "source_id": source_id,
            "source_thesis_title": source.get("source_thesis_title", ""),
            "source_similarity": source.get("source_similarity"),
            "bibliography_doc_number": source.get("bibliography_doc_number", ""),
            "bibliography_thesis_title": source.get("bibliography_thesis_title", ""),
            "bibliography_year": source.get("bibliography_year"),
            "bibliography_program": source.get("bibliography_program", ""),
            "match_type": source.get("match_type", ""),
        }

        source_theses.append(source_thesis)

        titles = source.get("titles", [])

        if not isinstance(titles, list):
            continue

        for title_idx, title in enumerate(titles, start=1):
            title = str(title).strip()

            if not title:
                continue

            key = title.lower()

            if key in seen_titles:
                continue

            seen_titles.add(key)

            bib_id = f"{source_id}_B{title_idx:02d}"

            bibliography_candidates.append({
                "bib_id": bib_id,
                "title": title,
                "source_id": source_id,
                "source_doc_number": source.get("bibliography_doc_number", ""),
                "source_thesis_title": source.get("source_thesis_title", ""),
                "bibliography_thesis_title": source.get("bibliography_thesis_title", ""),
                "source_similarity": source.get("source_similarity"),
            })

    payload = {
        "user_project": ctx.get("user_project", {}),
        "semantic_position": ctx.get("semantic_position", {}),
        "research_questions": ctx.get("research_questions", {}),
        "bibliography_status": ctx.get("bibliography_status", {}),
        "source_theses": source_theses,
        "bibliography_candidates": bibliography_candidates,
        "instructions": {
            "use_only_existing_bib_ids": True,
            "do_not_invent_sources": True,
            "candidate_count": len(bibliography_candidates),
        }
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH.relative_to(BASE_DIR)}")
    print("source theses:", len(source_theses))
    print("candidate titles:", len(bibliography_candidates))
    print("chars:", len(json.dumps(payload, ensure_ascii=False)))


if __name__ == "__main__":
    main()