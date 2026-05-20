import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# ─── ENV / PATHS ──────────────────────────────────────────────────────────────

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]

PROMPT_PATH = BASE_DIR / "prompts" / "conceptual_interpretation.md"
PAYLOAD_PATH = BASE_DIR / "payloads" / "ai_conceptual_payload.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "ai_conceptual_interpretation.json"


# ─── PROVIDER / MODEL CONFIG ──────────────────────────────────────────────────

PROVIDER = "cerebras"
PRIMARY_MODEL = "gpt-oss-120b"

# Cerebras puede estar en free tier; ajusta si después tienes pricing real.
INPUT_PRICE_PER_M = 0.0
OUTPUT_PRICE_PER_M = 0.0

MAX_TOKENS = 1000
TIMEOUT_SECONDS = 20.0


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

def validate_initial_note(parsed: dict) -> tuple[bool, str]:
    note = parsed.get("initial_note")

    if not isinstance(note, dict):
        return False, "missing initial_note"

    required = [
        "title",
        "paragraph",
        "possible_angles",
        "scope_note",
        "one_sentence_reframe",
    ]

    for key in required:
        if key not in note or note[key] in [None, "", [], {}]:
            return False, f"missing {key}"

    angles = note.get("possible_angles", [])

    if not isinstance(angles, list):
        return False, "possible_angles is not a list"

    if len(angles) < 3 or len(angles) > 4:
        return False, f"expected 3-4 angles, got {len(angles)}"

    for i, angle in enumerate(angles):
        if not isinstance(angle, dict):
            return False, f"angle {i} is not an object"

        if not angle.get("title") or not angle.get("description"):
            return False, f"angle {i} missing title or description"

    return True, "ok"


# ─── TOKEN / COST ─────────────────────────────────────────────────────────────

def estimate_cost(usage, latency_s: float) -> dict:
    token_usage = {
        "provider": PROVIDER,
        "model": PRIMARY_MODEL,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
        "estimated_cost_usd_uncached": None,
        "latency_s": latency_s,
    }

    if usage and token_usage["prompt_tokens"] is not None:
        token_usage["estimated_cost_usd_uncached"] = round(
            (token_usage["prompt_tokens"] / 1_000_000) * INPUT_PRICE_PER_M
            + (token_usage["completion_tokens"] / 1_000_000) * OUTPUT_PRICE_PER_M,
            8,
        )

    return token_usage


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("CEREBRAS_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Falta CEREBRAS_API_KEY. Define la variable en .env o export CEREBRAS_API_KEY='tu_key'"
        )

    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"No encontré prompt: {PROMPT_PATH}")

    if not PAYLOAD_PATH.exists():
        raise FileNotFoundError(f"No encontré payload: {PAYLOAD_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    user_message = (
        "Genera la nota inicial del laboratorio de tesis. "
        "Devuelve únicamente JSON válido, sin markdown ni explicación externa.\n\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.cerebras.ai/v1",
        max_retries=0,
        timeout=TIMEOUT_SECONDS,
    )

    start = time.time()

    response = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        temperature=0.2,
        max_tokens=MAX_TOKENS,
        extra_body={
            "reasoning_effort": "low"
        },
    )

    latency_s = round(time.time() - start, 3)

    content = response.choices[0].message.content or ""
    usage = response.usage

    try:
        parsed = extract_json(content)
        valid, validation_msg = validate_initial_note(parsed)
    except Exception as exc:
        parsed = {
            "raw_output": content,
            "parse_error": True,
        }
        valid = False
        validation_msg = str(exc)

    token_usage = estimate_cost(usage, latency_s)

    result = {
        "output": parsed,
        "validation": {
            "valid": valid,
            "message": validation_msg,
        },
        "token_usage": token_usage,
        "meta": {
            "provider": PROVIDER,
            "used_model": PRIMARY_MODEL,
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