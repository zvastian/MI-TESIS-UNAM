from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "atlas_preview_data"
AUDIT = ROOT / "audits" / "semantic_clusters"
OUT_ALL = AUDIT / "atlas_visible_label_review.v1.csv"
OUT_BY_AREA = AUDIT / "visible_label_blocks"
SEPARATOR = " - "


ACCENTS = {
    "Actuaria": "Actuaría",
    "Administracion": "Administración",
    "Analisis": "Análisis",
    "Anatomia": "Anatomía",
    "Anestesiologia": "Anestesiología",
    "Antropologia": "Antropología",
    "Area": "Área",
    "Artesanias": "Artesanías",
    "Arquitectonico": "Arquitectónico",
    "Biologia": "Biología",
    "Biologicas": "Biológicas",
    "Biologica": "Biológica",
    "Bioquimica": "Bioquímica",
    "Basicas": "Básicas",
    "Clinica": "Clínica",
    "Cirugia": "Cirugía",
    "Comunicacion": "Comunicación",
    "Computacion": "Computación",
    "Contaduria": "Contaduría",
    "Coordinacion": "Coordinación",
    "Determinacion": "Determinación",
    "Economia": "Economía",
    "Educacion": "Educación",
    "Electrica": "Eléctrica",
    "Energia": "Energía",
    "Evaluacion": "Evaluación",
    "Farmaceutico": "Farmacéutico",
    "Fisica": "Física",
    "Geografia": "Geografía",
    "Geologico": "Geológico",
    "Grafica": "Gráfica",
    "Ingenieria": "Ingeniería",
    "Juridica": "Jurídica",
    "Linguistica": "Lingüística",
    "Matematicas": "Matemáticas",
    "Mecanica": "Mecánica",
    "Medica": "Médica",
    "Metabolico": "Metabólico",
    "Metodos": "Métodos",
    "Mexico": "México",
    "Musica": "Música",
    "Neurologia": "Neurología",
    "Odontologia": "Odontología",
    "Optica": "Óptica",
    "Organizacion": "Organización",
    "Pediatria": "Pediatría",
    "Periodontologia": "Periodontología",
    "Politica": "Política",
    "Practica": "Práctica",
    "Petroleo": "Petróleo",
    "Psicologia": "Psicología",
    "Publica": "Pública",
    "Quimica": "Química",
    "Quimico": "Químico",
    "Regulacion": "Regulación",
    "Relacion": "Relación",
    "Tecnologia": "Tecnología",
    "Teoria": "Teoría",
    "Terapeutica": "Terapéutica",
    "Veterinaria": "Veterinaria",
}

QUESTION_REPAIRS = {
    "actuar?a": "actuaría",
    "administraci?n": "administración",
    "b?sicas": "básicas",
    "biolog?a": "biología",
    "biol?gicas": "biológicas",
    "bioqu?mica": "bioquímica",
    "bibliotecolog?a": "bibliotecología",
    "cl?nica": "clínica",
    "comunicaci?n": "comunicación",
    "computaci?n": "computación",
    "contadur?a": "contaduría",
    "cirug?a": "cirugía",
    "dise?o": "diseño",
    "econom?a": "economía",
    "educaci?n": "educación",
    "elaboraci?n": "elaboración",
    "endocrinolog?a": "endocrinología",
    "energ?a": "energía",
    "f?sica": "física",
    "filosof?a": "filosofía",
    "geograf?a": "geografía",
    "gesti?n": "gestión",
    "gr?fica": "gráfica",
    "ginecolog?a": "ginecología",
    "ingenier?a": "ingeniería",
    "informaci?n": "información",
    "infecci?n": "infección",
    "infectolog?a": "infectología",
    "inmunolog?a": "inmunología",
    "jur?dica": "jurídica",
    "mec?nica": "mecánica",
    "imagenolog?a": "imagenología",
    "matem?ticas": "matemáticas",
    "medi?tica": "mediática",
    "modelaci?n": "modelación",
    "m?sica": "música",
    "neumolog?a": "neumología",
    "neonatolog?a": "neonatología",
    "oncolog?a": "oncología",
    "organizaci?n": "organización",
    "patolog?a": "patología",
    "pedagog?a": "pedagogía",
    "pol?tica": "política",
    "producci?n": "producción",
    "psicolog?a": "psicología",
    "psiquiatr?a": "psiquiatría",
    "p?blica": "pública",
    "pr?ctica": "práctica",
    "petr?leo": "petróleo",
    "qu?mica": "química",
    "qu?mico": "químico",
    "regulaci?n": "regulación",
    "reumatolog?a": "reumatología",
    "tecnolog?a": "tecnología",
    "urolog?a": "urología",
}

STOP_START = {
    "estudio",
    "analisis",
    "revision",
    "generalidades",
    "aspectos",
    "conceptos",
    "principios",
    "modelo",
    "propuesta",
    "notas",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def repair_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    if any(mark in text for mark in ("Ã", "Â", "ã", "â", "�")):
        for enc in ("latin1", "cp1252"):
            try:
                fixed = text.encode(enc, errors="ignore").decode("utf-8", errors="ignore")
                if fixed and fixed.count("�") <= text.count("�"):
                    text = fixed
                    break
            except Exception:
                pass

    text = text.replace("Dise O", "Diseño").replace("dise O", "diseño")
    for bad, good in QUESTION_REPAIRS.items():
        text = re.sub(re.escape(bad), good, text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", repair_text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9ñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def title_word(token: str, is_first: bool) -> str:
    small = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "para", "por", "con"}
    raw = token
    edge_left = re.match(r"^\W+", raw)
    edge_right = re.search(r"\W+$", raw)
    left = edge_left.group(0) if edge_left else ""
    right = edge_right.group(0) if edge_right else ""
    core = raw[len(left) : len(raw) - len(right) if right else len(raw)]
    if not core:
        return raw

    lower = core.lower()
    clean = ACCENTS.get(lower[:1].upper() + lower[1:], lower)
    if clean in {"gas", "roo"}:
        clean = clean[:1].upper() + clean[1:]
    elif clean == "qfb":
        clean = "QFB"
    elif not is_first and clean in small:
        pass
    elif len(clean) <= 3 and clean not in small:
        clean = clean.upper()
    else:
        clean = clean[:1].upper() + clean[1:]
    return f"{left}{clean}{right}"


def clean_title_case(value: object) -> str:
    text = repair_text(value).lower()
    return " ".join(title_word(token, i == 0) for i, token in enumerate(text.split()))


def compact(value: object, max_len: int) -> str:
    text = clean_title_case(value)
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "..."


def split_label(label: str) -> tuple[str, str]:
    label = clean_title_case(label)
    if ":" not in label:
        return label, ""
    prefix, topic = label.split(":", 1)
    return prefix.strip(), topic.strip()


def parse_programs(value: object) -> str:
    text = repair_text(value)
    if not text:
        return ""
    first = text.split("|")[0].strip()
    first = re.sub(r"\s*\(\d+\)\s*$", "", first)
    return clean_title_case(first)


def parse_titles(value: object, limit: int = 3) -> str:
    text = repair_text(value)
    if not text:
        return ""
    titles = [compact(part.strip(), 80) for part in text.split("|") if part.strip()]
    return " | ".join(titles[:limit])


def simplify_label(node: dict) -> tuple[str, str, str]:
    current = clean_title_case(node.get("label") or node.get("id"))
    prefix, topic = split_label(current)
    program = parse_programs(node.get("programsTop")) or prefix

    if topic:
        normalized_topic = normalize(topic)
        words = normalized_topic.split()
        while words and words[0] in STOP_START:
            words.pop(0)
        if words:
            topic = clean_title_case(" ".join(words))
        suggested_short = compact(topic, 34)
        suggested_label = (
            f"{suggested_short}{SEPARATOR}{compact(program or prefix, 28)}"
            if (program or prefix)
            else suggested_short
        )
        return suggested_label, suggested_short, "topic_plus_program"

    return compact(current, 54), compact(current, 34), "current_clean"


def issue_flags(node: dict, suggested_label: str, suggested_short: str) -> str:
    flags = []
    current = clean_title_case(node.get("label"))
    if len(current) > 64:
        flags.append("current_long")
    if len(suggested_short) > 34:
        flags.append("short_long")
    if normalize(current) in {"derecho", "administracion", "medicina", "arquitectura", "psicologia", "biologia"}:
        flags.append("generic")
    if float(node.get("dominantAreaShare") or 0) < 0.40 and node.get("dominantAreaShare"):
        flags.append("low_area_purity")
    return ";".join(flags)


def visible_micro_nodes(payload: dict, policy: dict) -> list[dict]:
    min_size = int(policy["micro"]["min_visible_size"])
    max_nodes = int(policy["micro"]["max_visible_nodes_per_macro"])
    nodes = payload.get("nodes", [])
    visible = [node for node in nodes if int(node.get("size") or 0) >= min_size]
    visible = sorted(visible, key=lambda n: int(n.get("size") or 0), reverse=True)[:max_nodes]
    if not visible and nodes:
        visible = sorted(nodes, key=lambda n: int(n.get("size") or 0), reverse=True)[: min(8, len(nodes))]
    return visible


def collect_rows() -> list[dict]:
    policy = read_json(DATA / "atlas_display_policy.v1.json")
    rows = []

    macro = read_json(DATA / "atlas_balanced_macro_graph.json")
    for node in macro.get("nodes", []):
        rows.append(build_row("macro", "macro", "", node))

    for file in sorted((DATA / "meso_by_macro").glob("*.json")):
        payload = read_json(file)
        macro_id = payload.get("macro", {}).get("id") or file.stem
        for node in payload.get("nodes", []):
            rows.append(build_row("meso", file.name, macro_id, node))

    for file in sorted((DATA / "micro_by_macro").glob("*.json")):
        payload = read_json(file)
        macro_id = payload.get("macro", {}).get("id") or file.stem
        for node in visible_micro_nodes(payload, policy):
            rows.append(build_row("micro", file.name, macro_id, node))

    counts = Counter(f"{row['level']}::{normalize(row['suggested_label'])}" for row in rows)
    for row in rows:
        if counts[f"{row['level']}::{normalize(row['suggested_label'])}"] > 1:
            row["issue_flags"] = ";".join(filter(None, [row["issue_flags"], "suggested_duplicate"]))
    return rows


def build_row(level: str, source_file: str, macro_id: str, node: dict) -> dict:
    suggested_label, suggested_short, rule = simplify_label(node)
    return {
        "level": level,
        "area": node.get("area") or "",
        "macro_id": macro_id or node.get("id", ""),
        "source_file": source_file,
        "node_id": node.get("id"),
        "size": int(node.get("size") or 0),
        "current_label": clean_title_case(node.get("label")),
        "current_short_label": clean_title_case(node.get("shortLabel")),
        "suggested_label": suggested_label,
        "suggested_short_label": suggested_short,
        "suggestion_rule": rule,
        "issue_flags": issue_flags(node, suggested_label, suggested_short),
        "dominant_area_share": round(float(node.get("dominantAreaShare") or 0), 4),
        "interdisciplinarity": round(float(node.get("interdisciplinarity") or 0), 4),
        "programs_top": parse_programs(node.get("programsTop")),
        "sample_titles": parse_titles(node.get("sampleTitles")),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "level",
        "area",
        "macro_id",
        "source_file",
        "node_id",
        "size",
        "current_label",
        "current_short_label",
        "suggested_label",
        "suggested_short_label",
        "suggestion_rule",
        "issue_flags",
        "dominant_area_share",
        "interdisciplinarity",
        "programs_top",
        "sample_titles",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = collect_rows()
    write_csv(OUT_ALL, rows)

    if OUT_BY_AREA.exists():
        for old in OUT_BY_AREA.glob("*.csv"):
            old.unlink()
    OUT_BY_AREA.mkdir(parents=True, exist_ok=True)

    for area in sorted({row["area"] or "Sin area" for row in rows}):
        area_rows = [row for row in rows if (row["area"] or "Sin area") == area]
        safe_area = normalize(area).replace(" ", "_") or "sin_area"
        write_csv(OUT_BY_AREA / f"{safe_area}.csv", area_rows)

    counts = Counter(row["level"] for row in rows)
    flagged = sum(1 for row in rows if row["issue_flags"])
    print(f"Wrote: {OUT_ALL}")
    print(f"Wrote blocks: {OUT_BY_AREA}")
    print({"rows": len(rows), "by_level": dict(counts), "flagged": flagged})


if __name__ == "__main__":
    main()
