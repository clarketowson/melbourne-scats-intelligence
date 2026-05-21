#!/usr/bin/env python3
r"""
generate_weekday_weekend_chartsV3.py

Creates polished, media-ready weekday/weekend traffic charts and a clean dashboard infographic from:
  - weekday_weekend_split.csv
  - weekday_weekend_split_final.json

V3 upgrades over V2:
  - rebuilt dashboard with proper card layout and no heading collisions
  - larger infographic canvas, stronger spacing, and dedicated title bands
  - better mini-chart readability and dashboard-level callout cards
  - keeps individual charts polished from V2 with improved naming and labels

Example:
    python generate_weekday_weekend_chartsV3.py ^
      --csv A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_weekend_split.csv ^
      --json A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_weekend_split_final.json ^
      --out A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\weekday_weekend_v3
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
# Dashboard infographic — V3 rebuilt layout
# -----------------------------------------------------------------------------
def dashboard_card(fig, x, y, w, h, number: int, title: str, subtitle: str):
    """Create a rounded white dashboard card with a reserved heading band."""
    card = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.006,rounding_size=0.010",
        linewidth=1.0,
        edgecolor=BRAND["border"],
        facecolor="white",
        transform=fig.transFigure,
        zorder=0,
    )
    fig.patches.append(card)

    fig.text(x + 0.012, y + h - 0.032, f"{number}. {title}",
             ha="left", va="top", fontsize=12.5, fontweight="bold", color="#0B2E6D")
    fig.text(x + 0.012, y + h - 0.057, subtitle,
             ha="left", va="top", fontsize=9.4, color=BRAND["muted"])

    # Plot area leaves room at top for heading and bottom for labels.
    ax = fig.add_axes([x + 0.018, y + 0.045, w - 0.036, h - 0.105], zorder=2)
    ax.set_facecolor("white")
    return ax


def style_card_axis(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#94A3B8")
    ax.spines["bottom"].set_color("#94A3B8")
    ax.grid(True, axis=grid_axis, color=BRAND["grid"], alpha=0.65, linewidth=0.75)
    ax.tick_params(labelsize=8.5, colors=BRAND["total"])


def add_small_covid_band(ax):
    ax.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.75, zorder=0)
    ymin, ymax = ax.get_ylim()
    ax.text(COVID_START + (COVID_END - COVID_START) / 2,
            ymax - (ymax - ymin) * 0.08,
            "COVID disruption\nMar 2020 – Oct 2021",
            ha="center", va="top", fontsize=8.2, color=BRAND["covid"])


def dashboard(df: pd.DataFrame, meta: Dict, out_dir: Path):
    """Create a clean magazine-style dashboard with no text collisions."""
    fig = plt.figure(figsize=(26, 17), facecolor=BRAND["page"])

    # Header band
    fig.text(0.5, 0.965, "MELBOURNE SCATS TRAFFIC ANALYTICS",
             ha="center", va="center", fontsize=24, fontweight="bold", color="#0B2E6D")
    fig.text(0.5, 0.932, "WEEKDAY vs WEEKEND TRAFFIC: 12-YEAR BEHAVIOURAL INSIGHTS",
             ha="center", va="center", fontsize=30, fontweight="bold", color="#0B2E6D")
    fig.text(0.5, 0.900,
             "Analysis of 539.0 billion detected vehicle movement events across Melbourne's SCATS road network (1 Jan 2014 – 7 Apr 2026)",
             ha="center", va="center", fontsize=14.5, color=BRAND["muted"])

    # Card geometry
    left = 0.035
    gap = 0.022
    col_w = (0.93 - 2 * gap) / 3
    row_h = 0.185
    y1, y2, y3, y4 = 0.690, 0.470, 0.250, 0.055

    # 1 donut
    ax1 = dashboard_card(fig, left, y1, col_w, row_h, 1, "OVERALL TRAFFIC SHARE", "Weekday and weekend share of total detected movements")
    ax1.pie([meta["weekday_volume"], meta["weekend_volume"]],
            startangle=90, counterclock=False,
            colors=[BRAND["weekday"], BRAND["weekend"]],
            wedgeprops=dict(width=0.34, edgecolor="white", linewidth=2.0))
    ax1.text(0, 0.08, "539.0B", ha="center", va="center", fontsize=18, fontweight="bold", color=BRAND["total"])
    ax1.text(0, -0.12, "TOTAL VEHICLE\nMOVEMENTS", ha="center", va="center", fontsize=8.2, color=BRAND["muted"])
    ax1.text(1.15, 0.35, f"WEEKDAYS\n{meta['weekday_share']:.2f}%\n{billions(meta['weekday_volume'])}",
             color=BRAND["weekday"], fontsize=10.5, fontweight="bold", va="center")
    ax1.text(1.15, -0.38, f"WEEKENDS\n{meta['weekend_share']:.2f}%\n{billions(meta['weekend_volume'])}",
             color=BRAND["weekend"], fontsize=10.5, fontweight="bold", va="center")
    ax1.set_aspect("equal"); ax1.set_xticks([]); ax1.set_yticks([])
    ax1.set_xlim(-1.25, 1.85)

    # 2 total bar
    ax2 = dashboard_card(fig, left + col_w + gap, y1, col_w, row_h, 2, "TOTAL TRAFFIC VOLUME", "Total vehicle movement events over the full archive")
    vals = [meta["weekday_volume"], meta["weekend_volume"]]
    b = ax2.bar(["Weekday", "Weekend"], vals, color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax2.yaxis.set_major_formatter(FuncFormatter(y_billions)); ax2.set_ylim(0, max(vals)*1.25)
    style_card_axis(ax2); add_value_labels(ax2, b, billions, dy=0.015, fontsize=10.5)

    # 3 average day
    ax3 = dashboard_card(fig, left + 2*(col_w + gap), y1, col_w, row_h, 3, "AVERAGE DAILY TRAFFIC INTENSITY", "Average detected movements per weekday and weekend day")
    vals3 = [meta["weekday_avg_day_volume"], meta["weekend_avg_day_volume"]]
    b3 = ax3.bar(["Average\nweekday", "Average\nweekend day"], vals3, color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax3.yaxis.set_major_formatter(FuncFormatter(y_millions)); ax3.set_ylim(0, max(vals3)*1.25)
    style_card_axis(ax3); add_value_labels(ax3, b3, millions, dy=0.015, fontsize=10.5)

    # 4 monthly volume
    ax4 = dashboard_card(fig, left, y2, col_w, row_h, 4, "MONTHLY TRAFFIC VOLUMES OVER TIME", "Weekday and weekend vehicle movements per month")
    ax4.plot(df["month_start"], df["weekday"], color=BRAND["weekday"], linewidth=1.6, label="Weekday")
    ax4.plot(df["month_start"], df["weekend"], color=BRAND["weekend"], linewidth=1.6, label="Weekend")
    ax4.yaxis.set_major_formatter(FuncFormatter(y_billions)); ax4.xaxis.set_major_locator(mdates.YearLocator(2)); ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    style_card_axis(ax4); add_small_covid_band(ax4); ax4.legend(frameon=False, fontsize=8.5, loc="upper left")

    # 5 weekend share
    ax5 = dashboard_card(fig, left + col_w + gap, y2, col_w, row_h, 5, "WEEKEND SHARE OF TOTAL TRAFFIC", "Weekend movements as a percentage of total monthly traffic")
    ax5.plot(df["month_start"], df["weekend_share"], color=BRAND["weekend"], linewidth=1.0, alpha=0.6, label="Monthly")
    ax5.plot(df["month_start"], df["weekend_share_roll12"], color=BRAND["weekday"], linewidth=2.3, label="12-month rolling average")
    ax5.set_ylim(18, 32); ax5.xaxis.set_major_locator(mdates.YearLocator(2)); ax5.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    style_card_axis(ax5); add_small_covid_band(ax5); ax5.legend(frameon=False, fontsize=8.5, loc="upper left")

    # 6 relative intensity
    ax6 = dashboard_card(fig, left + 2*(col_w + gap), y2, col_w, row_h, 6, "WEEKEND DAILY INTENSITY RELATIVE TO WEEKDAY", "Weekend daily traffic as a percentage of weekday daily traffic")
    ax6.plot(df["month_start"], df["weekend_intensity_vs_weekday"], color=BRAND["weekend"], linewidth=1.9)
    ax6.axhline(100, color=BRAND["muted"], linestyle="--", linewidth=1.0)
    ax6.text(df["month_start"].max(), 100.4, "100% = weekday intensity", ha="right", va="bottom", fontsize=8, color=BRAND["muted"])
    ax6.set_ylim(60, 102); ax6.xaxis.set_major_locator(mdates.YearLocator(2)); ax6.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    style_card_axis(ax6); add_small_covid_band(ax6)

    # 7 stacked composition
    ax7 = dashboard_card(fig, left, y3, col_w, row_h, 7, "MONTHLY TRAFFIC COMPOSITION", "Each month split into weekday and weekend share")
    ax7.bar(df["month_start"], df["weekday_share"], width=24, color=BRAND["weekday"], label="Weekday")
    ax7.bar(df["month_start"], df["weekend_share"], width=24, bottom=df["weekday_share"], color=BRAND["weekend"], label="Weekend")
    ax7.set_ylim(0, 100); ax7.xaxis.set_major_locator(mdates.YearLocator(2)); ax7.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    style_card_axis(ax7); ax7.legend(frameon=False, fontsize=8.5, ncol=2, loc="upper left")

    # 8 heatmap
    ax8 = dashboard_card(fig, left + col_w + gap, y3, col_w, row_h, 8, "WEEKEND SHARE HEATMAP", "Year-by-month weekend share of total monthly traffic")
    d = df.dropna(subset=["weekend_share"]).copy(); d["year"] = d["month_start"].dt.year; d["month"] = d["month_start"].dt.month
    pivot = d.pivot(index="year", columns="month", values="weekend_share")
    im = ax8.imshow(pivot.values, aspect="auto", cmap="YlOrBr", vmin=np.nanmin(pivot.values), vmax=np.nanmax(pivot.values))
    ax8.set_xticks(range(12), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax8.set_yticks(range(len(pivot.index)), pivot.index)
    ax8.tick_params(labelsize=7.5)
    for s in ax8.spines.values():
        s.set_visible(True); s.set_edgecolor(BRAND["border"])

    # 9 COVID eras
    ax9 = dashboard_card(fig, left + 2*(col_w + gap), y3, col_w, row_h, 9, "TRAFFIC COMPOSITION ACROSS COVID ERAS", "Weekday and weekend share before, during, and after disruption")
    periods = [
        ("Pre\nCOVID", pd.Timestamp("2014-01-01"), pd.Timestamp("2020-02-29")),
        ("COVID\nDisruption", pd.Timestamp("2020-03-01"), pd.Timestamp("2021-10-31")),
        ("Recovery /\nPost-COVID", pd.Timestamp("2021-11-01"), pd.Timestamp("2026-04-30")),
    ]
    labels, ws, es = [], [], []
    for label, start, end in periods:
        sub = df[(df["month_start"] >= start) & (df["month_start"] <= end)]
        wsum = sub["weekday"].sum(skipna=True); esum = sub["weekend"].sum(skipna=True); tsum = wsum + esum
        labels.append(label); ws.append(wsum/tsum*100); es.append(esum/tsum*100)
    x = np.arange(3); width = 0.32
    ax9.bar(x - width/2, ws, width, color=BRAND["weekday"], label="Weekday")
    ax9.bar(x + width/2, es, width, color=BRAND["weekend"], label="Weekend")
    ax9.set_xticks(x, labels); ax9.set_ylim(0, 85)
    style_card_axis(ax9); ax9.legend(frameon=False, fontsize=8.5, loc="upper right")

    # 10 cumulative, wide
    wide_w = col_w * 2 + gap
    ax10 = dashboard_card(fig, left, y4, wide_w, 0.155, 10, "CUMULATIVE TRAFFIC VOLUMES OVER TIME", "Accumulation toward 539.0 billion detected vehicle movement events")
    ax10.plot(df["month_start"], df["cum_weekday"], color=BRAND["weekday"], linewidth=1.9, label=f"Weekday ({billions(meta['weekday_volume'])})")
    ax10.plot(df["month_start"], df["cum_weekend"], color=BRAND["weekend"], linewidth=1.9, label=f"Weekend ({billions(meta['weekend_volume'])})")
    ax10.plot(df["month_start"], df["cum_total"], color=BRAND["total"], linewidth=1.7, linestyle="--", label=f"Total ({billions(meta['total_volume'])})")
    ax10.yaxis.set_major_formatter(FuncFormatter(y_billions)); ax10.xaxis.set_major_locator(mdates.YearLocator(2)); ax10.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    style_card_axis(ax10); ax10.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=1)

    # Key takeaways card
    xk = left + 2*(col_w + gap)
    yk = y4
    wk = col_w
    hk = 0.155
    card = FancyBboxPatch((xk, yk), wk, hk, boxstyle="round,pad=0.006,rounding_size=0.010",
                          linewidth=1.0, edgecolor=BRAND["border"], facecolor="white",
                          transform=fig.transFigure, zorder=0)
    fig.patches.append(card)
    fig.text(xk + 0.025, yk + hk - 0.035, "KEY TAKEAWAYS", fontsize=15.5, fontweight="bold", color="#0B2E6D", ha="left", va="top")
    takeaways = [
        f"{meta['weekday_share']:.2f}% of all detected movements occur on weekdays.",
        f"Weekend days reach {meta['weekend_avg_day_volume']/meta['weekday_avg_day_volume']*100:.1f}% of weekday daily intensity.",
        "Weekend share has trended higher through the recovery period.",
        "Melbourne remains highly active every day of the week.",
        f"Total analysed archive: {billions(meta['total_volume'])} movement events.",
    ]
    ytxt = yk + hk - 0.065
    for item in takeaways:
        fig.text(xk + 0.030, ytxt, u"• " + item, fontsize=10.5, color=BRAND["total"], ha="left", va="top")
        ytxt -= 0.025

    fig.text(0.035, 0.025,
             "Source: Melbourne SCATS weekday/weekend split archive | Zero-data month: Dec 2018 | Analysis by Spotswood Trailers",
             fontsize=10.5, color=BRAND["muted"], ha="left")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "weekday_weekend_00_dashboard_infographic.png"
    fig.savefig(path, facecolor=fig.get_facecolor(), dpi=240)
    plt.close(fig)
    print(f"Wrote {path}")

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate polished V3 weekday/weekend SCATS charts and dashboard infographic.")
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

    print("\nDone. Generated polished V3 weekday/weekend chart set.")


if __name__ == "__main__":
    main()
