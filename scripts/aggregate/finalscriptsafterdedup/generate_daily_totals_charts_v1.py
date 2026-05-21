#!/usr/bin/env python3
r"""
generate_daily_totals_charts_v1.py

Generates chart images for the completed Daily Totals V3 result.

Input:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\18_daily_total_traffic_line.png
    A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\19_daily_total_traffic_7day_rolling.png
    A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\20_daily_total_traffic_30day_rolling.png
    A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\21_top_50_busiest_days.png
    A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\22_bottom_50_quietest_days.png
    A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\23_daily_totals_by_year_boxplot.png
    A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\24_largest_single_day_changes.png
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals_charts_summary.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
DAILY_CSV = REPORT_DIR / "daily_totals.csv"
DAILY_FINAL_JSON = REPORT_DIR / "daily_totals_final.json"
CHART_DIR = REPORT_DIR / "charts"
SUMMARY_JSON = REPORT_DIR / "daily_totals_charts_summary.json"


def fmt_int(n) -> str:
    if pd.isna(n):
        return "N/A"
    return f"{int(n):,}"


def fmt_billions(n) -> str:
    if pd.isna(n):
        return "N/A"
    return f"{float(n) / 1_000_000_000:.2f}B"


def savefig(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")


def load_daily_totals() -> pd.DataFrame:
    if not DAILY_CSV.exists():
        raise FileNotFoundError(f"Missing input CSV: {DAILY_CSV}")

    df = pd.read_csv(DAILY_CSV)

    # Expected columns from V3:
    # date_local,total_volume,day_elapsed_seconds,completed_at_epoch
    # But this keeps it tolerant if the date column name differs.
    date_col = None
    for candidate in ["date_local", "count_date", "date", "day"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col is None:
        raise ValueError(f"Could not find a date column in {DAILY_CSV}. Columns: {list(df.columns)}")

    volume_col = None
    for candidate in ["total_volume", "daily_total_volume", "day_total_volume", "cleaned_volume"]:
        if candidate in df.columns:
            volume_col = candidate
            break

    if volume_col is None:
        raise ValueError(f"Could not find a volume column in {DAILY_CSV}. Columns: {list(df.columns)}")

    df = df.rename(columns={date_col: "date", volume_col: "total_volume"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["total_volume"] = pd.to_numeric(df["total_volume"], errors="coerce")

    df = df.dropna(subset=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Exclude blank marker rows, but keep real zeroes if they ever exist.
    df_valid = df.dropna(subset=["total_volume"]).copy()
    df_valid["year"] = df_valid["date"].dt.year
    df_valid["month"] = df_valid["date"].dt.to_period("M").astype(str)
    df_valid["weekday"] = df_valid["date"].dt.day_name()
    df_valid["day_of_week_num"] = df_valid["date"].dt.dayofweek
    df_valid["rolling_7d"] = df_valid["total_volume"].rolling(7, min_periods=3).mean()
    df_valid["rolling_30d"] = df_valid["total_volume"].rolling(30, min_periods=10).mean()
    df_valid["daily_change"] = df_valid["total_volume"].diff()
    df_valid["daily_change_abs"] = df_valid["daily_change"].abs()

    return df_valid


def chart_daily_line(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "18_daily_total_traffic_line.png"
    plt.figure(figsize=(16, 7))
    plt.plot(df["date"], df["total_volume"] / 1_000_000)
    plt.title("Melbourne SCATS Daily Total Traffic")
    plt.xlabel("Date")
    plt.ylabel("Cleaned vehicle movements per day (millions)")
    plt.grid(True, alpha=0.3)
    savefig(path)
    return path


def chart_7day_rolling(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "19_daily_total_traffic_7day_rolling.png"
    plt.figure(figsize=(16, 7))
    plt.plot(df["date"], df["total_volume"] / 1_000_000, alpha=0.35, label="Daily total")
    plt.plot(df["date"], df["rolling_7d"] / 1_000_000, linewidth=2.0, label="7-day rolling average")
    plt.title("Melbourne SCATS Daily Traffic with 7-Day Rolling Average")
    plt.xlabel("Date")
    plt.ylabel("Cleaned vehicle movements per day (millions)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    savefig(path)
    return path


def chart_30day_rolling(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "20_daily_total_traffic_30day_rolling.png"
    plt.figure(figsize=(16, 7))
    plt.plot(df["date"], df["total_volume"] / 1_000_000, alpha=0.25, label="Daily total")
    plt.plot(df["date"], df["rolling_30d"] / 1_000_000, linewidth=2.2, label="30-day rolling average")
    plt.title("Melbourne SCATS Daily Traffic with 30-Day Rolling Average")
    plt.xlabel("Date")
    plt.ylabel("Cleaned vehicle movements per day (millions)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    savefig(path)
    return path


def chart_top_50_days(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "21_top_50_busiest_days.png"
    top = df.nlargest(50, "total_volume").copy()
    top = top.sort_values("total_volume", ascending=True)
    labels = top["date"].dt.strftime("%Y-%m-%d")

    plt.figure(figsize=(12, 14))
    plt.barh(labels, top["total_volume"] / 1_000_000)
    plt.title("Top 50 Busiest Melbourne SCATS Days")
    plt.xlabel("Cleaned vehicle movements (millions)")
    plt.ylabel("Date")
    plt.grid(True, axis="x", alpha=0.3)
    savefig(path)
    return path


def chart_bottom_50_days(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "22_bottom_50_quietest_days.png"
    bottom = df.nsmallest(50, "total_volume").copy()
    bottom = bottom.sort_values("total_volume", ascending=False)
    labels = bottom["date"].dt.strftime("%Y-%m-%d")

    plt.figure(figsize=(12, 14))
    plt.barh(labels, bottom["total_volume"] / 1_000_000)
    plt.title("Bottom 50 Quietest Melbourne SCATS Days")
    plt.xlabel("Cleaned vehicle movements (millions)")
    plt.ylabel("Date")
    plt.grid(True, axis="x", alpha=0.3)
    savefig(path)
    return path


def chart_year_boxplot(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "23_daily_totals_by_year_boxplot.png"
    years = sorted(df["year"].unique())
    data = [df.loc[df["year"] == y, "total_volume"] / 1_000_000 for y in years]

    plt.figure(figsize=(15, 7))
    plt.boxplot(data, labels=[str(y) for y in years], showfliers=False)
    plt.title("Daily Traffic Distribution by Year")
    plt.xlabel("Year")
    plt.ylabel("Daily cleaned vehicle movements (millions)")
    plt.grid(True, axis="y", alpha=0.3)
    plt.xticks(rotation=45)
    savefig(path)
    return path


def chart_largest_single_day_changes(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "24_largest_single_day_changes.png"
    changes = df.dropna(subset=["daily_change"]).copy()
    changes = changes.nlargest(30, "daily_change_abs").sort_values("daily_change_abs", ascending=True)

    labels = changes["date"].dt.strftime("%Y-%m-%d")
    values = changes["daily_change"] / 1_000_000

    plt.figure(figsize=(12, 10))
    plt.barh(labels, values)
    plt.title("Largest Single-Day Traffic Changes")
    plt.xlabel("Change from previous day (millions of cleaned vehicle movements)")
    plt.ylabel("Date")
    plt.axvline(0, linewidth=1)
    plt.grid(True, axis="x", alpha=0.3)
    savefig(path)
    return path


def write_summary(df: pd.DataFrame, chart_paths: list[Path]) -> None:
    busiest = df.loc[df["total_volume"].idxmax()]
    quietest = df.loc[df["total_volume"].idxmin()]

    changes = df.dropna(subset=["daily_change"]).copy()
    biggest_rise = changes.loc[changes["daily_change"].idxmax()]
    biggest_fall = changes.loc[changes["daily_change"].idxmin()]

    summary = {
        "metric_name": "daily_totals_charts",
        "input_csv": str(DAILY_CSV),
        "input_final_json": str(DAILY_FINAL_JSON),
        "charts_dir": str(CHART_DIR),
        "charts_created": [str(p) for p in chart_paths],
        "daily_rows_used": int(len(df)),
        "date_range_start": df["date"].min().date().isoformat(),
        "date_range_end": df["date"].max().date().isoformat(),
        "grand_total_volume": int(df["total_volume"].sum()),
        "average_daily_volume": int(round(df["total_volume"].mean())),
        "median_daily_volume": int(round(df["total_volume"].median())),
        "busiest_day": busiest["date"].date().isoformat(),
        "busiest_day_total_volume": int(busiest["total_volume"]),
        "quietest_day": quietest["date"].date().isoformat(),
        "quietest_day_total_volume": int(quietest["total_volume"]),
        "biggest_single_day_rise_date": biggest_rise["date"].date().isoformat(),
        "biggest_single_day_rise": int(biggest_rise["daily_change"]),
        "biggest_single_day_fall_date": biggest_fall["date"].date().isoformat(),
        "biggest_single_day_fall": int(biggest_fall["daily_change"]),
    }

    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote summary JSON: {SUMMARY_JSON}")
    print()
    print("DAILY TOTALS CHART SUMMARY")
    print("=" * 70)
    print(f"Daily rows used       : {fmt_int(summary['daily_rows_used'])}")
    print(f"Date range            : {summary['date_range_start']} to {summary['date_range_end']}")
    print(f"Grand total volume    : {fmt_int(summary['grand_total_volume'])}")
    print(f"Average daily volume  : {fmt_int(summary['average_daily_volume'])}")
    print(f"Median daily volume   : {fmt_int(summary['median_daily_volume'])}")
    print(f"Busiest day           : {summary['busiest_day']} ({fmt_int(summary['busiest_day_total_volume'])})")
    print(f"Quietest day          : {summary['quietest_day']} ({fmt_int(summary['quietest_day_total_volume'])})")
    print(f"Biggest daily rise    : {summary['biggest_single_day_rise_date']} ({fmt_int(summary['biggest_single_day_rise'])})")
    print(f"Biggest daily fall    : {summary['biggest_single_day_fall_date']} ({fmt_int(summary['biggest_single_day_fall'])})")
    print("=" * 70)


def main() -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("GENERATE DAILY TOTALS CHARTS V1")
    print("=" * 80)
    print(f"Input CSV      : {DAILY_CSV}")
    print(f"Input JSON     : {DAILY_FINAL_JSON}")
    print(f"Output charts  : {CHART_DIR}")
    print("=" * 80)

    df = load_daily_totals()

    chart_paths = [
        chart_daily_line(df),
        chart_7day_rolling(df),
        chart_30day_rolling(df),
        chart_top_50_days(df),
        chart_bottom_50_days(df),
        chart_year_boxplot(df),
        chart_largest_single_day_changes(df),
    ]

    write_summary(df, chart_paths)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
