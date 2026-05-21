
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


def cumulative_volume(rankings: pd.DataFrame, n: int) -> float:
    n = min(n, len(rankings))
    return rankings.head(n)["total_volume"].sum()


def main():
    parser = argparse.ArgumentParser(description="Revenue Simulation V2 — CPM, utilisation, ROI and tier scenarios.")
    parser.add_argument(
        "--input-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence",
    )
    parser.add_argument(
        "--output-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\revenue_charts_v2",
    )
    parser.add_argument("--cost-per-site", type=float, default=12000.0)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rankings = pd.read_csv(input_dir / "site_rankings.csv").sort_values("rank").copy()
    total_volume = rankings["total_volume"].sum()

    portfolio_sizes = [50, 100, 250, 500, 1000, 1500, 2000, 2500, 3000, 4000]
    cpm_scenarios = [2, 4, 8, 12, 16]
    utilisation_scenarios = [0.25, 0.50, 0.75, 1.00]

    print("=" * 80)
    print("REVENUE SIMULATION V2 — MARKET SCENARIOS")
    print("=" * 80)
    print(f"Input dir      : {input_dir}")
    print(f"Output dir     : {output_dir}")
    print(f"Cost per site  : ${args.cost_per_site:,.0f}")
    print(f"Total sites    : {len(rankings):,}")
    print(f"Grand volume   : {int(total_volume):,}")

    # Base portfolio dataframe
    base_rows = []
    for n in portfolio_sizes:
        vol = cumulative_volume(rankings, n)
        base_rows.append({
            "sites": n,
            "volume": vol,
            "traffic_share_percent": vol / total_volume * 100,
            "cost": n * args.cost_per_site,
        })
    base_df = pd.DataFrame(base_rows)

    # 1. Revenue by CPM scenario at 100% utilisation
    fig, ax = plt.subplots(figsize=(12, 7))
    for cpm, color in zip(cpm_scenarios, [COLORS["grey"], COLORS["blue"], COLORS["green"], COLORS["orange"], COLORS["red"]]):
        revenue = (base_df["volume"] / 1000) * cpm
        ax.plot(base_df["sites"], revenue / 1_000_000, marker="o", linewidth=2.5, label=f"${cpm} CPM", color=color)
    ax.set_title("Revenue by Portfolio Size — CPM Scenarios")
    ax.set_xlabel("Number of top-ranked sites")
    ax.set_ylabel("Revenue ($ millions)")
    ax.legend()
    apply_style(ax)
    save_chart(fig, output_dir / "01_revenue_by_cpm_scenario.png")

    # 2. Profit by CPM scenario
    fig, ax = plt.subplots(figsize=(12, 7))
    for cpm, color in zip(cpm_scenarios, [COLORS["grey"], COLORS["blue"], COLORS["green"], COLORS["orange"], COLORS["red"]]):
        revenue = (base_df["volume"] / 1000) * cpm
        profit = revenue - base_df["cost"]
        ax.plot(base_df["sites"], profit / 1_000_000, marker="o", linewidth=2.5, label=f"${cpm} CPM", color=color)
    ax.axhline(0, linestyle="--", color=COLORS["dark"], linewidth=1.2)
    ax.set_title("Profit by Portfolio Size — CPM Scenarios")
    ax.set_xlabel("Number of top-ranked sites")
    ax.set_ylabel("Profit ($ millions)")
    ax.legend()
    apply_style(ax)
    save_chart(fig, output_dir / "02_profit_by_cpm_scenario.png")

    # 3. Utilisation sensitivity at $8 CPM
    fig, ax = plt.subplots(figsize=(12, 7))
    base_cpm = 8
    for util, color in zip(utilisation_scenarios, [COLORS["grey"], COLORS["blue"], COLORS["orange"], COLORS["red"]]):
        revenue = (base_df["volume"] * util / 1000) * base_cpm
        profit = revenue - base_df["cost"]
        ax.plot(base_df["sites"], profit / 1_000_000, marker="o", linewidth=2.5, label=f"{int(util*100)}% utilisation", color=color)
    ax.axhline(0, linestyle="--", color=COLORS["dark"], linewidth=1.2)
    ax.set_title("Profit Sensitivity — Utilisation Scenarios at $8 CPM")
    ax.set_xlabel("Number of top-ranked sites")
    ax.set_ylabel("Profit ($ millions)")
    ax.legend()
    apply_style(ax)
    save_chart(fig, output_dir / "03_profit_by_utilisation_at_8_cpm.png")

    # 4. ROI by portfolio size at $8 CPM and utilisation scenarios
    fig, ax = plt.subplots(figsize=(12, 7))
    for util, color in zip(utilisation_scenarios, [COLORS["grey"], COLORS["blue"], COLORS["orange"], COLORS["red"]]):
        revenue = (base_df["volume"] * util / 1000) * base_cpm
        roi = (revenue - base_df["cost"]) / base_df["cost"] * 100
        ax.plot(base_df["sites"], roi, marker="o", linewidth=2.5, label=f"{int(util*100)}% utilisation", color=color)
    ax.axhline(0, linestyle="--", color=COLORS["dark"], linewidth=1.2)
    ax.set_title("ROI by Portfolio Size — Utilisation Scenarios at $8 CPM")
    ax.set_xlabel("Number of top-ranked sites")
    ax.set_ylabel("ROI (%)")
    ax.legend()
    apply_style(ax)
    save_chart(fig, output_dir / "04_roi_by_utilisation_at_8_cpm.png")

    # 5. Break-even CPM required by portfolio size at utilisation levels
    fig, ax = plt.subplots(figsize=(12, 7))
    for util, color in zip(utilisation_scenarios, [COLORS["grey"], COLORS["blue"], COLORS["orange"], COLORS["red"]]):
        break_even_cpm = base_df["cost"] / ((base_df["volume"] * util) / 1000)
        ax.plot(base_df["sites"], break_even_cpm, marker="o", linewidth=2.5, label=f"{int(util*100)}% utilisation", color=color)
    ax.set_title("Break-Even CPM Required by Portfolio Size")
    ax.set_xlabel("Number of top-ranked sites")
    ax.set_ylabel("Break-even CPM ($)")
    ax.legend()
    apply_style(ax)
    save_chart(fig, output_dir / "05_break_even_cpm_by_portfolio.png")

    # 6. Revenue per site by CPM scenario
    fig, ax = plt.subplots(figsize=(12, 7))
    for cpm, color in zip(cpm_scenarios, [COLORS["grey"], COLORS["blue"], COLORS["green"], COLORS["orange"], COLORS["red"]]):
        revenue = (base_df["volume"] / 1000) * cpm
        revenue_per_site = revenue / base_df["sites"]
        ax.plot(base_df["sites"], revenue_per_site / 1000, marker="o", linewidth=2.5, label=f"${cpm} CPM", color=color)
    ax.set_title("Revenue per Site — CPM Scenarios")
    ax.set_xlabel("Number of top-ranked sites")
    ax.set_ylabel("Revenue per site ($ thousands)")
    ax.legend()
    apply_style(ax)
    save_chart(fig, output_dir / "06_revenue_per_site_by_cpm.png")

    # 7. Scenario heatmap: ROI at 1000 sites
    heat_rows = []
    target_sites = 1000
    target_volume = cumulative_volume(rankings, target_sites)
    target_cost = target_sites * args.cost_per_site
    for util in utilisation_scenarios:
        row = []
        for cpm in cpm_scenarios:
            revenue = (target_volume * util / 1000) * cpm
            roi = (revenue - target_cost) / target_cost * 100
            row.append(roi)
        heat_rows.append(row)

    heat_df = pd.DataFrame(
        heat_rows,
        index=[f"{int(u*100)}%" for u in utilisation_scenarios],
        columns=[f"${c}" for c in cpm_scenarios],
    )

    fig, ax = plt.subplots(figsize=(10, 7))
    im = ax.imshow(heat_df.values, aspect="auto")
    ax.set_title("ROI Heatmap — 1,000-Site Portfolio")
    ax.set_xlabel("CPM")
    ax.set_ylabel("Utilisation")
    ax.set_xticks(range(len(heat_df.columns)))
    ax.set_xticklabels(heat_df.columns)
    ax.set_yticks(range(len(heat_df.index)))
    ax.set_yticklabels(heat_df.index)
    for i in range(len(heat_df.index)):
        for j in range(len(heat_df.columns)):
            ax.text(j, i, f"{heat_df.iloc[i, j]:.0f}%", ha="center", va="center", color="white" if heat_df.iloc[i, j] > heat_df.values.mean() else "black")
    fig.colorbar(im, ax=ax, label="ROI (%)")
    save_chart(fig, output_dir / "07_roi_heatmap_1000_site_portfolio.png")

    # 8. Tier-based revenue model
    def tier(rank):
        if rank <= 100:
            return "Top 100"
        if rank <= 500:
            return "101–500"
        if rank <= 1000:
            return "501–1000"
        if rank <= 2000:
            return "1001–2000"
        return "2001+"

    rankings["tier"] = rankings["rank"].apply(tier)
    tier_cpms = {
        "Top 100": 16,
        "101–500": 12,
        "501–1000": 8,
        "1001–2000": 5,
        "2001+": 3,
    }

    tier_summary = (
        rankings.groupby("tier", as_index=False)
        .agg(
            sites=("scats_site", "count"),
            volume=("total_volume", "sum"),
        )
    )
    tier_summary["cpm"] = tier_summary["tier"].map(tier_cpms)
    tier_summary["revenue"] = (tier_summary["volume"] / 1000) * tier_summary["cpm"]
    tier_summary["cost"] = tier_summary["sites"] * args.cost_per_site
    tier_summary["profit"] = tier_summary["revenue"] - tier_summary["cost"]
    tier_summary["roi_percent"] = tier_summary["profit"] / tier_summary["cost"] * 100

    tier_order = ["Top 100", "101–500", "501–1000", "1001–2000", "2001+"]
    tier_summary["tier"] = pd.Categorical(tier_summary["tier"], categories=tier_order, ordered=True)
    tier_summary = tier_summary.sort_values("tier")

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(tier_summary["tier"].astype(str), tier_summary["revenue"] / 1_000_000,
                  color=[COLORS["dark_red"], COLORS["red"], COLORS["orange"], COLORS["gold"], COLORS["grey"]])
    ax.set_title("Tier-Based Revenue Model")
    ax.set_xlabel("Traffic tier")
    ax.set_ylabel("Revenue ($ millions)")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height()*1.01, f"${b.get_height():,.0f}M", ha="center", fontsize=9)
    apply_style(ax)
    save_chart(fig, output_dir / "08_tier_based_revenue_model.png")

    # Export scenario summaries
    scenario_rows = []
    for n in portfolio_sizes:
        vol = cumulative_volume(rankings, n)
        cost = n * args.cost_per_site
        for cpm in cpm_scenarios:
            for util in utilisation_scenarios:
                revenue = (vol * util / 1000) * cpm
                profit = revenue - cost
                scenario_rows.append({
                    "sites": n,
                    "cpm": cpm,
                    "utilisation": util,
                    "traffic_volume": vol,
                    "traffic_share_percent": vol / total_volume * 100,
                    "revenue": revenue,
                    "cost": cost,
                    "profit": profit,
                    "roi_percent": profit / cost * 100,
                    "break_even_cpm": cost / ((vol * util) / 1000),
                })

    scenario_df = pd.DataFrame(scenario_rows)
    scenario_df.to_csv(output_dir / "revenue_simulation_v2_scenarios.csv", index=False)
    base_df.to_csv(output_dir / "portfolio_base_summary.csv", index=False)
    tier_summary.to_csv(output_dir / "tier_based_revenue_summary.csv", index=False)
    heat_df.to_csv(output_dir / "roi_heatmap_1000_site_portfolio.csv")

    chart_index = pd.DataFrame(
        [
            ["01_revenue_by_cpm_scenario.png", "Revenue by portfolio size across CPM scenarios"],
            ["02_profit_by_cpm_scenario.png", "Profit by portfolio size across CPM scenarios"],
            ["03_profit_by_utilisation_at_8_cpm.png", "Profit by utilisation at $8 CPM"],
            ["04_roi_by_utilisation_at_8_cpm.png", "ROI by utilisation at $8 CPM"],
            ["05_break_even_cpm_by_portfolio.png", "Break-even CPM required by portfolio size"],
            ["06_revenue_per_site_by_cpm.png", "Revenue per site across CPM scenarios"],
            ["07_roi_heatmap_1000_site_portfolio.png", "ROI heatmap for a 1,000-site portfolio"],
            ["08_tier_based_revenue_model.png", "Revenue by traffic tier using tiered CPM assumptions"],
        ],
        columns=["filename", "description"],
    )
    chart_index.to_csv(output_dir / "revenue_simulation_v2_chart_index.csv", index=False)

    print("Generated V2 revenue charts:")
    for f in chart_index["filename"]:
        print(f"  - {f}")
    print("=" * 80)
    print("REVENUE SIMULATION V2 COMPLETE")
    print(f"Charts written to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
