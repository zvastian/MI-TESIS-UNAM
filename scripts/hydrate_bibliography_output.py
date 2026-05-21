import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

PAYLOAD_PATH = BASE_DIR / "payloads" / "ai_bibliography_payload.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "ai_bibliography_groq_20b.json"

MAX_ITEMS = 5


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_fallback_title(s: str) -> str:
    s = str(s or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" .;:-")
    return s


def main():
    payload = load_json(PAYLOAD_PATH)
    result = load_json(OUTPUT_PATH)

    candidates = payload.get("bibliography_candidates", [])

    by_id = {
        str(c.get("bib_id", "")).strip(): c
        for c in candidates
        if str(c.get("bib_id", "")).strip()
    }

    output = result.get("output", result)
    br = output.get("bibliography_recommendations", {})

    raw_items = br.get("items", [])
    hydrated = []
    seen_ids = set()

    for item in raw_items:
        if len(hydrated) >= MAX_ITEMS:
            break

        bib_id = str(item.get("bib_id", "")).strip()

        if not bib_id or bib_id in seen_ids:
            continue

        c = by_id.get(bib_id)

        if not c:
            continue

        seen_ids.add(bib_id)

        clean_title = (
            item.get("clean_title")
            or item.get("title")
            or c.get("bibliography_title")
            or c.get("raw_title")
            or c.get("title")
            or ""
        )

        clean_title = clean_fallback_title(clean_title)

        hydrated.append({
            "rank": len(hydrated) + 1,
            "bib_id": bib_id,

            # Esto es bibliografía, NO título de tesis.
            "title": clean_title,

            "raw_title": c.get("raw_title", ""),
            "source_doc_number": c.get("source_doc_number", ""),
            "source_thesis_title": c.get("source_thesis_title", ""),
            "source_similarity": c.get("source_similarity"),
        })

    br["items"] = hydrated
    br["title"] = br.get("title") or "Bibliografía recomendada"

    output["bibliography_recommendations"] = br
    result["output"] = output

    write_json(OUTPUT_PATH, result)

    print("Hidratado:", OUTPUT_PATH)
    print("items:", len(hydrated))

    for x in hydrated:
        print(
            x["rank"],
            x["bib_id"],
            "-",
            x["title"][:110],
            "| extraído de:",
            x["source_thesis_title"][:80],
        )


if __name__ == "__main__":
    main()
