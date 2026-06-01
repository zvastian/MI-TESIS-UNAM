from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

META_PATH = BASE_DIR / "sample_50k_final_15d.parquet"
MACRO_NODES_PATH = BASE_DIR / "outputs" / "macroclusters" / "macrocluster_nodes_50k.parquet"

OUT_PATH = BASE_DIR / "static" / "explore" / "thesis_atlas_index.json"


def safe_str(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def safe_int(value):
    try:
        if pd.isna(value):
            return None
        return int(value)
    except Exception:
        return None


def safe_float(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def title_key(value: str) -> str:
    text = safe_str(value).lower()
    text = re.sub(r"[^a-záéíóúüñ0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def main():
    if not META_PATH.exists():
        raise FileNotFoundError(f"No existe META_PATH: {META_PATH}")

    if not MACRO_NODES_PATH.exists():
        raise FileNotFoundError(f"No existe MACRO_NODES_PATH: {MACRO_NODES_PATH}")

    print(f"Loading meta: {META_PATH}")
    meta = pd.read_parquet(META_PATH)

    print(f"Loading atlas nodes: {MACRO_NODES_PATH}")
    atlas = pd.read_parquet(MACRO_NODES_PATH)

    if "thesis_id" not in meta.columns:
        raise RuntimeError("meta no tiene thesis_id")

    if "thesis_id" not in atlas.columns:
        raise RuntimeError("macrocluster_nodes no tiene thesis_id")

    micro_col = pick_column(atlas, ["microcluster_id", "cluster_id", "cluster"])
    macro_col = pick_column(atlas, ["macrocluster_id", "macro_id"])
    x_col = pick_column(atlas, ["atlas_x", "x", "umap_x"])
    y_col = pick_column(atlas, ["atlas_y", "y", "umap_y"])

    if micro_col is None:
        raise RuntimeError(f"No encontré microcluster_id/cluster_id/cluster en atlas. Columnas: {atlas.columns.tolist()}")

    if macro_col is None:
        raise RuntimeError(f"No encontré macrocluster_id/macro_id en atlas. Columnas: {atlas.columns.tolist()}")

    if x_col is None or y_col is None:
        raise RuntimeError(f"No encontré coordenadas x/y en atlas. Columnas: {atlas.columns.tolist()}")

    meta_cols = [
        c for c in [
            "thesis_id",
            "doc_number_url",
            "ID_Limpio",
            "ID_Aleph",
            "titulo_normalizado",
            "titulo_limpio",
            "título",
            "Año",
            "programa",
            "nivel_estandar",
            "area",
            "plantel_estandarizado",
            "asesor_limpio_v2",
            "asesores_limpios_v2",
            "autor_limpio_v2",
        ]
        if c in meta.columns
    ]

    atlas_cols = [
        "thesis_id",
        micro_col,
        macro_col,
        x_col,
        y_col,
    ]

    for optional in ["macro_label", "micro_label", "cluster_label", "area_mix"]:
        if optional in atlas.columns:
            atlas_cols.append(optional)

    merged = (
        meta[meta_cols]
        .merge(
            atlas[atlas_cols].drop_duplicates(subset=["thesis_id"]),
            on="thesis_id",
            how="inner",
        )
        .copy()
    )

    by_thesis_id = {}
    by_doc_number_url = {}
    by_title_key = {}

    for _, row in merged.iterrows():
        thesis_id = safe_str(row.get("thesis_id"))
        doc_number_url = safe_str(row.get("doc_number_url"))

        title = (
            safe_str(row.get("titulo_normalizado"))
            or safe_str(row.get("titulo_limpio"))
            or safe_str(row.get("título"))
        )

        item = {
            "thesis_id": thesis_id,
            "doc_number_url": doc_number_url,
            "ID_Limpio": safe_str(row.get("ID_Limpio")),
            "ID_Aleph": safe_str(row.get("ID_Aleph")),
            "title": title,
            "year": safe_int(row.get("Año")),
            "program": safe_str(row.get("programa")),
            "degree": safe_str(row.get("nivel_estandar")),
            "area": safe_str(row.get("area")),
            "plantel": safe_str(row.get("plantel_estandarizado")),
            "advisor": safe_str(row.get("asesor_limpio_v2")) or safe_str(row.get("asesores_limpios_v2")),
            "author": safe_str(row.get("autor_limpio_v2")),
            "microcluster_id": safe_int(row.get(micro_col)),
            "macrocluster_id": safe_int(row.get(macro_col)),
            "atlas_x": safe_float(row.get(x_col)),
            "atlas_y": safe_float(row.get(y_col)),
            "macro_label": safe_str(row.get("macro_label")),
            "micro_label": safe_str(row.get("micro_label")) or safe_str(row.get("cluster_label")),
        }

        if thesis_id:
            by_thesis_id[thesis_id] = item

        if doc_number_url:
            by_doc_number_url[doc_number_url] = thesis_id

        tk = title_key(title)
        if tk and tk not in by_title_key:
            by_title_key[tk] = thesis_id

    payload = {
        "meta": {
            "source_meta": str(META_PATH.relative_to(BASE_DIR)),
            "source_atlas_nodes": str(MACRO_NODES_PATH.relative_to(BASE_DIR)),
            "rows": int(len(merged)),
            "by_thesis_id_count": len(by_thesis_id),
            "by_doc_number_url_count": len(by_doc_number_url),
            "by_title_key_count": len(by_title_key),
            "microcluster_column": micro_col,
            "macrocluster_column": macro_col,
            "x_column": x_col,
            "y_column": y_col,
        },
        "by_thesis_id": by_thesis_id,
        "by_doc_number_url": by_doc_number_url,
        "by_title_key": by_title_key,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    print(f"Saved: {OUT_PATH}")
    print(json.dumps(payload["meta"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
