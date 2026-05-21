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


def main():
    parser = argparse.ArgumentParser(description="Generate campaign-style SCATS site portfolio simulation charts.")
    parser.add_argument(
        "--input-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence",
    )
    parser.add_argument(
        "--output-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\campaign_charts",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    rankings_path = input_dir / "site_rankings.csv"
    rankings = pd.read_csv(rankings_path).sort_values("rank").copy()

    total_sites = len(rankings)
    grand_total = rankings["total_volume"].sum()
    rankings["cumulative_sites_percent"] = rankings["rank"] / total_sites * 100
    rankings["individual_share_percent"] = rankings["total_volume"] / grand_total * 100

    print("=" * 80)
    print("GENERATE CAMPAIGN SIMULATION VISUALS V1")
    print("=" * 80)
    print(f"Input rankings : {rankings_path}")
    print(f"Output dir     : {output_dir}")
    print(f"Total sites    : {total_sites:,}")
    print(f"Grand total    : {int(grand_total):,}")

    portfolio_sizes = [10, 25, 50, 100, 250, 500, 750, 1000, 1500, 2000, 2500, 3000, 4000, total_sites]
    portfolio_sizes = sorted(set([n for n in portfolio_sizes if n <= total_sites]))

    rows = []
    previous_volume = 0
    previous_n = 0

    for n in portfolio_sizes:
        subset = rankings.head(n)
        captured_volume = subset["total_volume"].sum()
        captured_share = captured_volume / grand_total * 100
        site_share = n / total_sites * 100
        incremental_volume = captured_volume - previous_volume
        incremental_sites = n - previous_n
        incremental_share = incremental_volume / grand_total * 100
        avg_incremental_share_per_site = incremental_share / incremental_sites if incremental_sites else 0
        efficiency_ratio = captured_share / site_share if site_share else 0

        rows.append(
            {
                "portfolio_size": n,
                "site_share_percent": site_share,
                "captured_volume": captured_volume,
                "captured_share_percent": captured_share,
                "incremental_sites": incremental_sites,
                "incremental_volume": incremental_volume,
                "incremental_share_percent": incremental_share,
                "avg_incremental_share_per_site": avg_incremental_share_per_site,
                "efficiency_ratio": efficiency_ratio,
            }
        )

        previous_volume = captured_volume
        previous_n = n

    simulation = pd.DataFrame(rows)
    simulation.to_csv(output_dir / "campaign_portfolio_simulation_summary.csv", index=False)

    # 1. Portfolio size vs traffic captured
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        simulation["portfolio_size"],
        simulation["captured_share_percent"],
        marker="o",
        linewidth=3,
        color=COLORS["red"],
    )
    ax.set_title("Campaign Portfolio Size vs Traffic Captured")
    ax.set_xlabel("Number of top-ranked SCATS sites selected")
    ax.set_ylabel("Share of total traffic captured (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "01_portfolio_size_vs_traffic_captured.png")

    # 2. Site share vs traffic share, efficiency view
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        simulation["site_share_percent"],
        simulation["captured_share_percent"],
        marker="o",
        linewidth=3,
        color=COLORS["dark_red"],
    )
    ax.plot([0, 100], [0, 100], linestyle="--", linewidth=1.5, color=COLORS["grey"])
    ax.set_title("Campaign Coverage Efficiency — Site Share vs Traffic Share")
    ax.set_xlabel("Share of SCATS sites selected (%)")
    ax.set_ylabel("Share of total traffic captured (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "02_campaign_coverage_efficiency.png")

    # 3. Incremental share by portfolio step
    step_labels = [f"+{int(x)}" for x in simulation["incremental_sites"]]
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.bar(step_labels, simulation["incremental_share_percent"], color=COLORS["orange"])
    ax.set_title("Incremental Traffic Gained at Each Portfolio Expansion Step")
    ax.set_xlabel("Additional sites added at each step")
    ax.set_ylabel("Additional traffic share captured (%)")
    ax.tick_params(axis="x", rotation=35)
    apply_style(ax)
    save_chart(fig, output_dir / "03_incremental_traffic_gain_by_step.png")

    # 4. Average incremental gain per added site
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.plot(
        simulation["portfolio_size"],
        simulation["avg_incremental_share_per_site"],
        marker="o",
        linewidth=3,
        color=COLORS["purple"],
    )
    ax.set_title("Diminishing Returns — Average Incremental Gain per Added Site")
    ax.set_xlabel("Portfolio size after expansion")
    ax.set_ylabel("Average added traffic share per added site (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "04_diminishing_returns_avg_gain_per_site.png")

    # 5. Efficiency ratio by portfolio size
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        simulation["portfolio_size"],
        simulation["efficiency_ratio"],
        marker="o",
        linewidth=3,
        color=COLORS["green"],
    )
    ax.axhline(1.0, linestyle="--", linewidth=1.5, color=COLORS["grey"])
    ax.set_title("Portfolio Efficiency Ratio — Traffic Share ÷ Site Share")
    ax.set_xlabel("Number of top-ranked SCATS sites selected")
    ax.set_ylabel("Efficiency ratio")
    apply_style(ax)
    save_chart(fig, output_dir / "05_portfolio_efficiency_ratio.png")

    # 6. Portfolio traffic captured table chart style
    fig, ax = plt.subplots(figsize=(13, 7))
    bars = ax.bar(
        simulation["portfolio_size"].astype(str),
        simulation["captured_share_percent"],
        color=[COLORS["gold"], COLORS["orange"], COLORS["red"], COLORS["dark_red"]] * 4,
    )
    ax.set_title("Traffic Captured by Selected Portfolio Sizes")
    ax.set_xlabel("Top-ranked site portfolio")
    ax.set_ylabel("Share of total traffic captured (%)")
    ax.tick_params(axis="x", rotation=35)
    apply_style(ax)
    for bar, value in zip(bars, simulation["captured_share_percent"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.1f}%", ha="center", va="bottom", fontsize=8)
    save_chart(fig, output_dir / "06_traffic_captured_by_portfolio_size.png")

    # 7. Remaining traffic after portfolio selection
    simulation["remaining_share_percent"] = 100 - simulation["captured_share_percent"]
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        simulation["portfolio_size"],
        simulation["remaining_share_percent"],
        marker="o",
        linewidth=3,
        color=COLORS["grey"],
    )
    ax.set_title("Remaining Network Traffic After Selecting Top Sites")
    ax.set_xlabel("Number of top-ranked SCATS sites selected")
    ax.set_ylabel("Remaining traffic share (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "07_remaining_traffic_after_portfolio_selection.png")

    chart_index = pd.DataFrame(
        [
            ["01_portfolio_size_vs_traffic_captured.png", "Traffic captured as portfolio size increases"],
            ["02_campaign_coverage_efficiency.png", "Campaign site share vs traffic share efficiency"],
            ["03_incremental_traffic_gain_by_step.png", "Incremental traffic gained by each portfolio expansion step"],
            ["04_diminishing_returns_avg_gain_per_site.png", "Average added gain per added site"],
            ["05_portfolio_efficiency_ratio.png", "Portfolio efficiency ratio"],
            ["06_traffic_captured_by_portfolio_size.png", "Traffic captured by selected portfolio sizes"],
            ["07_remaining_traffic_after_portfolio_selection.png", "Remaining traffic after top-site selection"],
        ],
        columns=["filename", "description"],
    )
    chart_index.to_csv(output_dir / "campaign_chart_index.csv", index=False)

    print("Generated campaign charts:")
    for filename in chart_index["filename"]:
        print(f"  - {filename}")

    print("=" * 80)
    print("CAMPAIGN SIMULATION VISUALS V1 COMPLETE")
    print(f"Charts written to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
