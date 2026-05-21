import json
import re
import unicodedata
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]

MINIMAL_CONTEXT_PATH = BASE_DIR / "payloads" / "context_minimal.json"
FULL_CONTEXT_PATH = BASE_DIR / "payloads" / "thesis_context_example.json"
OUTPUT_PATH = BASE_DIR / "payloads" / "ai_bibliography_payload.json"

MAX_SOURCE_THESES = 5
MAX_RAW_TITLES_PER_SOURCE = 30
MAX_PREFILTER_POOL = 50
MAX_TOTAL_CANDIDATES = 15

BAD_PATTERNS = [
    "tesis para obtener",
    "para obtener el grado",
    "universidad nacional autonoma",
    "universidad nacional autónoma",
    "facultad de",
    "bibliografia",
    "bibliografía",
    "indice",
    "índice",
]

WEAK_PATTERNS = [
    "centro de estudios",
    "revista del colegio",
    "económicas,",
    "gobierno y políticas públicas",
]

PROJECT_TERMS = [
    "banco", "banca", "bancario", "bancaria",
    "financiero", "financiera", "finanzas",
    "credito", "crédito", "inversion", "inversión",
    "capital", "mercado", "desarrollo",
    "mexico", "méxico", "china",
    "estado", "publica", "pública",
    "neoliberalismo", "historia", "economica", "económica",
]


def normalize_key(s: str) -> str:
    s = str(s or "").lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9ñ\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compact_text(s: str, max_chars: int = 240) -> str:
    s = str(s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_chars].strip()


def basic_clean(s: str) -> str:
    s = compact_text(s, 240)
    s = s.strip(" .;:-")
    s = re.sub(r"^,+\s*", "", s)
    s = re.sub(r"^\(?director\)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def looks_bad(title: str, source_thesis_title: str, bibliography_thesis_title: str) -> bool:
    title = basic_clean(title)

    if len(title) < 18:
        return True

    key = normalize_key(title)

    if not key:
        return True

    if key == normalize_key(source_thesis_title):
        return True

    if key == normalize_key(bibliography_thesis_title):
        return True

    for p in BAD_PATTERNS:
        if normalize_key(p) in key:
            return True

    if title.endswith(",") or title.endswith(" no") or title.endswith(" no."):
        return True

    if title.count("(") != title.count(")"):
        return True

    return False


def quality_score(title: str) -> float:
    t = basic_clean(title)
    key = normalize_key(t)
    score = 0.0

    if 35 <= len(t) <= 180:
        score += 2.0
    elif 20 <= len(t) < 35:
        score += 0.5
    elif len(t) > 180:
        score -= 0.8

    if re.search(r"\b(18|19|20)\d{2}\b", t):
        score += 1.2

    pub_words = [
        "fondo de cultura economica", "fondo de cultura económica",
        "editorial", "universidad", "revista", "banco de españa",
        "siglo xxi", "cepal", "unam", "civitas", "cambridge",
        "oxford", "routledge", "journal"
    ]

    if any(normalize_key(w) in key for w in pub_words):
        score += 1.2

    if "," in t:
        score += 0.4

    if "compilador" in key or "compiladores" in key or "coord" in key:
        score += 0.4

    if any(normalize_key(p) in key for p in WEAK_PATTERNS):
        score -= 1.5

    if t.startswith(",") or t.startswith("."):
        score -= 1.2

    if len(t.split()) < 4:
        score -= 2.0

    return score


def relevance_score(title: str, user_project: dict) -> float:
    key = normalize_key(title)
    score = 0.0

    for term in PROJECT_TERMS:
        if normalize_key(term) in key:
            score += 1.0

    user_terms = []
    user_terms.append(user_project.get("title", ""))

    for x in user_project.get("keywords", []):
        user_terms.append(str(x))

    for obj in user_project.get("objectives", []):
        user_terms.append(str(obj))

    user_blob = normalize_key(" ".join(user_terms))

    for token in set(user_blob.split()):
        if len(token) >= 5 and token in key:
            score += 0.4

    return score


def load_json(path: Path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_detected_titles(source):
    """
    Preferir detected_titles con score original.
    Fallback: titles como strings desde context_minimal.
    """
    detected = source.get("detected_titles", [])

    if isinstance(detected, str):
        try:
            detected = json.loads(detected)
        except Exception:
            detected = []

    items = []

    if isinstance(detected, list):
        for x in detected:
            if isinstance(x, dict):
                title = x.get("title") or x.get("bibliography_title") or ""
                score = x.get("score")
                items.append({
                    "title": title,
                    "source_title_score": score,
                })
            elif x:
                items.append({
                    "title": str(x),
                    "source_title_score": None,
                })

    if items:
        return items

    # fallback context_minimal
    titles = source.get("titles", [])
    if isinstance(titles, list):
        for t in titles:
            items.append({
                "title": str(t),
                "source_title_score": None,
            })

    return items


def get_bibliography_sources(minimal_ctx, full_ctx):
    """
    Preferimos full_context.bibliography_pool porque conserva detected_titles.score.
    Si no existe, usamos context_minimal.bibliography_summaries.
    """
    if isinstance(full_ctx, dict):
        pool = full_ctx.get("bibliography_pool", [])
        if isinstance(pool, list) and pool:
            return pool

    if isinstance(minimal_ctx, dict):
        summaries = minimal_ctx.get("bibliography_summaries", [])
        if isinstance(summaries, list):
            return summaries

    return []


def main():
    minimal_ctx = load_json(MINIMAL_CONTEXT_PATH) or {}
    full_ctx = load_json(FULL_CONTEXT_PATH) or {}

    bibliography_sources = get_bibliography_sources(minimal_ctx, full_ctx)

    user_project = minimal_ctx.get("user_project") or full_ctx.get("user_project") or {}

    compact_project = {
        "title": user_project.get("title", ""),
        "keywords": user_project.get("keywords", []),
        "objectives": user_project.get("objectives", []),
        "study_period": user_project.get("study_period", {}),
        "program": user_project.get("program", ""),
        "degree": user_project.get("degree", ""),
    }

    source_theses = []
    raw_candidates = []
    seen_titles = set()

    for source_idx, source in enumerate(bibliography_sources[:MAX_SOURCE_THESES], start=1):
        source_id = f"S{source_idx:02d}"

        source_thesis_title = compact_text(source.get("source_thesis_title", ""), 220)
        bibliography_thesis_title = compact_text(source.get("bibliography_thesis_title", ""), 220)

        source_theses.append({
            "source_id": source_id,
            "source_thesis_title": source_thesis_title,
            "source_similarity": source.get("source_similarity"),
        })

        detected_items = extract_detected_titles(source)

        for raw in detected_items[:MAX_RAW_TITLES_PER_SOURCE]:
            bibliography_title = basic_clean(raw.get("title", ""))
            source_title_score = raw.get("source_title_score")

            if looks_bad(
                bibliography_title,
                source_thesis_title,
                bibliography_thesis_title,
            ):
                continue

            title_key = normalize_key(bibliography_title)

            if title_key in seen_titles:
                continue

            seen_titles.add(title_key)

            q_score = quality_score(bibliography_title)
            r_score = relevance_score(bibliography_title, compact_project)

            try:
                st_score = float(source_title_score)
            except Exception:
                st_score = 0.0

            try:
                source_similarity = float(source.get("source_similarity") or 0)
            except Exception:
                source_similarity = 0.0

            final_score = (
                st_score * 0.50
                + r_score * 0.25
                + q_score * 0.15
                + source_similarity * 1.0
            )

            raw_candidates.append({
                "source_id": source_id,
                "raw_title": bibliography_title,
                "title": bibliography_title,
                "bibliography_title": bibliography_title,
                "source_title_score": source_title_score,
                "source_thesis_title": source_thesis_title,
                "source_doc_number": source.get("bibliography_doc_number", ""),
                "source_similarity": source.get("source_similarity"),
                "quality_score": round(q_score, 4),
                "relevance_score": round(r_score, 4),
                "final_score": round(final_score, 4),
            })

        # 1. Ordenar todos los candidatos crudos por score total.
    raw_candidates.sort(key=lambda x: x["final_score"], reverse=True)

    # 2. Pool preliminar amplio: mejores 50 antes de compactar para IA.
    prefilter_pool = raw_candidates[:MAX_PREFILTER_POOL]

    # 3. Diversificar un poco por tesis fuente para no mandar 15 de la misma tesis.
    selected = []
    per_source_count = {}

    # Primera pasada: máximo 5 por tesis fuente.
    for c in prefilter_pool:
        source_id = c.get("source_id", "")

        if per_source_count.get(source_id, 0) >= 5:
            continue

        selected.append(c)
        per_source_count[source_id] = per_source_count.get(source_id, 0) + 1

        if len(selected) >= MAX_TOTAL_CANDIDATES:
            break

    # Segunda pasada: si faltan, completar sin restricción.
    if len(selected) < MAX_TOTAL_CANDIDATES:
        selected_keys = {
            normalize_key(c["bibliography_title"])
            for c in selected
        }

        for c in prefilter_pool:
            key = normalize_key(c["bibliography_title"])

            if key in selected_keys:
                continue

            selected.append(c)
            selected_keys.add(key)

            if len(selected) >= MAX_TOTAL_CANDIDATES:
                break

    bibliography_candidates = []

    for i, c in enumerate(selected, start=1):
        bib_id = f"B{i:02d}"

        bibliography_candidates.append({
            "bib_id": bib_id,
            "raw_title": c["raw_title"],
            "title": c["title"],
            "bibliography_title": c["bibliography_title"],
            "source_title_score": c["source_title_score"],
            "source_id": c["source_id"],
            "source_thesis_title": c["source_thesis_title"],
            "source_doc_number": c["source_doc_number"],
            "source_similarity": c["source_similarity"],
            "quality_score": c["quality_score"],
            "relevance_score": c["relevance_score"],
            "final_score": c["final_score"],
        })

    payload = {
        "user_project": compact_project,
        "source_theses": source_theses,
        "bibliography_candidates": bibliography_candidates,
        "rules": {
            "max_recommendations": 5,
            "candidate_count": len(bibliography_candidates),
            "use_only_bib_ids": True,
            "clean_title_without_inventing": True,
            "bibliography_title_not_source_thesis_title": True,
            "uses_original_detected_title_score": True,
        }
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH.relative_to(BASE_DIR)}")
    print("sources:", len(source_theses))
    print("raw candidates:", len(raw_candidates))
    print("prefilter pool:", min(len(raw_candidates), MAX_PREFILTER_POOL))
    print("selected candidates for IA:", len(bibliography_candidates))
    print("chars:", len(json.dumps(payload, ensure_ascii=False)))

    print("\nCandidatos seleccionados:")
    for c in bibliography_candidates:
        print(
            c["bib_id"],
            "| final:", c["final_score"],
            "| detected:", c["source_title_score"],
            "| rel:", c["relevance_score"],
            "| q:", c["quality_score"],
            "-",
            c["bibliography_title"][:120]
        )
        print("  fuente:", c["source_thesis_title"][:90])


if __name__ == "__main__":
    main()
