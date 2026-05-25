import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from html import unescape


CANDIDATES = [
    Path("static/nobel/nobel_atlas_es_ui.json"),
    Path("outputs/nobel/nobel_atlas_es_ui.json"),
    Path("static/nobel/nobel_atlas_es.json"),
    Path("outputs/nobel/nobel_atlas_es.json"),
    Path("static/nobel/nobel_atlas.json"),
    Path("nobel/nobel_atlas.json"),
    Path("nobel_atlas.json"),
]

OUT_DIR = Path("outputs/nobel")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_JSON = OUT_DIR / "nobel_motivation_html_audit.json"
OUT_TXT = OUT_DIR / "nobel_motivation_html_audit.txt"

TAG_RE = re.compile(r"</?\s*([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>")
RAW_TAG_RE = re.compile(r"<[^>]+>")


def find_input():
    for path in CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("No encontré ningún nobel_atlas*.json")


def safe_str(x):
    if x is None:
        return ""
    return str(x)


def extract_tags(text):
    return [m.group(1).lower() for m in TAG_RE.finditer(text)]


def extract_raw_tags(text):
    return RAW_TAG_RE.findall(text)


def main():
    path = find_input()
    print("Auditing:", path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes = payload.get("nodes", [])

    fields = ["motivation", "motivation_es", "motivation_es_clean"]

    tag_counts = {field: Counter() for field in fields}
    raw_tag_counts = {field: Counter() for field in fields}
    nodes_with_tags = {field: [] for field in fields}
    suspicious = []

    for node in nodes:
        base = {
            "id": node.get("id"),
            "name": node.get("name"),
            "year": node.get("award_year"),
            "category": node.get("category"),
        }

        for field in fields:
            text = safe_str(node.get(field))
            if not text:
                continue

            tags = extract_tags(text)
            raw_tags = extract_raw_tags(text)

            if tags:
                tag_counts[field].update(tags)
                raw_tag_counts[field].update(raw_tags)

                nodes_with_tags[field].append({
                    **base,
                    "field": field,
                    "tags": tags,
                    "raw_tags": raw_tags,
                    "text": text,
                    "unescaped_text": unescape(text),
                })

            # suspicious patterns
            lowered = text.lower()
            if any(x in lowered for x in [
                "<script", "javascript:", "onerror=", "onclick=", "onload=",
                "<iframe", "<img", "<svg", "<object", "<embed", "<style"
            ]):
                suspicious.append({
                    **base,
                    "field": field,
                    "text": text,
                })

    audit = {
        "source": str(path),
        "total_nodes": len(nodes),
        "fields_checked": fields,
        "tag_counts": {
            field: dict(counter.most_common())
            for field, counter in tag_counts.items()
        },
        "raw_tag_counts": {
            field: dict(counter.most_common())
            for field, counter in raw_tag_counts.items()
        },
        "nodes_with_tags_count": {
            field: len(items)
            for field, items in nodes_with_tags.items()
        },
        "nodes_with_tags_sample": {
            field: items[:30]
            for field, items in nodes_with_tags.items()
        },
        "suspicious_count": len(suspicious),
        "suspicious_sample": suspicious[:50],
    }

    OUT_JSON.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    lines = []
    lines.append(f"SOURCE: {path}")
    lines.append(f"TOTAL NODES: {len(nodes)}")
    lines.append("")

    for field in fields:
        lines.append(f"=== FIELD: {field} ===")
        lines.append(f"NODES WITH TAGS: {len(nodes_with_tags[field])}")
        lines.append("TAG COUNTS:")
        if tag_counts[field]:
            for tag, count in tag_counts[field].most_common():
                lines.append(f"  <{tag}>: {count}")
        else:
            lines.append("  none")

        lines.append("RAW TAG COUNTS:")
        if raw_tag_counts[field]:
            for tag, count in raw_tag_counts[field].most_common():
                lines.append(f"  {tag}: {count}")
        else:
            lines.append("  none")

        lines.append("")
        lines.append("SAMPLES:")
        for item in nodes_with_tags[field][:12]:
            lines.append(f"- {item['year']} | {item['category']} | {item['name']}")
            lines.append(f"  tags: {item['raw_tags']}")
            lines.append(f"  text: {item['text']}")
        lines.append("")

    lines.append("=== SUSPICIOUS ===")
    lines.append(f"COUNT: {len(suspicious)}")
    for item in suspicious[:20]:
        lines.append(f"- {item['id']} | {item['field']} | {item['name']}")
        lines.append(f"  {item['text']}")

    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")

    print("\nDONE")
    print("Saved JSON:", OUT_JSON)
    print("Saved TXT:", OUT_TXT)
    print("\nSUMMARY:")
    for field in fields:
        print(f"\n{field}:")
        print("  nodes with tags:", len(nodes_with_tags[field]))
        print("  tags:", dict(tag_counts[field].most_common()))
    print("\nsuspicious:", len(suspicious))


if __name__ == "__main__":
    main()
