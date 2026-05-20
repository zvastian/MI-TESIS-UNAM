# contracts.py
# Contratos mínimos de salida para cada módulo del Laboratorio de Tesis.

MODULE_CONTRACTS = {
    "initial_note": {
        "root": "initial_note",
        "required": [
            "title",
            "paragraph",
            "possible_angles",
            "scope_note",
            "one_sentence_reframe",
        ],
    },

    "rerank": {
        "root": "reranked_theses",
        "required": [
            "title",
            "ordered_candidate_ids",
            "items",
        ],
    },

    "bloom": {
        "root": "bloom_analysis",
        "required": [
            "title",
            "cognitive_profile",
            "main_risk",
            "objective_ladder",
            "missing_cognitive_step",
            "revised_objectives",
            "final_note",
        ],
    },

    "questions": {
        "root": "research_questions",
        "required": [
            "title",
            "questions",
        ],
        "question_required": [
            "type",
            "question",
            "methodological_angle",
            "why_it_matters",
        ],
    },

    "bibliography": {
        "root": "bibliography_recommendations",
        "required": [
            "title",
            "items",
            "coverage_note",
            "missing_bibliography_warning",
        ],
        "item_required": [
            "rank",
            "bib_id",
            "title",
            "source_doc_number",
            "source_thesis_title",
        ],
    },

    "advisors": {
        "required": [
            "title",
            "ordered_advisor_ids",
            "disclaimer",
        ],
    },
}
