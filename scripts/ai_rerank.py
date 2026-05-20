import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# ─── ENV / PATHS ──────────────────────────────────────────────────────────────

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]

PROMPT_PATH = BASE_DIR / "prompts" / "rerank_theses.md"
PAYLOAD_PATH = BASE_DIR / "payloads" / "ai_rerank_payload.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "ai_rerank_groq_llama.json"


# ─── MODEL CONFIG ─────────────────────────────────────────────────────────────

PRIMARY_MODEL = "llama-3.1-8b-instant"

FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
]

INPUT_PRICE_PER_M = 0.05
OUTPUT_PRICE_PER_M = 0.08

BASE_MAX_TOKENS = 800
MAX_RETRY_ATTEMPTS = 2


# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# ─── JSON EXTRACTION ──────────────────────────────────────────────────────────

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


# ─── VALIDATION ───────────────────────────────────────────────────────────────

def validate_structure(parsed: dict, payload: dict) -> tuple[bool, str]:
    rr = parsed.get("reranked_theses")

    if not isinstance(rr, dict):
        return False, "missing or invalid 'reranked_theses'"

    ordered_ids = rr.get("ordered_candidate_ids")

    if not isinstance(ordered_ids, list):
        return False, "missing or invalid 'ordered_candidate_ids'"

    candidate_ids = [
        c.get("candidate_id")
        for c in payload.get("candidates", [])
        if c.get("candidate_id")
    ]

    if len(ordered_ids) != len(candidate_ids):
        return False, f"expected {len(candidate_ids)} ids, got {len(ordered_ids)}"

    if len(ordered_ids) != len(set(ordered_ids)):
        return False, "duplicate ids found"

    if set(ordered_ids) != set(candidate_ids):
        missing = sorted(set(candidate_ids) - set(ordered_ids))
        extra = sorted(set(ordered_ids) - set(candidate_ids))
        return False, f"ordered ids do not match candidates. missing={missing}, extra={extra}"

    return True, "ok"


def validate(parsed: dict, payload: dict) -> tuple[bool, str]:
    ok, msg = validate_structure(parsed, payload)

    if not ok:
        return False, f"[structure] {msg}"

    return True, "ok"


# ─── HYDRATION ────────────────────────────────────────────────────────────────

def hydrate_reranked_output(parsed: dict, payload: dict) -> dict:
    ordered_ids = parsed["reranked_theses"]["ordered_candidate_ids"]

    candidate_map = {
        c["candidate_id"]: c
        for c in payload.get("candidates", [])
    }

    items = []

    for rank, candidate_id in enumerate(ordered_ids, start=1):
        c = candidate_map[candidate_id]

        items.append({
            "rank": rank,
            "candidate_id": candidate_id,
            "title": c.get("title"),
            "year": c.get("year"),
            "program": c.get("program"),
        })

    return {
        "reranked_theses": {
            "title": "Tesis más útiles para tu proyecto",
            "ordered_candidate_ids": ordered_ids,
            "items": items,
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
        "temperature": 0.05,
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


# ─── REPAIR PROMPT ────────────────────────────────────────────────────────────

def build_repair_message(
    raw_output: str,
    error: str,
    original_user_message: str
) -> str:
    return (
        f"Tu salida anterior no cumple el contrato: {error}.\n\n"
        f"Salida anterior:\n{raw_output}\n\n"
        "Devuelve SOLO JSON válido. "
        "Usa exclusivamente los mismos candidate_id del input. "
        "No agregues títulos, razones, explicaciones, markdown ni texto externo.\n\n"
        f"Instrucción original:\n{original_user_message}"
    )


# ─── COST ESTIMATE ────────────────────────────────────────────────────────────

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

    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"No encontré prompt: {PROMPT_PATH}")

    if not PAYLOAD_PATH.exists():
        raise FileNotFoundError(f"No encontré payload: {PAYLOAD_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    original_user_message = (
        "Reordena estas tesis candidatas de más útil a menos útil para el proyecto del usuario. "
        "Devuelve únicamente JSON válido con ordered_candidate_ids. "
        "No incluyas títulos, razones ni explicación externa.\n\n"
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
            hydrated_output = hydrate_reranked_output(parsed, payload)
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
                        hydrated_output = hydrate_reranked_output(parsed, payload)
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