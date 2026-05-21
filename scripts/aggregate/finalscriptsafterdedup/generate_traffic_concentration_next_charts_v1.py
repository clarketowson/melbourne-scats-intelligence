from pathlib import Path
import argparse

import pandas as pd
import matplotlib.pyplot as plt


COLORS = {
    "red": "#d73027",
    "dark_red": "#a50f15",
    "orange": "#fc8d59",
    "gold": "#fdae61",
    "blue": "#1f78b4",
    "green": "#2ca25f",
    "purple": "#756bb1",
    "grey": "#777777",
    "dark": "#333333",
    "grid": "#cccccc",
}


def apply_style(ax):
    ax.grid(True, alpha=0.25, color=COLORS["grid"])
    ax.tick_params(colors=COLORS["dark"])
    ax.title.set_color(COLORS["dark"])
    ax.xaxis.label.set_color(COLORS["dark"])
    ax.yaxis.label.set_color(COLORS["dark"])


def save_chart(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def cumulative_share_at(rankings: pd.DataFrame, n: int) -> float:
    n = min(n, len(rankings))
    return rankings.head(n)["total_volume"].sum() / rankings["total_volume"].sum() * 100


def main():
    parser = argparse.ArgumentParser(description="Generate next-stage SCATS concentration and commercial charts.")
    parser.add_argument(
        "--input-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence",
    )
    parser.add_argument(
        "--output-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\concentration_charts",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rankings_path = input_dir / "site_rankings.csv"
    rankings = pd.read_csv(rankings_path).sort_values("rank").copy()

    total_sites = len(rankings)
    total_volume = rankings["total_volume"].sum()

    rankings["site_share_percent"] = rankings["rank"] / total_sites * 100
    rankings["traffic_share_percent"] = rankings["total_volume"] / total_volume * 100
    rankings["remaining_traffic_percent"] = 100 - rankings["cumulative_percent"]

    print("=" * 80)
    print("GENERATE TRAFFIC CONCENTRATION NEXT CHARTS V1")
    print("=" * 80)
    print(f"Input rankings : {rankings_path}")
    print(f"Output dir     : {output_dir}")
    print(f"Total sites    : {total_sites:,}")
    print(f"Grand total    : {int(total_volume):,}")

    # 1. Top 100 vs Rest
    top100 = cumulative_share_at(rankings, 100)
    rest100 = 100 - top100
    df = pd.DataFrame({"group": ["Top 100 Sites", "Remaining Sites"], "share": [top100, rest100]})

    fig, ax = plt.subplots(figsize=(9, 7))
    bars = ax.bar(df["group"], df["share"], color=[COLORS["dark_red"], COLORS["grey"]])
    ax.set_title("Top 100 Sites vs Remaining SCATS Network")
    ax.set_ylabel("Share of total traffic (%)")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1, f"{b.get_height():.1f}%", ha="center")
    apply_style(ax)
    save_chart(fig, output_dir / "01_top_100_vs_remaining_network.png")

    # 2. Top 500 vs Next 500 vs Remaining
    groups = [
        ("Top 500", rankings.iloc[:500]["total_volume"].sum()),
        ("Ranks 501–1000", rankings.iloc[500:1000]["total_volume"].sum()),
        ("Ranks 1001+", rankings.iloc[1000:]["total_volume"].sum()),
    ]
    group_df = pd.DataFrame(groups, columns=["group", "volume"])
    group_df["share"] = group_df["volume"] / total_volume * 100

    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.bar(group_df["group"], group_df["share"], color=[COLORS["dark_red"], COLORS["orange"], COLORS["grey"]])
    ax.set_title("Traffic Share: Top 500, Next 500, and Remaining Sites")
    ax.set_ylabel("Share of total traffic (%)")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1, f"{b.get_height():.1f}%", ha="center")
    apply_style(ax)
    save_chart(fig, output_dir / "02_top500_next500_remaining.png")

    # 3. City-level concentration points
    portfolio_sizes = [10, 25, 50, 100, 250, 500, 1000, 1500, 2000, 2500, 3000, 4000, total_sites]
    concentration = []
    for n in portfolio_sizes:
        n = min(n, total_sites)
        concentration.append({
            "sites": n,
            "site_share": n / total_sites * 100,
            "traffic_share": cumulative_share_at(rankings, n),
        })
    concentration_df = pd.DataFrame(concentration)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(concentration_df["site_share"], concentration_df["traffic_share"], marker="o", linewidth=3, color=COLORS["red"])
    ax.plot([0, 100], [0, 100], linestyle="--", color=COLORS["grey"], linewidth=1.5)
    ax.set_title("City-Level Traffic Concentration — Site Share vs Traffic Share")
    ax.set_xlabel("Share of SCATS sites selected (%)")
    ax.set_ylabel("Share of total traffic captured (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "03_city_level_concentration_curve.png")

    # 4. Site share required for traffic thresholds
    thresholds = [10, 25, 50, 75, 90, 95]
    rows = []
    for threshold in thresholds:
        hit = rankings[rankings["cumulative_percent"] >= threshold].head(1)
        if hit.empty:
            continue
        sites_needed = int(hit.iloc[0]["rank"])
        rows.append({
            "traffic_threshold": f"{threshold}%",
            "sites_needed": sites_needed,
            "site_share_percent": sites_needed / total_sites * 100,
        })
    threshold_df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(11, 7))
    bars = ax.bar(threshold_df["traffic_threshold"], threshold_df["sites_needed"], color=[
        COLORS["gold"], COLORS["orange"], COLORS["red"], COLORS["dark_red"], COLORS["purple"], COLORS["blue"]
    ][:len(threshold_df)])
    ax.set_title("How Many Top-Ranked Sites Are Needed to Capture Traffic Thresholds?")
    ax.set_xlabel("Traffic capture threshold")
    ax.set_ylabel("Number of sites required")
    for b, pct in zip(bars, threshold_df["site_share_percent"]):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + total_sites*0.01, f"{pct:.1f}% of sites", ha="center", fontsize=9)
    apply_style(ax)
    save_chart(fig, output_dir / "04_sites_needed_for_traffic_thresholds.png")

    # 5. Remaining traffic after major thresholds
    selected_sizes = [100, 250, 500, 1000, 1500, 2000, 2500, 3000, 4000]
    remaining_rows = []
    for n in selected_sizes:
        if n <= total_sites:
            captured = cumulative_share_at(rankings, n)
            remaining_rows.append({"sites": n, "remaining": 100 - captured})
    remaining_df = pd.DataFrame(remaining_rows)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(remaining_df["sites"], remaining_df["remaining"], marker="o", linewidth=3, color=COLORS["grey"])
    ax.set_title("Remaining Traffic After Selecting Top-Ranked Sites")
    ax.set_xlabel("Number of top-ranked SCATS sites selected")
    ax.set_ylabel("Remaining traffic share (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "05_remaining_traffic_after_selection.png")

    # 6. Traffic density per site group
    bins = [
        ("Top 100", 0, 100),
        ("101–500", 100, 500),
        ("501–1000", 500, 1000),
        ("1001–2000", 1000, 2000),
        ("2001–3000", 2000, 3000),
        ("3001+", 3000, total_sites),
    ]
    density_rows = []
    for label, start, end in bins:
        block = rankings.iloc[start:end]
        if len(block) == 0:
            continue
        density_rows.append({
            "group": label,
            "sites": len(block),
            "avg_volume_per_site": block["total_volume"].mean(),
            "traffic_share": block["total_volume"].sum() / total_volume * 100,
        })
    density_df = pd.DataFrame(density_rows)

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(density_df["group"], density_df["avg_volume_per_site"], color=[
        COLORS["dark_red"], COLORS["red"], COLORS["orange"], COLORS["gold"], COLORS["blue"], COLORS["grey"]
    ][:len(density_df)])
    ax.set_title("Average Traffic Volume per Site Group")
    ax.set_xlabel("Rank group")
    ax.set_ylabel("Average total volume per site")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height()*1.01, f"{b.get_height()/1_000_000:.1f}M", ha="center", fontsize=9)
    apply_style(ax)
    save_chart(fig, output_dir / "06_avg_volume_per_site_group.png")

    # 7. Traffic share by rank group
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(density_df["group"], density_df["traffic_share"], color=[
        COLORS["dark_red"], COLORS["red"], COLORS["orange"], COLORS["gold"], COLORS["blue"], COLORS["grey"]
    ][:len(density_df)])
    ax.set_title("Traffic Share by Rank Group")
    ax.set_xlabel("Rank group")
    ax.set_ylabel("Share of total traffic (%)")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.6, f"{b.get_height():.1f}%", ha="center", fontsize=9)
    apply_style(ax)
    save_chart(fig, output_dir / "07_traffic_share_by_rank_group.png")

    # 8. Commercial portfolio ladder
    ladder = concentration_df.copy()
    ladder["label"] = ladder["sites"].astype(str)

    fig, ax = plt.subplots(figsize=(13, 7))
    bars = ax.bar(ladder["label"], ladder["traffic_share"], color=[
        "#fee5d9", "#fcbba1", "#fc9272", "#fb6a4a", "#de2d26", "#a50f15",
        "#fdae61", "#fc8d59", "#d73027", "#b2182b", "#762a83", "#8073ac", "#636363"
    ][:len(ladder)])
    ax.set_title("Commercial Portfolio Ladder — Traffic Captured by Portfolio Size")
    ax.set_xlabel("Top-ranked SCATS sites selected")
    ax.set_ylabel("Traffic captured (%)")
    ax.tick_params(axis="x", rotation=30)
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1, f"{b.get_height():.1f}%", ha="center", fontsize=8)
    apply_style(ax)
    save_chart(fig, output_dir / "08_commercial_portfolio_ladder.png")

    # Export summary CSVs
    concentration_df.to_csv(output_dir / "city_level_concentration_summary.csv", index=False)
    threshold_df.to_csv(output_dir / "traffic_threshold_sites_required.csv", index=False)
    density_df.to_csv(output_dir / "rank_group_density_summary.csv", index=False)

    chart_index = pd.DataFrame(
        [
            ["01_top_100_vs_remaining_network.png", "Top 100 sites compared with the remaining network"],
            ["02_top500_next500_remaining.png", "Top 500, next 500, and remaining sites"],
            ["03_city_level_concentration_curve.png", "Site share versus traffic share concentration curve"],
            ["04_sites_needed_for_traffic_thresholds.png", "Number of sites required to reach traffic thresholds"],
            ["05_remaining_traffic_after_selection.png", "Remaining traffic after selecting top-ranked sites"],
            ["06_avg_volume_per_site_group.png", "Average traffic volume per site group"],
            ["07_traffic_share_by_rank_group.png", "Traffic share by rank group"],
            ["08_commercial_portfolio_ladder.png", "Commercial portfolio ladder by traffic captured"],
        ],
        columns=["filename", "description"],
    )
    chart_index.to_csv(output_dir / "traffic_concentration_next_chart_index.csv", index=False)

    print("Generated charts:")
    for f in chart_index["filename"]:
        print(f"  - {f}")
    print("=" * 80)
    print("TRAFFIC CONCENTRATION NEXT CHARTS V1 COMPLETE")
    print(f"Charts written to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
