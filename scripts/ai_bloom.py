import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# ─── ENV / PATHS ──────────────────────────────────────────────────────────────

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]

PROMPT_PATH = BASE_DIR / "prompts" / "bloom_analysis.md"
PAYLOAD_PATH = BASE_DIR / "payloads" / "ai_bloom_payload.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "ai_bloom_groq_20b.json"


# ─── MODEL CONFIG ─────────────────────────────────────────────────────────────

PRIMARY_MODEL = "openai/gpt-oss-20b"

FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

INPUT_PRICE_PER_M = 0.075
OUTPUT_PRICE_PER_M = 0.30

BASE_MAX_TOKENS = 2000
MAX_RETRY_ATTEMPTS = 1


# ─── JSON EXTRACTION / REPAIR ─────────────────────────────────────────────────

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
        candidate = text[start:end + 1]
        return json.loads(candidate)

    raise json.JSONDecodeError("No JSON object found", text, 0)


def repair_common_bloom_json_errors(text: str) -> str:
    if not text:
        return text

    text = re.sub(
        r'("revised_objectives"\s*:\s*\[[^\]]*?)\s*,\s*"final_note"\s*:',
        r'\1], "final_note":',
        text,
        flags=re.DOTALL,
    )

    text = re.sub(r",\s*([}\]])", r"\1", text)

    return text


def parse_model_output(content: str) -> dict:
    try:
        return extract_json(content)
    except Exception:
        repaired = repair_common_bloom_json_errors(content)
        return extract_json(repaired)


# ─── VALIDATION ───────────────────────────────────────────────────────────────

def validate_bloom_shape(parsed: dict) -> tuple[bool, str]:
    bloom = parsed.get("bloom_analysis")

    if not isinstance(bloom, dict):
        return False, "missing bloom_analysis"

    required = [
        "title",
        "cognitive_profile",
        "main_risk",
        "objective_ladder",
        "missing_cognitive_step",
        "revised_objectives",
        "final_note",
    ]

    for key in required:
        if key not in bloom:
            return False, f"missing {key}"

    if not isinstance(bloom.get("objective_ladder"), list):
        return False, "objective_ladder must be list"

    if not isinstance(bloom.get("revised_objectives"), list):
        return False, "revised_objectives must be list"

    if not isinstance(bloom.get("final_note"), str):
        return False, "final_note must be string"

    for i, obj in enumerate(bloom.get("objective_ladder", [])):
        if not isinstance(obj, dict):
            return False, f"objective_ladder item {i} must be object"

        for key in ["original_objective", "detected_level", "diagnosis", "improvement"]:
            if key not in obj:
                return False, f"objective_ladder item {i} missing {key}"

    return True, "ok"


# ─── MODEL CALL ───────────────────────────────────────────────────────────────

def call_model(
    client: Groq,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
) -> tuple[str, object, str]:
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

    content = response.choices[0].message.content or ""
    finish_reason = response.choices[0].finish_reason

    if not content.strip():
        raise ValueError("empty_model_output")

    return content, response.usage, finish_reason


def build_repair_message(
    raw_output: str,
    error: str,
    original_user_message: str
) -> str:
    return (
        f"Tu salida anterior no cumple el contrato: {error}.\n\n"
        f"Salida anterior:\n{raw_output}\n\n"
        "Devuelve SOLO JSON válido con la estructura bloom_analysis solicitada. "
        "Asegúrate de que revised_objectives sea un array de strings "
        "y final_note sea un string fuera de revised_objectives.\n\n"
        f"Instrucción original:\n{original_user_message}"
    )


def estimate_cost(usage, model: str, finish_reason: str | None = None) -> dict:
    token_usage = {
        "model": model,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
        "finish_reason": finish_reason,
        "estimated_cost_usd_uncached": None,
    }

    if usage:
        token_usage["estimated_cost_usd_uncached"] = round(
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
        "Analiza cognitivamente estos objetivos de tesis. "
        "Devuelve únicamente JSON válido, sin markdown ni explicación externa.\n\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )

    client = Groq(
        api_key=api_key,
        max_retries=0,
    )

    parsed = None
    valid = False
    validation_msg = "never_ran"
    token_usage = {}
    used_model = PRIMARY_MODEL
    raw_output = ""
    max_tokens = BASE_MAX_TOKENS

    user_message = original_user_message

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 2):
        print(f"[{PRIMARY_MODEL}] attempt {attempt}, max_tokens={max_tokens}")

        try:
            raw_output, usage, finish_reason = call_model(
                client=client,
                model=PRIMARY_MODEL,
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
            )

            parsed = parse_model_output(raw_output)
            valid, validation_msg = validate_bloom_shape(parsed)

            token_usage = estimate_cost(
                usage,
                PRIMARY_MODEL,
                finish_reason=finish_reason,
            )
            token_usage["attempt"] = attempt
            used_model = PRIMARY_MODEL

            if valid:
                break

            print(f"Invalid output: {validation_msg}")

            hit_limit = (
                usage
                and usage.completion_tokens
                and usage.completion_tokens >= max_tokens
            )

            if hit_limit:
                max_tokens = int(max_tokens * 1.25)
                user_message = original_user_message
            else:
                user_message = build_repair_message(
                    raw_output=raw_output,
                    error=validation_msg,
                    original_user_message=original_user_message,
                )

        except Exception as exc:
            parsed = {
                "raw_output": raw_output,
                "parse_error": True,
            }
            valid = False
            validation_msg = str(exc)
            print(f"Primary model failed: {validation_msg}")
            break

    if not valid:
        for fallback_model in FALLBACK_MODELS:
            print(f"[{fallback_model}] fallback attempt")

            fallback_message = original_user_message
            fallback_max_tokens = BASE_MAX_TOKENS

            for fb_attempt in range(1, 3):
                try:
                    raw_output, usage, finish_reason = call_model(
                        client=client,
                        model=fallback_model,
                        system_prompt=system_prompt,
                        user_message=fallback_message,
                        max_tokens=fallback_max_tokens,
                    )

                    parsed = parse_model_output(raw_output)
                    valid, validation_msg = validate_bloom_shape(parsed)

                    token_usage = estimate_cost(
                        usage,
                        fallback_model,
                        finish_reason=finish_reason,
                    )
                    token_usage["attempt"] = f"fallback_{fb_attempt}"
                    used_model = fallback_model

                    if valid:
                        break

                    hit_limit = (
                        usage
                        and usage.completion_tokens
                        and usage.completion_tokens >= fallback_max_tokens
                    )

                    if hit_limit:
                        fallback_max_tokens = int(fallback_max_tokens * 1.25)
                        fallback_message = original_user_message
                    else:
                        fallback_message = build_repair_message(
                            raw_output=raw_output,
                            error=validation_msg,
                            original_user_message=original_user_message,
                        )

                except Exception as exc:
                    parsed = {
                        "raw_output": raw_output,
                        "parse_error": True,
                    }
                    valid = False
                    validation_msg = str(exc)
                    print(f"[{fallback_model}] failed: {validation_msg}")
                    break

            if valid:
                break

    result = {
        "output": parsed,
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

    print(f"Guardado {OUTPUT_PATH}")

    print("\n── VALIDATION ──")
    print(json.dumps(result["validation"], ensure_ascii=False, indent=2))

    print("\n── TOKEN USAGE ──")
    print(json.dumps(token_usage, ensure_ascii=False, indent=2))

    print("\n── OUTPUT ──")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()