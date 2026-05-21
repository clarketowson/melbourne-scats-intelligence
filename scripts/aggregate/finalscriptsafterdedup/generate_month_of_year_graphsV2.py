#!/usr/bin/env python3
"""
generate_month_of_year_graphsV2.py

Creates colour-coded month-of-year seasonal SCATS traffic graphs.

This V2 works with the completed month_of_year_profile.csv structure:
  month_label, month_start, next_month_start, month_of_year, month_name,
  month_total_volume, days_loaded, avg_daily_volume, ...

Input default:
  A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\month_of_year_profile.csv

Output default:
  A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\month_of_year_graphs

Usage:
  python generate_month_of_year_graphsV2.py

Optional:
  python generate_month_of_year_graphsV2.py --input "A:\\...\\month_of_year_profile.csv" --output "A:\\...\\month_of_year_graphs"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_INPUT_CSV = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\month_of_year_profile.csv")
DEFAULT_OUTPUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\month_of_year_graphs")

MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SCATS month-of-year seasonal graphs.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_CSV, help="Input month_of_year_profile.csv path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output graph directory")
    return parser.parse_args()


def traffic_colours(values, cmap_name: str = "RdYlGn_r"):
    """Low values = green/yellow, high values = orange/red."""
    vals = pd.Series(values).astype(float)
    cmap = plt.colormaps[cmap_name]

    if vals.max() == vals.min():
        normed = np.full(len(vals), 0.5)
    else:
        norm = plt.Normalize(vals.min(), vals.max())
        normed = norm(vals)

    return [cmap(v) for v in normed]


def savefig(output_dir: Path, filename: str):
    path = output_dir / filename
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(path, dpi=240, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def add_value_labels_on_bars(bars, suffix="M", decimals=1, fontsize=9):
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            height,
            f"{height:.{decimals}f}{suffix}",
            ha="center",
            va="bottom",
            fontsize=fontsize,
        )


def load_and_prepare(input_csv: Path) -> pd.DataFrame:
    if not input_csv.exists():
        raise SystemExit(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv)

    required = {
        "month_label",
        "month_start",
        "month_of_year",
        "month_name",
        "month_total_volume",
        "days_loaded",
        "avg_daily_volume",
    }
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["month_start"] = pd.to_datetime(df["month_start"], errors="coerce")
    df["year"] = df["month_start"].dt.year

    numeric_cols = ["month_of_year", "month_total_volume", "days_loaded", "avg_daily_volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Remove the known zero-row month and any malformed rows.
    df = df[
        df["month_start"].notna()
        & df["year"].notna()
        & df["month_of_year"].between(1, 12)
        & df["month_total_volume"].fillna(0).gt(0)
        & df["avg_daily_volume"].fillna(0).gt(0)
    ].copy()

    df["year"] = df["year"].astype(int)
    df["month_of_year"] = df["month_of_year"].astype(int)
    df["month_name"] = pd.Categorical(df["month_name"], MONTH_ORDER, ordered=True)

    return df.sort_values(["year", "month_of_year"])


def build_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        df.groupby(["month_of_year", "month_name"], observed=True)
        .agg(
            avg_daily_volume=("avg_daily_volume", "mean"),
            median_daily_volume=("avg_daily_volume", "median"),
            avg_monthly_volume=("month_total_volume", "mean"),
            total_volume=("month_total_volume", "sum"),
            std_daily_volume=("avg_daily_volume", "std"),
            months_seen=("month_label", "nunique"),
            years_seen=("year", "nunique"),
        )
        .reset_index()
        .sort_values("month_of_year")
    )

    overall_mean = monthly["avg_daily_volume"].mean()
    monthly["seasonal_index"] = monthly["avg_daily_volume"] / overall_mean * 100

    return monthly


def main() -> int:
    args = parse_args()
    input_csv: Path = args.input
    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 90)
    print("MONTH OF YEAR SCATS GRAPH GENERATOR V2")
    print("=" * 90)
    print(f"Input : {input_csv}")
    print(f"Output: {output_dir}")
    print("=" * 90)

    df = load_and_prepare(input_csv)
    monthly = build_monthly_summary(df)

    print(f"Rows loaded after filtering: {len(df):,}")
    print(f"Date range: {df['month_start'].min().date()} to {df['month_start'].max().date()}")
    print(f"Years: {df['year'].min()} to {df['year'].max()}")
    print()

    # ------------------------------------------------------------------
    # 01. Flagship seasonal curve
    # ------------------------------------------------------------------
    plt.figure(figsize=(15, 8))
    plt.plot(
        monthly["month_name"].astype(str),
        monthly["avg_daily_volume"] / 1e6,
        marker="o",
        linewidth=3,
    )
    plt.title("Melbourne Seasonal Traffic Curve", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Average daily SCATS vehicle movements by calendar month, 2014–2026", y=0.94, fontsize=12)
    plt.ylabel("Average Daily Vehicle Movements (Millions)")
    plt.xlabel("Month")
    plt.grid(alpha=0.25)
    plt.xticks(rotation=35, ha="right")
    savefig(output_dir, "01_melbourne_seasonal_traffic_curve.png")

    # ------------------------------------------------------------------
    # 02. Ranked busiest months
    # ------------------------------------------------------------------
    ranked = monthly.sort_values("avg_daily_volume", ascending=False)
    plt.figure(figsize=(15, 8))
    colours = traffic_colours(ranked["avg_daily_volume"])
    bars = plt.bar(ranked["month_name"].astype(str), ranked["avg_daily_volume"] / 1e6, color=colours)
    plt.title("Melbourne's Busiest Traffic Months Ranked", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Colour scale: green = quieter, yellow = mid-range, red = busiest", y=0.94, fontsize=12)
    plt.ylabel("Average Daily Vehicle Movements (Millions)")
    plt.xlabel("Month")
    plt.xticks(rotation=35, ha="right")
    add_value_labels_on_bars(bars)
    savefig(output_dir, "02_busiest_months_ranked.png")

    # ------------------------------------------------------------------
    # 03. Seasonal index
    # ------------------------------------------------------------------
    plt.figure(figsize=(15, 8))
    colours = traffic_colours(monthly["seasonal_index"])
    bars = plt.bar(monthly["month_name"].astype(str), monthly["seasonal_index"], color=colours)
    plt.axhline(100, linestyle="--", linewidth=1.5, alpha=0.75)
    plt.title("Melbourne Seasonal Traffic Index", fontsize=22, weight="bold", pad=18)
    plt.suptitle("100 = normal seasonal baseline; above 100 = busier than average", y=0.94, fontsize=12)
    plt.ylabel("Seasonal Index")
    plt.xlabel("Month")
    plt.xticks(rotation=35, ha="right")
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, height, f"{height:.1f}", ha="center", va="bottom", fontsize=9)
    savefig(output_dir, "03_seasonal_traffic_index.png")

    # ------------------------------------------------------------------
    # 04. Month-by-year heatmap
    # ------------------------------------------------------------------
    heat = df.pivot_table(index="year", columns="month_of_year", values="avg_daily_volume", aggfunc="mean")
    plt.figure(figsize=(15, 9))
    plt.imshow(heat / 1e6, aspect="auto", cmap="YlOrRd")
    plt.colorbar(label="Average Daily Vehicle Movements (Millions)")
    plt.title("Month-by-Year Melbourne Traffic Heatmap", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Redder cells indicate higher citywide monthly traffic intensity", y=0.94, fontsize=12)
    plt.xlabel("Month")
    plt.ylabel("Year")
    plt.xticks(range(12), MONTH_ABBR)
    plt.yticks(range(len(heat.index)), heat.index)
    savefig(output_dir, "04_month_by_year_heatmap.png")

    # ------------------------------------------------------------------
    # 05. Multi-year seasonal overlay
    # ------------------------------------------------------------------
    plt.figure(figsize=(15, 8))
    years = sorted(df["year"].unique())
    for year in years:
        ydf = df[df["year"] == year].sort_values("month_of_year")
        alpha = 0.22 if year < 2020 else 0.65
        linewidth = 1.3 if year < 2020 else 2.0
        plt.plot(
            ydf["month_of_year"],
            ydf["avg_daily_volume"] / 1e6,
            marker="o",
            alpha=alpha,
            linewidth=linewidth,
            label=str(year),
        )
    plt.title("Seasonal Traffic Pattern by Year", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Each line shows Melbourne's month-by-month traffic rhythm for one year", y=0.94, fontsize=12)
    plt.ylabel("Average Daily Vehicle Movements (Millions)")
    plt.xlabel("Month")
    plt.xticks(range(1, 13), MONTH_ABBR)
    plt.grid(alpha=0.25)
    plt.legend(ncol=4, fontsize=8, frameon=False)
    savefig(output_dir, "05_multi_year_seasonal_overlay.png")

    # ------------------------------------------------------------------
    # 06. Monthly share of annual traffic
    # ------------------------------------------------------------------
    yearly_totals = df.groupby("year", as_index=False).agg(year_total=("month_total_volume", "sum"))
    share_df = df.merge(yearly_totals, on="year", how="left")
    share_df["month_share_of_year"] = share_df["month_total_volume"] / share_df["year_total"] * 100
    share = (
        share_df.groupby(["month_of_year", "month_name"], observed=True)
        .agg(avg_share=("month_share_of_year", "mean"))
        .reset_index()
        .sort_values("month_of_year")
    )
    plt.figure(figsize=(15, 8))
    colours = traffic_colours(share["avg_share"])
    bars = plt.bar(share["month_name"].astype(str), share["avg_share"], color=colours)
    plt.title("Average Share of Annual Melbourne Traffic by Month", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Shows how much of each year's SCATS traffic typically occurs in each month", y=0.94, fontsize=12)
    plt.ylabel("Average Share of Annual Traffic (%)")
    plt.xlabel("Month")
    plt.xticks(rotation=35, ha="right")
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, height, f"{height:.2f}%", ha="center", va="bottom", fontsize=8)
    savefig(output_dir, "06_monthly_share_of_annual_traffic.png")

    # ------------------------------------------------------------------
    # 07. Year-to-year volatility by month
    # ------------------------------------------------------------------
    vol = monthly.sort_values("month_of_year")
    plt.figure(figsize=(15, 8))
    colours = traffic_colours(vol["std_daily_volume"].fillna(0))
    bars = plt.bar(vol["month_name"].astype(str), vol["std_daily_volume"].fillna(0) / 1e6, color=colours)
    plt.title("Traffic Volatility by Month", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Higher bars show months whose average daily traffic varies more from year to year", y=0.94, fontsize=12)
    plt.ylabel("Standard Deviation of Avg Daily Volume (Millions)")
    plt.xlabel("Month")
    plt.xticks(rotation=35, ha="right")
    add_value_labels_on_bars(bars)
    savefig(output_dir, "07_monthly_traffic_volatility.png")

    # ------------------------------------------------------------------
    # 08. Long-term monthly growth lines
    # ------------------------------------------------------------------
    plt.figure(figsize=(15, 8))
    for month_num, month_abbr in enumerate(MONTH_ABBR, start=1):
        mdf = df[df["month_of_year"] == month_num].sort_values("year")
        plt.plot(mdf["year"], mdf["avg_daily_volume"] / 1e6, marker="o", linewidth=1.8, label=month_abbr)
    plt.title("Long-Term Monthly Traffic Growth", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Each line tracks one calendar month across the full SCATS period", y=0.94, fontsize=12)
    plt.ylabel("Average Daily Vehicle Movements (Millions)")
    plt.xlabel("Year")
    plt.grid(alpha=0.25)
    plt.legend(ncol=6, fontsize=9, frameon=False)
    savefig(output_dir, "08_long_term_monthly_growth.png")

    # ------------------------------------------------------------------
    # 09. Busiest vs quietest month
    # ------------------------------------------------------------------
    best = ranked.iloc[0]
    lowest = ranked.iloc[-1]
    compare = pd.DataFrame([best, lowest])
    plt.figure(figsize=(11, 7))
    colours = traffic_colours(compare["avg_daily_volume"])
    bars = plt.bar(compare["month_name"].astype(str), compare["avg_daily_volume"] / 1e6, color=colours)
    gap = (best["avg_daily_volume"] - lowest["avg_daily_volume"]) / 1e6
    plt.title("Melbourne's Busiest vs Quietest Traffic Month", fontsize=20, weight="bold", pad=18)
    plt.suptitle(f"Gap: approximately {gap:.1f} million vehicle movements per day", y=0.93, fontsize=12)
    plt.ylabel("Average Daily Vehicle Movements (Millions)")
    add_value_labels_on_bars(bars, fontsize=11)
    savefig(output_dir, "09_busiest_vs_quietest_month.png")

    # ------------------------------------------------------------------
    # 10. Calendar-year traffic intensity strip
    # ------------------------------------------------------------------
    values = monthly.sort_values("month_of_year")["avg_daily_volume"].to_numpy() / 1e6
    plt.figure(figsize=(14, 4))
    plt.imshow([values], aspect="auto", cmap="RdYlGn_r")
    plt.colorbar(label="Average Daily Vehicle Movements (Millions)")
    plt.title("Melbourne Calendar-Year Traffic Intensity Strip", fontsize=20, weight="bold", pad=18)
    plt.suptitle("A compact seasonal strip showing citywide traffic intensity from January to December", y=0.89, fontsize=11)
    plt.xticks(range(12), MONTH_ABBR)
    plt.yticks([])
    savefig(output_dir, "10_calendar_year_traffic_intensity_strip.png")

    # ------------------------------------------------------------------
    # 11. Monthly total volume ranked
    # ------------------------------------------------------------------
    total_ranked = monthly.sort_values("total_volume", ascending=False)
    plt.figure(figsize=(15, 8))
    colours = traffic_colours(total_ranked["total_volume"])
    bars = plt.bar(total_ranked["month_name"].astype(str), total_ranked["total_volume"] / 1e9, color=colours)
    plt.title("Total SCATS Volume by Calendar Month", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Cumulative traffic across all years grouped by month of year", y=0.94, fontsize=12)
    plt.ylabel("Total Vehicle Movements (Billions)")
    plt.xlabel("Month")
    plt.xticks(rotation=35, ha="right")
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, height, f"{height:.1f}B", ha="center", va="bottom", fontsize=9)
    savefig(output_dir, "11_total_volume_by_calendar_month.png")

    # ------------------------------------------------------------------
    # 12. COVID/recovery era grouped comparison
    # ------------------------------------------------------------------
    def era_for_year(year: int) -> str:
        if year <= 2019:
            return "Pre-COVID\n2014–2019"
        if year <= 2021:
            return "COVID Era\n2020–2021"
        return "Recovery/Recent\n2022–2026"

    era_df = df.copy()
    era_df["era"] = era_df["year"].apply(era_for_year)
    era_summary = (
        era_df.groupby(["era", "month_of_year", "month_name"], observed=True)
        .agg(avg_daily_volume=("avg_daily_volume", "mean"))
        .reset_index()
        .sort_values(["era", "month_of_year"])
    )

    plt.figure(figsize=(15, 8))
    for era in ["Pre-COVID\n2014–2019", "COVID Era\n2020–2021", "Recovery/Recent\n2022–2026"]:
        edf = era_summary[era_summary["era"] == era]
        plt.plot(edf["month_of_year"], edf["avg_daily_volume"] / 1e6, marker="o", linewidth=2.5, label=era)
    plt.title("Seasonal Traffic Pattern by Era", fontsize=22, weight="bold", pad=18)
    plt.suptitle("Compares pre-COVID, COVID-era, and recovery/recent seasonal traffic behaviour", y=0.94, fontsize=12)
    plt.ylabel("Average Daily Vehicle Movements (Millions)")
    plt.xlabel("Month")
    plt.xticks(range(1, 13), MONTH_ABBR)
    plt.grid(alpha=0.25)
    plt.legend(frameon=False)
    savefig(output_dir, "12_seasonal_pattern_by_era.png")

    print()
    print("Done.")
    print(f"Graphs written to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
