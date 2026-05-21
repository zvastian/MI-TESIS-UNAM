import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

PAYLOAD_PATH = BASE_DIR / "payloads" / "ai_advisors_payload.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "ai_advisors.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def first_present(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default


def find_candidate_list(payload):
    """
    Soporta varias formas posibles:
    - advisor_candidates
    - advisors
    - candidates
    - advisor_evidence
    - context.advisor_evidence
    """
    for key in [
        "advisor_candidates",
        "advisors",
        "candidates",
        "advisor_evidence",
    ]:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    context = payload.get("context", {})
    if isinstance(context, dict):
        value = context.get("advisor_evidence")
        if isinstance(value, list):
            return value

    return []


def candidate_id_for_index(i):
    return f"A{i:02d}"


def main():
    payload = load_json(PAYLOAD_PATH)
    result = load_json(OUTPUT_PATH)

    candidates = find_candidate_list(payload)

    by_id = {}

    for i, c in enumerate(candidates, start=1):
        advisor_id = first_present(
            c,
            ["advisor_id", "id", "candidate_id"],
            candidate_id_for_index(i)
        )
        advisor_id = str(advisor_id).strip()

        by_id[advisor_id] = c

    output = result.get("output", result)
    ar = output.get("advisor_recommendations", {})

    ordered_ids = ar.get("ordered_advisor_ids", [])

    hydrated_items = []

    for rank, advisor_id in enumerate(ordered_ids, start=1):
        advisor_id = str(advisor_id).strip()
        c = by_id.get(advisor_id, {})

        representative_titles = first_present(
            c,
            [
                "representative_titles",
                "representative_theses",
                "related_titles",
                "theses",
            ],
            []
        )

        # Si viene como lista de objetos thesis records, convertir a títulos.
        if isinstance(representative_titles, list):
            converted = []
            for item in representative_titles:
                if isinstance(item, dict):
                    title = first_present(item, ["title", "titulo", "thesis_title"], "")
                    if title:
                        converted.append(title)
                elif item:
                    converted.append(str(item))
            representative_titles = converted
        else:
            representative_titles = []

        hydrated_items.append({
            "rank": rank,
            "advisor_id": advisor_id,
            "advisor_name": first_present(
                c,
                ["advisor_name", "name", "asesor", "advisor"],
                ""
            ),
            "related_thesis_count": first_present(
                c,
                ["related_thesis_count", "related_thesis_count_top50", "count"],
                None
            ),
            "global_advised_count_sample": first_present(
                c,
                ["global_advised_count_sample", "global_advised_count"],
                None
            ),
            "global_main_cluster_count_sample": first_present(
                c,
                ["global_main_cluster_count_sample", "global_main_cluster_count"],
                None
            ),
            "last_year": first_present(
                c,
                ["last_year", "global_last_year"],
                None
            ),
            "main_cluster_last_year": first_present(
                c,
                ["main_cluster_last_year"],
                None
            ),
            "programs": first_present(
                c,
                ["programs", "programas"],
                []
            ),
            "representative_titles": representative_titles,
        })

    ar["items"] = hydrated_items
    output["advisor_recommendations"] = ar
    result["output"] = output

    write_json(OUTPUT_PATH, result)

    print("Hidratado:", OUTPUT_PATH)
    print("candidates:", len(candidates))
    print("mapped ids:", list(by_id.keys()))
    print("items:", len(hydrated_items))

    for item in hydrated_items:
        print(
            item["rank"],
            item["advisor_id"],
            "-",
            item.get("advisor_name", ""),
            "| tesis:",
            len(item.get("representative_titles", []))
        )


if __name__ == "__main__":
    main()