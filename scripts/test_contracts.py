import json
from pathlib import Path

from normalizers import normalize_module_output
from validators import validate_module_output


BASE_DIR = Path(__file__).resolve().parents[1]

TEST_FILES = {
    "initial_note": [
        BASE_DIR / "outputs" / "ai_conceptual_interpretation.json",
    ],
    "rerank": [
        BASE_DIR / "outputs" / "ai_rerank_groq_llama.json",
    ],
    "bloom": [
        BASE_DIR / "outputs" / "ai_bloom_groq_20b.json",
    ],
    "questions": [
        BASE_DIR / "outputs" / "ai_questions_groq_20b.json",
    ],
    "advisors": [
        BASE_DIR / "outputs" / "ai_advisors.json",
        BASE_DIR / "outputs" / "ai_advisors_groq_llama.json",
    ],
    "bibliography": [
        BASE_DIR / "outputs" / "ai_bibliography_groq_20b.json",
    ],
}


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_module(module: str, paths: list[Path]):
    print(f"\n=== {module.upper()} ===")

    found_any = False

    for path in paths:
        if not path.exists():
            print(f"SKIP {path.relative_to(BASE_DIR)}")
            continue

        found_any = True

        try:
            raw = read_json(path)
            normalized = normalize_module_output(module, raw)
            ok, msg = validate_module_output(module, normalized)
            print(f"{path.relative_to(BASE_DIR)}: {ok} | {msg}")

        except Exception as exc:
            print(f"{path.relative_to(BASE_DIR)}: False | exception: {exc}")

    if not found_any:
        print("NO FILES FOUND")


def main():
    for module, paths in TEST_FILES.items():
        test_module(module, paths)


if __name__ == "__main__":
    main()
