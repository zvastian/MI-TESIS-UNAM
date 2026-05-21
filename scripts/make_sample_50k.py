import pandas as pd
import numpy as np
import pyarrow.parquet as pq
from pathlib import Path

BASE_PATH = Path("base_with_ids.parquet")
OUT_PATH = Path("sample_50k_final_15d.parquet")

N = 50_000
RANDOM_STATE = 42
rng = np.random.default_rng(RANDOM_STATE)

WANTED_COLS = [
    "thesis_id",
    "doc_number_url",
    "ID_Limpio",
    "ID_Aleph",
    "Año",
    "título",
    "titulo_limpio",
    "titulo_normalizado",
    "programa",
    "grado",
    "grado_norm",
    "nivel_estandar",
    "area",
    "plantel_final",
    "plantel_limpio_final",
    "plantel_estandarizado",
    "asesor_limpio",
    "asesor_limpio_v2",
    "asesores_limpios_v2",
    "autor_limpio_v2",
    "autor(es)",
    "link_extraido_regex",
    "palabras clave",
    "materia general",
]

# Leer schema sin cargar parquet completo
pf = pq.ParquetFile(BASE_PATH)
available = pf.schema.names

cols = [c for c in WANTED_COLS if c in available]

print("Columnas disponibles seleccionadas:")
for c in cols:
    print("-", c)

if "Año" not in cols:
    raise RuntimeError("No encontré columna 'Año'. Revisa nombres reales del parquet.")

if "thesis_id" not in cols:
    raise RuntimeError("No encontré columna 'thesis_id'. Asegúrate de usar base_with_ids.parquet.")

# Leer solo columnas útiles
df = pd.read_parquet(BASE_PATH, columns=cols, engine="pyarrow")

print("\nbase shape:", df.shape)

# Normalizar año
df["Año"] = pd.to_numeric(df["Año"], errors="coerce")

df["year_bucket"] = pd.cut(
    df["Año"],
    bins=[0, 1980, 1990, 2000, 2010, 2020, 2030],
    labels=[
        "antes_1980",
        "1981_1990",
        "1991_2000",
        "2001_2010",
        "2011_2020",
        "2021_2030",
    ],
)

# Crear columnas si faltan
for c in ["area", "nivel_estandar", "year_bucket"]:
    if c not in df.columns:
        df[c] = "desconocido"

df["area"] = df["area"].astype("string").fillna("desconocido")
df["nivel_estandar"] = df["nivel_estandar"].astype("string").fillna("desconocido")
df["year_bucket"] = df["year_bucket"].astype("string").fillna("desconocido")

df["_stratum"] = (
    df["area"].astype(str)
    + " | "
    + df["nivel_estandar"].astype(str)
    + " | "
    + df["year_bucket"].astype(str)
)

counts = df["_stratum"].value_counts()

# Calcular muestra proporcional por estrato
target_counts = (counts / len(df) * N).round().astype(int)
target_counts[target_counts < 1] = 1

chosen_indices = []

for stratum, n in target_counts.items():
    idx = df.index[df["_stratum"] == stratum].to_numpy()
    n = min(int(n), len(idx))

    if n > 0:
        chosen = rng.choice(idx, size=n, replace=False)
        chosen_indices.extend(chosen.tolist())

# Crear sample
sample = df.loc[chosen_indices]

# Ajustar exactamente a N
if len(sample) > N:
    sample = sample.sample(N, random_state=RANDOM_STATE)
elif len(sample) < N:
    remaining = df.drop(sample.index)
    extra = remaining.sample(N - len(sample), random_state=RANDOM_STATE)
    sample = pd.concat([sample, extra], ignore_index=False)

sample = sample.drop(columns=["_stratum"], errors="ignore")
sample = sample.reset_index(drop=True)

sample.to_parquet(OUT_PATH, index=False)

print("\nSAVED:", OUT_PATH)
print("shape:", sample.shape)
print("unique thesis_id:", sample["thesis_id"].nunique())

if "doc_number_url" in sample.columns:
    print("doc_number_url coverage:", sample["doc_number_url"].notna().mean())

print("\narea:")
print(sample["area"].value_counts(dropna=False).head(20))

print("\nnivel_estandar:")
print(sample["nivel_estandar"].value_counts(dropna=False).head(20))

print("\nyear_bucket:")
print(sample["year_bucket"].value_counts(dropna=False).sort_index())