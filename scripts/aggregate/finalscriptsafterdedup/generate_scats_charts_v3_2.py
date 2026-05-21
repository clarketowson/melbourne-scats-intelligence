#!/usr/bin/env python3
"""
generate_scats_charts_v3_2.py

CSV-only chart generator for the Melbourne SCATS unified reporting workflow.
It reads completed V3 CSV outputs and writes publication-ready PNG charts plus
CSV summaries and a chart_manifest.json file.

V3.2 improvements:
  - Forces SCATS site IDs to integer-only string labels with no decimals.
  - Improves Top 20 SCATS Sites bar labels and x-axis readability.

V3.1 improvements:
  - Fixes horizontal bar chart axes so category labels are never formatted as millions.
  - Makes Top 20 SCATS Sites x-axis meaningful with million-unit ticks and end labels.

V3 improvements:
  - Keeps the V2 2018-12 broken-line data-gap handling and annotation.
  - Applies a semantic, publication-friendly colour scheme so charts are easier
    to scan and do not all appear as default matplotlib blue.
  - Uses consistent colours for total traffic, rolling averages, growth,
    disruption, AM peak, PM peak, off-peak, seasonality, rankings, and quiet periods.

Default input directory:
  A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped

Default output directory:
  A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\charts
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


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
KNOWN_DATA_GAP_MONTHS = {"2018-12"}


# Semantic chart palette. Keep these stable so colours have consistent meaning
# across the public-facing chart set.
PALETTE = {
    "traffic": "#1f4e79",
    "traffic_light": "#5b9bd5",
    "rolling": "#f28e2b",
    "growth_pos": "#2ca02c",
    "growth_neg": "#d62728",
    "disruption": "#c44e52",
    "am_peak": "#7b5fc9",
    "pm_peak": "#17a2a8",
    "off_peak": "#9aa0a6",
    "seasonality": "#d4a017",
    "ranking": "#4e79a7",
    "quiet": "#9e9e9e",
    "processing": "#6f4e7c",
    "gap": "#555555",
}


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


def first_existing(df: pd.DataFrame, names: Iterable[str]) -> Optional[str]:
    for name in names:
        if name in df.columns:
            return name
    return None


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

    out["is_known_data_gap"] = out["month_label"].isin(KNOWN_DATA_GAP_MONTHS)
    out["is_zero_volume"] = out["volume"].eq(0)
    out["volume_for_chart"] = out["volume"].astype(float)
    out.loc[out["is_known_data_gap"] & out["is_zero_volume"], "volume_for_chart"] = np.nan

    return out[["month_label", "month", "year", "volume", "volume_for_chart", "is_known_data_gap", "is_zero_volume"]]


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
    """Format a vertical chart y-axis in millions."""
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000:.0f}M")


def x_millions_axis(ax) -> None:
    """Format a horizontal chart x-axis in millions."""
    ax.xaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000:.0f}M")


def x_billions_axis(ax) -> None:
    """Format a horizontal chart x-axis in billions."""
    ax.xaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000_000:.1f}B")


def rotate_x(degrees: int = 45) -> None:
    plt.xticks(rotation=degrees, ha="right")


def annotate_monthly_data_gaps(ax, monthly: pd.DataFrame, y_col: str = "volume_for_chart") -> None:
    if "is_known_data_gap" not in monthly.columns or y_col not in monthly.columns:
        return
    gaps = monthly[monthly["is_known_data_gap"] == True].copy()
    visible = monthly[y_col].dropna()
    if gaps.empty or visible.empty:
        return
    y_mid = visible.median()
    for _, row in gaps.iterrows():
        ax.axvline(row["month"], linestyle="--", linewidth=1.2, alpha=0.7, color=PALETTE["gap"])
        ax.annotate(
            f"Data gap\n{row['month_label']}",
            xy=(row["month"], y_mid),
            xytext=(10, 30),
            textcoords="offset points",
            arrowprops={"arrowstyle": "->", "lw": 1, "alpha": 0.75},
            fontsize=9,
            ha="left",
            va="center",
            bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "0.7", "alpha": 0.9},
        )


def format_site_id(value) -> Optional[str]:
    """Return a SCATS site ID as an integer-only string, never as 4415.0."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
        if np.isfinite(number) and number.is_integer():
            return str(int(number))
    except Exception:
        pass
    if re.fullmatch(r"\d+", text):
        return text
    text = re.sub(r"\.0$", "", text)
    return text

def add_gap_note(ax) -> None:
    ax.text(
        0.01,
        0.01,
        "Known zero-volume source gap shown as broken line: 2018-12",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
        ha="left",
        alpha=0.75,
    )


def chart_monthly_totals(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(monthly["month"], monthly["volume_for_chart"], linewidth=2.2, color=PALETTE["traffic"])
    annotate_monthly_data_gaps(ax, monthly)
    add_gap_note(ax)
    billions_axis(ax)
    path = out_dir / "01_monthly_total_traffic_line.png"
    save_fig(path, "Melbourne SCATS Monthly Cleaned Traffic Volume", "Month", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Monthly total traffic line chart", "source": "monthly_totals", "gap_handling": "2018-12 shown as a broken line and annotated"})

    chartable = monthly.copy()
    if chartable["volume_for_chart"].notna().sum() >= 6:
        chartable["rolling_6_month_avg"] = chartable["volume_for_chart"].rolling(6, min_periods=1).mean()
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.plot(chartable["month"], chartable["volume_for_chart"], linewidth=1.4, label="Monthly total", color=PALETTE["traffic_light"])
        ax.plot(chartable["month"], chartable["rolling_6_month_avg"], linewidth=2.6, label="6-month rolling average", color=PALETTE["rolling"])
        annotate_monthly_data_gaps(ax, chartable)
        add_gap_note(ax)
        ax.legend()
        billions_axis(ax)
        path = out_dir / "02_monthly_total_traffic_with_rolling_average.png"
        save_fig(path, "Monthly Traffic With 6-Month Rolling Average", "Month", "Cleaned vehicle movements")
        manifest.append({"file": path.name, "title": "Monthly totals with rolling average", "source": "monthly_totals", "gap_handling": "2018-12 shown as a broken line and annotated"})


def chart_yearly_totals(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    yearly = monthly.groupby("year", as_index=False)["volume"].sum()
    yearly.to_csv(out_dir / "yearly_totals_from_monthly.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(yearly["year"].astype(str), yearly["volume"], color=PALETTE["ranking"])
    if monthly["is_known_data_gap"].any():
        ax.text(0.01, 0.01, "Note: 2018 includes known missing month 2018-12.", transform=ax.transAxes, fontsize=8, va="bottom", ha="left", alpha=0.75)
    billions_axis(ax)
    rotate_x(45)
    path = out_dir / "03_yearly_total_traffic_bar.png"
    save_fig(path, "Yearly Cleaned Traffic Volume", "Year", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Yearly total traffic bar chart", "source": "monthly_totals", "gap_handling": "2018 yearly total includes the known missing month as raw zero and is annotated"})

    full_years = yearly[yearly["year"] < yearly["year"].max()].copy()
    full_years["yoy_pct_change"] = full_years["volume"].pct_change() * 100
    full_years.to_csv(out_dir / "yearly_growth_from_monthly.csv", index=False)
    if len(full_years.dropna(subset=["yoy_pct_change"])) >= 2:
        fig, ax = plt.subplots(figsize=(12, 7))
        ax.bar(full_years["year"].astype(str), full_years["yoy_pct_change"], color=[PALETTE["growth_pos"] if v >= 0 else PALETTE["growth_neg"] for v in full_years["yoy_pct_change"].fillna(0)])
        ax.axhline(0, linewidth=1, color=PALETTE["gap"], alpha=0.8)
        ax.text(0.01, 0.01, "2018/2019 affected by known missing month 2018-12.", transform=ax.transAxes, fontsize=8, va="bottom", ha="left", alpha=0.75)
        rotate_x(45)
        path = out_dir / "04_yearly_growth_rate_bar.png"
        save_fig(path, "Year-on-Year Traffic Growth", "Year", "Growth vs previous year (%)")
        manifest.append({"file": path.name, "title": "Year-on-year traffic growth", "source": "monthly_totals", "gap_handling": "2018/2019 growth affected by known 2018-12 gap and annotated"})


def chart_covid_period(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    covid = monthly[(monthly["month"] >= "2019-01-01") & (monthly["month"] <= "2022-12-01")].copy()
    if covid.empty:
        return
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.plot(covid["month"], covid["volume_for_chart"], linewidth=2.2, color=PALETTE["disruption"])
    billions_axis(ax)
    path = out_dir / "05_covid_disruption_and_recovery_monthly.png"
    save_fig(path, "COVID-Era Traffic Disruption and Recovery", "Month", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "COVID disruption and recovery", "source": "monthly_totals"})


def chart_seasonality(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    chartable = monthly.dropna(subset=["volume_for_chart"]).copy()
    if chartable.empty:
        return
    chartable["month_of_year"] = chartable["month"].dt.month
    season = chartable.groupby("month_of_year", as_index=False)["volume_for_chart"].mean().rename(columns={"volume_for_chart": "volume"})
    season["month_name"] = pd.to_datetime(season["month_of_year"], format="%m").dt.strftime("%b")
    season.to_csv(out_dir / "monthly_seasonality_average.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(season["month_name"], season["volume"], color=PALETTE["seasonality"])
    billions_axis(ax)
    path = out_dir / "06_average_month_by_seasonality.png"
    save_fig(path, "Average Traffic by Month of Year", "Month", "Average cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Monthly seasonality", "source": "monthly_totals", "gap_handling": "Known data-gap months excluded from monthly averages"})


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
    ax.plot(d["month"], d["am_share"], linewidth=2.2, label="AM peak share", color=PALETTE["am_peak"])
    ax.plot(d["month"], d["pm_share"], linewidth=2.2, label="PM peak share", color=PALETTE["pm_peak"])
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
            ax.bar(["AM peak\n07:00-10:00", "PM peak\n16:00-19:00", "Other hours"], [am, pm, off], color=[PALETTE["am_peak"], PALETTE["pm_peak"], PALETTE["off_peak"]])
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
    ax.plot(agg["time_bin"], agg["avg_daily_volume"], linewidth=2.2, color=PALETTE["traffic"])
    ax.set_xticks(range(0, len(agg), 4))
    ax.set_xticklabels(agg["time_bin"].iloc[::4], rotation=45, ha="right")
    millions_axis(ax)
    path = out_dir / "09_average_daily_traffic_by_time_of_day.png"
    save_fig(path, "Average Daily Traffic by 15-Minute Time Bin", "Time of day", "Average daily cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Average daily traffic by time of day", "source": "chunked_busiest_time_bin_monthly"})

    top = agg.sort_values("avg_daily_volume", ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(top["time_bin"], top["avg_daily_volume"], color=PALETTE["ranking"])
    millions_axis(ax)
    path = out_dir / "10_top_10_busiest_time_bins.png"
    save_fig(path, "Top 10 Busiest 15-Minute Time Bins", "Time bin", "Average daily cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Top 10 busiest time bins", "source": "chunked_busiest_time_bin_monthly"})

    quiet = agg.sort_values("avg_daily_volume", ascending=True).head(10)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(quiet["time_bin"], quiet["avg_daily_volume"], color=PALETTE["quiet"])
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
    ax.barh(top["date_label"] + "\n" + top["day_name"], top["volume"], color=PALETTE["ranking"])
    x_millions_axis(ax)
    ax.set_xlim(0, top["volume"].max() * 1.08)
    for y, v in enumerate(top["volume"]):
        ax.text(v, y, f" {v/1_000_000:.1f}M", va="center", fontsize=8, color="#27364a")
    path = out_dir / "12_top_10_busiest_days.png"
    save_fig(path, "Top 10 Busiest Recorded Days", "Cleaned vehicle movements (millions)", "Date")
    manifest.append({"file": path.name, "title": "Top 10 busiest days", "source": "chunked_busiest_day_monthly"})

    d["year"] = d["count_date"].dt.year
    idx = d.groupby("year")["volume"].idxmax()
    by_year = d.loc[idx].copy().sort_values("year")
    by_year["date_label"] = by_year["count_date"].dt.strftime("%Y-%m-%d")
    by_year.to_csv(out_dir / "busiest_day_by_year.csv", index=False)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(by_year["year"].astype(str), by_year["volume"], color=PALETTE["ranking"])
    millions_axis(ax)
    rotate_x(45)
    path = out_dir / "13_busiest_day_by_year.png"
    save_fig(path, "Busiest Day Volume by Year", "Year", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Busiest day by year", "source": "chunked_busiest_day_monthly"})

    weekday = d.groupby(d["count_date"].dt.day_name(), as_index=True)["volume"].mean()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weekday.reindex(order).dropna()
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(weekday.index, weekday.values, color=PALETTE["traffic"])
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

    # SCATS site IDs are identifiers, not measured quantities. Force them to
    # integer-only string labels so matplotlib/pandas can never render them as
    # floats such as 4415.0 or apply million-format tick labels to them.
    d["site"] = d["scats_site"].map(format_site_id)
    d = d.dropna(subset=["site"]).copy()
    d["volume"] = pd.to_numeric(d["month_site_volume"], errors="coerce").fillna(0)

    sites = d.groupby("site", as_index=False)["volume"].sum().sort_values("volume", ascending=False)
    sites.to_csv(out_dir / "site_totals_from_monthly.csv", index=False)
    if sites.empty:
        return

    top = sites.head(20).sort_values("volume").copy()
    top["site_label"] = "Site " + top["site"].map(format_site_id)

    fig, ax = plt.subplots(figsize=(14, 9.5))
    bars = ax.barh(top["site_label"], top["volume"], color=PALETTE["ranking"])
    x_millions_axis(ax)
    ax.set_xlim(0, top["volume"].max() * 1.14)

    for bar, v in zip(bars, top["volume"]):
        ax.text(
            v + top["volume"].max() * 0.008,
            bar.get_y() + bar.get_height() / 2,
            f"{v/1_000_000:.1f}M",
            va="center",
            fontsize=9,
            color="#27364a",
        )

    ax.text(
        0.01,
        0.01,
        "Site labels are integer SCATS site IDs. X-axis and bar labels show total cleaned vehicle movements in millions.",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
        ha="left",
        alpha=0.75,
    )
    path = out_dir / "15_top_20_busiest_scats_sites.png"
    save_fig(path, "Top 20 Busiest SCATS Sites", "Total cleaned vehicle movements (millions)", "SCATS site ID")
    manifest.append({"file": path.name, "title": "Top 20 busiest SCATS sites", "source": "chunked_busiest_site_monthly", "axis_fix": "V3.2 forces integer-only site IDs and formats vehicle volumes in millions"})

    if "month_label" in d.columns:
        top_site = format_site_id(sites.iloc[0]["site"])
        ts = d[d["site"] == top_site].copy()
        ts = ts[ts["month_label"].astype(str).str.match(MONTH_RE, na=False)]
        ts["month"] = pd.to_datetime(ts["month_label"] + "-01", errors="coerce")
        ts = ts.sort_values("month")
        if not ts.empty:
            fig, ax = plt.subplots(figsize=(14, 7))
            ax.plot(ts["month"], ts["volume"], linewidth=2.2, color=PALETTE["traffic"])
            millions_axis(ax)
            path = out_dir / "16_busiest_site_monthly_trend.png"
            save_fig(path, f"Monthly Trend for Busiest SCATS Site {top_site}", "Month", "Cleaned vehicle movements")
            manifest.append({"file": path.name, "title": "Monthly trend for busiest SCATS site", "source": "chunked_busiest_site_monthly", "site_id_format": "integer string"})


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
    ax.barh(proc["source"], proc["total_hours"], color=PALETTE["processing"])
    ax.set_xlim(0, proc["total_hours"].max() * 1.10)
    for y, v in enumerate(proc["total_hours"]):
        ax.text(v, y, f" {v:.1f}h", va="center", fontsize=8, color="#27364a")
    path = out_dir / "17_processing_time_by_completed_csv.png"
    save_fig(path, "Processing Time Represented by Completed CSVs", "Hours", "")
    manifest.append({"file": path.name, "title": "Processing time by completed CSV", "source": "all CSVs with month_elapsed_seconds"})


def write_manifest(out_dir: Path, manifest: List[dict], source_paths: Dict[str, str]) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "chart_count": len(manifest),
        "gap_handling": "Known data-gap month 2018-12 is retained but plotted as NaN/broken line in monthly charts.",
        "colour_scheme": PALETTE,
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
        "axes.edgecolor": "#c9d3df",
        "axes.labelcolor": "#27364a",
        "axes.titlecolor": "#1f2d3d",
        "axes.titlesize": 16,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "xtick.color": "#4b5563",
        "ytick.color": "#4b5563",
        "grid.color": "#d9e2ec",
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
