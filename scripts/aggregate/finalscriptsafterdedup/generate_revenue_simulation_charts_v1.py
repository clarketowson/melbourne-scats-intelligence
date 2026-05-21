
from pathlib import Path
import argparse
import pandas as pd
import matplotlib.pyplot as plt

def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)

def cumulative_share(rankings, n):
    n = min(n, len(rankings))
    return rankings.head(n)["total_volume"].sum()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence")
    parser.add_argument("--output-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\revenue_charts")
    parser.add_argument("--cpm", type=float, default=8.0)
    parser.add_argument("--cost-per-site", type=float, default=12000)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rankings = pd.read_csv(input_dir / "site_rankings.csv").sort_values("rank")

    total_volume = rankings["total_volume"].sum()

    portfolio_sizes = [50,100,250,500,1000,1500,2000,2500,3000,4000]

    rows = []
    for n in portfolio_sizes:
        volume = cumulative_share(rankings, n)
        impressions = volume
        revenue = (impressions / 1000) * args.cpm
        cost = n * args.cost_per_site
        profit = revenue - cost

        rows.append({
            "sites": n,
            "revenue": revenue,
            "cost": cost,
            "profit": profit
        })

    df = pd.DataFrame(rows)

    # Revenue vs Portfolio Size
    fig, ax = plt.subplots(figsize=(12,7))
    ax.plot(df["sites"], df["revenue"]/1_000_000,
            marker="o", linewidth=3)
    ax.set_title("Revenue vs Portfolio Size")
    ax.set_xlabel("Number of Sites")
    ax.set_ylabel("Revenue (Millions)")
    save(fig, output_dir / "01_revenue_vs_portfolio.png")

    # Cost vs Portfolio Size
    fig, ax = plt.subplots(figsize=(12,7))
    ax.plot(df["sites"], df["cost"]/1_000_000,
            marker="o", linewidth=3)
    ax.set_title("Cost vs Portfolio Size")
    ax.set_xlabel("Number of Sites")
    ax.set_ylabel("Cost (Millions)")
    save(fig, output_dir / "02_cost_vs_portfolio.png")

    # Profit Curve
    fig, ax = plt.subplots(figsize=(12,7))
    ax.plot(df["sites"], df["profit"]/1_000_000,
            marker="o", linewidth=3)
    ax.set_title("Profit vs Portfolio Size")
    ax.set_xlabel("Number of Sites")
    ax.set_ylabel("Profit (Millions)")
    save(fig, output_dir / "03_profit_curve.png")

    # Revenue per Site
    df["revenue_per_site"] = df["revenue"] / df["sites"]

    fig, ax = plt.subplots(figsize=(12,7))
    ax.bar(df["sites"].astype(str),
           df["revenue_per_site"]/1000)
    ax.set_title("Revenue per Site by Portfolio Size")
    ax.set_xlabel("Portfolio Size")
    ax.set_ylabel("Revenue per Site ($ thousands)")
    save(fig, output_dir / "04_revenue_per_site.png")

    df.to_csv(output_dir / "revenue_simulation_summary.csv",
              index=False)

    print("="*70)
    print("REVENUE SIMULATION CHARTS COMPLETE")
    print(f"Output dir: {output_dir}")
    print("="*70)

if __name__ == "__main__":
    main()
