from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


NODES_PATH = Path("cluster_nodes_final_50k.parquet")
SUMMARY_PATH = Path("cluster_summary_50k.parquet")
OUT_DIR = Path("outputs")
OUT_PNG = OUT_DIR / "umap_clusters_50k.png"
OUT_HTML = OUT_DIR / "umap_clusters_50k.html"

OUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading nodes...")
df = pd.read_parquet(NODES_PATH)

required = {"x", "y", "cluster_id", "thesis_id"}
missing = required - set(df.columns)
if missing:
    raise RuntimeError(f"Faltan columnas necesarias: {missing}")

print("Rows:", len(df))
print("Columns:", df.columns.tolist())

n_clusters = df.loc[df["cluster_id"] != -1, "cluster_id"].nunique()
noise = int((df["cluster_id"] == -1).sum())

print("Clusters:", n_clusters)
print("Noise:", noise)
print("Noise share:", round(noise / len(df), 4))

# -----------------------------
# PNG estático
# -----------------------------
print("Building PNG...")

plot_df = df.copy()
plot_df["cluster_id"] = plot_df["cluster_id"].astype(int)

clusters = sorted([c for c in plot_df["cluster_id"].unique() if c != -1])
cluster_to_color_idx = {c: i for i, c in enumerate(clusters)}

fig, ax = plt.subplots(figsize=(14, 10), dpi=180)

# Noise primero, gris tenue.
noise_df = plot_df[plot_df["cluster_id"] == -1]
if len(noise_df):
    ax.scatter(
        noise_df["x"],
        noise_df["y"],
        s=1.8,
        c="#d8d5ce",
        alpha=0.28,
        linewidths=0,
        label="Ruido / no asignado",
    )

# Clusters.
clustered = plot_df[plot_df["cluster_id"] != -1]
colors = clustered["cluster_id"].map(cluster_to_color_idx).to_numpy()

sc = ax.scatter(
    clustered["x"],
    clustered["y"],
    c=colors,
    cmap="tab20",
    s=2.2,
    alpha=0.72,
    linewidths=0,
)

ax.set_title("UMAP 50k · clusters semánticos", fontsize=16)
ax.set_xticks([])
ax.set_yticks([])
ax.set_frame_on(False)

caption = f"{len(df):,} tesis · {n_clusters} clusters · {noise:,} sin asignar"
ax.text(
    0.01,
    0.01,
    caption,
    transform=ax.transAxes,
    fontsize=9,
    alpha=0.65,
)

plt.tight_layout()
fig.savefig(OUT_PNG, bbox_inches="tight")
plt.close(fig)

print("Saved PNG:", OUT_PNG)

# -----------------------------
# HTML interactivo Plotly
# -----------------------------
print("Building interactive HTML...")

try:
    import plotly.express as px

    html_df = df.copy()

    def safe_col(col):
        return col if col in html_df.columns else None

    title_col = safe_col("titulo_limpio") or safe_col("título")
    program_col = safe_col("programa")
    year_col = safe_col("Año")
    area_col = safe_col("area")
    level_col = safe_col("level") or safe_col("nivel_estandar")
    plantel_col = safe_col("plantel") or safe_col("plantel_limpio_final")

    html_df["cluster_label"] = html_df["cluster_id"].apply(
        lambda x: "RUIDO / NO ASIGNADO" if int(x) == -1 else f"CLUSTER {int(x)}"
    )

    hover_cols = [
        c for c in [
            "thesis_id",
            title_col,
            "cluster_id",
            "cluster_strength",
            program_col,
            year_col,
            area_col,
            level_col,
            plantel_col,
        ]
        if c is not None and c in html_df.columns
    ]

    fig = px.scatter(
        html_df,
        x="x",
        y="y",
        color="cluster_label",
        hover_data=hover_cols,
        render_mode="webgl",
        title="UMAP 50k · clusters semánticos",
        opacity=0.78,
    )

    fig.update_traces(marker=dict(size=4, line=dict(width=0)))
    fig.update_layout(
        width=1400,
        height=900,
        plot_bgcolor="#f7f5ef",
        paper_bgcolor="#f7f5ef",
        font=dict(family="Montserrat, Arial, sans-serif", size=11),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        legend=dict(
            title="Cluster",
            itemsizing="constant",
            font=dict(size=9),
        ),
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.write_html(OUT_HTML, include_plotlyjs="cdn")
    print("Saved HTML:", OUT_HTML)

except ImportError:
    print("Plotly no está instalado. Instala con: pip install plotly")
    print("Solo se generó PNG.")

print("Done.")
