#!/usr/bin/env python3
r"""
generate_weekday_weekend_chartsV2.py

Creates polished, media-ready weekday/weekend traffic charts from:
  - weekday_weekend_split.csv
  - weekday_weekend_split_final.json

V2 upgrades over V1:
  - cleaner titles and subtitles
  - consistent dashboard-style typography
  - light card-like chart backgrounds
  - stronger labels, legends, annotations and footers
  - improved colour coding: weekday blue, weekend orange, total charcoal, COVID soft red
  - adds one full dashboard infographic PNG as well as individual charts

Example:
    python generate_weekday_weekend_chartsV2.py ^
      --csv A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_weekend_split.csv ^
      --json A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_weekend_split_final.json ^
      --out A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\weekday_weekend_v2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Design system
# -----------------------------------------------------------------------------
BRAND = {
    "weekday": "#0B5FA5",       # institutional / workweek blue
    "weekend": "#FF8C1A",       # warm leisure / weekend orange
    "total": "#202124",         # charcoal
    "muted": "#64748B",         # slate grey
    "grid": "#D9E2EC",          # light grid
    "card": "#FFFFFF",
    "page": "#F7FAFC",
    "border": "#CBD5E1",
    "covid": "#E11D48",         # red annotation
    "covid_fill": "#FEE2E2",
    "green": "#16A34A",
    "heat_low": "#FFF7BC",
    "heat_high": "#8C2D04",
}

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 240,
    "font.family": "DejaVu Sans",
    "axes.titleweight": "bold",
    "axes.labelcolor": BRAND["total"],
    "xtick.color": BRAND["total"],
    "ytick.color": BRAND["total"],
    "axes.edgecolor": "#64748B",
    "axes.linewidth": 0.8,
})

COVID_START = pd.Timestamp("2020-03-01")
COVID_END = pd.Timestamp("2021-10-31")

# -----------------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------------
def billions(x: float) -> str:
    return f"{x / 1_000_000_000:.1f}B"


def millions(x: float) -> str:
    return f"{x / 1_000_000:.0f}M"


def pct(x: float, decimals: int = 1) -> str:
    return f"{x:.{decimals}f}%"


def y_billions(x, _pos=None):
    if abs(x) < 1_000_000_000:
        return "0B" if x == 0 else f"{x/1_000_000:.0f}M"
    return f"{x/1_000_000_000:.1f}B"


def y_millions(x, _pos=None):
    return f"{x/1_000_000:.0f}M"


def safe_div(a: float, b: float) -> float:
    return 0.0 if b == 0 else a / b


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------
def load_data(csv_path: Path, json_path: Path) -> Tuple[pd.DataFrame, Dict]:
    df = pd.read_csv(csv_path)
    meta = json.loads(json_path.read_text(encoding="utf-8"))

    df["month_start"] = pd.to_datetime(df["month_start"])
    df = df.sort_values("month_start").reset_index(drop=True)

    # Drop true zero-row months from percentage/intensity calculations but keep
    # the time gap visible in line charts by allowing NaNs.
    df["total"] = pd.to_numeric(df["month_total_volume"], errors="coerce")
    df["weekday"] = pd.to_numeric(df["month_weekday_volume"], errors="coerce")
    df["weekend"] = pd.to_numeric(df["month_weekend_volume"], errors="coerce")
    df["weekday_days"] = pd.to_numeric(df["month_weekday_days"], errors="coerce")
    df["weekend_days"] = pd.to_numeric(df["month_weekend_days"], errors="coerce")

    zero_mask = df["total"].fillna(0).eq(0)
    df.loc[zero_mask, ["total", "weekday", "weekend", "weekday_days", "weekend_days"]] = np.nan

    df["weekday_share"] = df["weekday"] / df["total"] * 100
    df["weekend_share"] = df["weekend"] / df["total"] * 100
    df["weekday_avg_day"] = df["weekday"] / df["weekday_days"]
    df["weekend_avg_day"] = df["weekend"] / df["weekend_days"]
    df["weekend_intensity_vs_weekday"] = df["weekend_avg_day"] / df["weekday_avg_day"] * 100
    df["weekend_share_roll12"] = df["weekend_share"].rolling(12, min_periods=6).mean()
    df["cum_weekday"] = df["weekday"].fillna(0).cumsum()
    df["cum_weekend"] = df["weekend"].fillna(0).cumsum()
    df["cum_total"] = df["total"].fillna(0).cumsum()

    return df, meta


# -----------------------------------------------------------------------------
# Styling helpers
# -----------------------------------------------------------------------------
def start_figure(figsize=(15, 8), facecolor="white"):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(facecolor)
    ax.set_facecolor("white")
    return fig, ax


def style_axis(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis=grid_axis, color=BRAND["grid"], linewidth=0.8, alpha=0.75)
    ax.tick_params(labelsize=11)


def add_title(ax, title: str, subtitle: str | None = None):
    ax.set_title(title, loc="left", fontsize=21, fontweight="bold", color=BRAND["total"], pad=18)
    if subtitle:
        ax.text(0, 1.015, subtitle, transform=ax.transAxes, ha="left", va="bottom",
                fontsize=12, color=BRAND["muted"])


def add_footer(fig, text="Source: Melbourne SCATS weekday/weekend split archive | Analysis by Spotswood Trailers"):
    fig.text(0.01, 0.01, text, fontsize=9, color=BRAND["muted"], ha="left", va="bottom")


def add_covid_band(ax, label=True):
    ax.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.75, zorder=0)
    if label:
        ymin, ymax = ax.get_ylim()
        ax.text(COVID_START + (COVID_END - COVID_START) / 2, ymax - (ymax - ymin) * 0.07,
                "COVID disruption\nMar 2020 – Oct 2021",
                ha="center", va="top", fontsize=10, color=BRAND["covid"])


def save(fig, out_dir: Path, name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Wrote {path}")


def add_value_labels(ax, bars, formatter, dy=0.015, fontsize=12):
    ymin, ymax = ax.get_ylim()
    offset = (ymax - ymin) * dy
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width()/2, h + offset, formatter(h),
                ha="center", va="bottom", fontsize=fontsize, fontweight="bold", color="black")


# -----------------------------------------------------------------------------
# Individual charts
# -----------------------------------------------------------------------------
def chart_01_donut(meta: Dict, out_dir: Path):
    weekday = meta["weekday_volume"]
    weekend = meta["weekend_volume"]
    total = meta["total_volume"]
    wshare = meta["weekday_share"]
    eshare = meta["weekend_share"]

    fig, ax = start_figure(figsize=(12, 9))
    add_title(ax, "Overall Traffic Share: Weekday vs Weekend",
              "Share of all detected SCATS vehicle movement events, 1 Jan 2014 – 7 Apr 2026")

    wedges, _ = ax.pie(
        [weekday, weekend],
        startangle=90,
        counterclock=False,
        colors=[BRAND["weekday"], BRAND["weekend"]],
        wedgeprops=dict(width=0.38, edgecolor="white", linewidth=3),
    )
    ax.text(0, 0.08, billions(total), ha="center", va="center", fontsize=28,
            fontweight="bold", color=BRAND["total"])
    ax.text(0, -0.08, "total vehicle\nmovement events", ha="center", va="center",
            fontsize=13, color=BRAND["muted"], linespacing=1.1)

    legend_labels = [
        f"Weekday — {wshare:.2f}% ({billions(weekday)})",
        f"Weekend — {eshare:.2f}% ({billions(weekend)})",
    ]
    ax.legend(wedges, legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.08),
              ncol=1, frameon=False, fontsize=13)
    ax.set_aspect("equal")
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_01_overall_share_donut.png")


def chart_02_total_bar(meta: Dict, out_dir: Path):
    fig, ax = start_figure(figsize=(15, 8))
    add_title(ax, "Total Vehicle Movements: Weekday vs Weekend",
              "Full Melbourne SCATS archive, 2014-01-01 to 2026-04-07")
    vals = [meta["weekday_volume"], meta["weekend_volume"]]
    bars = ax.bar(["Weekday", "Weekend"], vals, color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax.set_ylabel("Vehicle movement events")
    ax.yaxis.set_major_formatter(FuncFormatter(y_billions))
    ax.set_ylim(0, max(vals) * 1.18)
    style_axis(ax)
    add_value_labels(ax, bars, billions, fontsize=15)
    ax.text(0.5, 0.91,
            f"Weekdays account for {billions(vals[0])}; weekends still account for {billions(vals[1])}.",
            transform=ax.transAxes, ha="center", va="center", fontsize=12, color=BRAND["muted"])
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_02_total_volume_bar.png")


def chart_03_avg_day(meta: Dict, out_dir: Path):
    vals = [meta["weekday_avg_day_volume"], meta["weekend_avg_day_volume"]]
    intensity = vals[1] / vals[0] * 100
    fig, ax = start_figure(figsize=(15, 8))
    add_title(ax, "Average Daily Traffic Intensity: Weekday vs Weekend",
              f"A typical weekend day reaches {intensity:.1f}% of weekday daily intensity")
    bars = ax.bar(["Average weekday", "Average weekend day"], vals,
                  color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax.set_ylabel("Average vehicle movement events per day")
    ax.yaxis.set_major_formatter(FuncFormatter(y_millions))
    ax.set_ylim(0, max(vals) * 1.22)
    style_axis(ax)
    add_value_labels(ax, bars, millions, fontsize=15)
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_03_average_daily_intensity_bar.png")


def chart_04_monthly_trends(df: pd.DataFrame, out_dir: Path):
    fig, ax = start_figure(figsize=(16, 8))
    add_title(ax, "Monthly Traffic Volumes Over Time",
              "Weekday and weekend vehicle movements per month across the Melbourne SCATS archive")
    ax.plot(df["month_start"], df["weekday"], color=BRAND["weekday"], linewidth=2.2, label="Weekday monthly total")
    ax.plot(df["month_start"], df["weekend"], color=BRAND["weekend"], linewidth=2.2, label="Weekend monthly total")
    style_axis(ax)
    ax.yaxis.set_major_formatter(FuncFormatter(y_billions))
    ax.set_ylabel("Monthly vehicle movement events")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    add_covid_band(ax)
    ax.legend(frameon=False, loc="upper left")
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_04_monthly_traffic_volumes_over_time.png")


def chart_05_weekend_share(df: pd.DataFrame, out_dir: Path):
    fig, ax = start_figure(figsize=(16, 8))
    add_title(ax, "Weekend Share of Total Traffic Over Time",
              "Weekend vehicle movements as a percentage of total monthly SCATS traffic")
    ax.plot(df["month_start"], df["weekend_share"], color=BRAND["weekend"], linewidth=1.25,
            alpha=0.55, label="Monthly weekend share")
    ax.plot(df["month_start"], df["weekend_share_roll12"], color=BRAND["weekday"], linewidth=3,
            label="12-month rolling average")
    style_axis(ax)
    ax.set_ylabel("Weekend share of monthly traffic (%)")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylim(max(15, np.nanmin(df["weekend_share"]) - 2), min(35, np.nanmax(df["weekend_share"]) + 2))
    add_covid_band(ax)
    ax.legend(frameon=False, loc="upper left")
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_05_weekend_share_over_time.png")


def chart_06_intensity(df: pd.DataFrame, out_dir: Path):
    fig, ax = start_figure(figsize=(16, 8))
    add_title(ax, "Weekend Daily Intensity Relative to Weekday",
              "Weekend daily traffic as a percentage of weekday daily traffic, normalised by day count")
    ax.plot(df["month_start"], df["weekend_intensity_vs_weekday"], color=BRAND["weekend"], linewidth=2.4)
    ax.axhline(100, color=BRAND["total"], linestyle="--", linewidth=1.2, alpha=0.65)
    ax.text(df["month_start"].max(), 100.3, "100% = weekday intensity", ha="right", va="bottom",
            color=BRAND["muted"], fontsize=10)
    style_axis(ax)
    ax.set_ylabel("Weekend intensity / weekday intensity (%)")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylim(max(55, np.nanmin(df["weekend_intensity_vs_weekday"]) - 4), 102)
    add_covid_band(ax)
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_06_weekend_daily_intensity_relative_to_weekday.png")


def chart_07_stacked(df: pd.DataFrame, out_dir: Path):
    fig, ax = start_figure(figsize=(18, 8))
    add_title(ax, "Monthly Traffic Composition: Weekday vs Weekend Share",
              "Each bar sums to 100% for the month")
    x = df["month_start"]
    width_days = 24
    ax.bar(x, df["weekday_share"], width=width_days, color=BRAND["weekday"], label="Weekday share")
    ax.bar(x, df["weekend_share"], width=width_days, bottom=df["weekday_share"],
           color=BRAND["weekend"], label="Weekend share")
    style_axis(ax)
    ax.set_ylabel("Share of monthly traffic (%)")
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(frameon=False, loc="upper left", ncol=2)
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_07_monthly_traffic_composition.png")


def chart_08_heatmap(df: pd.DataFrame, out_dir: Path):
    fig, ax = plt.subplots(figsize=(15, 8))
    fig.patch.set_facecolor("white")
    add_title(ax, "Weekend Share Heatmap by Year and Month",
              "Darker cells indicate months where weekends made up a larger share of Melbourne SCATS traffic")
    d = df.dropna(subset=["weekend_share"]).copy()
    d["year"] = d["month_start"].dt.year
    d["month"] = d["month_start"].dt.month
    pivot = d.pivot(index="year", columns="month", values="weekend_share")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrBr", vmin=np.nanmin(pivot.values), vmax=np.nanmax(pivot.values))
    ax.set_xticks(range(12), months)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iloc[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=8, color="#111827")
    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.04)
    cbar.set_label("Weekend share (%)", fontsize=12)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor(BRAND["border"])
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_08_weekend_share_heatmap.png")


def chart_09_covid_periods(df: pd.DataFrame, out_dir: Path):
    periods = [
        ("Pre-COVID\nJan 2014 – Feb 2020", pd.Timestamp("2014-01-01"), pd.Timestamp("2020-02-29")),
        ("COVID disruption\nMar 2020 – Oct 2021", pd.Timestamp("2020-03-01"), pd.Timestamp("2021-10-31")),
        ("Recovery / post-COVID\nNov 2021 – Apr 2026", pd.Timestamp("2021-11-01"), pd.Timestamp("2026-04-30")),
    ]
    labels, weekday_shares, weekend_shares = [], [], []
    for label, start, end in periods:
        sub = df[(df["month_start"] >= start) & (df["month_start"] <= end)]
        w = sub["weekday"].sum(skipna=True)
        e = sub["weekend"].sum(skipna=True)
        t = w + e
        labels.append(label)
        weekday_shares.append(w / t * 100)
        weekend_shares.append(e / t * 100)

    x = np.arange(len(labels))
    width = 0.34
    fig, ax = start_figure(figsize=(15, 8))
    add_title(ax, "Traffic Composition Across COVID Eras",
              "Average weekday and weekend share before, during, and after the COVID disruption period")
    b1 = ax.bar(x - width/2, weekday_shares, width, color=BRAND["weekday"], label="Weekday share")
    b2 = ax.bar(x + width/2, weekend_shares, width, color=BRAND["weekend"], label="Weekend share")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Share of period traffic (%)")
    ax.set_ylim(0, 85)
    style_axis(ax)
    add_value_labels(ax, b1, lambda v: f"{v:.1f}%", dy=0.006, fontsize=11)
    add_value_labels(ax, b2, lambda v: f"{v:.1f}%", dy=0.006, fontsize=11)
    ax.legend(frameon=False, loc="upper right")
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_09_traffic_composition_across_covid_eras.png")


def chart_10_cumulative(df: pd.DataFrame, meta: Dict, out_dir: Path):
    fig, ax = start_figure(figsize=(16, 8))
    add_title(ax, "Cumulative Traffic Volumes Over Time",
              f"Accumulation toward {billions(meta['total_volume'])} detected vehicle movement events")
    ax.plot(df["month_start"], df["cum_weekday"], color=BRAND["weekday"], linewidth=2.5,
            label=f"Cumulative weekday ({billions(meta['weekday_volume'])})")
    ax.plot(df["month_start"], df["cum_weekend"], color=BRAND["weekend"], linewidth=2.5,
            label=f"Cumulative weekend ({billions(meta['weekend_volume'])})")
    ax.plot(df["month_start"], df["cum_total"], color=BRAND["total"], linewidth=2.2, linestyle="--",
            label=f"Cumulative total ({billions(meta['total_volume'])})")
    style_axis(ax)
    ax.yaxis.set_major_formatter(FuncFormatter(y_billions))
    ax.set_ylabel("Cumulative vehicle movement events")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(frameon=False, loc="upper left")
    add_footer(fig)
    save(fig, out_dir, "weekday_weekend_10_cumulative_traffic_volumes_over_time.png")


# -----------------------------------------------------------------------------
# Dashboard infographic
# -----------------------------------------------------------------------------
def mini_title(ax, number: int, title: str, subtitle: str):
    ax.text(0.0, 1.08, f"{number}. {title}", transform=ax.transAxes,
            fontsize=10.5, fontweight="bold", color="#0B2E6D", ha="left", va="bottom")
    ax.text(0.0, 1.02, subtitle, transform=ax.transAxes,
            fontsize=8.2, color=BRAND["muted"], ha="left", va="bottom")


def cardify(ax):
    ax.set_facecolor("white")
    for s in ax.spines.values():
        s.set_edgecolor(BRAND["border"])
        s.set_linewidth(0.8)
    ax.grid(True, axis="y", color=BRAND["grid"], alpha=0.6, linewidth=0.7)


def dashboard(df: pd.DataFrame, meta: Dict, out_dir: Path):
    fig = plt.figure(figsize=(22, 14), facecolor=BRAND["page"])
    gs = fig.add_gridspec(4, 3, left=0.035, right=0.985, top=0.88, bottom=0.07, hspace=0.65, wspace=0.24)

    fig.text(0.5, 0.955, "MELBOURNE SCATS TRAFFIC ANALYTICS", ha="center", va="center",
             fontsize=24, fontweight="bold", color="#0B2E6D")
    fig.text(0.5, 0.925, "WEEKDAY vs WEEKEND TRAFFIC: 12-YEAR BEHAVIOURAL INSIGHTS", ha="center", va="center",
             fontsize=28, fontweight="bold", color="#0B2E6D")
    fig.text(0.5, 0.895, "Analysis of 539.0 Billion Vehicle Movements Across Melbourne's Road Network (1 Jan 2014 – 7 Apr 2026)",
             ha="center", va="center", fontsize=15, color=BRAND["muted"])

    # 1 donut
    ax1 = fig.add_subplot(gs[0, 0]); cardify(ax1); mini_title(ax1, 1, "OVERALL TRAFFIC SHARE", "Proportion of total vehicle movements")
    ax1.pie([meta["weekday_volume"], meta["weekend_volume"]], startangle=90, counterclock=False,
            colors=[BRAND["weekday"], BRAND["weekend"]], wedgeprops=dict(width=0.34, edgecolor="white", linewidth=2))
    ax1.text(0, 0.04, "539.0B", ha="center", va="center", fontsize=15, fontweight="bold", color=BRAND["total"])
    ax1.text(0, -0.13, "TOTAL VEHICLE\nMOVEMENTS", ha="center", va="center", fontsize=8, color=BRAND["muted"])
    ax1.text(1.05, 0.35, f"WEEKDAYS\n{meta['weekday_share']:.2f}%\n{billions(meta['weekday_volume'])}", color=BRAND["weekday"], fontsize=11, fontweight="bold", va="center")
    ax1.text(1.05, -0.35, f"WEEKENDS\n{meta['weekend_share']:.2f}%\n{billions(meta['weekend_volume'])}", color=BRAND["weekend"], fontsize=11, fontweight="bold", va="center")
    ax1.set_aspect("equal"); ax1.set_xticks([]); ax1.set_yticks([])

    # 2 total bar
    ax2 = fig.add_subplot(gs[0, 1]); cardify(ax2); mini_title(ax2, 2, "TOTAL TRAFFIC VOLUME", "Total vehicle movements over the 12-year period")
    vals = [meta["weekday_volume"], meta["weekend_volume"]]
    bars = ax2.bar(["WEEKDAYS", "WEEKENDS"], vals, color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax2.yaxis.set_major_formatter(FuncFormatter(y_billions)); ax2.set_ylim(0, max(vals)*1.25)
    add_value_labels(ax2, bars, billions, dy=0.012, fontsize=11)
    ax2.tick_params(labelsize=8)

    # 3 avg day
    ax3 = fig.add_subplot(gs[0, 2]); cardify(ax3); mini_title(ax3, 3, "AVERAGE DAILY TRAFFIC INTENSITY", "Average vehicle movements per day")
    vals3 = [meta["weekday_avg_day_volume"], meta["weekend_avg_day_volume"]]
    bars3 = ax3.bar(["AVERAGE\nWEEKDAY", "AVERAGE\nWEEKEND DAY"], vals3, color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax3.yaxis.set_major_formatter(FuncFormatter(y_millions)); ax3.set_ylim(0, max(vals3)*1.25)
    add_value_labels(ax3, bars3, millions, dy=0.012, fontsize=11)
    ax3.tick_params(labelsize=8)

    # 4 monthly volume
    ax4 = fig.add_subplot(gs[1, 0]); cardify(ax4); mini_title(ax4, 4, "MONTHLY TRAFFIC VOLUMES OVER TIME", "Weekday and weekend vehicle movements per month")
    ax4.plot(df["month_start"], df["weekday"], color=BRAND["weekday"], linewidth=1.3, label="Weekday")
    ax4.plot(df["month_start"], df["weekend"], color=BRAND["weekend"], linewidth=1.3, label="Weekend")
    ax4.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.7)
    ax4.yaxis.set_major_formatter(FuncFormatter(y_billions)); ax4.xaxis.set_major_locator(mdates.YearLocator(2)); ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax4.tick_params(labelsize=8); ax4.legend(frameon=False, fontsize=8, loc="upper left")

    # 5 weekend share
    ax5 = fig.add_subplot(gs[1, 1]); cardify(ax5); mini_title(ax5, 5, "WEEKEND SHARE OF TOTAL TRAFFIC", "Weekend traffic as a percentage of total monthly traffic")
    ax5.plot(df["month_start"], df["weekend_share"], color=BRAND["weekend"], linewidth=1.0, alpha=0.65, label="Monthly")
    ax5.plot(df["month_start"], df["weekend_share_roll12"], color=BRAND["weekday"], linewidth=2.3, label="12-month avg")
    ax5.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.7)
    ax5.set_ylim(18, 32); ax5.xaxis.set_major_locator(mdates.YearLocator(2)); ax5.xaxis.set_major_formatter(mdates.DateFormatter("%Y")); ax5.tick_params(labelsize=8); ax5.legend(frameon=False, fontsize=8)

    # 6 intensity
    ax6 = fig.add_subplot(gs[1, 2]); cardify(ax6); mini_title(ax6, 6, "WEEKEND DAILY INTENSITY RELATIVE TO WEEKDAY", "Weekend daily traffic as a % of weekday daily intensity")
    ax6.plot(df["month_start"], df["weekend_intensity_vs_weekday"], color=BRAND["green"], linewidth=1.5)
    ax6.axhline(100, color=BRAND["muted"], linestyle="--", linewidth=1)
    ax6.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.7)
    ax6.set_ylim(60, 102); ax6.xaxis.set_major_locator(mdates.YearLocator(2)); ax6.xaxis.set_major_formatter(mdates.DateFormatter("%Y")); ax6.tick_params(labelsize=8)

    # 7 stacked
    ax7 = fig.add_subplot(gs[2, 0]); cardify(ax7); mini_title(ax7, 7, "MONTHLY TRAFFIC COMPOSITION", "Weekday and weekend share of total traffic each month")
    ax7.bar(df["month_start"], df["weekday_share"], width=24, color=BRAND["weekday"], label="Weekday")
    ax7.bar(df["month_start"], df["weekend_share"], width=24, bottom=df["weekday_share"], color=BRAND["weekend"], label="Weekend")
    ax7.set_ylim(0, 100); ax7.xaxis.set_major_locator(mdates.YearLocator(2)); ax7.xaxis.set_major_formatter(mdates.DateFormatter("%Y")); ax7.tick_params(labelsize=8); ax7.legend(frameon=False, fontsize=8, ncol=2)

    # 8 heatmap
    ax8 = fig.add_subplot(gs[2, 1]); mini_title(ax8, 8, "WEEKEND SHARE HEATMAP BY YEAR AND MONTH", "Weekend share (%) of total traffic")
    d = df.dropna(subset=["weekend_share"]).copy(); d["year"] = d["month_start"].dt.year; d["month"] = d["month_start"].dt.month
    pivot = d.pivot(index="year", columns="month", values="weekend_share")
    im = ax8.imshow(pivot.values, aspect="auto", cmap="YlOrBr")
    ax8.set_xticks(range(12), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax8.set_yticks(range(len(pivot.index)), pivot.index)
    ax8.tick_params(labelsize=7)
    for s in ax8.spines.values(): s.set_edgecolor(BRAND["border"])

    # 9 eras
    ax9 = fig.add_subplot(gs[2, 2]); cardify(ax9); mini_title(ax9, 9, "TRAFFIC COMPOSITION ACROSS COVID ERAS", "Average weekday and weekend share by period")
    periods = [
        ("Pre\nCOVID", pd.Timestamp("2014-01-01"), pd.Timestamp("2020-02-29")),
        ("COVID\nDisruption", pd.Timestamp("2020-03-01"), pd.Timestamp("2021-10-31")),
        ("Recovery /\nPost-COVID", pd.Timestamp("2021-11-01"), pd.Timestamp("2026-04-30")),
    ]
    labels, ws, es = [], [], []
    for label, start, end in periods:
        sub = df[(df["month_start"] >= start) & (df["month_start"] <= end)]
        w = sub["weekday"].sum(skipna=True); e = sub["weekend"].sum(skipna=True); t = w + e
        labels.append(label); ws.append(w/t*100); es.append(e/t*100)
    x = np.arange(3); width = 0.32
    ax9.bar(x - width/2, ws, width, color=BRAND["weekday"], label="Weekday")
    ax9.bar(x + width/2, es, width, color=BRAND["weekend"], label="Weekend")
    ax9.set_xticks(x, labels); ax9.set_ylim(0, 85); ax9.tick_params(labelsize=8); ax9.legend(frameon=False, fontsize=8)

    # 10 cumulative + summary text
    ax10 = fig.add_subplot(gs[3, 0:2]); cardify(ax10); mini_title(ax10, 10, "CUMULATIVE TRAFFIC VOLUMES OVER TIME", "Cumulative vehicle movements since January 2014")
    ax10.plot(df["month_start"], df["cum_weekday"], color=BRAND["weekday"], linewidth=1.8, label="Cumulative weekday")
    ax10.plot(df["month_start"], df["cum_weekend"], color=BRAND["weekend"], linewidth=1.8, label="Cumulative weekend")
    ax10.plot(df["month_start"], df["cum_total"], color=BRAND["total"], linewidth=1.5, linestyle="--", label="Cumulative total")
    ax10.yaxis.set_major_formatter(FuncFormatter(y_billions)); ax10.xaxis.set_major_locator(mdates.YearLocator(2)); ax10.xaxis.set_major_formatter(mdates.DateFormatter("%Y")); ax10.tick_params(labelsize=8); ax10.legend(frameon=False, fontsize=8, loc="upper left")

    ax11 = fig.add_subplot(gs[3, 2]); ax11.axis("off")
    bbox = FancyBboxPatch((0.02, 0.05), 0.96, 0.88, boxstyle="round,pad=0.02,rounding_size=0.025",
                          linewidth=1, edgecolor=BRAND["border"], facecolor="white", transform=ax11.transAxes)
    ax11.add_patch(bbox)
    ax11.text(0.08, 0.82, "KEY TAKEAWAYS", fontsize=15, fontweight="bold", color="#0B2E6D", transform=ax11.transAxes)
    takeaways = [
        f"{meta['weekday_share']:.2f}% of all vehicle movements occur on weekdays.",
        f"Weekend days reach {meta['weekend_avg_day_volume']/meta['weekday_avg_day_volume']*100:.1f}% of weekday daily intensity.",
        "Weekend share has trended higher through the recovery period.",
        "Melbourne's road network remains highly active every day of the week.",
        f"Total analysed archive: {billions(meta['total_volume'])} movement events.",
    ]
    y = 0.68
    for item in takeaways:
        ax11.text(0.10, y, u"• " + item, fontsize=10.5, color=BRAND["total"], transform=ax11.transAxes)
        y -= 0.12

    fig.text(0.035, 0.035, "Source: Melbourne SCATS weekday/weekend split archive | Zero-data month: Dec 2018 | Analysis by Spotswood Trailers",
             fontsize=10, color=BRAND["muted"], ha="left")
    save(fig, out_dir, "weekday_weekend_00_dashboard_infographic.png")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate polished weekday/weekend SCATS charts.")
    parser.add_argument("--csv", required=True, help="Path to weekday_weekend_split.csv")
    parser.add_argument("--json", required=True, help="Path to weekday_weekend_split_final.json")
    parser.add_argument("--out", required=True, help="Output directory for PNG charts")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    json_path = Path(args.json)
    out_dir = Path(args.out)

    df, meta = load_data(csv_path, json_path)

    dashboard(df, meta, out_dir)
    chart_01_donut(meta, out_dir)
    chart_02_total_bar(meta, out_dir)
    chart_03_avg_day(meta, out_dir)
    chart_04_monthly_trends(df, out_dir)
    chart_05_weekend_share(df, out_dir)
    chart_06_intensity(df, out_dir)
    chart_07_stacked(df, out_dir)
    chart_08_heatmap(df, out_dir)
    chart_09_covid_periods(df, out_dir)
    chart_10_cumulative(df, meta, out_dir)

    print("\nDone. Generated polished V2 weekday/weekend chart set.")


if __name__ == "__main__":
    main()
