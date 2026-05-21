# validators.py
# Valida contratos mínimos. No evalúa estilo ni calidad subjetiva.

from typing import Any
from contracts import MODULE_CONTRACTS


def _non_empty(value: Any) -> bool:
    return value not in [None, "", [], {}]


def validate_initial_note(data: dict) -> tuple[bool, str]:
    note = data.get("initial_note")

    if not isinstance(note, dict):
        return False, "missing initial_note"

    for key in MODULE_CONTRACTS["initial_note"]["required"]:
        if not _non_empty(note.get(key)):
            return False, f"missing {key}"

    angles = note.get("possible_angles")

    if not isinstance(angles, list):
        return False, "possible_angles must be list"

    if len(angles) < 1:
        return False, "possible_angles empty"

    for i, angle in enumerate(angles):
        if not isinstance(angle, dict):
            return False, f"angle {i} must be object"

        if not _non_empty(angle.get("title")):
            return False, f"angle {i} missing title"

        if not _non_empty(angle.get("description")):
            return False, f"angle {i} missing description"

    return True, "ok"


def validate_rerank(
    data: dict,
    candidate_ids: set[str] | None = None
) -> tuple[bool, str]:
    rr = data.get("reranked_theses")

    if not isinstance(rr, dict):
        return False, "missing reranked_theses"

    for key in MODULE_CONTRACTS["rerank"]["required"]:
        if not _non_empty(rr.get(key)):
            return False, f"missing {key}"

    ordered = rr.get("ordered_candidate_ids")
    items = rr.get("items")

    if not isinstance(ordered, list):
        return False, "ordered_candidate_ids must be list"

    if not isinstance(items, list):
        return False, "items must be list"

    if len(ordered) != len(set(ordered)):
        return False, "duplicate candidate ids"

    if candidate_ids:
        unknown = sorted(set(ordered) - candidate_ids)
        if unknown:
            return False, f"unknown candidate_ids: {unknown}"

    return True, "ok"


def validate_bloom(data: dict) -> tuple[bool, str]:
    bloom = data.get("bloom_analysis")

    if not isinstance(bloom, dict):
        return False, "missing bloom_analysis"

    for key in MODULE_CONTRACTS["bloom"]["required"]:
        if not _non_empty(bloom.get(key)):
            return False, f"missing {key}"

    if not isinstance(bloom.get("objective_ladder"), list):
        return False, "objective_ladder must be list"

    if not isinstance(bloom.get("revised_objectives"), list):
        return False, "revised_objectives must be list"

    return True, "ok"


def validate_questions(data: dict) -> tuple[bool, str]:
    rq = data.get("research_questions")

    if not isinstance(rq, dict):
        return False, "missing research_questions"

    for key in MODULE_CONTRACTS["questions"]["required"]:
        if not _non_empty(rq.get(key)):
            return False, f"missing {key}"

    questions = rq.get("questions")

    if not isinstance(questions, list):
        return False, "questions must be list"

    if len(questions) < 1:
        return False, "questions empty"

    required = set(MODULE_CONTRACTS["questions"]["question_required"])

    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            return False, f"question {i} must be object"

        missing = required - set(q.keys())
        if missing:
            return False, f"question {i} missing fields: {sorted(missing)}"

        for key in required:
            if not _non_empty(q.get(key)):
                return False, f"question {i} empty {key}"

    return True, "ok"


def validate_bibliography(
    data: dict,
    valid_bib_ids: set[str] | None = None
) -> tuple[bool, str]:
    br = data.get("bibliography_recommendations")

    if not isinstance(br, dict):
        return False, "missing bibliography_recommendations"

    for key in MODULE_CONTRACTS["bibliography"]["required"]:
        if key not in br:
            return False, f"missing {key}"

    items = br.get("items")

    if not isinstance(items, list):
        return False, "items must be list"

    if len(items) < 1:
        return False, "items empty"

    if len(items) > 5:
        return False, f"too many bibliography items: {len(items)}"

    required = set(MODULE_CONTRACTS["bibliography"]["item_required"])
    seen_ids = set()
    seen_ranks = set()

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            return False, f"item {i} must be object"

        missing = required - set(item.keys())
        if missing:
            return False, f"item {i} missing fields: {sorted(missing)}"

        bib_id = str(item.get("bib_id", "")).strip()

        if not bib_id:
            return False, f"item {i} empty bib_id"

        if bib_id in seen_ids:
            return False, f"duplicate bib_id: {bib_id}"

        seen_ids.add(bib_id)

        if valid_bib_ids is not None and bib_id not in valid_bib_ids:
            return False, f"unknown bib_id: {bib_id}"

        try:
            rank = int(item.get("rank"))
        except Exception:
            return False, f"invalid rank in item {i}"

        if rank in seen_ranks:
            return False, f"duplicate rank: {rank}"

        seen_ranks.add(rank)

        if not _non_empty(item.get("title")):
            return False, f"item {i} empty title"

        if not _non_empty(item.get("source_doc_number")):
            return False, f"item {i} empty source_doc_number"

        if not _non_empty(item.get("source_thesis_title")):
            return False, f"item {i} empty source_thesis_title"

    return True, "ok"


def validate_advisors(data):
    ar = data.get("advisor_recommendations")

    if not isinstance(ar, dict):
        return False, "missing advisor_recommendations"

    required = set(
        MODULE_CONTRACTS["advisors"]["required"]
    )

    missing = required - set(ar.keys())

    if missing:
        return False, f"missing fields: {sorted(missing)}"

    advisor_ids = ar.get("ordered_advisor_ids")

    if not isinstance(advisor_ids, list):
        return False, "ordered_advisor_ids must be list"

    if len(advisor_ids) < 1:
        return False, "ordered_advisor_ids empty"

    seen = set()

    for aid in advisor_ids:
        aid = str(aid).strip()

        if not aid:
            return False, "empty advisor_id"

        if aid in seen:
            return False, f"duplicate advisor_id: {aid}"

        seen.add(aid)

    return True, "ok"

def validate_module_output(
    module: str,
    data: dict,
    *,
    candidate_ids: set[str] | None = None,
    valid_bib_ids: set[str] | None = None,
    valid_advisor_ids: set[str] | None = None,
) -> tuple[bool, str]:
    if module == "initial_note":
        return validate_initial_note(data)

    if module == "rerank":
        return validate_rerank(data, candidate_ids=candidate_ids)

    if module == "bloom":
        return validate_bloom(data)

    if module == "questions":
        return validate_questions(data)

    if module == "bibliography":
        return validate_bibliography(data, valid_bib_ids=valid_bib_ids)

    if module == "advisors":
        return validate_advisors(data)

    return False, f"unknown module: {module}"
