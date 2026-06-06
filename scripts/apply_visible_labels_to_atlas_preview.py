from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from build_visible_label_review import clean_title_case, read_json, repair_text, simplify_label


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "atlas_preview_data"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clean_area_text(value: object) -> str:
    text = repair_text(value)
    return (
        text.replace("?rea", "Área")
        .replace("Area", "Área")
        .replace("F?sico", "Físico")
        .replace("Matem?ticas", "Matemáticas")
        .replace("Ingenier?as", "Ingenierías")
        .replace("Biol?gicas", "Biológicas")
        .replace("Qu?micas", "Químicas")
    )


def clean_anchor_name(value: object) -> str:
    text = clean_area_text(value)
    names = {
        "Ciencias Físico-matemáticas e Ingenierías": "Ciencias Físico-Matemáticas e Ingenierías",
        "Ciencias Físico-matemáticas e ingenierías": "Ciencias Físico-Matemáticas e Ingenierías",
        "Ciencias biológicas, químicas y de la Salud": "Ciencias Biológicas, Químicas y de la Salud",
        "Ciencias sociales": "Ciencias Sociales",
        "Humanidades y artes": "Humanidades y Artes",
    }
    return names.get(text, text)


def patch_node(node: dict) -> bool:
    before = (
        node.get("label"),
        node.get("shortLabel"),
        node.get("description"),
        node.get("programsTop"),
        node.get("sampleTitles"),
    )
    suggested_label, suggested_short, _rule = simplify_label(node)
    node["label"] = suggested_label
    if node.get("level") == "macro":
        node["shortLabel"] = clean_title_case(node.get("shortLabel") or suggested_short)
    else:
        node["shortLabel"] = suggested_short

    if "areaLabel" in node:
        node["areaLabel"] = clean_area_text(node.get("areaLabel"))
    if "description" in node:
        node["description"] = clean_area_text(node.get("description"))
    if "name" in node:
        node["name"] = clean_area_text(node.get("name"))
    if "programsTop" in node:
        node["programsTop"] = clean_area_text(node.get("programsTop"))
    if "sampleTitles" in node:
        node["sampleTitles"] = clean_area_text(node.get("sampleTitles"))

    after = (
        node.get("label"),
        node.get("shortLabel"),
        node.get("description"),
        node.get("programsTop"),
        node.get("sampleTitles"),
    )
    return before != after


def patch_graph(path: Path) -> tuple[int, int]:
    payload = read_json(path)
    changed = 0
    nodes = payload.get("nodes", [])
    for node in nodes:
        changed += int(patch_node(node))

    for anchor in payload.get("anchors", []):
        if "label" in anchor:
            anchor["label"] = clean_area_text(anchor.get("label"))
        if "name" in anchor:
            anchor["name"] = clean_anchor_name(anchor.get("name"))

    if "macro" in payload and isinstance(payload["macro"], dict):
        patch_node(payload["macro"])

    write_json(path, payload)
    return len(nodes), changed


def main() -> None:
    stamp = int(time.time())
    backup = DATA.with_name(f"{DATA.name}.before_labels_{stamp}")
    if backup.exists():
        raise SystemExit(f"Backup already exists: {backup}")
    shutil.copytree(DATA, backup)

    total_nodes = 0
    total_changed = 0

    files = [DATA / "atlas_balanced_macro_graph.json"]
    files += sorted((DATA / "meso_by_macro").glob("*.json"))
    files += sorted((DATA / "micro_by_macro").glob("*.json"))

    for path in files:
        nodes, changed = patch_graph(path)
        total_nodes += nodes
        total_changed += changed

    print("Backup:", backup)
    print("Files patched:", len(files))
    print("Nodes seen:", total_nodes)
    print("Nodes changed:", total_changed)


if __name__ == "__main__":
    main()
