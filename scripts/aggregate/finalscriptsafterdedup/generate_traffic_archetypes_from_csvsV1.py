# generate_traffic_archetypes_from_csvsV1.py

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
OUT = ROOT / "traffic_archetypes"
OUT.mkdir(parents=True, exist_ok=True)

SITE_TOTALS = ROOT / "site_intelligence" / "site_rankings.csv"
SITE_MONTH = ROOT / "site_month_totals.csv"
MAP_DATA = ROOT / "all_scats_sites_map_data_audit.csv"

print("=" * 100)
print("MELBOURNE SCATS TRAFFIC ARCHETYPES FROM EXISTING CSVs V1")
print("=" * 100)

site = pd.read_csv(SITE_TOTALS)
month = pd.read_csv(SITE_MONTH)
maps = pd.read_csv(MAP_DATA)

# -----------------------------
# Normalise column names
# -----------------------------

site = site.rename(columns={
    "scats_site": "site_id",
    "total_volume": "total_volume"
})

month = month.rename(columns={
    "scats_site": "site_id",
    "month_site_volume": "month_volume"
})

maps = maps.rename(columns={
    "site_id": "site_id",
    "friendly_name": "friendly_name",
    "site_name": "site_name",
    "latitude": "latitude",
    "longitude": "longitude",
    "traffic_band": "traffic_band"
})

site["site_id"] = site["site_id"].astype(str)
month["site_id"] = month["site_id"].astype(str)
maps["site_id"] = maps["site_id"].astype(str)

# remove non-data summary rows if present
month = month[pd.to_numeric(month["site_id"], errors="coerce").notna()].copy()
month["month_volume"] = pd.to_numeric(month["month_volume"], errors="coerce")
month = month.dropna(subset=["month_volume"])

# -----------------------------
# Monthly behaviour features
# -----------------------------

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

# first 12 vs last 12 growth
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
        "growth_pct": growth_pct
    })

growth = pd.DataFrame(growth_rows)

# -----------------------------
# Merge master feature table
# -----------------------------

master = site.merge(monthly_features, on="site_id", how="left")
master = master.merge(growth, on="site_id", how="left")

map_cols = [
    "site_id", "friendly_name", "site_name", "latitude", "longitude",
    "traffic_band", "percentile_rank", "volume_ratio", "google_maps_url"
]
map_cols = [c for c in map_cols if c in maps.columns]

master = master.merge(maps[map_cols], on="site_id", how="left")

# -----------------------------
# Scoring helpers
# -----------------------------

def pct_rank(s, ascending=True):
    return s.rank(pct=True, ascending=ascending).fillna(0)

master["scale_score"] = pct_rank(master["total_volume"], ascending=True) * 100
master["stability_score"] = (1 - pct_rank(master["monthly_cv"], ascending=True)) * 100
master["volatility_score"] = pct_rank(master["monthly_cv"], ascending=True) * 100
master["growth_score"] = pct_rank(master["growth_pct"], ascending=True) * 100
master["spike_score"] = pct_rank(master["max_to_mean_ratio"], ascending=True) * 100

# -----------------------------
# Archetype classification
# -----------------------------

def classify(row):
    scale = row.get("scale_score", 0)
    stability = row.get("stability_score", 0)
    volatility = row.get("volatility_score", 0)
    growth = row.get("growth_score", 0)
    spike = row.get("spike_score", 0)

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

# -----------------------------
# Opportunity / intelligence scores
# -----------------------------

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

# -----------------------------
# Save core CSVs
# -----------------------------

master.to_csv(OUT / "traffic_archetypes_master.csv", index=False)

master.sort_values("ooh_exposure_score", ascending=False).head(100).to_csv(
    OUT / "top100_ooh_exposure_archetype_sites.csv", index=False
)

master.sort_values("research_interest_score", ascending=False).head(100).to_csv(
    OUT / "top100_research_interest_archetype_sites.csv", index=False
)

master.sort_values("volatility_score", ascending=False).head(100).to_csv(
    OUT / "top100_most_volatile_sites.csv", index=False
)

master.sort_values("stability_score", ascending=False).head(100).to_csv(
    OUT / "top100_most_stable_sites.csv", index=False
)

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
    .sort_values("total_volume", ascending=False)
)

summary["traffic_share_pct"] = summary["total_volume"] / summary["total_volume"].sum() * 100
summary.to_csv(OUT / "traffic_archetype_summary.csv", index=False)

# -----------------------------
# Chart helper
# -----------------------------

def savefig(name):
    plt.tight_layout()
    path = OUT / name
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")

# -----------------------------
# Chart 1: Archetype site counts
# -----------------------------

plot = summary.sort_values("sites", ascending=True)

plt.figure(figsize=(14, 9))
plt.barh(plot["traffic_archetype"], plot["sites"])
plt.title("Melbourne SCATS Traffic Archetypes: Number of Sites", fontsize=18, weight="bold", pad=16)
plt.xlabel("SCATS sites")
for i, v in enumerate(plot["sites"]):
    plt.text(v, i, f" {int(v):,}", va="center", fontsize=9)
savefig("traffic_archetypes_site_counts.png")

# -----------------------------
# Chart 2: Archetype traffic share
# -----------------------------

plot = summary.sort_values("traffic_share_pct", ascending=True)

plt.figure(figsize=(14, 9))
plt.barh(plot["traffic_archetype"], plot["traffic_share_pct"])
plt.title("Traffic Share by Melbourne SCATS Archetype", fontsize=18, weight="bold", pad=16)
plt.xlabel("Share of total analysed traffic volume (%)")
for i, v in enumerate(plot["traffic_share_pct"]):
    plt.text(v, i, f" {v:.1f}%", va="center", fontsize=9)
savefig("traffic_archetypes_traffic_share.png")

# -----------------------------
# Chart 3: Scale vs volatility scatter
# -----------------------------

plt.figure(figsize=(13, 9))
plt.scatter(master["scale_score"], master["volatility_score"], s=16, alpha=0.65)
plt.title("Melbourne SCATS Sites: Scale vs Volatility", fontsize=18, weight="bold", pad=16)
plt.xlabel("Scale score: cumulative traffic importance")
plt.ylabel("Volatility score: month-to-month variability")
plt.grid(alpha=0.25)
savefig("traffic_archetypes_scale_vs_volatility.png")

# -----------------------------
# Chart 4: Growth vs scale scatter
# -----------------------------

plt.figure(figsize=(13, 9))
plt.scatter(master["scale_score"], master["growth_score"], s=16, alpha=0.65)
plt.title("Melbourne SCATS Sites: Scale vs Growth", fontsize=18, weight="bold", pad=16)
plt.xlabel("Scale score")
plt.ylabel("Growth score")
plt.grid(alpha=0.25)
savefig("traffic_archetypes_scale_vs_growth.png")

# -----------------------------
# Chart 5: Top 25 OOH exposure sites
# -----------------------------

top = master.sort_values("ooh_exposure_score", ascending=False).head(25).copy()
top["label"] = top["site_id"] + " — " + top.get("site_name", "").fillna(top.get("friendly_name", "").fillna(""))
top = top.sort_values("ooh_exposure_score")

plt.figure(figsize=(15, 11))
plt.barh(top["label"], top["ooh_exposure_score"])
plt.title("Top 25 SCATS Sites by OOH Exposure Archetype Score", fontsize=18, weight="bold", pad=16)
plt.xlabel("OOH exposure score")
savefig("top25_ooh_exposure_archetype_sites.png")

# -----------------------------
# Chart 6: Top 25 research-interest sites
# -----------------------------

top = master.sort_values("research_interest_score", ascending=False).head(25).copy()
top["label"] = top["site_id"] + " — " + top.get("site_name", "").fillna(top.get("friendly_name", "").fillna(""))
top = top.sort_values("research_interest_score")

plt.figure(figsize=(15, 11))
plt.barh(top["label"], top["research_interest_score"])
plt.title("Top 25 SCATS Sites by Research Interest Score", fontsize=18, weight="bold", pad=16)
plt.xlabel("Research interest score")
savefig("top25_research_interest_sites.png")

# -----------------------------
# Chart 7: Archetype score heatmap
# -----------------------------

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

plt.figure(figsize=(14, 8))
plt.imshow(heat.values, aspect="auto")
plt.title("Traffic Archetype Behavioural Score Heatmap", fontsize=18, weight="bold", pad=16)
plt.yticks(range(len(heat.index)), heat.index)
plt.xticks(
    range(len(heat_cols)),
    [
        "Scale",
        "Stability",
        "Volatility",
        "Growth",
        "OOH Exposure",
        "Research Interest",
    ],
    rotation=35,
    ha="right"
)
cbar = plt.colorbar()
cbar.set_label("Average score")
savefig("traffic_archetype_score_heatmap.png")

# -----------------------------
# JSON summary
# -----------------------------

json_summary = {
    "input_files": {
        "site_rankings": str(SITE_TOTALS),
        "site_month_totals": str(SITE_MONTH),
        "map_data": str(MAP_DATA),
    },
    "outputs": {
        "master": str(OUT / "traffic_archetypes_master.csv"),
        "summary": str(OUT / "traffic_archetype_summary.csv"),
    },
    "site_count": int(master["site_id"].nunique()),
    "archetype_count": int(master["traffic_archetype"].nunique()),
    "archetypes": summary.to_dict(orient="records"),
    "method_note": (
        "CSV-only derived archetype model using site-level total volume, monthly volatility, "
        "first-12-vs-last-12 growth, stability, spike behaviour, and mapped site metadata. "
        "This does not re-query DuckDB."
    ),
}

with open(OUT / "traffic_archetypes_summary.json", "w", encoding="utf-8") as f:
    json.dump(json_summary, f, indent=2)

print("\nDONE")
print(f"Output directory: {OUT}")
print(f"Master CSV:       {OUT / 'traffic_archetypes_master.csv'}")
print(f"Summary CSV:      {OUT / 'traffic_archetype_summary.csv'}")
print(f"JSON summary:     {OUT / 'traffic_archetypes_summary.json'}")