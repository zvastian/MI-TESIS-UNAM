import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import umap
from sentence_transformers import SentenceTransformer


RAW_LAUREATES = Path("outputs/nobel/raw/laureates_complete.json")
RAW_PRIZES = Path("outputs/nobel/raw/nobelPrizes_complete.json")
OUT_DIR = Path("outputs/nobel/processed")
ANALYSIS_DIR = Path("outputs/nobel/analysis")
STATIC_DIR = Path("static/nobel")

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
K_NEIGHBORS = 12

CATEGORY_SPECS = {
    "phy": {
        "en": "Physics",
        "es": "Física",
        "color": "#D96A72",
        "pole": [-4.4, 2.7],
    },
    "che": {
        "en": "Chemistry",
        "es": "Química",
        "color": "#58AF83",
        "pole": [-1.3, 3.6],
    },
    "med": {
        "en": "Physiology or Medicine",
        "es": "Fisiología o Medicina",
        "color": "#5A90D4",
        "pole": [2.4, 2.8],
    },
    "pea": {
        "en": "Peace",
        "es": "Paz",
        "color": "#AD79C9",
        "pole": [4.2, -1.0],
    },
    "lit": {
        "en": "Literature",
        "es": "Literatura",
        "color": "#E3B950",
        "pole": [0.7, -3.6],
    },
    "eco": {
        "en": "Economic Sciences",
        "es": "Ciencias Económicas",
        "color": "#43AAA6",
        "pole": [-3.4, -2.4],
    },
}

CATEGORY_CODE = {
    spec["en"]: code for code, spec in CATEGORY_SPECS.items()
}


def english(value, default=""):
    if isinstance(value, dict):
        return value.get("en") or next(iter(value.values()), default)
    return value if value is not None else default


def first_nonempty(*values):
    for value in values:
        if value not in ("", None, [], {}):
            return value
    return ""


def number(value):
    try:
        return float(value)
    except Exception:
        return None


def year_number(value):
    try:
        return int(str(value)[:4])
    except Exception:
        return None


def normalize_rows(matrix):
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-9, None)


def robust_scale(values):
    values = np.asarray(values, dtype=np.float32)
    center = np.median(values, axis=0)
    lo = np.percentile(values, 5, axis=0)
    hi = np.percentile(values, 95, axis=0)
    scale = np.maximum(hi - lo, 1e-6)
    result = (values - center) / (scale / 2)
    return np.clip(result, -1.35, 1.35)


def softmax(values, temperature=0.095):
    z = np.asarray(values, dtype=np.float32) / temperature
    z = z - np.max(z)
    exp = np.exp(z)
    return exp / np.sum(exp)


def hex_to_rgb(value):
    value = value.lstrip("#")
    return np.array([
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    ], dtype=np.float32)


def blend_color(weights):
    rgb = np.zeros(3, dtype=np.float32)
    for code, weight in weights.items():
        rgb += hex_to_rgb(CATEGORY_SPECS[code]["color"]) * float(weight)
    rgb = np.clip(np.round(rgb), 0, 255).astype(int)
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def safe_json_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def location_from_place(place):
    place = place or {}
    city_now = place.get("cityNow") or {}
    country_now = place.get("countryNow") or {}
    lat = number(city_now.get("latitude"))
    lng = number(city_now.get("longitude"))

    return {
        "city": first_nonempty(english(city_now), english(place.get("city"))),
        "country": first_nonempty(english(country_now), english(place.get("country"))),
        "continent": english(place.get("continent")),
        "label": english(place.get("locationString")),
        "latitude": lat,
        "longitude": lng,
    }


def build_nodes(laureates):
    nodes = []
    entities = {}
    organization_ids = set()

    for laureate in laureates:
        laureate_id = str(laureate.get("id", "")).strip()
        org_name = english(laureate.get("orgName"))
        person_name = first_nonempty(
            english(laureate.get("knownName")),
            english(laureate.get("fullName")),
        )
        is_organization = bool(org_name) or laureate.get("gender") == "org"
        name = org_name if is_organization else person_name
        name = name or laureate_id

        if is_organization:
            organization_ids.add(laureate_id)

        birth = laureate.get("birth") or {}
        birth_location = location_from_place(birth.get("place"))

        entity = {
            "laureate_id": laureate_id,
            "name": name,
            "entity_type": "organization" if is_organization else "person",
            "gender": "organization" if is_organization else (laureate.get("gender") or "unknown"),
            "birth_year": year_number(birth.get("year") or birth.get("date")),
            "birth_location": birth_location,
            "wikipedia": (laureate.get("wikipedia") or {}).get("english", ""),
            "wikidata": (laureate.get("wikidata") or {}).get("url", ""),
        }
        entities[laureate_id] = entity

        for award_index, award in enumerate(laureate.get("nobelPrizes") or []):
            category_en = english(award.get("category"))
            category_code = CATEGORY_CODE.get(category_en)

            if not category_code:
                raise RuntimeError(f"Categoría inesperada: {category_en!r}")

            award_year = year_number(award.get("awardYear"))
            motivation = english(award.get("motivation")).strip()
            affiliations = []

            for affiliation in award.get("affiliations") or []:
                location = location_from_place(affiliation)
                affiliations.append({
                    "name": first_nonempty(
                        english(affiliation.get("nameNow")),
                        english(affiliation.get("name")),
                    ),
                    **location,
                })

            residences = []
            for residence in award.get("residences") or []:
                residences.append(location_from_place(residence))

            node_id = f"NOBEL::{laureate_id}::{category_code}::{award_year}::{award_index}"
            event_id = f"PRIZE::{category_code}::{award_year}"

            nodes.append({
                "id": node_id,
                "laureate_id": laureate_id,
                "name": name,
                "entity_type": entity["entity_type"],
                "gender": entity["gender"],
                "award_year": award_year,
                "category_code": category_code,
                "category": CATEGORY_SPECS[category_code]["es"],
                "category_en": category_en,
                "prize_event_id": event_id,
                "motivation": motivation,
                "portion": award.get("portion", ""),
                "date_awarded": award.get("dateAwarded", ""),
                "prize_status": award.get("prizeStatus", ""),
                "prize_amount": award.get("prizeAmount"),
                "prize_amount_adjusted": award.get("prizeAmountAdjusted"),
                "birth_year": entity["birth_year"],
                "birth_location": birth_location,
                "affiliations": affiliations,
                "residences": residences,
                "wikipedia": entity["wikipedia"],
                "wikidata": entity["wikidata"],
                "external_link": next(
                    (
                        link.get("href", "")
                        for link in award.get("links") or []
                        if link.get("rel") == "external"
                        and "facts" in (link.get("class") or [])
                    ),
                    "",
                ),
            })

    return nodes, entities, organization_ids


def build_edges(nodes):
    events = defaultdict(list)
    laureate_awards = defaultdict(list)

    for node in nodes:
        events[node["prize_event_id"]].append(node["id"])
        laureate_awards[node["laureate_id"]].append(node["id"])

    edges = []
    edge_index = 0

    for event_id, node_ids in events.items():
        for source, target in combinations(node_ids, 2):
            edges.append({
                "id": f"E::{edge_index}",
                "source": source,
                "target": target,
                "type": "same_prize_event",
                "event_id": event_id,
                "weight": 1.0,
            })
            edge_index += 1

    for laureate_id, node_ids in laureate_awards.items():
        if len(node_ids) < 2:
            continue

        for source, target in combinations(node_ids, 2):
            edges.append({
                "id": f"E::{edge_index}",
                "source": source,
                "target": target,
                "type": "same_laureate_multiple_award",
                "laureate_id": laureate_id,
                "weight": 1.0,
            })
            edge_index += 1

    return edges, events, laureate_awards


def build_semantics(nodes):
    texts = [
        node["motivation"] or f'{node["name"]} {node["category_en"]}'
        for node in nodes
    ]

    print("Cargando modelo semántico:", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)

    print("Creando embeddings de motivation...")
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
    ).astype("float32")

    embeddings = normalize_rows(embeddings)

    print("Calculando UMAP semántico 2D...")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=28,
        min_dist=0.16,
        metric="cosine",
        random_state=42,
    )
    semantic_xy = robust_scale(reducer.fit_transform(embeddings))

    category_centroids = {}
    for code in CATEGORY_SPECS:
        indices = [
            index for index, node in enumerate(nodes)
            if node["category_code"] == code
        ]
        centroid = np.mean(embeddings[indices], axis=0, keepdims=True)
        category_centroids[code] = normalize_rows(centroid)[0]

    category_order = list(CATEGORY_SPECS.keys())

    for index, node in enumerate(nodes):
        similarities = np.array([
            float(embeddings[index] @ category_centroids[code])
            for code in category_order
        ], dtype=np.float32)

        affinities = softmax(similarities)
        affinity_map = {
            code: round(float(affinities[position]), 6)
            for position, code in enumerate(category_order)
        }

        mix = {}
        for code in category_order:
            official_weight = 0.68 if code == node["category_code"] else 0.0
            mix[code] = official_weight + 0.32 * affinity_map[code]

        total_mix = sum(mix.values())
        mix = {
            code: round(float(value / total_mix), 6)
            for code, value in mix.items()
        }

        pole = np.zeros(2, dtype=np.float32)
        for code, weight in mix.items():
            pole += np.asarray(CATEGORY_SPECS[code]["pole"], dtype=np.float32) * weight

        semantic_offset = semantic_xy[index] * 1.48
        field_position = pole + semantic_offset

        node["semantic_x"] = round(float(semantic_xy[index][0]), 6)
        node["semantic_y"] = round(float(semantic_xy[index][1]), 6)
        node["x"] = round(float(field_position[0]), 6)
        node["y"] = round(float(field_position[1]), 6)
        node["category_affinity"] = affinity_map
        node["color_mix"] = mix
        node["color"] = blend_color(mix)
        node["size"] = 4.1

    print("Calculando vecinos semánticos...")
    similarity_matrix = embeddings @ embeddings.T
    np.fill_diagonal(similarity_matrix, -np.inf)

    for index, node in enumerate(nodes):
        row = similarity_matrix[index]
        candidates = np.argpartition(-row, K_NEIGHBORS)[:K_NEIGHBORS]
        candidates = candidates[np.argsort(-row[candidates])]

        node["semantic_neighbors"] = [
            {
                "id": nodes[int(candidate)]["id"],
                "similarity": round(float(row[candidate]), 6),
            }
            for candidate in candidates
        ]

    return embeddings


def write_csv(nodes, path):
    fields = [
        "id",
        "laureate_id",
        "name",
        "entity_type",
        "gender",
        "award_year",
        "category",
        "category_code",
        "motivation",
        "portion",
        "birth_country",
        "affiliation_names",
        "affiliation_countries",
        "x",
        "y",
        "color",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for node in nodes:
            writer.writerow({
                "id": node["id"],
                "laureate_id": node["laureate_id"],
                "name": node["name"],
                "entity_type": node["entity_type"],
                "gender": node["gender"],
                "award_year": node["award_year"],
                "category": node["category"],
                "category_code": node["category_code"],
                "motivation": node["motivation"],
                "portion": node["portion"],
                "birth_country": node["birth_location"]["country"],
                "affiliation_names": " | ".join(
                    item["name"] for item in node["affiliations"] if item["name"]
                ),
                "affiliation_countries": " | ".join(
                    item["country"] for item in node["affiliations"] if item["country"]
                ),
                "x": node["x"],
                "y": node["y"],
                "color": node["color"],
            })


def main():
    if not RAW_LAUREATES.exists():
        raise FileNotFoundError(f"No encontré {RAW_LAUREATES}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    laureate_payload = json.loads(RAW_LAUREATES.read_text(encoding="utf-8"))
    laureates = laureate_payload.get("laureates", [])

    prizes = []
    if RAW_PRIZES.exists():
        prizes = json.loads(RAW_PRIZES.read_text(encoding="utf-8")).get("nobelPrizes", [])

    print("Construyendo nodos laureado-premio...")
    nodes, entities, organization_ids = build_nodes(laureates)
    edges, events, laureate_awards = build_edges(nodes)

    embeddings = build_semantics(nodes)
    np.save(OUT_DIR / "nobel_motivation_embeddings.npy", embeddings)

    category_counts = Counter(node["category"] for node in nodes)
    edge_counts = Counter(edge["type"] for edge in edges)
    entity_counts = Counter(entity["entity_type"] for entity in entities.values())

    multiple_awards = []
    for laureate_id, node_ids in laureate_awards.items():
        if len(node_ids) > 1:
            entity = entities[laureate_id]
            multiple_awards.append({
                "laureate_id": laureate_id,
                "name": entity["name"],
                "entity_type": entity["entity_type"],
                "award_count": len(node_ids),
                "awards": [
                    {
                        "year": next(n["award_year"] for n in nodes if n["id"] == node_id),
                        "category": next(n["category"] for n in nodes if n["id"] == node_id),
                    }
                    for node_id in node_ids
                ],
            })

    meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Nobel Prize API 2.1",
        "model": MODEL_NAME,
        "layout": "official_category_poles_plus_motivation_semantics_v1",
        "node_unit": "laureate_award",
        "laureate_count": len(entities),
        "award_node_count": len(nodes),
        "prize_event_count": len(events),
        "official_prize_endpoint_count": len(prizes),
        "edge_count": len(edges),
        "semantic_neighbors_per_node": K_NEIGHBORS,
    }

    categories = [
        {
            "code": code,
            **spec,
            "count": sum(node["category_code"] == code for node in nodes),
        }
        for code, spec in CATEGORY_SPECS.items()
    ]

    nodes_payload = {
        "meta": meta,
        "categories": categories,
        "nodes": nodes,
    }

    relations_payload = {
        "meta": meta,
        "edges": edges,
    }

    atlas_payload = {
        "meta": meta,
        "categories": categories,
        "nodes": nodes,
        "edges": edges,
    }

    summary = {
        "meta": meta,
        "entity_types": dict(entity_counts),
        "organization_ids": sorted(organization_ids),
        "category_counts": dict(category_counts),
        "relationship_counts": dict(edge_counts),
        "multiple_award_entities": sorted(
            multiple_awards,
            key=lambda item: (-item["award_count"], item["name"])
        ),
        "coverage": {
            "motivation": sum(bool(node["motivation"]) for node in nodes),
            "birth_coordinates": sum(
                node["birth_location"]["latitude"] is not None
                for node in nodes
            ),
            "affiliation_coordinates": sum(
                any(aff["latitude"] is not None for aff in node["affiliations"])
                for node in nodes
            ),
        },
    }

    safe_json_write(OUT_DIR / "nobel_award_nodes.json", nodes_payload)
    safe_json_write(OUT_DIR / "nobel_relationships.json", relations_payload)
    safe_json_write(OUT_DIR / "nobel_atlas.json", atlas_payload)
    safe_json_write(ANALYSIS_DIR / "nobel_atlas_summary.json", summary)
    safe_json_write(STATIC_DIR / "nobel_atlas.json", atlas_payload)

    write_csv(nodes, OUT_DIR / "nobel_award_nodes.csv")

    print()
    print("=" * 76)
    print("NOBEL ATLAS · PAYLOAD CONSTRUIDO")
    print("=" * 76)
    print("Entidades únicas:", len(entities))
    print("  Personas:", entity_counts.get("person", 0))
    print("  Organizaciones:", entity_counts.get("organization", 0))
    print("Nodos laureado-premio:", len(nodes))
    print("Eventos premiados:", len(events))
    print("Relaciones:", len(edges))
    print()

    print("NODOS POR CATEGORÍA")
    for label, count in category_counts.most_common():
        print(f"- {label}: {count}")

    print()
    print("RELACIONES")
    for label, count in edge_counts.items():
        print(f"- {label}: {count}")

    print()
    print("PREMIADOS MÚLTIPLES")
    for item in summary["multiple_award_entities"]:
        awards = ", ".join(
            f'{award["category"]} {award["year"]}'
            for award in item["awards"]
        )
        print(f'- {item["name"]} [{item["entity_type"]}]: {awards}')

    print()
    print("ARCHIVOS GENERADOS")
    print("-", OUT_DIR / "nobel_award_nodes.json")
    print("-", OUT_DIR / "nobel_relationships.json")
    print("-", OUT_DIR / "nobel_atlas.json")
    print("-", OUT_DIR / "nobel_motivation_embeddings.npy")
    print("-", OUT_DIR / "nobel_award_nodes.csv")
    print("-", ANALYSIS_DIR / "nobel_atlas_summary.json")
    print("-", STATIC_DIR / "nobel_atlas.json")
    print()
    print("Siguiente paso: montar este payload como mapa independiente en Laboratorio.")


if __name__ == "__main__":
    main()
