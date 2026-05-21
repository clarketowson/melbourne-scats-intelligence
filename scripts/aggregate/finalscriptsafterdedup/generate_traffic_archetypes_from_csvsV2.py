# generate_traffic_archetypes_from_csvsV2.py

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
OUT = ROOT / "traffic_archetypes_v2"
OUT.mkdir(parents=True, exist_ok=True)

SITE_TOTALS = ROOT / "site_intelligence" / "site_rankings.csv"
SITE_MONTH = ROOT / "site_month_totals.csv"
MAP_DATA = ROOT / "all_scats_sites_map_data_audit.csv"

ARCHETYPE_COLOURS = {
    "Metropolitan Backbone": "#7b1fa2",
    "Reliable Exposure Corridor": "#1565c0",
    "High-Volume Volatile Corridor": "#d32f2f",
    "Rising Growth Corridor": "#2e7d32",
    "Event / Disruption Sensitive Site": "#f57c00",
    "Emerging Local Growth Site": "#43a047",
    "Stable Low-Volume Local Site": "#607d8b",
    "Unstable / Variable Site": "#c2185b",
    "Mixed Urban Traffic Site": "#8d6e63",
}

print("=" * 100)
print("MELBOURNE SCATS TRAFFIC ARCHETYPES FROM EXISTING CSVs V2")
print("=" * 100)

site = pd.read_csv(SITE_TOTALS)
month = pd.read_csv(SITE_MONTH)
maps = pd.read_csv(MAP_DATA)

site = site.rename(columns={"scats_site": "site_id"})
month = month.rename(columns={"scats_site": "site_id", "month_site_volume": "month_volume"})

site["site_id"] = site["site_id"].astype(str)
month["site_id"] = month["site_id"].astype(str)
maps["site_id"] = maps["site_id"].astype(str)

month = month[pd.to_numeric(month["site_id"], errors="coerce").notna()].copy()
month["month_volume"] = pd.to_numeric(month["month_volume"], errors="coerce")
month = month.dropna(subset=["month_volume"])

monthly_features = (
    month.groupby("site_id")
    .agg(
        months_present=("month_label", "nunique"),
        monthly_total=("month_volume", "sum"),
        monthly_mean=("month_volume", "mean"),
        monthly_median=("month_volume", "median"),
        monthly_std=("month_volume", "std"),
        monthly_max=("month_volume", "max"),
        monthly_min=("month_volume", "min"),
    )
    .reset_index()
)

monthly_features["monthly_cv"] = monthly_features["monthly_std"] / monthly_features["monthly_mean"]
monthly_features["max_to_mean_ratio"] = monthly_features["monthly_max"] / monthly_features["monthly_mean"]

month_sorted = month.sort_values(["site_id", "month_start"]).copy()

growth_rows = []
for sid, g in month_sorted.groupby("site_id"):
    g = g.sort_values("month_start")
    first = g.head(12)["month_volume"].mean()
    last = g.tail(12)["month_volume"].mean()
    growth_abs = last - first
    growth_pct = (growth_abs / first * 100) if first and first > 0 else np.nan
    growth_rows.append({
        "site_id": sid,
        "first12_avg": first,
        "last12_avg": last,
        "growth_abs": growth_abs,
        "growth_pct": growth_pct,
    })

growth = pd.DataFrame(growth_rows)

master = site.merge(monthly_features, on="site_id", how="left")
master = master.merge(growth, on="site_id", how="left")

map_cols = [
    "site_id", "friendly_name", "site_name", "latitude", "longitude",
    "traffic_band", "percentile_rank", "volume_ratio", "google_maps_url"
]
map_cols = [c for c in map_cols if c in maps.columns]
master = master.merge(maps[map_cols], on="site_id", how="left")

def pct_rank(s, ascending=True):
    return s.rank(pct=True, ascending=ascending).fillna(0)

master["scale_score"] = pct_rank(master["total_volume"], ascending=True) * 100
master["stability_score"] = (1 - pct_rank(master["monthly_cv"], ascending=True)) * 100
master["volatility_score"] = pct_rank(master["monthly_cv"], ascending=True) * 100
master["growth_score"] = pct_rank(master["growth_pct"], ascending=True) * 100
master["spike_score"] = pct_rank(master["max_to_mean_ratio"], ascending=True) * 100

def classify(row):
    scale = row["scale_score"]
    stability = row["stability_score"]
    volatility = row["volatility_score"]
    growth = row["growth_score"]
    spike = row["spike_score"]

    if scale >= 90 and stability >= 65:
        return "Metropolitan Backbone"
    if scale >= 85 and volatility >= 70:
        return "High-Volume Volatile Corridor"
    if growth >= 85 and scale >= 60:
        return "Rising Growth Corridor"
    if volatility >= 85 and spike >= 75:
        return "Event / Disruption Sensitive Site"
    if scale >= 75 and stability >= 80:
        return "Reliable Exposure Corridor"
    if scale < 40 and growth >= 80:
        return "Emerging Local Growth Site"
    if scale < 35 and stability >= 70:
        return "Stable Low-Volume Local Site"
    if volatility >= 75:
        return "Unstable / Variable Site"
    return "Mixed Urban Traffic Site"

master["traffic_archetype"] = master.apply(classify, axis=1)
master["archetype_colour"] = master["traffic_archetype"].map(ARCHETYPE_COLOURS)

master["ooh_exposure_score"] = (
    master["scale_score"] * 0.55 +
    master["stability_score"] * 0.25 +
    master["growth_score"] * 0.20
)

master["research_interest_score"] = (
    master["volatility_score"] * 0.35 +
    master["growth_score"] * 0.30 +
    master["scale_score"] * 0.20 +
    master["spike_score"] * 0.15
)

master["strategic_importance_score"] = (
    master["scale_score"] * 0.45 +
    master["stability_score"] * 0.20 +
    master["growth_score"] * 0.20 +
    master["volatility_score"] * 0.15
)

master = master.sort_values("strategic_importance_score", ascending=False)

summary = (
    master.groupby("traffic_archetype")
    .agg(
        sites=("site_id", "count"),
        total_volume=("total_volume", "sum"),
        avg_total_volume=("total_volume", "mean"),
        avg_scale_score=("scale_score", "mean"),
        avg_stability_score=("stability_score", "mean"),
        avg_volatility_score=("volatility_score", "mean"),
        avg_growth_score=("growth_score", "mean"),
        avg_ooh_exposure_score=("ooh_exposure_score", "mean"),
        avg_research_interest_score=("research_interest_score", "mean"),
    )
    .reset_index()
)

summary["traffic_share_pct"] = summary["total_volume"] / summary["total_volume"].sum() * 100
summary["colour"] = summary["traffic_archetype"].map(ARCHETYPE_COLOURS)

master.to_csv(OUT / "traffic_archetypes_master_v2.csv", index=False)
summary.to_csv(OUT / "traffic_archetype_summary_v2.csv", index=False)

master.sort_values("ooh_exposure_score", ascending=False).head(100).to_csv(
    OUT / "top100_ooh_exposure_archetype_sites_v2.csv", index=False
)

master.sort_values("research_interest_score", ascending=False).head(100).to_csv(
    OUT / "top100_research_interest_archetype_sites_v2.csv", index=False
)

def savefig(name):
    plt.tight_layout()
    path = OUT / name
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")

def add_archetype_legend():
    handles = [
        Patch(facecolor=colour, label=name)
        for name, colour in ARCHETYPE_COLOURS.items()
    ]
    plt.legend(
        handles=handles,
        title="Traffic Archetype",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=9,
        title_fontsize=10,
        frameon=True,
    )

# 1. Site counts by archetype
plot = summary.sort_values("sites", ascending=True)

plt.figure(figsize=(15, 9))
plt.barh(plot["traffic_archetype"], plot["sites"], color=plot["colour"])
plt.title("Melbourne SCATS Traffic Archetypes: Number of Sites", fontsize=20, weight="bold", pad=18)
plt.xlabel("SCATS sites")
for i, v in enumerate(plot["sites"]):
    plt.text(v, i, f" {int(v):,}", va="center", fontsize=10, weight="bold")
savefig("traffic_archetypes_site_counts_v2.png")

# 2. Traffic share by archetype
plot = summary.sort_values("traffic_share_pct", ascending=True)

plt.figure(figsize=(15, 9))
plt.barh(plot["traffic_archetype"], plot["traffic_share_pct"], color=plot["colour"])
plt.title("Traffic Share by Melbourne SCATS Archetype", fontsize=20, weight="bold", pad=18)
plt.xlabel("Share of total analysed traffic volume (%)")
for i, v in enumerate(plot["traffic_share_pct"]):
    plt.text(v, i, f" {v:.1f}%", va="center", fontsize=10, weight="bold")
savefig("traffic_archetypes_traffic_share_v2.png")

# 3. Scale vs volatility scatter
plt.figure(figsize=(15, 10))
for archetype, g in master.groupby("traffic_archetype"):
    plt.scatter(
        g["scale_score"],
        g["volatility_score"],
        s=22,
        alpha=0.70,
        color=ARCHETYPE_COLOURS.get(archetype, "#999999"),
        label=archetype,
    )
plt.title("Melbourne SCATS Sites: Scale vs Volatility by Traffic Archetype", fontsize=20, weight="bold", pad=18)
plt.xlabel("Scale score: cumulative traffic importance")
plt.ylabel("Volatility score: month-to-month variability")
plt.grid(alpha=0.25)
add_archetype_legend()
savefig("traffic_archetypes_scale_vs_volatility_v2.png")

# 4. Scale vs growth scatter
plt.figure(figsize=(15, 10))
for archetype, g in master.groupby("traffic_archetype"):
    plt.scatter(
        g["scale_score"],
        g["growth_score"],
        s=22,
        alpha=0.70,
        color=ARCHETYPE_COLOURS.get(archetype, "#999999"),
        label=archetype,
    )
plt.title("Melbourne SCATS Sites: Scale vs Growth by Traffic Archetype", fontsize=20, weight="bold", pad=18)
plt.xlabel("Scale score")
plt.ylabel("Growth score")
plt.grid(alpha=0.25)
add_archetype_legend()
savefig("traffic_archetypes_scale_vs_growth_v2.png")

# 5. Top 25 OOH exposure sites
top = master.sort_values("ooh_exposure_score", ascending=False).head(25).copy()
top["label"] = top["site_id"] + " — " + top["site_name"].fillna(top["friendly_name"]).fillna("")
top = top.sort_values("ooh_exposure_score")

plt.figure(figsize=(16, 11))
plt.barh(top["label"], top["ooh_exposure_score"], color=top["archetype_colour"])
plt.title("Top 25 SCATS Sites by OOH Exposure Archetype Score", fontsize=20, weight="bold", pad=18)
plt.xlabel("OOH exposure score")
for i, v in enumerate(top["ooh_exposure_score"]):
    plt.text(v, i, f" {v:.1f}", va="center", fontsize=9, weight="bold")
add_archetype_legend()
savefig("top25_ooh_exposure_archetype_sites_v2.png")

# 6. Top 25 research interest sites
top = master.sort_values("research_interest_score", ascending=False).head(25).copy()
top["label"] = top["site_id"] + " — " + top["site_name"].fillna(top["friendly_name"]).fillna("")
top = top.sort_values("research_interest_score")

plt.figure(figsize=(16, 11))
plt.barh(top["label"], top["research_interest_score"], color=top["archetype_colour"])
plt.title("Top 25 SCATS Sites by Research Interest Score", fontsize=20, weight="bold", pad=18)
plt.xlabel("Research interest score")
for i, v in enumerate(top["research_interest_score"]):
    plt.text(v, i, f" {v:.1f}", va="center", fontsize=9, weight="bold")
add_archetype_legend()
savefig("top25_research_interest_sites_v2.png")

# 7. Behavioural score heatmap
heat_cols = [
    "avg_scale_score",
    "avg_stability_score",
    "avg_volatility_score",
    "avg_growth_score",
    "avg_ooh_exposure_score",
    "avg_research_interest_score",
]

heat = summary.set_index("traffic_archetype")[heat_cols]
heat = heat.sort_values("avg_ooh_exposure_score", ascending=False)

plt.figure(figsize=(15, 8))
plt.imshow(heat.values, aspect="auto", cmap="viridis")
plt.title("Traffic Archetype Behavioural Score Heatmap", fontsize=20, weight="bold", pad=18)
plt.yticks(range(len(heat.index)), heat.index)
plt.xticks(
    range(len(heat_cols)),
    ["Scale", "Stability", "Volatility", "Growth", "OOH Exposure", "Research Interest"],
    rotation=35,
    ha="right",
)
cbar = plt.colorbar()
cbar.set_label("Average score")
savefig("traffic_archetype_score_heatmap_v2.png")

# 8. Strategic importance top 25
top = master.sort_values("strategic_importance_score", ascending=False).head(25).copy()
top["label"] = top["site_id"] + " — " + top["site_name"].fillna(top["friendly_name"]).fillna("")
top = top.sort_values("strategic_importance_score")

plt.figure(figsize=(16, 11))
plt.barh(top["label"], top["strategic_importance_score"], color=top["archetype_colour"])
plt.title("Top 25 SCATS Sites by Strategic Importance Score", fontsize=20, weight="bold", pad=18)
plt.xlabel("Strategic importance score")
for i, v in enumerate(top["strategic_importance_score"]):
    plt.text(v, i, f" {v:.1f}", va="center", fontsize=9, weight="bold")
add_archetype_legend()
savefig("top25_strategic_importance_sites_v2.png")

# 9. Archetype colour legend chart
legend_df = pd.DataFrame([
    {"traffic_archetype": k, "colour": v}
    for k, v in ARCHETYPE_COLOURS.items()
])

plt.figure(figsize=(12, 6))
plt.barh(legend_df["traffic_archetype"], [1] * len(legend_df), color=legend_df["colour"])
plt.title("Traffic Archetype Colour Key", fontsize=18, weight="bold", pad=16)
plt.xticks([])
plt.xlabel("")
for i, row in legend_df.iterrows():
    plt.text(0.03, i, row["traffic_archetype"], va="center", color="white", fontsize=10, weight="bold")
savefig("traffic_archetype_colour_key_v2.png")

json_summary = {
    "input_files": {
        "site_rankings": str(SITE_TOTALS),
        "site_month_totals": str(SITE_MONTH),
        "map_data": str(MAP_DATA),
    },
    "outputs": {
        "master": str(OUT / "traffic_archetypes_master_v2.csv"),
        "summary": str(OUT / "traffic_archetype_summary_v2.csv"),
    },
    "site_count": int(master["site_id"].nunique()),
    "archetype_count": int(master["traffic_archetype"].nunique()),
    "archetype_colours": ARCHETYPE_COLOURS,
    "archetypes": summary.to_dict(orient="records"),
    "method_note": (
        "CSV-only derived archetype model using site-level total volume, monthly volatility, "
        "first-12-vs-last-12 growth, stability, spike behaviour, mapped site metadata, and "
        "consistent archetype colour coding. This does not re-query DuckDB."
    ),
}

with open(OUT / "traffic_archetypes_summary_v2.json", "w", encoding="utf-8") as f:
    json.dump(json_summary, f, indent=2)

print("\nDONE")
print(f"Output directory: {OUT}")
print(f"Master CSV:       {OUT / 'traffic_archetypes_master_v2.csv'}")
print(f"Summary CSV:      {OUT / 'traffic_archetype_summary_v2.csv'}")
print(f"JSON summary:     {OUT / 'traffic_archetypes_summary_v2.json'}")