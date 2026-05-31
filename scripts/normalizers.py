# normalizers.py
# Convierte variantes aceptables de distintos proveedores en contratos estables.

import json


def extract_json(text: str) -> dict:
    """
    Extrae el primer objeto JSON de una respuesta.
    Soporta respuestas limpias o texto con JSON incrustado.
    """
    text = (text or "").strip()

    if not text:
        raise ValueError("empty_model_output")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError("no_json_object_found")


def unwrap_output(data: dict) -> dict:
    """
    Algunos scripts guardan:
    { "output": { ... } }

    La UX/validadores quieren el contenido real.
    """
    if isinstance(data, dict) and isinstance(data.get("output"), dict):
        return data["output"]
    return data


def normalize_initial_note(data: dict) -> dict:
    data = unwrap_output(data)

    note = data.get("initial_note")

    if not isinstance(note, dict):
        legacy_keys = [
            "paragraph",
            "possible_angles",
            "scope_note",
            "one_sentence_reframe",
            "central_problem",
            "main_objects",
        ]

        if any(k in data for k in legacy_keys):
            note = data
        else:
            return data

    # Nuevo schema estructurado
    if any(k in note for k in [
        "central_problem",
        "main_objects",
        "interpretive_angle",
        "scope",
        "possible_contribution",
        "cautions",
    ]):
        note.setdefault("title", "Comprendí tu tesis así")
        note.setdefault("intro", "Leí tu idea como un proyecto con un problema académico propio y un territorio de análisis que conviene precisar.")
        note.setdefault("central_problem", "")
        note.setdefault("main_objects", [])
        note.setdefault("interpretive_angle", "")
        note.setdefault("possible_contribution", "")
        note.setdefault("cautions", [])

        scope = note.get("scope")
        if not isinstance(scope, dict):
            scope = {}

        scope.setdefault("temporal", "Conviene delimitar con mayor precisión el periodo de análisis.")
        scope.setdefault("geographic", "Conviene precisar el espacio geográfico o las unidades de comparación.")
        scope.setdefault("disciplinary", "Conviene precisar el campo disciplinario principal y sus cruces.")

        note["scope"] = scope

        if isinstance(note.get("main_objects"), str):
            note["main_objects"] = [note["main_objects"]]

        if isinstance(note.get("cautions"), str):
            note["cautions"] = [note["cautions"]]

        return {"initial_note": note}

    # Compatibilidad con schema viejo
    note.setdefault("title", "Lectura inicial")
    note.setdefault("paragraph", "")
    note.setdefault("possible_angles", [])

    if not note.get("scope_note"):
        note["scope_note"] = (
            "Conviene delimitar con mayor precisión el alcance temporal, "
            "temático y metodológico de la investigación."
        )

    if not note.get("one_sentence_reframe"):
        note["one_sentence_reframe"] = (
            note.get("paragraph", "")[:220]
            or "Reformular la idea para precisar objeto, periodo y enfoque de análisis."
        )

    angles = note.get("possible_angles", [])
    if isinstance(angles, list):
        normalized_angles = []

        for angle in angles:
            if isinstance(angle, str):
                normalized_angles.append({
                    "title": angle[:60],
                    "description": angle,
                })
            elif isinstance(angle, dict):
                normalized_angles.append({
                    "title": angle.get("title") or angle.get("name") or "Ruta posible",
                    "description": angle.get("description") or angle.get("text") or "",
                })

        note["possible_angles"] = normalized_angles

    # Generar un puente mínimo al nuevo schema para frontend futuro,
    # sin eliminar los campos viejos.
    note.setdefault("intro", note.get("paragraph", "")[:240])
    note.setdefault("central_problem", note.get("one_sentence_reframe", ""))
    note.setdefault("main_objects", [])
    note.setdefault("interpretive_angle", "")
    note.setdefault("scope", {
        "temporal": note.get("scope_note", ""),
        "geographic": "",
        "disciplinary": "",
    })
    note.setdefault("possible_contribution", "")
    note.setdefault("cautions", [note.get("scope_note", "")] if note.get("scope_note") else [])

    return {"initial_note": note}


def normalize_rerank(data: dict) -> dict:
    data = unwrap_output(data)

    rr = data.get("reranked_theses")

    if not isinstance(rr, dict):
        if "ordered_candidates" in data:
            items = data.get("ordered_candidates", [])
            rr = {
                "title": "Tesis más útiles para tu proyecto",
                "ordered_candidate_ids": [
                    item.get("candidate_id")
                    for item in items
                    if item.get("candidate_id")
                ],
                "items": items,
            }
        else:
            return data

    rr.setdefault("title", "Tesis más útiles para tu proyecto")

    if "ordered_candidate_ids" not in rr and isinstance(rr.get("items"), list):
        rr["ordered_candidate_ids"] = [
            item.get("candidate_id")
            for item in rr["items"]
            if item.get("candidate_id")
        ]

    return {"reranked_theses": rr}


def normalize_bloom(data: dict) -> dict:
    data = unwrap_output(data)

    bloom = data.get("bloom_analysis")

    if not isinstance(bloom, dict):
        possible_keys = [
            "title",
            "cognitive_profile",
            "profile",
            "main_risk",
            "risk",
            "objective_ladder",
            "missing_cognitive_step",
            "revised_objectives",
            "rewritten_objectives",
            "final_note",
            "categories",
        ]

        if any(k in data for k in possible_keys):
            bloom = data
        else:
            return data

    if "main_risk" not in bloom and "risk" in bloom:
        bloom["main_risk"] = bloom.pop("risk")

    if "final_note" not in bloom and "note" in bloom:
        bloom["final_note"] = bloom.pop("note")

    if "cognitive_profile" not in bloom and "profile" in bloom:
        bloom["cognitive_profile"] = bloom.pop("profile")

    if "revised_objectives" not in bloom and "rewritten_objectives" in bloom:
        bloom["revised_objectives"] = bloom.pop("rewritten_objectives")

    bloom.setdefault("title", "Análisis cognitivo de tus objetivos")

    if not bloom.get("cognitive_profile"):
        bloom["cognitive_profile"] = (
            "El análisis identifica la progresión cognitiva de los objetivos "
            "y sugiere fortalecer la relación entre descripción, análisis, evaluación y propuesta."
        )

    if not bloom.get("main_risk"):
        bloom["main_risk"] = (
            "El principal riesgo es que los objetivos no avancen de forma lógica "
            "hacia una evaluación suficientemente fundamentada."
        )

    if not bloom.get("objective_ladder"):
        bloom["objective_ladder"] = []

    if not bloom.get("missing_cognitive_step"):
        bloom["missing_cognitive_step"] = (
            "Conviene reforzar la etapa de evaluación antes de formular propuestas o conclusiones."
        )

    if not bloom.get("revised_objectives"):
        bloom["revised_objectives"] = []

    if not bloom.get("final_note"):
        bloom["final_note"] = (
            "La tesis ganará solidez si cada objetivo cumple una función cognitiva clara "
            "dentro del argumento general."
        )

    return {"bloom_analysis": bloom}


def normalize_questions(data: dict) -> dict:
    data = unwrap_output(data)

    rq = data.get("research_questions")

    if not isinstance(rq, dict):
        if isinstance(data.get("questions"), list):
            rq = {
                "title": "Preguntas de investigación sugeridas",
                "questions": data["questions"],
            }
        else:
            return data

    rq.setdefault("title", "Preguntas de investigación sugeridas")

    questions = rq.get("questions", [])

    if isinstance(questions, list):
        for q in questions:
            if not isinstance(q, dict):
                continue

            if "why_it_matters" not in q and "why_it_matter" in q:
                q["why_it_matters"] = q.pop("why_it_matter")

            if "why_it_matters" not in q and "why_matters" in q:
                q["why_it_matters"] = q.pop("why_matters")

            if "methodological_angle" not in q and "methodology" in q:
                q["methodological_angle"] = q.pop("methodology")

            if "methodological_angle" not in q and "methodological_approach" in q:
                q["methodological_angle"] = q.pop("methodological_approach")

            if "methodological_angle" not in q and "methodological_focus" in q:
                q["methodological_angle"] = q.pop("methodological_focus")

            if "type" not in q and "question_type" in q:
                q["type"] = q.pop("question_type")

    return {"research_questions": rq}


def normalize_bibliography(data: dict) -> dict:
    data = unwrap_output(data)

    br = data.get("bibliography_recommendations")

    if not isinstance(br, dict):
        if isinstance(data.get("bibliography"), list):
            br = {
                "title": "Bibliografía recomendada",
                "items": data.get("bibliography", []),
                "coverage_note": "",
                "missing_bibliography_warning": data.get(
                    "missing_bibliography_warning",
                    ""
                ),
            }
        else:
            return data

    br.setdefault("title", "Bibliografía recomendada")

    items = br.get("items", [])

    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue

            if "bib_id" not in item and "id" in item:
                item["bib_id"] = item.pop("id")

            # Campos eliminados del contrato final de bibliografía.
            item.pop("why_useful", None)
            item.pop("why_it_matters", None)
            item.pop("why_it_matter", None)
            item.pop("reason", None)
            item.pop("use_type", None)
            item.pop("tags", None)
            item.pop("fit", None)

    br.setdefault("coverage_note", "")
    br.setdefault("missing_bibliography_warning", "")

    return {"bibliography_recommendations": br}


def normalize_advisors(data: dict) -> dict:
    data = unwrap_output(data)

    ar = data.get("advisor_recommendations")

    if not isinstance(ar, dict):
        if isinstance(data.get("advisors"), list):
            items = data.get("advisors", [])
            ar = {
                "title": "Asesores relacionados con tu tema",
                "ordered_advisor_ids": [
                    item.get("advisor_id")
                    for item in items
                    if item.get("advisor_id")
                ],
                "items": items,
                "disclaimer": data.get("disclaimer", ""),
            }
        else:
            return data

    ar.setdefault("title", "Asesores relacionados con tu tema")

    if "ordered_advisor_ids" not in ar and isinstance(ar.get("items"), list):
        ar["ordered_advisor_ids"] = [
            item.get("advisor_id")
            for item in ar["items"]
            if item.get("advisor_id")
        ]

    ar.setdefault(
        "disclaimer",
        "La sugerencia se basa en tesis históricas del acervo y no indica disponibilidad actual."
    )

    return {"advisor_recommendations": ar}


def normalize_module_output(module: str, data: dict) -> dict:
    if module == "initial_note":
        return normalize_initial_note(data)

    if module == "rerank":
        return normalize_rerank(data)

    if module == "bloom":
        return normalize_bloom(data)

    if module == "questions":
        return normalize_questions(data)

    if module == "bibliography":
        return normalize_bibliography(data)

    if module == "advisors":
        return normalize_advisors(data)

    raise ValueError(f"unknown module: {module}")