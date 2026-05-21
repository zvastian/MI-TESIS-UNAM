import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

CONTEXT_PATH = BASE_DIR / "payloads" / "context_minimal.json"
OUTPUT_PATH = BASE_DIR / "payloads" / "ai_advisors_payload.json"


def main():
    if not CONTEXT_PATH.exists():
        raise FileNotFoundError(f"No encontré contexto: {CONTEXT_PATH}")

    with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
        ctx = json.load(f)

    advisor_evidence = ctx.get("advisor_evidence", [])

    advisor_candidates = []

    for i, advisor in enumerate(advisor_evidence, start=1):
        advisor_id = f"A{i:02d}"

        advisor_candidates.append({
            "advisor_id": advisor_id,
            "advisor_name": advisor.get("advisor_name", ""),
            "related_thesis_count_top50": advisor.get("related_thesis_count_top50"),
            "global_advised_count_sample": advisor.get("global_advised_count_sample"),
            "global_main_cluster_count_sample": advisor.get("global_main_cluster_count_sample"),
            "last_year": advisor.get("last_year"),
            "main_cluster_last_year": advisor.get("main_cluster_last_year"),
            "programs": advisor.get("programs", []),
            "representative_titles": advisor.get("representative_titles", []),
        })

    payload = {
        "user_project": ctx.get("user_project", {}),
        "semantic_position": ctx.get("semantic_position", {}),
        "keywords_detected": ctx.get("keywords_detected", []),
        "advisor_candidates": advisor_candidates,
        "instructions": {
            "use_only_existing_advisor_ids": True,
            "do_not_invent_advisors": True,
            "candidate_count": len(advisor_candidates),
        }
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH.relative_to(BASE_DIR)}")
    print("advisor candidates:", len(advisor_candidates))
    print("chars:", len(json.dumps(payload, ensure_ascii=False)))


if __name__ == "__main__":
    main()