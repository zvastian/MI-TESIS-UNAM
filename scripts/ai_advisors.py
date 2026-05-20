import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from validators import validate_advisors


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]

PROVIDER = "groq"
MODEL = "llama-3.1-8b-instant"
PROMPT_PATH = BASE_DIR / "prompts" / "advisors.md"
PAYLOAD_PATH = BASE_DIR / "payloads" / "ai_advisors_payload.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "ai_advisors.json"

INPUT_PRICE_PER_M = 0.15
OUTPUT_PRICE_PER_M = 0.60


def extract_json(text):
    text = text.strip()

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


def main():
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError("Falta GROQ_API_KEY")

    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"No encontré prompt: {PROMPT_PATH}")

    if not PAYLOAD_PATH.exists():
        raise FileNotFoundError(f"No encontré payload: {PAYLOAD_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    user_message = (
        "Analiza estos posibles asesores académicos.\n"
        "Devuelve únicamente JSON válido.\n\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

    start = time.time()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        temperature=0.2,
        max_tokens=1400,
        response_format={"type": "json_object"}
    )

    latency_s = round(time.time() - start, 3)

    content = response.choices[0].message.content
    usage = response.usage

    token_usage = {
        "provider": PROVIDER,
        "model": MODEL,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "estimated_cost_usd_uncached": None,
        "latency_s": latency_s
    }

    if usage:
        token_usage["estimated_cost_usd_uncached"] = (
            (usage.prompt_tokens / 1_000_000) * INPUT_PRICE_PER_M
            + (usage.completion_tokens / 1_000_000) * OUTPUT_PRICE_PER_M
        )

    try:
        parsed = extract_json(content)
    except json.JSONDecodeError:
        parsed = {
            "parse_error": True,
            "raw_output": content
        }

    valid, message = validate_advisors(parsed)

    validation = {
        "valid": valid,
        "message": message
    }

    result = {
        "output": parsed,
        "validation": validation,
        "token_usage": token_usage
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH}")

    print("\n── VALIDATION ──")
    print(json.dumps(validation, ensure_ascii=False, indent=2))

    print("\n── TOKEN USAGE ──")
    print(json.dumps(token_usage, ensure_ascii=False, indent=2))

    print("\n── OUTPUT ──")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()