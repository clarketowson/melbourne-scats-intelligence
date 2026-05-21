import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def fmt_int(n):
    return f"{int(n):,}"


def save_chart(fig, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate SCATS site intelligence visual charts.")
    parser.add_argument(
        "--input-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence",
        help="Directory containing site intelligence CSV outputs.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\charts",
        help="Directory to write PNG charts.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    rankings_path = input_dir / "site_rankings.csv"
    trend_path = input_dir / "site_totals_monthly_network_trend.csv"
    percentile_path = input_dir / "site_volume_percentile_bands.csv"

    print("=" * 80)
    print("GENERATE SITE VISUALS V1")
    print("=" * 80)
    print(f"Input dir : {input_dir}")
    print(f"Output dir: {output_dir}")
    print("=" * 80)

    rankings = pd.read_csv(rankings_path)
    trend = pd.read_csv(trend_path)
    percentiles = pd.read_csv(percentile_path)

    rankings = rankings.sort_values("rank").copy()
    trend["month_label"] = trend["month_label"].astype(str)

    grand_total = rankings["total_volume"].sum()

    # 1. Pareto / cumulative traffic share curve
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(rankings["rank"], rankings["cumulative_percent"], linewidth=2)
    ax.set_title("SCATS Traffic Concentration Curve — Cumulative Share by Site Rank")
    ax.set_xlabel("SCATS site rank")
    ax.set_ylabel("Cumulative share of total traffic (%)")
    ax.grid(True, alpha=0.3)
    save_chart(fig, output_dir / "01_site_pareto_cumulative_share.png")

    # 2. Rank decay curve
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(rankings["rank"], rankings["total_volume"], linewidth=2)
    ax.set_title("SCATS Site Rank Decay — Total Volume by Site Rank")
    ax.set_xlabel("SCATS site rank")
    ax.set_ylabel("Total vehicle volume")
    ax.grid(True, alpha=0.3)
    save_chart(fig, output_dir / "02_site_rank_decay_total_volume.png")

    # 3. Log rank decay curve
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(rankings["rank"], rankings["total_volume"], linewidth=2)
    ax.set_yscale("log")
    ax.set_title("SCATS Site Rank Decay — Log Scale")
    ax.set_xlabel("SCATS site rank")
    ax.set_ylabel("Total vehicle volume, log scale")
    ax.grid(True, alpha=0.3)
    save_chart(fig, output_dir / "03_site_rank_decay_log_scale.png")

    # 4. Monthly network total volume
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(trend["month_label"], trend["total_volume"], linewidth=2)
    ax.set_title("Monthly SCATS Network Volume")
    ax.set_xlabel("Month")
    ax.set_ylabel("Total vehicle volume")
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    save_chart(fig, output_dir / "04_monthly_network_volume.png")

    # 5. Active site count over time
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(trend["month_label"], trend["active_sites"], linewidth=2)
    ax.set_title("Active SCATS Sites Over Time")
    ax.set_xlabel("Month")
    ax.set_ylabel("Active sites")
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    save_chart(fig, output_dir / "05_active_sites_over_time.png")

    # 6. Percentile band traffic share
    percentile_order = ["Top 1%", "Top 5%", "Top 10%", "Top 25%", "Top 50%", "Bottom 50%"]
    percentiles["percentile_band"] = pd.Categorical(
        percentiles["percentile_band"],
        categories=percentile_order,
        ordered=True,
    )
    percentiles = percentiles.sort_values("percentile_band")

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(percentiles["percentile_band"].astype(str), percentiles["share_percent"])
    ax.set_title("Traffic Share by SCATS Site Percentile Band")
    ax.set_xlabel("Percentile band")
    ax.set_ylabel("Share of total traffic (%)")
    ax.grid(True, axis="y", alpha=0.3)
    save_chart(fig, output_dir / "06_percentile_band_traffic_share.png")

    # 7. Top N share comparison
    top_n_rows = []
    for n in [10, 25, 50, 100, 500, 1000]:
        subset = rankings.head(n)
        share = subset["total_volume"].sum() / grand_total * 100
        top_n_rows.append({"label": f"Top {n}", "share_percent": share})

    top_n = pd.DataFrame(top_n_rows)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(top_n["label"], top_n["share_percent"])
    ax.set_title("Traffic Share Captured by Top-Ranked SCATS Sites")
    ax.set_xlabel("Site group")
    ax.set_ylabel("Share of total traffic (%)")
    ax.grid(True, axis="y", alpha=0.3)
    save_chart(fig, output_dir / "07_top_n_traffic_share.png")

    # 8. Top 25 site volumes
    top25 = rankings.head(25).copy()
    top25["label"] = top25["rank"].astype(str) + " — " + top25["scats_site"].astype(str)

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.barh(top25["label"][::-1], top25["total_volume"][::-1])
    ax.set_title("Top 25 SCATS Sites by Total Vehicle Volume")
    ax.set_xlabel("Total vehicle volume")
    ax.set_ylabel("Rank — SCATS site")
    ax.grid(True, axis="x", alpha=0.3)
    save_chart(fig, output_dir / "08_top_25_sites_total_volume.png")

    # 9. Monthly average volume per active site
    trend["avg_volume_per_active_site"] = trend["total_volume"] / trend["active_sites"]

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(trend["month_label"], trend["avg_volume_per_active_site"], linewidth=2)
    ax.set_title("Average Monthly Volume per Active SCATS Site")
    ax.set_xlabel("Month")
    ax.set_ylabel("Average volume per active site")
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    save_chart(fig, output_dir / "09_avg_volume_per_active_site.png")

    # 10. Output chart index CSV
    chart_index = pd.DataFrame(
        [
            ["01_site_pareto_cumulative_share.png", "Cumulative traffic share by site rank"],
            ["02_site_rank_decay_total_volume.png", "Total volume by site rank"],
            ["03_site_rank_decay_log_scale.png", "Rank decay on log scale"],
            ["04_monthly_network_volume.png", "Monthly total SCATS network volume"],
            ["05_active_sites_over_time.png", "Active SCATS sites over time"],
            ["06_percentile_band_traffic_share.png", "Traffic share by percentile band"],
            ["07_top_n_traffic_share.png", "Traffic share captured by top N sites"],
            ["08_top_25_sites_total_volume.png", "Top 25 SCATS sites by total volume"],
            ["09_avg_volume_per_active_site.png", "Average monthly volume per active site"],
        ],
        columns=["filename", "description"],
    )
    chart_index.to_csv(output_dir / "site_visuals_chart_index.csv", index=False)

    print("Generated charts:")
    for filename in chart_index["filename"]:
        print(f"  - {filename}")

    print("=" * 80)
    print("SITE VISUALS V1 COMPLETE")
    print(f"Charts written to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()