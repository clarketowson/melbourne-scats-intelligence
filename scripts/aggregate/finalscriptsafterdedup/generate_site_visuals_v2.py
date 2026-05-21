from pathlib import Path
import argparse

import pandas as pd
import matplotlib.pyplot as plt


COLORS = {
    "traffic_red": "#d73027",
    "traffic_orange": "#fc8d59",
    "traffic_gold": "#fdae61",
    "network_blue": "#1f78b4",
    "network_teal": "#1b9e77",
    "infrastructure_green": "#2ca25f",
    "purple": "#756bb1",
    "dark": "#333333",
    "grey": "#777777",
    "light_grid": "#cccccc",
}


def save_chart(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def apply_common_style(ax):
    ax.grid(True, alpha=0.25, color=COLORS["light_grid"])
    ax.tick_params(colors=COLORS["dark"])
    ax.title.set_color(COLORS["dark"])
    ax.xaxis.label.set_color(COLORS["dark"])
    ax.yaxis.label.set_color(COLORS["dark"])


def main():
    parser = argparse.ArgumentParser(description="Generate coloured SCATS site intelligence charts V2.")
    parser.add_argument(
        "--input-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence",
    )
    parser.add_argument(
        "--output-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\charts_v2",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    rankings = pd.read_csv(input_dir / "site_rankings.csv").sort_values("rank").copy()
    trend = pd.read_csv(input_dir / "site_totals_monthly_network_trend.csv").copy()
    percentiles = pd.read_csv(input_dir / "site_volume_percentile_bands.csv").copy()

    trend["month_label"] = trend["month_label"].astype(str)
    grand_total = rankings["total_volume"].sum()

    print("=" * 80)
    print("GENERATE SITE VISUALS V2 — COLOURED CHARTS")
    print("=" * 80)
    print(f"Input dir : {input_dir}")
    print(f"Output dir: {output_dir}")

    # 1. Pareto curve
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        rankings["rank"],
        rankings["cumulative_percent"],
        linewidth=3,
        color=COLORS["traffic_red"],
    )
    ax.set_title("SCATS Traffic Concentration Curve — Cumulative Share by Site Rank")
    ax.set_xlabel("SCATS site rank")
    ax.set_ylabel("Cumulative share of total traffic (%)")
    apply_common_style(ax)
    save_chart(fig, output_dir / "01_site_pareto_cumulative_share_v2.png")

    # 2. Rank decay
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        rankings["rank"],
        rankings["total_volume"],
        linewidth=2.5,
        color=COLORS["traffic_orange"],
    )
    ax.set_title("SCATS Site Rank Decay — Total Volume by Site Rank")
    ax.set_xlabel("SCATS site rank")
    ax.set_ylabel("Total vehicle volume")
    apply_common_style(ax)
    save_chart(fig, output_dir / "02_site_rank_decay_total_volume_v2.png")

    # 3. Log scale rank decay
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        rankings["rank"],
        rankings["total_volume"],
        linewidth=2.5,
        color=COLORS["purple"],
    )
    ax.set_yscale("log")
    ax.set_title("SCATS Site Rank Decay — Log Scale")
    ax.set_xlabel("SCATS site rank")
    ax.set_ylabel("Total vehicle volume, log scale")
    apply_common_style(ax)
    save_chart(fig, output_dir / "03_site_rank_decay_log_scale_v2.png")

    # 4. Monthly network volume
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(
        trend["month_label"],
        trend["total_volume"],
        linewidth=2.5,
        color=COLORS["network_blue"],
    )
    ax.set_title("Monthly SCATS Network Volume")
    ax.set_xlabel("Month")
    ax.set_ylabel("Total vehicle volume")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    apply_common_style(ax)
    save_chart(fig, output_dir / "04_monthly_network_volume_v2.png")

    # 5. Active sites over time
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(
        trend["month_label"],
        trend["active_sites"],
        linewidth=2.5,
        color=COLORS["infrastructure_green"],
    )
    ax.set_title("Active SCATS Sites Over Time")
    ax.set_xlabel("Month")
    ax.set_ylabel("Active sites")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    apply_common_style(ax)
    save_chart(fig, output_dir / "05_active_sites_over_time_v2.png")

    # 6. Percentile band chart
    percentile_order = ["Top 1%", "Top 5%", "Top 10%", "Top 25%", "Top 50%", "Bottom 50%"]
    band_colours = [
        COLORS["traffic_red"],
        COLORS["traffic_orange"],
        COLORS["traffic_gold"],
        COLORS["purple"],
        COLORS["network_blue"],
        COLORS["grey"],
    ]

    percentiles["percentile_band"] = pd.Categorical(
        percentiles["percentile_band"],
        categories=percentile_order,
        ordered=True,
    )
    percentiles = percentiles.sort_values("percentile_band")

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(
        percentiles["percentile_band"].astype(str),
        percentiles["share_percent"],
        color=band_colours[: len(percentiles)],
    )
    ax.set_title("Traffic Share by SCATS Site Percentile Band")
    ax.set_xlabel("Percentile band")
    ax.set_ylabel("Share of total traffic (%)")
    apply_common_style(ax)
    save_chart(fig, output_dir / "06_percentile_band_traffic_share_v2.png")

    # 7. Top-N traffic share
    top_n_rows = []
    for n in [10, 25, 50, 100, 500, 1000]:
        share = rankings.head(n)["total_volume"].sum() / grand_total * 100
        top_n_rows.append({"label": f"Top {n}", "share_percent": share})

    top_n = pd.DataFrame(top_n_rows)
    top_n_colours = [
        "#fee5d9",
        "#fcbba1",
        "#fc9272",
        "#fb6a4a",
        "#de2d26",
        "#a50f15",
    ]

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(top_n["label"], top_n["share_percent"], color=top_n_colours)
    ax.set_title("Traffic Share Captured by Top-Ranked SCATS Sites")
    ax.set_xlabel("Site group")
    ax.set_ylabel("Share of total traffic (%)")
    apply_common_style(ax)
    save_chart(fig, output_dir / "07_top_n_traffic_share_v2.png")

    # 8. Top 25 sites
    top25 = rankings.head(25).copy()
    top25["label"] = top25["rank"].astype(str) + " — " + top25["scats_site"].astype(str)

    gradient_colours = [
        "#a50f15", "#b8191d", "#c92822", "#d73027", "#e34a33",
        "#ef6548", "#f46d43", "#f98558", "#fc8d59", "#fdae61",
        "#fdbb72", "#fdc086", "#fdd49e", "#fee0b6", "#fee8c8",
        "#fddbc7", "#f4a582", "#d6604d", "#b2182b", "#762a83",
        "#8073ac", "#4393c3", "#2166ac", "#1f78b4", "#0571b0",
    ]

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.barh(
        top25["label"][::-1],
        top25["total_volume"][::-1],
        color=gradient_colours[::-1],
    )
    ax.set_title("Top 25 SCATS Sites by Total Vehicle Volume")
    ax.set_xlabel("Total vehicle volume")
    ax.set_ylabel("Rank — SCATS site")
    apply_common_style(ax)
    save_chart(fig, output_dir / "08_top_25_sites_total_volume_v2.png")

    # 9. Average monthly volume per active site
    trend["avg_volume_per_active_site"] = trend["total_volume"] / trend["active_sites"]

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(
        trend["month_label"],
        trend["avg_volume_per_active_site"],
        linewidth=2.5,
        color=COLORS["network_teal"],
    )
    ax.set_title("Average Monthly Volume per Active SCATS Site")
    ax.set_xlabel("Month")
    ax.set_ylabel("Average volume per active site")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    apply_common_style(ax)
    save_chart(fig, output_dir / "09_avg_volume_per_active_site_v2.png")

    chart_index = pd.DataFrame(
        [
            ["01_site_pareto_cumulative_share_v2.png", "Coloured cumulative traffic share by site rank"],
            ["02_site_rank_decay_total_volume_v2.png", "Coloured total volume by site rank"],
            ["03_site_rank_decay_log_scale_v2.png", "Coloured rank decay on log scale"],
            ["04_monthly_network_volume_v2.png", "Coloured monthly total SCATS network volume"],
            ["05_active_sites_over_time_v2.png", "Coloured active SCATS sites over time"],
            ["06_percentile_band_traffic_share_v2.png", "Coloured traffic share by percentile band"],
            ["07_top_n_traffic_share_v2.png", "Coloured traffic share captured by top N sites"],
            ["08_top_25_sites_total_volume_v2.png", "Coloured top 25 SCATS sites by total volume"],
            ["09_avg_volume_per_active_site_v2.png", "Coloured average monthly volume per active site"],
        ],
        columns=["filename", "description"],
    )

    chart_index.to_csv(output_dir / "site_visuals_v2_chart_index.csv", index=False)

    print("Generated V2 charts:")
    for filename in chart_index["filename"]:
        print(f"  - {filename}")

    print("=" * 80)
    print("SITE VISUALS V2 COMPLETE")
    print(f"Charts written to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()