# generate_traffic_archetypes_from_csvsV4.py

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
OUT = ROOT / "traffic_archetypes_v4"
OUT.mkdir(parents=True, exist_ok=True)

SITE_TOTALS = ROOT / "site_intelligence" / "site_rankings.csv"
SITE_MONTH = ROOT / "site_month_totals.csv"
MAP_DATA = ROOT / "all_scats_sites_map_data_audit.csv"

ARCHETYPE_COLOURS = {
    "Metropolitan Backbone": "#7b1fa2",
    "Reliable Exposure Corridor": "#1565c0",
    "Mature Urban Arterial": "#795548",
    "Balanced Metropolitan Site": "#8d6e63",
    "Secondary Connector Corridor": "#a1887f",
    "Rising Growth Corridor": "#2e7d32",
    "Emerging Local Growth Site": "#43a047",
    "High-Volume Volatile Corridor": "#d32f2f",
    "Event / Disruption Sensitive Site": "#f57c00",
    "Unstable / Variable Site": "#c2185b",
    "Stable Low-Volume Local Site": "#607d8b",
}

ARCHETYPE_ORDER = [
    "Metropolitan Backbone",
    "Reliable Exposure Corridor",
    "Mature Urban Arterial",
    "Balanced Metropolitan Site",
    "Secondary Connector Corridor",
    "Rising Growth Corridor",
    "Emerging Local Growth Site",
    "High-Volume Volatile Corridor",
    "Event / Disruption Sensitive Site",
    "Unstable / Variable Site",
    "Stable Low-Volume Local Site",
]

ARCHETYPE_PROFILES = {
    "Metropolitan Backbone": "Highest-scale, structurally important, stable high-volume corridors.",
    "Reliable Exposure Corridor": "High-volume and stable corridors with strong persistent exposure value.",
    "Mature Urban Arterial": "Large established roads with mature traffic demand and moderate change.",
    "Balanced Metropolitan Site": "Typical mixed urban traffic sites with no single extreme behaviour.",
    "Secondary Connector Corridor": "Mid-scale connector roads linking local and arterial traffic systems.",
    "Rising Growth Corridor": "High or mid-scale corridors showing strong long-term growth.",
    "Emerging Local Growth Site": "Lower-scale sites with unusually strong growth signals.",
    "High-Volume Volatile Corridor": "Major sites with both high volume and high month-to-month variability.",
    "Event / Disruption Sensitive Site": "Sites with strong spike behaviour and unusually high volatility.",
    "Unstable / Variable Site": "Sites with high variability but lower overall strategic scale.",
    "Stable Low-Volume Local Site": "Low-volume sites with stable, predictable local traffic patterns.",
}

def savefig(name):
    plt.tight_layout()
    path = OUT / name
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")

def subtitle(text, y=0.94):
    plt.figtext(0.5, y, text, ha="center", fontsize=11, color="#555555")

def add_present_legend(df):
    present = [a for a in ARCHETYPE_ORDER if a in set(df["traffic_archetype"].dropna())]
    handles = [Patch(facecolor=ARCHETYPE_COLOURS[a], label=a) for a in present]
    if handles:
        plt.legend(handles=handles, title="Traffic Archetype",
                   loc="center left", bbox_to_anchor=(1.02, 0.5),
                   fontsize=9, title_fontsize=10, frameon=True)

def add_full_legend():
    handles = [Patch(facecolor=ARCHETYPE_COLOURS[a], label=a) for a in ARCHETYPE_ORDER]
    plt.legend(handles=handles, title="Traffic Archetype",
               loc="center left", bbox_to_anchor=(1.02, 0.5),
               fontsize=8, title_fontsize=10, frameon=True)

def label_site(row):
    name = row.get("site_name")
    if pd.isna(name) or not str(name).strip():
        name = row.get("friendly_name", "")
    if pd.isna(name):
        name = ""
    return f"{row['site_id']} — {name}"

print("=" * 100)
print("MELBOURNE SCATS TRAFFIC ARCHETYPES FROM EXISTING CSVs V4")
print("=" * 100)

site = pd.read_csv(SITE_TOTALS).rename(columns={"scats_site": "site_id"})
month = pd.read_csv(SITE_MONTH).rename(columns={"scats_site": "site_id", "month_site_volume": "month_volume"})
maps = pd.read_csv(MAP_DATA)

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

growth_rows = []
for sid, g in month.sort_values(["site_id", "month_start"]).groupby("site_id"):
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

master = site.merge(monthly_features, on="site_id", how="left").merge(growth, on="site_id", how="left")

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

    # Split old broad "Mixed Urban Traffic Site"
    if scale >= 70 and stability >= 45:
        return "Mature Urban Arterial"
    if scale >= 45:
        return "Balanced Metropolitan Site"
    return "Secondary Connector Corridor"

master["traffic_archetype"] = master.apply(classify, axis=1)
master["archetype_colour"] = master["traffic_archetype"].map(ARCHETYPE_COLOURS)

master["ooh_exposure_score"] = (
    master["scale_score"] * 0.55 +
    master["stability_score"] * 0.25 +
    master["growth_score"] * 0.20
)

master["traffic_transformation_index"] = (
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
        avg_traffic_transformation_index=("traffic_transformation_index", "mean"),
        avg_strategic_importance_score=("strategic_importance_score", "mean"),
    )
    .reset_index()
)

summary["traffic_share_pct"] = summary["total_volume"] / summary["total_volume"].sum() * 100
summary["colour"] = summary["traffic_archetype"].map(ARCHETYPE_COLOURS)
summary["description"] = summary["traffic_archetype"].map(ARCHETYPE_PROFILES)
summary["order"] = summary["traffic_archetype"].map({a: i for i, a in enumerate(ARCHETYPE_ORDER)})
summary = summary.sort_values("order")

profile_df = pd.DataFrame([
    {"traffic_archetype": a, "colour": ARCHETYPE_COLOURS[a], "description": ARCHETYPE_PROFILES[a]}
    for a in ARCHETYPE_ORDER
])

master.to_csv(OUT / "traffic_archetypes_master_v4.csv", index=False)
summary.to_csv(OUT / "traffic_archetype_summary_v4.csv", index=False)
profile_df.to_csv(OUT / "traffic_archetype_profiles_v4.csv", index=False)

master.sort_values("ooh_exposure_score", ascending=False).head(100).to_csv(OUT / "top100_ooh_exposure_archetype_sites_v4.csv", index=False)
master.sort_values("traffic_transformation_index", ascending=False).head(100).to_csv(OUT / "top100_traffic_transformation_sites_v4.csv", index=False)
master.sort_values("strategic_importance_score", ascending=False).head(100).to_csv(OUT / "top100_strategic_importance_sites_v4.csv", index=False)

# 1. Site counts
plot = summary.sort_values("sites", ascending=True)
plt.figure(figsize=(15, 9))
plt.barh(plot["traffic_archetype"], plot["sites"], color=plot["colour"])
plt.title("Melbourne SCATS Traffic Archetypes: Number of Sites", fontsize=20, weight="bold", pad=28)
subtitle("V4 splits mixed sites into mature arterials, balanced metropolitan sites, and secondary connector corridors.")
plt.xlabel("SCATS sites")
for i, v in enumerate(plot["sites"]):
    plt.text(v, i, f" {int(v):,}", va="center", fontsize=10, weight="bold")
savefig("traffic_archetypes_site_counts_v4.png")

# 2. Traffic share
plot = summary.sort_values("traffic_share_pct", ascending=True)
plt.figure(figsize=(15, 9))
plt.barh(plot["traffic_archetype"], plot["traffic_share_pct"], color=plot["colour"])
plt.title("Traffic Share by Melbourne SCATS Archetype", fontsize=20, weight="bold", pad=28)
subtitle("Shows which behavioural road classes carry the greatest share of analysed movement.")
plt.xlabel("Share of total analysed traffic volume (%)")
for i, v in enumerate(plot["traffic_share_pct"]):
    plt.text(v, i, f" {v:.1f}%", va="center", fontsize=10, weight="bold")
savefig("traffic_archetypes_traffic_share_v4.png")

# 3. Scale vs volatility
plt.figure(figsize=(15, 10))
for archetype in ARCHETYPE_ORDER:
    g = master[master["traffic_archetype"] == archetype]
    if len(g):
        plt.scatter(g["scale_score"], g["volatility_score"], s=16, alpha=0.45,
                    color=ARCHETYPE_COLOURS[archetype], label=archetype)
plt.axvline(75, linestyle="--", linewidth=1, alpha=0.45)
plt.axhline(75, linestyle="--", linewidth=1, alpha=0.45)
plt.text(77, 78, "High-volume\nvolatile zone", fontsize=10, weight="bold")
plt.text(77, 8, "Backbone / reliable\nexposure zone", fontsize=10, weight="bold")
plt.text(8, 78, "Local volatility / event\nsensitivity zone", fontsize=10, weight="bold")
plt.title("Melbourne SCATS Sites: Scale vs Volatility by Traffic Archetype", fontsize=20, weight="bold", pad=28)
subtitle("Lower opacity reveals the underlying behavioural clustering more clearly.")
plt.xlabel("Scale score: cumulative traffic importance")
plt.ylabel("Volatility score: month-to-month variability")
plt.grid(alpha=0.25)
add_full_legend()
savefig("traffic_archetypes_scale_vs_volatility_v4.png")

# 4. Scale vs growth
plt.figure(figsize=(15, 10))
for archetype in ARCHETYPE_ORDER:
    g = master[master["traffic_archetype"] == archetype]
    if len(g):
        plt.scatter(g["scale_score"], g["growth_score"], s=16, alpha=0.45,
                    color=ARCHETYPE_COLOURS[archetype], label=archetype)
plt.axvline(75, linestyle="--", linewidth=1, alpha=0.45)
plt.axhline(75, linestyle="--", linewidth=1, alpha=0.45)
plt.text(77, 78, "High-scale\ngrowth corridor", fontsize=10, weight="bold")
plt.text(8, 78, "Emerging local\ngrowth zone", fontsize=10, weight="bold")
plt.text(77, 8, "Mature high-scale\ncorridor", fontsize=10, weight="bold")
plt.title("Melbourne SCATS Sites: Scale vs Growth by Traffic Archetype", fontsize=20, weight="bold", pad=28)
subtitle("Separates established high-volume corridors from emerging growth locations.")
plt.xlabel("Scale score")
plt.ylabel("Growth score")
plt.grid(alpha=0.25)
add_full_legend()
savefig("traffic_archetypes_scale_vs_growth_v4.png")

# 5. Pure OOH top 25
top = master.sort_values("ooh_exposure_score", ascending=False).head(25).copy()
top["label"] = top.apply(label_site, axis=1)
top = top.sort_values("ooh_exposure_score")
plt.figure(figsize=(16, 11))
plt.barh(top["label"], top["ooh_exposure_score"], color=top["archetype_colour"])
plt.title("Top 25 SCATS Sites by Pure OOH Exposure Score", fontsize=20, weight="bold", pad=28)
subtitle("Pure ranking: top OOH exposure sites remain dominated by Metropolitan Backbone corridors.")
plt.xlabel("OOH exposure score")
for i, v in enumerate(top["ooh_exposure_score"]):
    plt.text(v, i, f" {v:.1f}", va="center", fontsize=9, weight="bold")
add_present_legend(top)
savefig("top25_ooh_exposure_archetype_sites_v4.png")

# 6. Diversified OOH top 25
parts = []
for archetype, g in master.sort_values("ooh_exposure_score", ascending=False).groupby("traffic_archetype"):
    parts.append(g.head(3))
diverse = pd.concat(parts).sort_values("ooh_exposure_score", ascending=False).head(25).copy()
diverse["label"] = diverse.apply(label_site, axis=1)
diverse = diverse.sort_values("ooh_exposure_score")
diverse.to_csv(OUT / "top25_diversified_ooh_exposure_archetype_sites_v4.csv", index=False)
plt.figure(figsize=(16, 11))
plt.barh(diverse["label"], diverse["ooh_exposure_score"], color=diverse["archetype_colour"])
plt.title("Top 25 Diversified OOH Exposure Sites by Archetype", fontsize=20, weight="bold", pad=28)
subtitle("Diversified view surfaces strong OOH candidates across multiple behavioural road classes.")
plt.xlabel("OOH exposure score")
for i, v in enumerate(diverse["ooh_exposure_score"]):
    plt.text(v, i, f" {v:.1f}", va="center", fontsize=9, weight="bold")
add_present_legend(diverse)
savefig("top25_diversified_ooh_exposure_archetype_sites_v4.png")

# 7. Traffic Transformation Index
top = master.sort_values("traffic_transformation_index", ascending=False).head(25).copy()
top["label"] = top.apply(label_site, axis=1)
top = top.sort_values("traffic_transformation_index")
plt.figure(figsize=(16, 11))
plt.barh(top["label"], top["traffic_transformation_index"], color=top["archetype_colour"])
plt.title("Top 25 SCATS Sites by Traffic Transformation Index", fontsize=20, weight="bold", pad=28)
subtitle("Highlights growth, volatility, spikes, and structural change rather than simple traffic volume.")
plt.xlabel("Traffic Transformation Index")
for i, v in enumerate(top["traffic_transformation_index"]):
    plt.text(v, i, f" {v:.1f}", va="center", fontsize=9, weight="bold")
add_present_legend(top)
savefig("top25_traffic_transformation_sites_v4.png")

# 8. Strategic importance
top = master.sort_values("strategic_importance_score", ascending=False).head(25).copy()
top["label"] = top.apply(label_site, axis=1)
top = top.sort_values("strategic_importance_score")
plt.figure(figsize=(16, 11))
plt.barh(top["label"], top["strategic_importance_score"], color=top["archetype_colour"])
plt.title("Top 25 SCATS Sites by Strategic Importance Score", fontsize=20, weight="bold", pad=28)
subtitle("Balances traffic scale, stability, growth, and volatility into one network-importance ranking.")
plt.xlabel("Strategic importance score")
for i, v in enumerate(top["strategic_importance_score"]):
    plt.text(v, i, f" {v:.1f}", va="center", fontsize=9, weight="bold")
add_present_legend(top)
savefig("top25_strategic_importance_sites_v4.png")

# 9. Heatmap
heat_cols = [
    "avg_scale_score", "avg_stability_score", "avg_volatility_score",
    "avg_growth_score", "avg_ooh_exposure_score",
    "avg_traffic_transformation_index", "avg_strategic_importance_score"
]
heat = summary.set_index("traffic_archetype").loc[
    [a for a in ARCHETYPE_ORDER if a in set(summary["traffic_archetype"])],
    heat_cols
]
plt.figure(figsize=(16, 9))
plt.imshow(heat.values, aspect="auto", cmap="viridis")
plt.title("Traffic Archetype Behavioural Score Heatmap", fontsize=20, weight="bold", pad=28)
subtitle("Each archetype has a distinct behavioural signature across scale, stability, volatility, growth and exposure.")
plt.yticks(range(len(heat.index)), heat.index)
plt.xticks(
    range(len(heat_cols)),
    ["Scale", "Stability", "Volatility", "Growth", "OOH", "Transform", "Strategic"],
    rotation=35,
    ha="right"
)
for y in range(heat.shape[0]):
    for x in range(heat.shape[1]):
        val = heat.values[y, x]
        plt.text(x, y, f"{val:.0f}", ha="center", va="center",
                 fontsize=8, weight="bold",
                 color="white" if val < 55 else "black")
cbar = plt.colorbar()
cbar.set_label("Average score")
savefig("traffic_archetype_score_heatmap_v4.png")

# 10. Compact colour key
legend_df = pd.DataFrame([{"traffic_archetype": a, "colour": ARCHETYPE_COLOURS[a]} for a in ARCHETYPE_ORDER])
plt.figure(figsize=(12, 5))
plt.barh(legend_df["traffic_archetype"], [1] * len(legend_df), color=legend_df["colour"])
plt.title("Traffic Archetype Colour Key", fontsize=16, weight="bold", pad=12)
plt.xticks([])
for i, row in legend_df.iterrows():
    plt.text(0.03, i, row["traffic_archetype"], va="center", color="white", fontsize=9, weight="bold")
savefig("traffic_archetype_colour_key_v4.png")

with open(OUT / "traffic_archetypes_summary_v4.json", "w", encoding="utf-8") as f:
    json.dump({
        "input_files": {
            "site_rankings": str(SITE_TOTALS),
            "site_month_totals": str(SITE_MONTH),
            "map_data": str(MAP_DATA),
        },
        "site_count": int(master["site_id"].nunique()),
        "archetype_count": int(master["traffic_archetype"].nunique()),
        "archetype_colours": ARCHETYPE_COLOURS,
        "outputs_dir": str(OUT),
        "method_note": "CSV-only traffic archetype V4 model with split mixed-site classes, Traffic Transformation Index, refined opacity, ordered heatmap and archetype profiles."
    }, f, indent=2)

print("\nDONE")
print(f"Output directory: {OUT}")