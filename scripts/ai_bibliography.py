import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# ─── ENV / PATHS ──────────────────────────────────────────────────────────────

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]

PROMPT_PATH_CANDIDATES = [
    BASE_DIR / "prompts" / "bibliography_recommendations.md",
]

PAYLOAD_PATH = BASE_DIR / "payloads" / "ai_bibliography_payload.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "ai_bibliography_groq_20b.json"


# ─── MODEL CONFIG ─────────────────────────────────────────────────────────────

PRIMARY_MODEL = "openai/gpt-oss-20b"

FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

INPUT_PRICE_PER_M = 0.075
OUTPUT_PRICE_PER_M = 0.30

BASE_MAX_TOKENS = 700
MAX_RETRY_ATTEMPTS = 1


# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def first_existing_path(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path

    raise FileNotFoundError(f"No encontré ninguno de estos archivos: {paths}")


def extract_json(text: str) -> dict:
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

    raise json.JSONDecodeError("No JSON object found", text, 0)


def build_bib_map(payload: dict) -> dict:
    """
    Construye bib_id -> metadata.

    Soporta:
    1. Estructura nueva plana:
       payload["bibliography_candidates"] = [
         {"bib_id": "S01_B01", "raw_title": "...", "source_thesis_title": "..."}
       ]

    2. Estructura legacy:
       payload["bibliography_candidates"] = [
         {"source_id": "S01", "titles": [{"bib_id": "...", "title": "..."}]}
       ]
    """
    bib_map = {}

    candidates = payload.get("bibliography_candidates", [])

    if not isinstance(candidates, list):
        return bib_map

    for source in candidates:
        if not isinstance(source, dict):
            continue

        # Caso nuevo: candidato bibliográfico plano.
        if source.get("bib_id"):
            bib_id = str(source.get("bib_id", "")).strip()

            title = (
                source.get("bibliography_title")
                or source.get("raw_title")
                or source.get("title")
                or ""
            )
            title = str(title).strip()

            if bib_id and title:
                bib_map[bib_id] = {
                    "bib_id": bib_id,
                    "title": title,
                    "raw_title": source.get("raw_title", title),
                    "bibliography_title": source.get("bibliography_title", title),
                    "source_id": source.get("source_id", ""),
                    "source_doc_number": source.get("source_doc_number", ""),
                    "source_thesis_title": source.get("source_thesis_title", ""),
                    "source_similarity": source.get("source_similarity"),
                }

            continue

        # Caso legacy: source con titles internos.
        source_doc = source.get("source_doc_number", "")
        source_title = source.get("source_thesis_title", "")

        for item in source.get("titles", []):
            if not isinstance(item, dict):
                continue

            bib_id = str(item.get("bib_id", "")).strip()

            title = (
                item.get("bibliography_title")
                or item.get("raw_title")
                or item.get("title")
                or ""
            )
            title = str(title).strip()

            if bib_id and title:
                bib_map[bib_id] = {
                    "bib_id": bib_id,
                    "title": title,
                    "raw_title": item.get("raw_title", title),
                    "bibliography_title": item.get("bibliography_title", title),
                    "source_doc_number": source_doc,
                    "source_thesis_title": source_title,
                    "source_similarity": source.get("source_similarity"),
                }

    return bib_map


# ─── VALIDATION ───────────────────────────────────────────────────────────────

def validate_structure(parsed: dict, payload: dict) -> tuple[bool, str]:
    br = parsed.get("bibliography_recommendations")

    if not isinstance(br, dict):
        return False, "missing or invalid 'bibliography_recommendations'"

    items = br.get("items", [])

    if not isinstance(items, list):
        return False, "'items' is not a list"

    if len(items) < 3:
        return False, f"expected at least 3 items, got {len(items)}"

    if len(items) > 8:
        return False, f"expected max 8 items, got {len(items)}"

    bib_map = build_bib_map(payload)

    if not bib_map:
        return False, "no bibliography candidates available"

    required_fields = {"rank", "bib_id"}

    forbidden_fields = {
        "why_useful",
        "why_it_matters",
        "why_it_matter",
        "reason",
        "tags",
        "fit",
        "use_type",
        "title",
        "source_doc_number",
        "source_thesis_title",
    }

    seen_bib_ids = set()
    seen_ranks = set()

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            return False, f"item {i} is not an object"

        missing = required_fields - set(item.keys())
        if missing:
            return False, f"item {i} missing fields: {sorted(missing)}"

        present_forbidden = forbidden_fields & set(item.keys())
        if present_forbidden:
            return False, f"item {i} has forbidden fields: {sorted(present_forbidden)}"

        bib_id = str(item.get("bib_id", "")).strip()

        if not bib_id:
            return False, f"empty bib_id in item {i}"

        if bib_id not in bib_map:
            return False, f"unknown bib_id: {bib_id}"

        if bib_id in seen_bib_ids:
            return False, f"duplicate bib_id: {bib_id}"

        seen_bib_ids.add(bib_id)

        try:
            rank = int(item.get("rank"))
        except Exception:
            return False, f"invalid rank in item {i}"

        if rank in seen_ranks:
            return False, f"duplicate rank: {rank}"

        seen_ranks.add(rank)

    expected_ranks = set(range(1, len(items) + 1))

    if seen_ranks != expected_ranks:
        return False, f"ranks must be consecutive 1-{len(items)}"

    if "coverage_note" not in br:
        return False, "missing coverage_note"

    if "missing_bibliography_warning" not in br:
        return False, "missing missing_bibliography_warning"

    if not isinstance(br.get("coverage_note"), str):
        return False, "coverage_note must be string"

    if not isinstance(br.get("missing_bibliography_warning"), str):
        return False, "missing_bibliography_warning must be string"

    return True, "ok"


def validate(parsed: dict, payload: dict) -> tuple[bool, str]:
    ok, msg = validate_structure(parsed, payload)

    if not ok:
        return False, f"[structure] {msg}"

    return True, "ok"


# ─── HYDRATION ────────────────────────────────────────────────────────────────

def hydrate_bibliography_output(parsed: dict, payload: dict) -> dict:
    bib_map = build_bib_map(payload)

    br = parsed["bibliography_recommendations"]
    hydrated_items = []

    for item in br.get("items", []):
        bib_id = str(item["bib_id"]).strip()
        source = bib_map[bib_id]

        hydrated_items.append({
            "rank": int(item.get("rank")),
            "bib_id": bib_id,
            "title": source["title"],
            "source_doc_number": source["source_doc_number"],
            "source_thesis_title": source["source_thesis_title"],
        })

    return {
        "bibliography_recommendations": {
            "title": br.get("title", "Bibliografía recomendada"),
            "items": hydrated_items,
            "coverage_note": br.get("coverage_note", ""),
            "missing_bibliography_warning": br.get("missing_bibliography_warning", ""),
        }
    }


# ─── MODEL CALL ───────────────────────────────────────────────────────────────

def call_model(
    client: Groq,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
) -> tuple[str, object]:
    params = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "temperature": 0.15,
        "max_tokens": max_tokens,
    }

    if "gpt-oss" in model:
        params["extra_body"] = {
            "reasoning_effort": "low"
        }

    response = client.chat.completions.create(**params)

    content = (response.choices[0].message.content or "").strip()

    if not content:
        raise ValueError("empty_model_output")

    return content, response.usage


def build_repair_message(
    raw_output: str,
    error: str,
    original_user_message: str
) -> str:
    return (
        f"Tu salida anterior no cumple el contrato: {error}.\n\n"
        f"Salida anterior:\n{raw_output}\n\n"
        "Devuelve SOLO JSON válido con la estructura solicitada. "
        "Usa exclusivamente bib_id existentes en el input. "
        "No inventes títulos, autores ni fuentes externas. "
        "Cada item debe contener SOLO rank y bib_id. "
        "No incluyas why_useful, why_it_matters, reason, tags, fit, use_type, "
        "title, source_doc_number ni source_thesis_title dentro de items.\n\n"
        f"Instrucción original:\n{original_user_message}"
    )


def estimate_cost(usage, model: str) -> dict:
    token_usage = {
        "model": model,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
        "estimated_cost_usd": None,
    }

    if usage:
        token_usage["estimated_cost_usd"] = round(
            (usage.prompt_tokens / 1_000_000) * INPUT_PRICE_PER_M
            + (usage.completion_tokens / 1_000_000) * OUTPUT_PRICE_PER_M,
            8,
        )

    return token_usage


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Falta GROQ_API_KEY. Define la variable en .env o export GROQ_API_KEY='tu_key'"
        )

    if not PAYLOAD_PATH.exists():
        raise FileNotFoundError(f"No encontré payload: {PAYLOAD_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    prompt_path = first_existing_path(PROMPT_PATH_CANDIDATES)
    system_prompt = prompt_path.read_text(encoding="utf-8")

    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    original_user_message = (
        "Selecciona bibliografía útil para este proyecto de tesis. "
        "Devuelve únicamente JSON válido con bib_id existentes. "
        "No inventes títulos, autores ni fuentes externas. "
        "Cada item debe contener SOLO rank y bib_id. "
        "El backend completará title, source_doc_number y source_thesis_title. "
        "No incluyas why_useful, why_it_matters, reason, tags, fit ni use_type.\n\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )

    client = Groq(
        api_key=api_key,
        max_retries=0,
    )

    parsed = None
    hydrated_output = None
    valid = False
    validation_msg = "never_ran"
    token_usage = {}
    used_model = PRIMARY_MODEL
    raw_output = ""
    max_tokens = BASE_MAX_TOKENS

    user_message = original_user_message

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 2):
        log.info(f"[{PRIMARY_MODEL}] attempt {attempt}, max_tokens={max_tokens}")

        try:
            raw_output, usage = call_model(
                client=client,
                model=PRIMARY_MODEL,
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            log.warning(f"Primary model call failed: {exc}")
            validation_msg = str(exc)
            break

        hit_limit = (
            usage
            and usage.completion_tokens
            and usage.completion_tokens >= max_tokens
        )

        try:
            parsed = extract_json(raw_output)
            valid, validation_msg = validate(parsed, payload)
        except Exception as exc:
            parsed = {
                "raw_output": raw_output,
                "parse_error": True,
            }
            valid = False
            validation_msg = str(exc)

        token_usage = estimate_cost(usage, PRIMARY_MODEL)
        token_usage["attempt"] = attempt
        used_model = PRIMARY_MODEL

        if valid:
            hydrated_output = hydrate_bibliography_output(parsed, payload)
            log.info(f"✅ Valid output on attempt {attempt}")
            break

        log.warning(f"Invalid output: {validation_msg}")

        if hit_limit:
            max_tokens = int(max_tokens * 1.5)
            log.info(f"Output likely truncated — increasing max_tokens to {max_tokens}")
            user_message = original_user_message
        else:
            user_message = build_repair_message(
                raw_output=raw_output,
                error=validation_msg,
                original_user_message=original_user_message,
            )

    if not valid:
        for fallback_model in FALLBACK_MODELS:
            log.info(f"[{fallback_model}] fallback attempt")

            fallback_message = original_user_message
            fallback_max_tokens = BASE_MAX_TOKENS

            for fb_attempt in range(1, 3):
                try:
                    raw_output, usage = call_model(
                        client=client,
                        model=fallback_model,
                        system_prompt=system_prompt,
                        user_message=fallback_message,
                        max_tokens=fallback_max_tokens,
                    )

                    hit_limit = (
                        usage
                        and usage.completion_tokens
                        and usage.completion_tokens >= fallback_max_tokens
                    )

                    try:
                        parsed = extract_json(raw_output)
                        valid, validation_msg = validate(parsed, payload)
                    except Exception as exc:
                        parsed = {
                            "raw_output": raw_output,
                            "parse_error": True,
                        }
                        valid = False
                        validation_msg = str(exc)

                    token_usage = estimate_cost(usage, fallback_model)
                    token_usage["attempt"] = f"fallback_{fb_attempt}"
                    used_model = fallback_model

                    if valid:
                        hydrated_output = hydrate_bibliography_output(parsed, payload)
                        log.info(f"✅ Fallback succeeded with {fallback_model}")
                        break

                    log.warning(f"[{fallback_model}] invalid output: {validation_msg}")

                    if hit_limit:
                        fallback_max_tokens = int(fallback_max_tokens * 1.5)
                        fallback_message = original_user_message
                    else:
                        fallback_message = build_repair_message(
                            raw_output=raw_output,
                            error=validation_msg,
                            original_user_message=original_user_message,
                        )

                except Exception as exc:
                    log.warning(f"[{fallback_model}] failed: {exc}")
                    valid = False
                    validation_msg = str(exc)
                    break

            if valid:
                break

    result = {
        "output": hydrated_output if valid else parsed,
        "raw_model_output": parsed,
        "validation": {
            "valid": valid,
            "message": validation_msg,
        },
        "token_usage": token_usage,
        "meta": {
            "used_model": used_model,
            "primary_model": PRIMARY_MODEL,
            "fallback_models": FALLBACK_MODELS,
        },
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info(f"Saved → {OUTPUT_PATH}")

    print("\n── VALIDATION ──")
    print(json.dumps(result["validation"], ensure_ascii=False, indent=2))

    print("\n── TOKEN USAGE ──")
    print(json.dumps(token_usage, ensure_ascii=False, indent=2))

    print("\n── OUTPUT ──")
    print(json.dumps(result["output"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()