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
    parser = argparse.ArgumentParser(description="Generate strategic SCATS site intelligence charts.")
    parser.add_argument(
        "--input-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence",
    )
    parser.add_argument(
        "--output-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\strategy_charts",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    rankings = pd.read_csv(input_dir / "site_rankings.csv").sort_values("rank").copy()

    rankings["cumulative_sites_percent"] = rankings["rank"] / len(rankings) * 100
    rankings["marginal_share_percent"] = rankings["total_volume"] / rankings["total_volume"].sum() * 100

    print("=" * 80)
    print("GENERATE SITE STRATEGY VISUALS V1")
    print("=" * 80)
    print(f"Input dir : {input_dir}")
    print(f"Output dir: {output_dir}")

    # 1. Coverage efficiency curve
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        rankings["cumulative_sites_percent"],
        rankings["cumulative_percent"],
        linewidth=3,
        color=COLORS["red"],
    )
    ax.plot([0, 100], [0, 100], linestyle="--", linewidth=1.5, color=COLORS["grey"])
    ax.set_title("SCATS Coverage Efficiency Curve — Sites Required vs Traffic Captured")
    ax.set_xlabel("Cumulative share of SCATS sites (%)")
    ax.set_ylabel("Cumulative share of total traffic (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "01_coverage_efficiency_curve.png")

    # 2. Marginal gain by rank
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        rankings["rank"],
        rankings["marginal_share_percent"],
        linewidth=2.2,
        color=COLORS["orange"],
    )
    ax.set_title("Marginal Traffic Gain by Additional SCATS Site")
    ax.set_xlabel("SCATS site rank")
    ax.set_ylabel("Individual site share of total traffic (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "02_marginal_gain_by_rank.png")

    # 3. Marginal gain by rank log scale
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(
        rankings["rank"],
        rankings["marginal_share_percent"],
        linewidth=2.2,
        color=COLORS["purple"],
    )
    ax.set_yscale("log")
    ax.set_title("Marginal Traffic Gain by Additional Site — Log Scale")
    ax.set_xlabel("SCATS site rank")
    ax.set_ylabel("Individual site share of total traffic (%), log scale")
    apply_style(ax)
    save_chart(fig, output_dir / "03_marginal_gain_log_scale.png")

    # 4. Traffic tier classification
    def tier(rank):
        if rank <= 50:
            return "Tier 1: Core"
        if rank <= 100:
            return "Tier 2: Strategic"
        if rank <= 500:
            return "Tier 3: Major"
        if rank <= 1000:
            return "Tier 4: Broad Network"
        return "Tier 5: Long Tail"

    rankings["traffic_tier"] = rankings["rank"].apply(tier)

    tier_summary = (
        rankings.groupby("traffic_tier", as_index=False)
        .agg(
            sites=("scats_site", "count"),
            total_volume=("total_volume", "sum"),
        )
    )
    tier_summary["share_percent"] = tier_summary["total_volume"] / rankings["total_volume"].sum() * 100

    tier_order = [
        "Tier 1: Core",
        "Tier 2: Strategic",
        "Tier 3: Major",
        "Tier 4: Broad Network",
        "Tier 5: Long Tail",
    ]

    tier_summary["traffic_tier"] = pd.Categorical(
        tier_summary["traffic_tier"],
        categories=tier_order,
        ordered=True,
    )
    tier_summary = tier_summary.sort_values("traffic_tier")

    tier_colours = [
        COLORS["dark_red"],
        COLORS["red"],
        COLORS["orange"],
        COLORS["gold"],
        COLORS["grey"],
    ]

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(
        tier_summary["traffic_tier"].astype(str),
        tier_summary["share_percent"],
        color=tier_colours,
    )
    ax.set_title("Traffic Share by Strategic SCATS Site Tier")
    ax.set_xlabel("Strategic tier")
    ax.set_ylabel("Share of total traffic (%)")
    ax.tick_params(axis="x", rotation=20)
    apply_style(ax)
    save_chart(fig, output_dir / "04_traffic_share_by_strategy_tier.png")

    # 5. Site count by tier
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(
        tier_summary["traffic_tier"].astype(str),
        tier_summary["sites"],
        color=tier_colours,
    )
    ax.set_title("Number of SCATS Sites by Strategic Tier")
    ax.set_xlabel("Strategic tier")
    ax.set_ylabel("Number of sites")
    ax.tick_params(axis="x", rotation=20)
    apply_style(ax)
    save_chart(fig, output_dir / "05_site_count_by_strategy_tier.png")

    # 6. Efficiency comparison: traffic share divided by site share
    tier_summary["site_share_percent"] = tier_summary["sites"] / len(rankings) * 100
    tier_summary["efficiency_ratio"] = tier_summary["share_percent"] / tier_summary["site_share_percent"]

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(
        tier_summary["traffic_tier"].astype(str),
        tier_summary["efficiency_ratio"],
        color=tier_colours,
    )
    ax.axhline(1.0, linestyle="--", linewidth=1.5, color=COLORS["grey"])
    ax.set_title("Traffic Efficiency Ratio by Strategic Tier")
    ax.set_xlabel("Strategic tier")
    ax.set_ylabel("Traffic share ÷ site share")
    ax.tick_params(axis="x", rotation=20)
    apply_style(ax)
    save_chart(fig, output_dir / "06_efficiency_ratio_by_strategy_tier.png")

    # 7. Top 1000 vs remaining network
    top1000_volume = rankings.head(1000)["total_volume"].sum()
    rest_volume = rankings.iloc[1000:]["total_volume"].sum()

    comparison = pd.DataFrame(
        {
            "group": ["Top 1000 Sites", "Remaining Sites"],
            "volume": [top1000_volume, rest_volume],
        }
    )
    comparison["share_percent"] = comparison["volume"] / comparison["volume"].sum() * 100

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.bar(
        comparison["group"],
        comparison["share_percent"],
        color=[COLORS["red"], COLORS["grey"]],
    )
    ax.set_title("Top 1000 Sites vs Remaining SCATS Network")
    ax.set_xlabel("Group")
    ax.set_ylabel("Share of total traffic (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "07_top_1000_vs_remaining_network.png")

    # 8. Top 500 vs next 500 vs rest
    group_rows = [
        {
            "group": "Top 500",
            "volume": rankings.iloc[:500]["total_volume"].sum(),
        },
        {
            "group": "Ranks 501–1000",
            "volume": rankings.iloc[500:1000]["total_volume"].sum(),
        },
        {
            "group": "Ranks 1001+",
            "volume": rankings.iloc[1000:]["total_volume"].sum(),
        },
    ]
    group_df = pd.DataFrame(group_rows)
    group_df["share_percent"] = group_df["volume"] / rankings["total_volume"].sum() * 100

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.bar(
        group_df["group"],
        group_df["share_percent"],
        color=[COLORS["dark_red"], COLORS["orange"], COLORS["grey"]],
    )
    ax.set_title("Traffic Share: Top 500, Next 500, and Remaining Sites")
    ax.set_xlabel("Site group")
    ax.set_ylabel("Share of total traffic (%)")
    apply_style(ax)
    save_chart(fig, output_dir / "08_top500_next500_rest_share.png")

    # Export tier summary
    tier_summary.to_csv(output_dir / "site_strategy_tier_summary.csv", index=False)

    chart_index = pd.DataFrame(
        [
            ["01_coverage_efficiency_curve.png", "Traffic captured as cumulative site share increases"],
            ["02_marginal_gain_by_rank.png", "Marginal traffic contribution of each additional ranked site"],
            ["03_marginal_gain_log_scale.png", "Marginal gain on log scale"],
            ["04_traffic_share_by_strategy_tier.png", "Traffic share by strategic tier"],
            ["05_site_count_by_strategy_tier.png", "Number of sites by strategic tier"],
            ["06_efficiency_ratio_by_strategy_tier.png", "Traffic efficiency ratio by tier"],
            ["07_top_1000_vs_remaining_network.png", "Top 1000 vs remaining traffic share"],
            ["08_top500_next500_rest_share.png", "Top 500 vs next 500 vs rest"],
        ],
        columns=["filename", "description"],
    )

    chart_index.to_csv(output_dir / "site_strategy_chart_index.csv", index=False)

    print("Generated strategic charts:")
    for filename in chart_index["filename"]:
        print(f"  - {filename}")

    print("=" * 80)
    print("SITE STRATEGY VISUALS V1 COMPLETE")
    print(f"Charts written to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()