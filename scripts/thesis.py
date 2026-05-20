import json
import re
from pathlib import Path
import pyarrow.dataset as ds
import unicodedata

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = Path(__file__).resolve().parents[1]
META_PATH = BASE_DIR / "sample_50k_final_15d.parquet"
EMBEDDINGS_PATH = BASE_DIR / "sample_50k_embeddings.npy"
NODES_PATH = BASE_DIR / "cluster_nodes_final_50k.parquet"
EDGES_PATH = BASE_DIR / "cluster_edges_mutual_knn_50k.parquet"
BIBLIOGRAPHY_PATH = None
QUERY_VECTOR_PATH = BASE_DIR / "payloads" / "query_vector.json"
CLUSTER_COL = "cluster"
EMBEDDING_MODEL_NAME = "Xenova/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSIONS = 384


# ============================================================
# HELPERS
# ============================================================

def normalize_id(x):
    """
    Normaliza IDs de tesis para hacer match con doc_number.
    Ejemplo: 881440 -> '000881440'
    """
    if pd.isna(x):
        return None
    return str(x).strip().zfill(9)


def l2_normalize(v):
    """
    Normaliza un vector para similitud coseno.
    """
    v = np.asarray(v, dtype=np.float32)
    norm = np.linalg.norm(v)

    if norm == 0:
        return v

    return v / norm


def split_objectives(objectives):
    """
    Acepta objetivos como lista o como string largo.
    Devuelve lista limpia.
    """
    if isinstance(objectives, list):
        return [str(o).strip() for o in objectives if str(o).strip()]

    if isinstance(objectives, str):
        parts = re.split(r"\n|;|\.\s+", objectives)
        return [p.strip(" -•\t") for p in parts if p.strip()]

    return []

def normalize_title_key(s):
    """
    Normaliza títulos para hacer match exacto entre:
    - meta["titulo_normalizado"]
    - bibliography_df["titulo_normalizado"]

    No usa fuzzy.
    """
    if pd.isna(s):
        return ""

    s = str(s).lower().strip()

    # quitar acentos
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))

    # normalizar separadores comunes
    s = s.replace(":", " ")
    s = s.replace("/", " ")
    s = s.replace("-", " ")
    s = s.replace("–", " ")
    s = s.replace("—", " ")

    # quitar puntuación rara
    s = re.sub(r"[^a-z0-9ñ\s]", " ", s)

    # espacios
    s = re.sub(r"\s+", " ", s).strip()

    return s

def json_safe(obj):
    """
    Convierte tipos numpy/pandas/NaN a JSON válido.
    """
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [json_safe(v) for v in obj]

    if isinstance(obj, tuple):
        return [json_safe(v) for v in obj]

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        if np.isnan(obj):
            return None
        return float(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass

    return obj
    
BLOOM_VERBS = {
    "recordar": [
        "identificar", "listar", "definir", "describir", "reconocer",
        "nombrar", "señalar", "enumerar", "localizar", "memorizar",
        "recuperar", "reproducir", "indicar", "citar", "etiquetar",
        "subrayar", "registrar", "repasar", "copiar", "repetir",
        "marcar", "mencionar", "recolectar", "catalogar", "situar",
        "retener", "observar", "apreciar", "referenciar", "tabular"
    ],
    "comprender": [
        "explicar", "interpretar", "resumir", "clasificar", "comparar",
        "distinguir", "comprender", "parafrasear", "ilustrar", "inferir",
        "predecir", "traducir", "ejemplificar", "asociar", "reescribir",
        "discutir", "extrapolar", "narrar", "simbolizar", "generalizar",
        "reinterpretar", "esquematizar", "categorizar", "contextualizar",
        "reflexionar", "deducir", "contrastar", "relacionar", "reformular",
        "clarificar"
    ],
    "aplicar": [
        "aplicar", "usar", "implementar", "emplear", "utilizar",
        "resolver", "calcular", "ejecutar", "operar", "practicar",
        "manipular", "experimentar", "simular", "adaptar", "editar",
        "completar", "modificar", "programar", "producir", "preparar",
        "automatizar", "ensayar", "realizar", "transferir", "desplegar",
        "configurar", "instalar", "demostrar", "modelar", "presentar"
    ],
    "analizar": [
        "analizar", "examinar", "diferenciar", "diagnosticar", "estudiar",
        "descomponer", "inspeccionar", "cuestionar", "investigar", "testear",
        "depurar", "rastrear", "descubrir", "detectar", "mapear",
        "segmentar", "separar", "atribuir", "correlacionar", "jerarquizar",
        "discriminar", "escrutar", "diseccionar", "triangular", "identificar",
        "caracterizar", "vincular", "perfilar", "categorizar", "ordenar"
    ],
    "evaluar": [
        "juzgar", "criticar", "validar", "determinar", "medir",
        "argumentar", "defender", "debatir", "justificar", "refutar",
        "monitorear", "auditar", "calificar", "ponderar", "fundamentar",
        "contraargumentar", "puntuar", "dictaminar", "arbitrar", "recomendar",
        "concluir", "decidir", "sopesar", "priorizar", "estimar",
        "revisar", "apreciar", "verificar", "seleccionar", "diagnosticar"
    ],
    "crear": [
        "proponer", "diseñar", "desarrollar", "formular", "generar",
        "elaborar", "crear", "sugerir", "inventar", "planificar",
        "imaginar", "componer", "integrar", "combinar", "innovar",
        "idear", "proyectar", "sintetizar", "redactar", "publicar",
        "codificar", "prototipar", "articular", "reimaginar", "transformar",
        "iniciar", "fundar", "trazar", "estructurar", "hipotetizar",
        "construir", "organizar"
    ],
}

def bloom_preanalysis(objectives):
    """
    Detecta verbos de objetivos y los mapea a Bloom.
    No usa IA.
    """
    objectives = split_objectives(objectives)

    detected = []
    counts = {level: 0 for level in BLOOM_VERBS}

    for i, obj in enumerate(objectives):
        text = obj.lower()

        for level, verbs in BLOOM_VERBS.items():
            for verb in verbs:
                if re.search(rf"\b{re.escape(verb)}\w*\b", text):
                    detected.append({
                        "objective_index": i,
                        "objective": obj,
                        "verb": verb,
                        "bloom_level": level
                    })
                    counts[level] += 1

    dominant = [
        k for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ]

    missing = [k for k, v in counts.items() if v == 0]

    return {
        "objectives": objectives,
        "detected_verbs": detected,
        "counts_by_level": counts,
        "dominant_levels": dominant,
        "missing_levels": missing
    }


def top_similar_indices(query_vector, X, k=50):
    """
    Busca las tesis más cercanas por similitud coseno.
    """
    q = l2_normalize(query_vector)

    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)

    Xn = X / norms
    sims = Xn @ q

    idx = np.argsort(sims)[::-1][:k]

    return idx, sims[idx]


def build_thesis_record(row, similarity=None, cluster_col=CLUSTER_COL):
    """
    Convierte una fila de meta en un registro compacto para el contexto.
    """
    record = {
        "id": normalize_id(row["ID_Limpio"]),
        "title": row.get("titulo_normalizado"),
        "year": int(row["Año"]) if pd.notna(row.get("Año")) else None,
        "program": row.get("programa"),
        "degree": row.get("nivel_estandar"),
        "area": row.get("area"),
        "advisor": row.get("asesor_limpio_v2"),
        "advisors": row.get("asesores_limpios_v2"),
        "plantel": row.get("plantel_estandarizado"),
        "period": row.get("periodo")
    }

    if cluster_col in row.index:
        value = row.get(cluster_col)
        record["cluster_id"] = int(value) if pd.notna(value) else None

    if similarity is not None:
        record["embedding_similarity"] = float(similarity)

    return record


def load_query_vector(path):
    """
    Lee query_vector.json.
    Acepta:
    1) [0.1, 0.2, ...]
    2) {"embedding": [0.1, 0.2, ...]}
    3) {"query_vector": [0.1, 0.2, ...]}
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        vector = data
    elif isinstance(data, dict) and "embedding" in data:
        vector = data["embedding"]
    elif isinstance(data, dict) and "query_vector" in data:
        vector = data["query_vector"]
    else:
        raise ValueError(
            "query_vector.json debe ser una lista de 384 floats, "
            "o un objeto con clave 'embedding' / 'query_vector'."
        )

    vector = np.asarray(vector, dtype=np.float32)

    if vector.shape[0] != 384:
        raise ValueError(f"query_vector debe tener dimensión 384. Tiene: {vector.shape}")

    return vector


def load_bibliography_for_exact_titles(path, titles, max_records=5):
    """
    Carga bibliografía solo para títulos con match exacto-normalizado.

    Regla:
    - NO usa ID_Limpio.
    - NO usa fuzzy.
    - Busca en bibliography["titulo_normalizado"].
    - Devuelve máximo max_records en el orden de los títulos recibidos.
    """

    if not path:
        return {}

    path = Path(path)

    if not path.exists():
        print(f"AVISO: No encontré bibliografía en {path}.")
        return {}

    titles = [
        str(t).strip()
        for t in titles
        if t is not None and str(t).strip()
    ]

    if not titles:
        return {}

    title_keys = [
        normalize_title_key(t)
        for t in titles
    ]

    title_keys = [
        k for k in title_keys
        if k
    ]

    if not title_keys:
        return {}

    wanted_columns = [
        "doc_number",
        "titulo",
        "titulo_normalizado",
        "anio",
        "autor",
        "asesor",
        "programa",
        "nivel",
        "area",
        "plantel",
        "detected_titles",
        "average_title_score",
        "bibliography_embedding_text",
        "bibliography_ref_count",
        "ready_for_ai",
        "ai_context_chunk"
    ]

    dataset = ds.dataset(str(path), format="parquet")
    available_columns = set(dataset.schema.names)

    columns = [
        c for c in wanted_columns
        if c in available_columns
    ]

    table = dataset.to_table(columns=columns)
    df = table.to_pandas()

    if df.empty or "titulo_normalizado" not in df.columns:
        return {}

    df["_title_key"] = df["titulo_normalizado"].apply(normalize_title_key)

    df = df[df["_title_key"].isin(title_keys)].copy()

    if df.empty:
        return {}

    # preservar orden semántico: top 1, top 2, top 3...
    order = {
        key: i
        for i, key in enumerate(title_keys)
    }

    df["_order"] = df["_title_key"].map(order)

    df = (
        df
        .sort_values("_order")
        .drop_duplicates("_title_key")
        .head(max_records)
    )

    return {
        row["_title_key"]: row
        for _, row in df.iterrows()
    }  

    if not path:
        return {}

    path = Path(path)

    if not path.exists():
        print(f"AVISO: No encontré bibliografía en {path}.")
        return {}

    doc_numbers = [
        normalize_id(d)
        for d in doc_numbers
        if d is not None
    ]

    doc_numbers = list(dict.fromkeys(doc_numbers))  # quitar duplicados preservando orden

    if not doc_numbers:
        return {}

    dataset = ds.dataset(str(path), format="parquet")

    wanted_columns = [
        "doc_number",
        "titulo",
        "titulo_normalizado",
        "anio",
        "autor",
        "asesor",
        "programa",
        "nivel",
        "area",
        "plantel",
        "detected_titles",
        "average_title_score",
        "bibliography_embedding_text",
        "bibliography_ref_count",
        "ready_for_ai",
        "ai_context_chunk"
    ]

    available_columns = set(dataset.schema.names)

    columns = [
        c for c in wanted_columns
        if c in available_columns
    ]

    table = dataset.to_table(
        columns=columns,
        filter=ds.field("doc_number").isin(doc_numbers)
    )

    df = table.to_pandas()

    if df.empty:
        return {}

    df["_doc_number"] = df["doc_number"].apply(normalize_id)

    order = {
        doc: i
        for i, doc in enumerate(doc_numbers)
    }

    df["_order"] = df["_doc_number"].map(order)

    df = (
        df
        .sort_values("_order")
        .head(max_records)
    )

    return {
        row["_doc_number"]: row
        for _, row in df.iterrows()
    }
    """
    Carga dataset de bibliografía.
    Soporta JSON list, JSON dict, JSONL y Parquet.
    Si no existe o path está vacío, devuelve DataFrame vacío.
    """

    if not path:
        print("AVISO: Sin bibliografía por ahora. Continuaré sin bibliography_pool.")
        return pd.DataFrame()

    path = Path(path)

    if not path.exists():
        print(f"AVISO: No encontré bibliografía en {path}. Continuaré sin bibliography_pool.")
        return pd.DataFrame()

SPANISH_STOPWORDS = [
    "de", "del", "la", "el", "los", "las", "y", "en", "para", "por",
    "con", "un", "una", "uno", "sobre", "sus", "su", "al", "a",
    "que", "como", "caso", "analisis", "estudio", "propuesta",
    "tesis", "mexico", "mexicana", "mexicano"
]


def extract_keywords_from_titles(titles, top_n=18):
    """
    Extrae keywords determinísticas desde títulos similares.
    Usa TF-IDF con ngramas 1-3.
    No usa IA.
    """

    titles = [
        str(t).strip()
        for t in titles
        if t is not None and str(t).strip()
    ]

    if not titles:
        return []

    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        stop_words=SPANISH_STOPWORDS,
        ngram_range=(1, 3),
        min_df=1,
        max_features=400
    )

    X_kw = vectorizer.fit_transform(titles)
    scores = np.asarray(X_kw.mean(axis=0)).ravel()
    terms = np.array(vectorizer.get_feature_names_out())

    order = np.argsort(scores)[::-1]

    keywords = []

    for idx in order[:top_n]:
        term = terms[idx]
        score = float(scores[idx])

        if len(term) < 3:
            continue

        keywords.append({
            "keyword": term,
            "score": score
        })

    return keywords

def build_temporal_patterns(retrieved):
    """
    Resume patrones temporales desde las tesis recuperadas.
    """

    years = retrieved["Año"].dropna().astype(int)

    if len(years) == 0:
        return {}

    period_distribution = {
        str(k): int(v)
        for k, v in retrieved["periodo"].value_counts().to_dict().items()
    }

    recent_share = float((years >= 2020).mean())
    post_2000_share = float((years >= 2000).mean())

    if years.min() < 1980 and years.max() >= 2020:
        historical_depth = "alta"
    elif years.min() < 1995:
        historical_depth = "media"
    else:
        historical_depth = "reciente"

    return {
        "year_min": int(years.min()),
        "year_max": int(years.max()),
        "median_year": int(years.median()),
        "period_distribution_top50": period_distribution,
        "recent_share_2020_onwards": recent_share,
        "post_2000_share": post_2000_share,
        "historical_depth": historical_depth
    }

# ============================================================
# LIMPIEZA DE BIBLIOGRAFÍA PARA LLM
# ============================================================

def clean_bibliography_line(s):
    """
    Limpia una línea/título bibliográfico extraído.
    No intenta hacer APA perfecto; solo reduce ruido para LLM.
    """
    if s is None or pd.isna(s):
        return ""

    s = str(s)

    # quitar numeración inicial
    s = re.sub(r"^\s*\d+[\.\-\)]\s*", "", s)
    s = re.sub(r"^\s*[•\-]\s*", "", s)

    # normalizar espacios
    s = re.sub(r"\s+", " ", s).strip()

    # limpiar basura OCR frecuente
    s = s.replace("lllBLIOGRAFÍA", "Bibliografía")
    s = s.replace("BIBLIOGRAFIA", "")
    s = s.replace("Bibliografía", "")
    s = s.strip(" .;:-")

    return s


def extract_bibliography_titles_clean(bib_record, max_titles=15):
    """
    Extrae una lista limpia de posibles títulos bibliográficos desde:
    1. detected_titles, si existe y trae títulos útiles.
    2. ai_context_chunk, especialmente la sección 'Títulos bibliográficos detectados'.
    3. bibliography_embedding_text como fallback.

    Devuelve una lista corta, deduplicada y legible.
    """

    candidates = []

    detected_titles = bib_record.get("detected_titles", [])

    # 1. detected_titles estructurado
    if isinstance(detected_titles, list):
        for item in detected_titles:
            if isinstance(item, dict):
                title = item.get("title", "")
            else:
                title = str(item)

            title = clean_bibliography_line(title)

            if title:
                candidates.append(title)

    elif isinstance(detected_titles, str):
        try:
            parsed = json.loads(detected_titles)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        title = item.get("title", "")
                    else:
                        title = str(item)

                    title = clean_bibliography_line(title)

                    if title:
                        candidates.append(title)
        except Exception:
            pass

    # 2. ai_context_chunk
    ai_chunk = str(bib_record.get("ai_context_chunk", "") or "")

    if ai_chunk:
        # intenta capturar líneas numeradas después de "Títulos bibliográficos detectados"
        m = re.search(
            r"Títulos bibliográficos detectados:(.*?)(Bibliografía extraída:|$)",
            ai_chunk,
            flags=re.DOTALL | re.IGNORECASE
        )

        if m:
            detected_section = m.group(1)

            lines = re.split(r"\n|(?=\s*\d+\.)", detected_section)

            for line in lines:
                line = clean_bibliography_line(line)

                if len(line) >= 20:
                    candidates.append(line)

    # 3. fallback desde bibliography_embedding_text
    if len(candidates) < 5:
        raw = str(bib_record.get("bibliography_embedding_text", "") or "")

        # dividir por patrones comunes de bibliografía
        parts = re.split(
            r"\n|(?=\s*\d+[\.\)])|(?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+,\s)",
            raw
        )

        for part in parts:
            part = clean_bibliography_line(part)

            if 25 <= len(part) <= 220:
                candidates.append(part)

            if len(candidates) >= max_titles * 2:
                break

    # Deduplicar conservando orden
    seen = set()
    clean = []

    for title in candidates:
        title = clean_bibliography_line(title)

        if not title:
            continue

        # filtros de ruido
        if len(title) < 12:
            continue

        if title.lower() in {"bibliografia", "bibliografias", "bibliografía", "bibliografías"}:
            continue

        key = normalize_title_key(title)

        if key in seen:
            continue

        seen.add(key)
        clean.append(title)

        if len(clean) >= max_titles:
            break

    return clean
# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def build_thesis_context(
    user_input,
    query_vector,
    meta,
    X,
    nodes,
    edges,
    bibliography_path=None,
    cluster_col=CLUSTER_COL,
    top_k=50
    
):
    """
    Construye el contexto estructurado del Laboratorio de Tesis.

    No usa IA.
    Solo retrieval, clusters, bloom, bibliografía, asesores y señales semánticas.
    """

    meta = meta.copy()

    if cluster_col not in meta.columns:
        raise ValueError(
            f"No existe la columna '{cluster_col}' en meta.\n"
            f"Columnas actuales: {meta.columns.tolist()}\n\n"
            "Necesitas usar el parquet de la muestra que ya tenga cluster_15d por tesis. "
            "Si en notebook sí lo tienes, guarda:\n"
            "meta.to_parquet('sample_50k_clusters_with_15d.parquet', index=False)\n"
            "y cambia META_PATH a ese archivo."
        )

    if len(meta) != len(X):
        raise ValueError(
            f"meta y X no tienen el mismo tamaño: meta={len(meta)}, X={len(X)}"
        )

    meta["_doc_number"] = meta["ID_Limpio"].apply(normalize_id)

    # -----------------------------
    # 1. Retrieval top K
    # -----------------------------
    idx, sims = top_similar_indices(query_vector, X, k=top_k)

    retrieved = meta.iloc[idx].copy()
    retrieved["_similarity"] = sims

    top_50 = [
        build_thesis_record(row, similarity=row["_similarity"], cluster_col=cluster_col)
        for _, row in retrieved.iterrows()
    ]

    top_10 = top_50[:10]
    top_5 = top_50[:5]

    keywords_detected = extract_keywords_from_titles(
    [t["title"] for t in top_50[:50]],
    top_n=18
)
    # -----------------------------
    # 2. Cluster principal
    # -----------------------------
    top_for_cluster = retrieved.head(20)

    cluster_counts = (
        top_for_cluster[top_for_cluster[cluster_col] != -1][cluster_col]
        .value_counts()
    )

    if len(cluster_counts) > 0:
        main_cluster_id = int(cluster_counts.index[0])
    else:
        main_cluster_id = None

    node_map = {
        int(row["id"]): row.to_dict()
        for _, row in nodes.iterrows()
    }

    main_cluster = None

    if main_cluster_id is not None and main_cluster_id in node_map:
        n = node_map[main_cluster_id]

        main_cluster = {
            "id": main_cluster_id,
            "label": n.get("label"),
            "macro_domain": n.get("macro_domain"),
            "main_area": n.get("main_area"),
            "size": int(n.get("size", 0)),
            "centrality": {
                "degree": float(n.get("degree_centrality", 0)),
                "betweenness": float(n.get("betweenness_centrality", 0)),
                "pagerank": float(n.get("pagerank", 0))
            },
            "x": float(n.get("x", 0)),
            "y": float(n.get("y", 0))
        }

    # -----------------------------
    # 3. Clusters vecinos
    # -----------------------------
    neighbor_clusters = []

    if main_cluster_id is not None and len(edges) > 0:
        e = edges[
            (edges["source"] == main_cluster_id) |
            (edges["target"] == main_cluster_id)
        ].copy()

        if len(e) > 0:
            e["neighbor"] = e.apply(
                lambda r: int(r["target"])
                if int(r["source"]) == main_cluster_id
                else int(r["source"]),
                axis=1
            )

            e = e.sort_values("weight", ascending=False)

            for _, row in e.head(8).iterrows():
                nid = int(row["neighbor"])

                if nid in node_map:
                    n = node_map[nid]

                    neighbor_clusters.append({
                        "id": nid,
                        "label": n.get("label"),
                        "macro_domain": n.get("macro_domain"),
                        "main_area": n.get("main_area"),
                        "edge_weight": float(row["weight"]),
                        "size": int(n.get("size", 0))
                    })

    # -----------------------------
    # 4. Distribuciones top50
    # -----------------------------
    program_distribution = {
        str(k): int(v)
        for k, v in retrieved["programa"].value_counts().head(10).to_dict().items()
    }

    degree_distribution = {
        str(k): int(v)
        for k, v in retrieved["nivel_estandar"].value_counts().head(10).to_dict().items()
    }

    area_distribution = {
        str(k): int(v)
        for k, v in retrieved["area"].value_counts().head(10).to_dict().items()
    }

    temporal_patterns = build_temporal_patterns(retrieved)
    # -----------------------------
    # 5. Bloom
    # -----------------------------
    bloom = bloom_preanalysis(user_input.get("objectives", []))
    # -----------------------------
        # -----------------------------
    # 6. Bibliography pool por título exacto
    # -----------------------------
    bibliography_pool = []

    # Regla:
    # tomar top 20 tesis semánticamente cercanas,
    # buscar cuáles tienen bibliografía por título exacto,
    # conservar máximo 5 en orden de cercanía.
    candidate_titles = [
        thesis["title"]
        for thesis in top_50[:20]
    
    ]

    bib_by_title = load_bibliography_for_exact_titles(
        bibliography_path,
        candidate_titles,
        max_records=5
    )

    for thesis in top_50[:20]:
        title_key = normalize_title_key(thesis["title"])

        if title_key in bib_by_title:
            b = bib_by_title[title_key]

            detected_titles = b.get("detected_titles", [])

            if isinstance(detected_titles, str):
                try:
                    detected_titles = json.loads(detected_titles)
                except Exception:
                    detected_titles = []
            
            bibliography_titles_clean = extract_bibliography_titles_clean(
                b,
                max_titles=15
            )
                        
            bibliography_pool.append({
                "source_thesis_id": thesis["id"],
                "source_thesis_title": thesis["title"],
                "source_similarity": thesis["embedding_similarity"],

                "bibliography_doc_number": str(b.get("doc_number", "")),
                "match_type": "exact_title",
                "match_score": 100,

                "bibliography_thesis_title": str(b.get("titulo", "")),
                "bibliography_year": int(b.get("anio")) if pd.notna(b.get("anio")) else None,
                "bibliography_program": str(b.get("programa", "")),
                "bibliography_level": str(b.get("nivel", "")),
                "bibliography_area": str(b.get("area", "")),
                "bibliography_plantel": str(b.get("plantel", "")),
                "bibliography_ref_count": int(b.get("bibliography_ref_count", 0))
                if pd.notna(b.get("bibliography_ref_count", None))
                else None,

                "detected_titles": detected_titles[:12]
                if isinstance(detected_titles, list)
                else [],

                "bibliography_titles_clean": bibliography_titles_clean,

                "bibliography_embedding_text": str(
                    b.get("bibliography_embedding_text", "")
                )[:2500],

                "ai_context_chunk": str(
                    b.get("ai_context_chunk", "")
                )[:3500]
            })

        if len(bibliography_pool) >= 5:
            break
    bibliography_status = {
        "searched_top_n": 20,
        "matched_exact_titles": len(bibliography_pool),
        "max_records": 5,
        "match_policy": "exact_title_only",
        "id_policy": "ID_Limpio is not used for bibliography matching"
    }
    # -----------------------------
    # 7. Advisor candidates
    # -----------------------------
    advisor_rows = []

    top_retrieved = retrieved.head(50).copy()

    for advisor, group in top_retrieved.groupby("asesor_limpio_v2"):
        if pd.isna(advisor) or str(advisor).strip() == "":
            continue

        years = sorted([
            int(y) for y in group["Año"].dropna().unique().tolist()
        ])

        clusters = []
        for c in group[cluster_col].dropna().unique().tolist():
            c = int(c)
            if c != -1:
                clusters.append(c)
                global_advisor = meta[
            meta["asesor_limpio_v2"].astype(str) == str(advisor)
        ]

        if main_cluster_id is not None:
            global_in_main_cluster = global_advisor[
                global_advisor[cluster_col] == main_cluster_id
            ]
        else:
            global_in_main_cluster = pd.DataFrame()

        global_years = sorted([
            int(y) for y in global_advisor["Año"].dropna().unique().tolist()
        ])

        cluster_years = sorted([
            int(y) for y in global_in_main_cluster["Año"].dropna().unique().tolist()
        ])

        advisor_rows.append({
            "advisor_name": str(advisor),
            "related_thesis_count": int(len(group)),
            "max_similarity": float(group["_similarity"].max()),
            "avg_similarity": float(group["_similarity"].mean()),
            "years": years,
            "last_year": max(years) if years else None,
            "programs": [
                str(x) for x in group["programa"].value_counts().head(5).index.tolist()
            ],
            "clusters": clusters,
            "representative_theses": [
                build_thesis_record(r, similarity=r["_similarity"], cluster_col=cluster_col)
                for _, r in group.sort_values("_similarity", ascending=False).head(5).iterrows()
            ],
                        "global_advised_count": int(len(global_advisor)),
            "global_main_cluster_count": int(len(global_in_main_cluster)),
            "global_last_year": max(global_years) if global_years else None,
            "main_cluster_last_year": max(cluster_years) if cluster_years else None,
        })

    advisor_candidates = sorted(
        advisor_rows,
        key=lambda x: (
            x["related_thesis_count"],
            x["max_similarity"],
            x["last_year"] or 0
        ),
        reverse=True
    )[:15]

    # -----------------------------
    # 8. Novelty / interdisciplinarity signals
    # -----------------------------
    retrieved_clusters = (
        retrieved[cluster_col]
        .value_counts(normalize=True)
        .head(8)
        .to_dict()
    )

    cluster_pull = []

    for cid, share in retrieved_clusters.items():
        cid = int(cid)

        if cid == -1:
            continue

        if cid in node_map:
            cluster_pull.append({
                "cluster_id": cid,
                "label": node_map[cid].get("label"),
                "macro_domain": node_map[cid].get("macro_domain"),
                "pull": float(share)
            })

    bridge_clusters = []

    for item in cluster_pull:
        if main_cluster_id is not None and item["cluster_id"] == main_cluster_id:
            continue

        if item["pull"] >= 0.06:
            bridge_clusters.append({
                "cluster_id": item["cluster_id"],
                "label": item["label"],
                "macro_domain": item["macro_domain"],
                "pull": item["pull"],
                "interpretation": "cluster secundario detectado en top50"
            })

    top50_cluster_diversity = int(len([
        c for c in retrieved[cluster_col].unique()
        if int(c) != -1
    ]))

    if len(cluster_pull) <= 2:
        interpretation_hint = "zona_central"
    elif len(cluster_pull) <= 5:
        interpretation_hint = "zona_interdisciplinaria"
    else:
        interpretation_hint = "zona_puente"

    novelty_signals = {
        "cluster_pull": cluster_pull,
        "main_cluster_pull": float(retrieved_clusters.get(main_cluster_id, 0))
        if main_cluster_id is not None
        else None,
        "top50_cluster_diversity": top50_cluster_diversity,
        "interpretation_hint": interpretation_hint
    }
    # -----------------------------
    # 9. Context final
    # -----------------------------
    context = {
        "query_embedding_info": {
            "model": EMBEDDING_MODEL_NAME,
            "dimensions": EMBEDDING_DIMENSIONS,
            "stored_in_response": False
        },

        "user_project": {
            "title": user_input.get("title", ""),
            "keywords": user_input.get("keywords", []),
            "objectives": bloom["objectives"],
            "program": user_input.get("program", ""),
            "degree": user_input.get("degree", ""),
            "study_period": user_input.get("study_period", {
            "applies": False,
            "start_year": None,
            "end_year": None,
            "label": "No aplica"
            })
        },

        "semantic_position": {
            "main_cluster": main_cluster,
            "neighbor_clusters": neighbor_clusters,
            "program_distribution_top50": program_distribution,
            "degree_distribution_top50": degree_distribution,
            "area_distribution_top50": area_distribution
        },

        "keywords_detected": keywords_detected,

        "temporal_patterns": temporal_patterns,

        "similar_theses": {
            "top_50": top_50,
            "top_10_candidates": top_10,
            "top_5_raw": top_5
        },

        "bloom": bloom,

        "bibliography_pool": bibliography_pool,

        "bibliography_status": bibliography_status,

        "advisor_candidates": advisor_candidates,

        "novelty_signals": novelty_signals,

        "bridge_clusters": bridge_clusters
    }

    return json_safe(context)

# ============================================================
# CONTEXTO COMPRIMIDO PARA LLM
# ============================================================

def build_context_for_llm(context, max_titles=10, max_advisors=5, max_bib_sources=5):
    """
    Construye un contexto compacto para llamadas de IA.
    No incluye embeddings, textos bibliográficos largos ni top_50 completo.
    """

    user_project = context.get("user_project", {})
    semantic_position = context.get("semantic_position", {})
    main_cluster = semantic_position.get("main_cluster", {})

    top_10 = context.get("similar_theses", {}).get("top_10_candidates", [])[:max_titles]

    top_10_compact = [
        {
            "title": t.get("title"),
            "year": t.get("year"),
            "program": t.get("program"),
            "degree": t.get("degree"),
            "area": t.get("area"),
            "cluster_id": t.get("cluster_id"),
            "similarity": round(float(t.get("embedding_similarity", 0)), 4)
            if t.get("embedding_similarity") is not None
            else None
        }
        for t in top_10
    ]

    keywords_compact = [
        k.get("keyword")
        for k in context.get("keywords_detected", [])[:18]
        if k.get("keyword")
    ]

    advisor_evidence = []

    for a in context.get("advisor_candidates", [])[:max_advisors]:
        advisor_evidence.append({
            "advisor_name": a.get("advisor_name"),
            "related_thesis_count_top50": a.get("related_thesis_count"),
            "global_advised_count_sample": a.get("global_advised_count"),
            "global_main_cluster_count_sample": a.get("global_main_cluster_count"),
            "last_year": a.get("last_year"),
            "main_cluster_last_year": a.get("main_cluster_last_year"),
            "programs": a.get("programs", []),
            "representative_titles": [
                r.get("title")
                for r in a.get("representative_theses", [])[:3]
            ]
        })

    bibliography_summaries = []

    for b in context.get("bibliography_pool", [])[:max_bib_sources]:
        bibliography_summaries.append({
            "source_thesis_title": b.get("source_thesis_title"),
            "source_similarity": round(float(b.get("source_similarity", 0)), 4)
            if b.get("source_similarity") is not None
            else None,
            "bibliography_doc_number": b.get("bibliography_doc_number"),
            "match_type": b.get("match_type"),
            "bibliography_thesis_title": b.get("bibliography_thesis_title"),
            "bibliography_year": b.get("bibliography_year"),
            "bibliography_program": b.get("bibliography_program"),
            "titles": b.get("bibliography_titles_clean", [])[:15]
        })

    return {
        "user_project": user_project,

        "semantic_position": {
            "main_cluster": {
                "id": main_cluster.get("id"),
                "label": main_cluster.get("label"),
                "macro_domain": main_cluster.get("macro_domain"),
                "main_area": main_cluster.get("main_area")
            },
            "neighbor_clusters": semantic_position.get("neighbor_clusters", []),
            "program_distribution_top50": semantic_position.get("program_distribution_top50", {}),
            "degree_distribution_top50": semantic_position.get("degree_distribution_top50", {}),
            "area_distribution_top50": semantic_position.get("area_distribution_top50", {})
        },

        "keywords_detected": keywords_compact,

        "temporal_patterns": context.get("temporal_patterns", {}),

        "top_similar_theses": top_10_compact,

        "bloom": context.get("bloom", {}),

        "advisor_evidence": advisor_evidence,

        "bibliography_status": context.get("bibliography_status", {}),

        "bibliography_summaries": bibliography_summaries,

        "novelty_signals": context.get("novelty_signals", {}),

        "bridge_clusters": context.get("bridge_clusters", [])
    }

def print_context_summary(context):
    """
    Imprime un resumen legible del thesis_context completo.
    """
def print_context_summary(context):
    sections = [
        ("USER PROJECT", context.get("user_project", {})),
        ("QUERY EMBEDDING INFO", context.get("query_embedding_info", {})),
        ("SEMANTIC POSITION", context.get("semantic_position", {})),
        ("KEYWORDS DETECTED", context.get("keywords_detected", [])),
        ("TEMPORAL PATTERNS", context.get("temporal_patterns", {})),
        ("BRIDGE CLUSTERS", context.get("bridge_clusters", [])),
        ("TOP 10 SIMILAR THESES", context.get("similar_theses", {}).get("top_10_candidates", [])),
        ("BLOOM", context.get("bloom", {})),
        ("BIBLIOGRAPHY STATUS", context.get("bibliography_status", {})),
        ("BIBLIOGRAPHY POOL", context.get("bibliography_pool", [])),
        ("ADVISOR CANDIDATES", context.get("advisor_candidates", [])[:8]),
        ("NOVELTY SIGNALS", context.get("novelty_signals", {})),
        ("CONTEXT FOR LLM", context.get("context_for_llm", {})),
    ]

    for title, payload in sections:
        print("\n" + "=" * 90)
        print(title)
        print("=" * 90)
        print(json.dumps(payload, ensure_ascii=False, indent=2))


# ============================================================
# INPUT DEL LABORATORIO
# ============================================================

def load_lab_input():
    """
    Lee el input del usuario generado por FastAPI / lab_orchestrator.

    Prioridad:
    1. input.json
    2. lab_input.json
    3. fallback de prueba local
    """
    candidates = [
        Path("input.json"),
        Path("lab_input.json"),
    ]

    for path in candidates:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return {
                "title": data.get("title", ""),
                "keywords": data.get("keywords", []),
                "objectives": data.get("objectives", []),
                "program": data.get("program", ""),
                "degree": data.get("degree", ""),
                "plantel": data.get("plantel", ""),
                "study_period": data.get("study_period", {
                    "applies": False,
                    "start_year": None,
                    "end_year": None,
                    "label": "No aplica"
                }),
            }

    print("AVISO: No encontré input.json ni lab_input.json. Usando input de prueba.")

    return {
        "title": "Analisis del sistema bancario de Mexico y China 1850-2009",
        "keywords": [
            "México",
            "China",
            "banco",
            "sistema bancario",
            "economía"
        ],
        "objectives": [
            "Analizar las diferencias entre ambos sistemas bancarios",
            "Reconocer diferencias en los procesos históricos",
            "Sugerir mejoras para el sistema bancario mexicano"
        ],
        "program": "Economía",
        "degree": "Licenciatura",
        "plantel": "Facultad de Economía",
        "study_period": {
            "applies": True,
            "start_year": 1850,
            "end_year": 2009,
            "label": "1850-2009"
        },
    }


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    print("Cargando archivos...")

    meta = pd.read_parquet(META_PATH)
    X = np.load(EMBEDDINGS_PATH)
    nodes = pd.read_parquet(NODES_PATH)
    mutual_edges = pd.read_parquet(EDGES_PATH)

    print("meta:", meta.shape)
    print("X:", X.shape)
    print("nodes:", nodes.shape)
    print("edges:", mutual_edges.shape)
    print("bibliography: carga bajo demanda")

    user_input = load_lab_input()

    query_vector = load_query_vector(QUERY_VECTOR_PATH)

    context = build_thesis_context(
        user_input=user_input,
        query_vector=query_vector,
        meta=meta,
        X=X,
        nodes=nodes,
        edges=mutual_edges,
        bibliography_path=BIBLIOGRAPHY_PATH,
        cluster_col=CLUSTER_COL,
        top_k=50,
    )

    context_for_llm = build_context_for_llm(context)
    context["context_for_llm"] = context_for_llm

    with open("thesis_context_example.json", "w", encoding="utf-8") as f:
        json.dump(context, f, ensure_ascii=False, indent=2)

    with open("context_minimal.json", "w", encoding="utf-8") as f:
        json.dump(context_for_llm, f, ensure_ascii=False, indent=2)

    print("\nGuardado thesis_context_example.json")
    print("Guardado context_minimal.json")

    print_context_summary(context)