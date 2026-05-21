#!/usr/bin/env python3
"""
generate_scats_charts_v1.py

CSV-only chart generator for the Melbourne SCATS unified reporting workflow.
It reads completed V3 CSV outputs and writes publication-ready PNG charts plus
CSV summaries and a chart_manifest.json file.

Default input directory:
  A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped

Default output directory:
  A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\charts

Example:
  python generate_scats_charts_v1.py
  python generate_scats_charts_v1.py --input-dir A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped --output-dir A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\charts
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_INPUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "charts"

CSV_CANDIDATES = {
    "monthly_totals": ["monthly_totals.csv", "chunked_total_cleaned_volume_monthly.csv"],
    "total_cleaned_volume": ["chunked_total_cleaned_volume_monthly.csv", "monthly_totals.csv"],
    "busiest_day_monthly": ["chunked_busiest_day_monthly.csv"],
    "busiest_site_monthly": ["chunked_busiest_site_monthly.csv"],
    "busiest_time_bin_monthly": ["chunked_busiest_time_bin_monthly.csv"],
    "peak_shares_monthly": ["chunked_peak_shares_monthly.csv"],
    "headline_metrics": ["headline_metrics.csv"],
    "distinct_sites": ["distinct_sites.csv"],
}

MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def read_csv_if_exists(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"WARNING: could not read {path}: {exc}")
        return None


def find_csv(input_dir: Path, candidates: Iterable[str]) -> Optional[Path]:
    for name in candidates:
        path = input_dir / name
        if path.exists():
            return path

    # Also accept browser/download suffixes such as monthly_totals(2).csv
    # while still preferring the clean production filenames above.
    for name in candidates:
        stem = Path(name).stem
        matches = sorted(input_dir.glob(f"{stem}*.csv"))
        if matches:
            return matches[0]

    return None


def load_sources(input_dir: Path) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str]]:
    data: Dict[str, pd.DataFrame] = {}
    paths: Dict[str, str] = {}
    for key, candidates in CSV_CANDIDATES.items():
        path = find_csv(input_dir, candidates)
        if path is None:
            continue
        df = read_csv_if_exists(path)
        if df is not None:
            data[key] = df
            paths[key] = str(path)
            print(f"Loaded {key}: {path.name} ({len(df):,} rows)")
    return data, paths


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def clean_monthly(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "month_label" not in out.columns:
        raise ValueError("Monthly CSV must contain month_label")
    volume_col = first_existing(out, ["month_total_volume", "month_total_cleaned_volume"])
    if volume_col is None:
        raise ValueError("Monthly CSV must contain month_total_volume or month_total_cleaned_volume")
    out = out[out["month_label"].astype(str).str.match(MONTH_RE, na=False)].copy()
    out["month"] = pd.to_datetime(out["month_label"] + "-01", errors="coerce")
    out["volume"] = pd.to_numeric(out[volume_col], errors="coerce").fillna(0)
    out = out.dropna(subset=["month"]).sort_values("month")
    out["year"] = out["month"].dt.year
    return out[["month_label", "month", "year", "volume"]]


def first_existing(df: pd.DataFrame, names: Iterable[str]) -> Optional[str]:
    for name in names:
        if name in df.columns:
            return name
    return None


def save_fig(path: Path, title: str, xlabel: str = "", ylabel: str = "") -> None:
    plt.title(title)
    if xlabel:
        plt.xlabel(xlabel)
    if ylabel:
        plt.ylabel(ylabel)
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote {path}")


def billions_axis(ax) -> None:
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000_000:.1f}B")


def millions_axis(ax) -> None:
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000:.0f}M")


def rotate_x(degrees: int = 45) -> None:
    plt.xticks(rotation=degrees, ha="right")


def chart_monthly_totals(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(monthly["month"], monthly["volume"], linewidth=2)
    billions_axis(ax)
    path = out_dir / "01_monthly_total_traffic_line.png"
    save_fig(path, "Melbourne SCATS Monthly Cleaned Traffic Volume", "Month", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Monthly total traffic line chart", "source": "monthly_totals"})

    nonzero = monthly[monthly["volume"] > 0].copy()
    if len(nonzero) >= 6:
        nonzero["rolling_6_month_avg"] = nonzero["volume"].rolling(6, min_periods=1).mean()
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.plot(nonzero["month"], nonzero["volume"], linewidth=1.4, label="Monthly total")
        ax.plot(nonzero["month"], nonzero["rolling_6_month_avg"], linewidth=2.4, label="6-month rolling average")
        ax.legend()
        billions_axis(ax)
        path = out_dir / "02_monthly_total_traffic_with_rolling_average.png"
        save_fig(path, "Monthly Traffic With 6-Month Rolling Average", "Month", "Cleaned vehicle movements")
        manifest.append({"file": path.name, "title": "Monthly totals with rolling average", "source": "monthly_totals"})


def chart_yearly_totals(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    yearly = monthly.groupby("year", as_index=False)["volume"].sum()
    yearly.to_csv(out_dir / "yearly_totals_from_monthly.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(yearly["year"].astype(str), yearly["volume"])
    billions_axis(ax)
    rotate_x(45)
    path = out_dir / "03_yearly_total_traffic_bar.png"
    save_fig(path, "Yearly Cleaned Traffic Volume", "Year", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Yearly total traffic bar chart", "source": "monthly_totals"})

    full_years = yearly[yearly["year"] < yearly["year"].max()].copy()
    full_years["yoy_pct_change"] = full_years["volume"].pct_change() * 100
    full_years.to_csv(out_dir / "yearly_growth_from_monthly.csv", index=False)
    if len(full_years.dropna(subset=["yoy_pct_change"])) >= 2:
        fig, ax = plt.subplots(figsize=(12, 7))
        ax.bar(full_years["year"].astype(str), full_years["yoy_pct_change"])
        ax.axhline(0, linewidth=1)
        rotate_x(45)
        path = out_dir / "04_yearly_growth_rate_bar.png"
        save_fig(path, "Year-on-Year Traffic Growth", "Year", "Growth vs previous year (%)")
        manifest.append({"file": path.name, "title": "Year-on-year traffic growth", "source": "monthly_totals"})


def chart_covid_period(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    covid = monthly[(monthly["month"] >= "2019-01-01") & (monthly["month"] <= "2022-12-01")].copy()
    if covid.empty:
        return
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.plot(covid["month"], covid["volume"], linewidth=2)
    billions_axis(ax)
    path = out_dir / "05_covid_disruption_and_recovery_monthly.png"
    save_fig(path, "COVID-Era Traffic Disruption and Recovery", "Month", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "COVID disruption and recovery", "source": "monthly_totals"})


def chart_seasonality(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    nonzero = monthly[monthly["volume"] > 0].copy()
    if nonzero.empty:
        return
    nonzero["month_of_year"] = nonzero["month"].dt.month
    season = nonzero.groupby("month_of_year", as_index=False)["volume"].mean()
    season["month_name"] = pd.to_datetime(season["month_of_year"], format="%m").dt.strftime("%b")
    season.to_csv(out_dir / "monthly_seasonality_average.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(season["month_name"], season["volume"])
    billions_axis(ax)
    path = out_dir / "06_average_month_by_seasonality.png"
    save_fig(path, "Average Traffic by Month of Year", "Month", "Average cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Monthly seasonality", "source": "monthly_totals"})


def chart_peak_shares(df: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    required = {"month_label", "month_am_share_pct", "month_pm_share_pct"}
    if not required.issubset(df.columns):
        return
    d = df.copy()
    d = d[d["month_label"].astype(str).str.match(MONTH_RE, na=False)]
    d["month"] = pd.to_datetime(d["month_label"] + "-01", errors="coerce")
    d["am_share"] = pd.to_numeric(d["month_am_share_pct"], errors="coerce")
    d["pm_share"] = pd.to_numeric(d["month_pm_share_pct"], errors="coerce")
    d = d.dropna(subset=["month"]).sort_values("month")
    if d.empty:
        return

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(d["month"], d["am_share"], linewidth=2, label="AM peak share")
    ax.plot(d["month"], d["pm_share"], linewidth=2, label="PM peak share")
    ax.legend()
    path = out_dir / "07_am_pm_peak_share_over_time.png"
    save_fig(path, "AM vs PM Peak Share Over Time", "Month", "Share of monthly traffic (%)")
    manifest.append({"file": path.name, "title": "AM and PM peak share over time", "source": "chunked_peak_shares_monthly"})

    total_col = first_existing(d, ["month_total_volume"])
    am_col = first_existing(df, ["month_am_volume"])
    pm_col = first_existing(df, ["month_pm_volume"])
    if total_col and am_col and pm_col:
        total = pd.to_numeric(df[total_col], errors="coerce").sum()
        am = pd.to_numeric(df[am_col], errors="coerce").sum()
        pm = pd.to_numeric(df[pm_col], errors="coerce").sum()
        off = max(total - am - pm, 0)
        if total > 0:
            fig, ax = plt.subplots(figsize=(10, 7))
            ax.bar(["AM peak\n07:00-10:00", "PM peak\n16:00-19:00", "Other hours"], [am, pm, off])
            billions_axis(ax)
            path = out_dir / "08_peak_vs_off_peak_volume_bar.png"
            save_fig(path, "Peak vs Off-Peak Cleaned Traffic Volume", "Period", "Cleaned vehicle movements")
            manifest.append({"file": path.name, "title": "Peak vs off-peak volume", "source": "chunked_peak_shares_monthly"})


def chart_time_bins(df: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    required = {"time_bin", "month_time_bin_volume", "month_distinct_dates"}
    if not required.issubset(df.columns):
        return
    d = df.copy()
    d["volume"] = pd.to_numeric(d["month_time_bin_volume"], errors="coerce").fillna(0)
    d["dates"] = pd.to_numeric(d["month_distinct_dates"], errors="coerce").fillna(0)
    d = d[d["time_bin"].astype(str).str.match(r"^\d{2}:\d{2}$", na=False)]
    agg = d.groupby("time_bin", as_index=False).agg(total_volume=("volume", "sum"), distinct_dates=("dates", "sum"))
    agg = agg[agg["distinct_dates"] > 0]
    agg["avg_daily_volume"] = agg["total_volume"] / agg["distinct_dates"]
    agg = agg.sort_values("time_bin")
    agg.to_csv(out_dir / "time_bin_profile_aggregated.csv", index=False)
    if agg.empty:
        return

    fig, ax = plt.subplots(figsize=(15, 7))
    ax.plot(agg["time_bin"], agg["avg_daily_volume"], linewidth=2)
    ax.set_xticks(range(0, len(agg), 4))
    ax.set_xticklabels(agg["time_bin"].iloc[::4], rotation=45, ha="right")
    millions_axis(ax)
    path = out_dir / "09_average_daily_traffic_by_time_of_day.png"
    save_fig(path, "Average Daily Traffic by 15-Minute Time Bin", "Time of day", "Average daily cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Average daily traffic by time of day", "source": "chunked_busiest_time_bin_monthly"})

    top = agg.sort_values("avg_daily_volume", ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(top["time_bin"], top["avg_daily_volume"])
    millions_axis(ax)
    path = out_dir / "10_top_10_busiest_time_bins.png"
    save_fig(path, "Top 10 Busiest 15-Minute Time Bins", "Time bin", "Average daily cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Top 10 busiest time bins", "source": "chunked_busiest_time_bin_monthly"})

    quiet = agg.sort_values("avg_daily_volume", ascending=True).head(10)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(quiet["time_bin"], quiet["avg_daily_volume"])
    path = out_dir / "11_top_10_quietest_time_bins.png"
    save_fig(path, "Top 10 Quietest 15-Minute Time Bins", "Time bin", "Average daily cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Top 10 quietest time bins", "source": "chunked_busiest_time_bin_monthly"})


def chart_busiest_days(df: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    required = {"count_date", "day_total_volume"}
    if not required.issubset(df.columns):
        return
    d = df.copy()
    d["count_date"] = pd.to_datetime(d["count_date"], errors="coerce")
    d["volume"] = pd.to_numeric(d["day_total_volume"], errors="coerce").fillna(0)
    d = d.dropna(subset=["count_date"])
    if d.empty:
        return
    daily = d.groupby("count_date", as_index=False)["volume"].sum().sort_values("volume", ascending=False)
    daily["date_label"] = daily["count_date"].dt.strftime("%Y-%m-%d")
    daily["day_name"] = daily["count_date"].dt.day_name()
    daily.head(50).to_csv(out_dir / "top_50_busiest_days.csv", index=False)

    top = daily.head(10).sort_values("volume")
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(top["date_label"] + "\n" + top["day_name"], top["volume"])
    millions_axis(ax)
    path = out_dir / "12_top_10_busiest_days.png"
    save_fig(path, "Top 10 Busiest Recorded Days", "Cleaned vehicle movements", "")
    manifest.append({"file": path.name, "title": "Top 10 busiest days", "source": "chunked_busiest_day_monthly"})

    d["year"] = d["count_date"].dt.year
    idx = d.groupby("year")["volume"].idxmax()
    by_year = d.loc[idx].copy().sort_values("year")
    by_year["date_label"] = by_year["count_date"].dt.strftime("%Y-%m-%d")
    by_year.to_csv(out_dir / "busiest_day_by_year.csv", index=False)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(by_year["year"].astype(str), by_year["volume"])
    millions_axis(ax)
    rotate_x(45)
    path = out_dir / "13_busiest_day_by_year.png"
    save_fig(path, "Busiest Day Volume by Year", "Year", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Busiest day by year", "source": "chunked_busiest_day_monthly"})

    weekday = d.groupby(d["count_date"].dt.day_name(), as_index=True)["volume"].mean()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weekday.reindex(order).dropna()
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(weekday.index, weekday.values)
    millions_axis(ax)
    rotate_x(30)
    path = out_dir / "14_average_daily_volume_by_weekday.png"
    save_fig(path, "Average Daily Traffic by Day of Week", "Day", "Average cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Average daily volume by weekday", "source": "chunked_busiest_day_monthly"})


def chart_busiest_sites(df: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    required = {"scats_site", "month_site_volume"}
    if not required.issubset(df.columns):
        return
    d = df.copy()
    d["site"] = d["scats_site"].astype(str)
    d["volume"] = pd.to_numeric(d["month_site_volume"], errors="coerce").fillna(0)
    sites = d.groupby("site", as_index=False)["volume"].sum().sort_values("volume", ascending=False)
    sites.to_csv(out_dir / "site_totals_from_monthly.csv", index=False)
    if sites.empty:
        return

    top = sites.head(20).sort_values("volume")
    fig, ax = plt.subplots(figsize=(12, 9))
    ax.barh(top["site"], top["volume"])
    millions_axis(ax)
    path = out_dir / "15_top_20_busiest_scats_sites.png"
    save_fig(path, "Top 20 Busiest SCATS Sites", "Cleaned vehicle movements", "SCATS site")
    manifest.append({"file": path.name, "title": "Top 20 busiest SCATS sites", "source": "chunked_busiest_site_monthly"})

    if "month_label" in d.columns:
        top_site = sites.iloc[0]["site"]
        ts = d[d["site"] == top_site].copy()
        ts = ts[ts["month_label"].astype(str).str.match(MONTH_RE, na=False)]
        ts["month"] = pd.to_datetime(ts["month_label"] + "-01", errors="coerce")
        ts = ts.sort_values("month")
        if not ts.empty:
            fig, ax = plt.subplots(figsize=(14, 7))
            ax.plot(ts["month"], ts["volume"], linewidth=2)
            millions_axis(ax)
            path = out_dir / "16_busiest_site_monthly_trend.png"
            save_fig(path, f"Monthly Trend for Busiest SCATS Site {top_site}", "Month", "Cleaned vehicle movements")
            manifest.append({"file": path.name, "title": "Monthly trend for busiest SCATS site", "source": "chunked_busiest_site_monthly"})


def chart_processing_time(data: Dict[str, pd.DataFrame], out_dir: Path, manifest: List[dict]) -> None:
    rows = []
    for key, df in data.items():
        elapsed_col = first_existing(df, ["month_elapsed_seconds"])
        if elapsed_col is None or "month_label" not in df.columns:
            continue
        tmp = df[["month_label", elapsed_col]].drop_duplicates().copy()
        tmp["elapsed_seconds"] = pd.to_numeric(tmp[elapsed_col], errors="coerce")
        tmp = tmp.dropna(subset=["elapsed_seconds"])
        if not tmp.empty:
            rows.append({"source": key, "total_hours": tmp["elapsed_seconds"].sum() / 3600, "months_or_batches": len(tmp)})
    if not rows:
        return
    proc = pd.DataFrame(rows).sort_values("total_hours", ascending=False)
    proc.to_csv(out_dir / "processing_time_summary.csv", index=False)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(proc["source"], proc["total_hours"])
    path = out_dir / "17_processing_time_by_completed_csv.png"
    save_fig(path, "Processing Time Represented by Completed CSVs", "Hours", "")
    manifest.append({"file": path.name, "title": "Processing time by completed CSV", "source": "all CSVs with month_elapsed_seconds"})


def write_manifest(out_dir: Path, manifest: List[dict], source_paths: Dict[str, str]) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "chart_count": len(manifest),
        "source_paths": source_paths,
        "charts": manifest,
    }
    path = out_dir / "chart_manifest.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SCATS charts from completed CSV outputs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir or (input_dir / "charts")
    ensure_dir(output_dir)

    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.titlesize": 16,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 10,
    })

    data, paths = load_sources(input_dir)
    manifest: List[dict] = []

    monthly_source = data.get("monthly_totals")
    if monthly_source is None:
        monthly_source = data.get("total_cleaned_volume")
    if monthly_source is not None:
        monthly = clean_monthly(monthly_source)
        monthly.to_csv(output_dir / "monthly_totals_cleaned_for_charts.csv", index=False)
        chart_monthly_totals(monthly, output_dir, manifest)
        chart_yearly_totals(monthly, output_dir, manifest)
        chart_covid_period(monthly, output_dir, manifest)
        chart_seasonality(monthly, output_dir, manifest)
    else:
        print("WARNING: monthly totals CSV not found; skipping monthly/yearly charts")

    if "peak_shares_monthly" in data:
        chart_peak_shares(data["peak_shares_monthly"], output_dir, manifest)
    else:
        print("WARNING: peak shares CSV not found; skipping peak-share charts")

    if "busiest_time_bin_monthly" in data:
        chart_time_bins(data["busiest_time_bin_monthly"], output_dir, manifest)
    else:
        print("WARNING: time-bin CSV not found; skipping time-of-day charts")

    if "busiest_day_monthly" in data:
        chart_busiest_days(data["busiest_day_monthly"], output_dir, manifest)
    else:
        print("WARNING: busiest-day CSV not found; skipping busiest-day charts")

    if "busiest_site_monthly" in data:
        chart_busiest_sites(data["busiest_site_monthly"], output_dir, manifest)
    else:
        print("WARNING: busiest-site CSV not found; skipping busiest-site charts")

    chart_processing_time(data, output_dir, manifest)
    write_manifest(output_dir, manifest, paths)

    print("\nDONE")
    print(f"Charts written to: {output_dir}")
    print(f"Chart count: {len(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
