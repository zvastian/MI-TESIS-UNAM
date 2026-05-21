import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

PAYLOAD_PATH = BASE_DIR / "payloads" / "ai_bibliography_payload.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "ai_bibliography_groq_20b.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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

    items = br.get("items", [])

    hydrated = []

    for i, item in enumerate(items, start=1):
        bib_id = str(item.get("bib_id", "")).strip()
        c = by_id.get(bib_id, {})

        hydrated.append({
            "rank": int(item.get("rank", i)),
            "bib_id": bib_id,
            "title": c.get("title", item.get("title", "")),
            "source_doc_number": c.get("source_doc_number", item.get("source_doc_number", "")),
            "source_thesis_title": c.get("source_thesis_title", item.get("source_thesis_title", "")),
        })

    br["items"] = hydrated
    output["bibliography_recommendations"] = br

    result["output"] = output

    write_json(OUTPUT_PATH, result)

    print("Hidratado:", OUTPUT_PATH)
    print("items:", len(hydrated))
    for x in hydrated[:5]:
        print(x["rank"], x["bib_id"], "-", x["title"][:80])


if __name__ == "__main__":
    main()
