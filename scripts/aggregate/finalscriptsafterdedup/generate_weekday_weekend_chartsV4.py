#!/usr/bin/env python3
r"""
generate_weekday_weekend_chartsV4.py

Creates polished, publication-ready weekday/weekend traffic charts and a dashboard infographic.

V4 fixes:
  - Individual chart titles/subtitles are drawn at the FIGURE level, not the axes level.
    This prevents heading/subheading collisions on saved PNGs.
  - Donut chart is properly centred with the legend centred underneath.
  - Larger top margins and consistent title bands across all charts.
  - Dashboard cards use a safer 4 + 4 + 3 layout with clear card title/subtitle spacing.
  - Better legend placement, less cramped labels, and cleaner source footer handling.

Example:
    python generate_weekday_weekend_chartsV4.py ^
      --csv A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_weekend_split.csv ^
      --json A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_weekend_split_final.json ^
      --out A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\weekday_weekend_v4
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

BRAND = {
    "weekday": "#0B5FA5",
    "weekend": "#FF8C1A",
    "total": "#202124",
    "muted": "#64748B",
    "grid": "#D9E2EC",
    "page": "#F6F9FC",
    "card": "#FFFFFF",
    "border": "#CBD5E1",
    "covid": "#E11D48",
    "covid_fill": "#FEE2E2",
    "green": "#16A34A",
}

COVID_START = pd.Timestamp("2020-03-01")
COVID_END = pd.Timestamp("2021-10-31")
SOURCE = "Source: Melbourne SCATS weekday/weekend split archive | Analysis by Spotswood Trailers"

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 240,
    "font.family": "DejaVu Sans",
    "axes.labelcolor": BRAND["total"],
    "xtick.color": BRAND["total"],
    "ytick.color": BRAND["total"],
    "axes.edgecolor": "#64748B",
    "axes.linewidth": 0.8,
})


def billions(x: float) -> str:
    return f"{x / 1_000_000_000:.1f}B"


def millions(x: float) -> str:
    return f"{x / 1_000_000:.0f}M"


def y_billions(x, _pos=None):
    if abs(x) < 1_000_000_000:
        return "0B" if abs(x) < 1 else f"{x / 1_000_000:.0f}M"
    return f"{x / 1_000_000_000:.1f}B"


def y_millions(x, _pos=None):
    return f"{x / 1_000_000:.0f}M"


def load_data(csv_path: Path, json_path: Path) -> Tuple[pd.DataFrame, Dict]:
    df = pd.read_csv(csv_path)
    meta = json.loads(json_path.read_text(encoding="utf-8"))

    if "month_start" not in df.columns:
        raise ValueError("CSV must include a month_start column")

    df["month_start"] = pd.to_datetime(df["month_start"])
    df = df.sort_values("month_start").reset_index(drop=True)

    colmap = {
        "total": "month_total_volume",
        "weekday": "month_weekday_volume",
        "weekend": "month_weekend_volume",
        "weekday_days": "month_weekday_days",
        "weekend_days": "month_weekend_days",
    }
    for out_col, in_col in colmap.items():
        if in_col not in df.columns:
            raise ValueError(f"CSV missing required column: {in_col}")
        df[out_col] = pd.to_numeric(df[in_col], errors="coerce")

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


def start_chart(figsize=(16, 9), top=0.84, bottom=0.10, left=0.10, right=0.98):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top)
    return fig, ax


def fig_header(fig, title: str, subtitle: str | None = None, y_title=0.965, y_sub=0.925):
    # Figure-level text avoids title/subtitle collisions caused by axes bbox cropping.
    fig.text(0.5, y_title, title, ha="center", va="top",
             fontsize=25, fontweight="bold", color=BRAND["total"])
    if subtitle:
        fig.text(0.5, y_sub, subtitle, ha="center", va="top",
                 fontsize=15, color=BRAND["muted"])


def footer(fig):
    fig.text(0.012, 0.018, SOURCE, ha="left", va="bottom", fontsize=10, color=BRAND["muted"])


def style_axis(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis=grid_axis, color=BRAND["grid"], linewidth=0.8, alpha=0.75)
    ax.tick_params(labelsize=12)


def add_covid_band(ax, label=True):
    ax.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.75, zorder=0)
    if label:
        ymin, ymax = ax.get_ylim()
        ax.text(COVID_START + (COVID_END - COVID_START) / 2, ymax - (ymax - ymin) * 0.065,
                "COVID disruption\nMar 2020 – Oct 2021", ha="center", va="top",
                fontsize=11, color=BRAND["covid"])


def value_labels(ax, bars, formatter, fontsize=15):
    ymin, ymax = ax.get_ylim()
    offset = (ymax - ymin) * 0.025
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + offset, formatter(h),
                ha="center", va="bottom", fontsize=fontsize, fontweight="bold", color="black")


def save(fig, out_dir: Path, filename: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Wrote {path}")


def chart_01_donut(meta: Dict, out_dir: Path):
    weekday = meta["weekday_volume"]
    weekend = meta["weekend_volume"]
    total = meta["total_volume"]
    wshare = meta["weekday_share"]
    eshare = meta["weekend_share"]

    fig, ax = start_chart(figsize=(12, 9), top=0.82, bottom=0.18, left=0.05, right=0.95)
    fig_header(fig, "Overall Traffic Share: Weekday vs Weekend",
               "Share of all detected SCATS vehicle movement events, 1 Jan 2014 – 7 Apr 2026")

    wedges, _ = ax.pie(
        [weekday, weekend], startangle=90, counterclock=False,
        colors=[BRAND["weekday"], BRAND["weekend"]], radius=1.0,
        wedgeprops=dict(width=0.37, edgecolor="white", linewidth=3),
    )
    ax.text(0, 0.08, billions(total), ha="center", va="center", fontsize=32,
            fontweight="bold", color=BRAND["total"])
    ax.text(0, -0.09, "total vehicle\nmovement events", ha="center", va="center",
            fontsize=14, color=BRAND["muted"], linespacing=1.1)

    ax.legend(
        wedges,
        [f"Weekday — {wshare:.2f}% ({billions(weekday)})", f"Weekend — {eshare:.2f}% ({billions(weekend)})"],
        loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=1, frameon=False, fontsize=14,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_anchor("C")
    footer(fig)
    save(fig, out_dir, "weekday_weekend_01_overall_share_donut.png")


def chart_02_total_bar(meta: Dict, out_dir: Path):
    fig, ax = start_chart(top=0.82)
    fig_header(fig, "Total Vehicle Movements: Weekday vs Weekend",
               "Full Melbourne SCATS archive, 2014-01-01 to 2026-04-07")
    values = [meta["weekday_volume"], meta["weekend_volume"]]
    bars = ax.bar(["Weekday", "Weekend"], values, color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax.set_ylim(0, max(values) * 1.32)
    value_labels(ax, bars, billions, fontsize=16)
    ax.text(0.5, 0.91, "Weekdays account for 404.9B movements; weekends still account for 134.1B.",
            transform=ax.transAxes, ha="center", va="center", fontsize=15, color=BRAND["muted"])
    ax.set_ylabel("Vehicle movement events", fontsize=13)
    ax.yaxis.set_major_formatter(FuncFormatter(y_billions))
    style_axis(ax)
    footer(fig)
    save(fig, out_dir, "weekday_weekend_02_total_volume_bar.png")


def chart_03_avg_day(meta: Dict, out_dir: Path):
    fig, ax = start_chart(top=0.82)
    fig_header(fig, "Average Daily Traffic Intensity: Weekday vs Weekend",
               "A typical weekend day reaches 82.7% of weekday daily intensity")
    values = [meta["weekday_avg_day_volume"], meta["weekend_avg_day_volume"]]
    bars = ax.bar(["Average weekday", "Average weekend day"], values,
                  color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax.set_ylim(0, max(values) * 1.35)
    value_labels(ax, bars, millions, fontsize=16)
    ax.set_ylabel("Average vehicle movement events per day", fontsize=13)
    ax.yaxis.set_major_formatter(FuncFormatter(y_millions))
    style_axis(ax)
    footer(fig)
    save(fig, out_dir, "weekday_weekend_03_average_daily_intensity_bar.png")


def chart_04_monthly_lines(df: pd.DataFrame, out_dir: Path):
    fig, ax = start_chart(top=0.82, bottom=0.12)
    fig_header(fig, "Monthly Traffic Volumes Over Time",
               "Weekday and weekend vehicle movements per month across the Melbourne SCATS archive")
    ax.plot(df["month_start"], df["weekday"], color=BRAND["weekday"], linewidth=2.2, label="Weekday monthly total")
    ax.plot(df["month_start"], df["weekend"], color=BRAND["weekend"], linewidth=2.2, label="Weekend monthly total")
    ax.yaxis.set_major_formatter(FuncFormatter(y_billions))
    ax.set_ylabel("Monthly vehicle movement events", fontsize=13)
    style_axis(ax)
    add_covid_band(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    footer(fig)
    save(fig, out_dir, "weekday_weekend_04_monthly_traffic_volumes_over_time.png")


def chart_05_weekend_share(df: pd.DataFrame, out_dir: Path):
    fig, ax = start_chart(top=0.82, bottom=0.12)
    fig_header(fig, "Weekend Share of Total Traffic Over Time",
               "Weekend vehicle movements as a percentage of total monthly SCATS traffic")
    ax.plot(df["month_start"], df["weekend_share"], color=BRAND["weekend"], linewidth=1.1, alpha=0.65, label="Monthly weekend share")
    ax.plot(df["month_start"], df["weekend_share_roll12"], color=BRAND["weekday"], linewidth=3.0, label="12-month rolling average")
    ax.set_ylabel("Weekend share of monthly traffic (%)", fontsize=13)
    ax.set_ylim(17, 32)
    style_axis(ax)
    add_covid_band(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    footer(fig)
    save(fig, out_dir, "weekday_weekend_05_weekend_share_over_time.png")


def chart_06_intensity(df: pd.DataFrame, out_dir: Path):
    fig, ax = start_chart(top=0.82, bottom=0.12)
    fig_header(fig, "Weekend Daily Intensity Relative to Weekday",
               "Weekend daily traffic as a percentage of weekday daily traffic, normalised by day count")
    ax.plot(df["month_start"], df["weekend_intensity_vs_weekday"], color=BRAND["weekend"], linewidth=2.4)
    ax.axhline(100, color=BRAND["total"], linestyle="--", linewidth=1.2, alpha=0.75)
    ax.text(0.90, 0.96, "100% = weekday intensity", transform=ax.transAxes,
            ha="right", va="center", fontsize=12, color=BRAND["muted"])
    ax.set_ylabel("Weekend intensity / weekday intensity (%)", fontsize=13)
    ax.set_ylim(62, 102)
    style_axis(ax)
    add_covid_band(ax)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    footer(fig)
    save(fig, out_dir, "weekday_weekend_06_weekend_daily_intensity_relative_to_weekday.png")


def chart_07_composition(df: pd.DataFrame, out_dir: Path):
    fig, ax = start_chart(figsize=(18, 8), top=0.80, bottom=0.14)
    fig_header(fig, "Monthly Traffic Composition: Weekday vs Weekend Share",
               "Each bar sums to 100% for the month")
    x = df["month_start"]
    ax.bar(x, df["weekday_share"], width=23, color=BRAND["weekday"], label="Weekday share")
    ax.bar(x, df["weekend_share"], bottom=df["weekday_share"], width=23, color=BRAND["weekend"], label="Weekend share")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of monthly traffic (%)", fontsize=13)
    style_axis(ax)
    ax.legend(loc="upper left", bbox_to_anchor=(0.04, 1.01), ncol=2, frameon=False, fontsize=12)
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    footer(fig)
    save(fig, out_dir, "weekday_weekend_07_monthly_traffic_composition.png")


def chart_08_heatmap(df: pd.DataFrame, out_dir: Path):
    tmp = df.copy()
    tmp["year"] = tmp["month_start"].dt.year
    tmp["month"] = tmp["month_start"].dt.month
    pivot = tmp.pivot(index="year", columns="month", values="weekend_share")
    fig, ax = start_chart(figsize=(16, 9), top=0.82, bottom=0.12, left=0.10, right=0.91)
    fig_header(fig, "Weekend Share Heatmap by Year and Month",
               "Darker cells indicate months where weekends made up a larger share of Melbourne SCATS traffic")
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrBr", vmin=np.nanmin(pivot.values), vmax=np.nanmax(pivot.values))
    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], fontsize=12)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index.astype(str), fontsize=12)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=9, color="#111827")
    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.04)
    cbar.set_label("Weekend share (%)", fontsize=13)
    footer(fig)
    save(fig, out_dir, "weekday_weekend_08_weekend_share_heatmap.png")


def chart_09_covid_eras(df: pd.DataFrame, out_dir: Path):
    periods = [
        ("Pre-COVID\nJan 2014 – Feb 2020", df["month_start"] < COVID_START),
        ("COVID disruption\nMar 2020 – Oct 2021", (df["month_start"] >= COVID_START) & (df["month_start"] <= COVID_END)),
        ("Recovery / post-COVID\nNov 2021 – Apr 2026", df["month_start"] > COVID_END),
    ]
    labels, wday, wend = [], [], []
    for label, mask in periods:
        sub = df.loc[mask]
        total = sub["total"].sum(skipna=True)
        labels.append(label)
        wday.append(sub["weekday"].sum(skipna=True) / total * 100)
        wend.append(sub["weekend"].sum(skipna=True) / total * 100)
    x = np.arange(len(labels))
    width = 0.34
    fig, ax = start_chart(top=0.82, bottom=0.18)
    fig_header(fig, "Traffic Composition Across COVID Eras",
               "Average weekday and weekend share before, during, and after the COVID disruption period")
    b1 = ax.bar(x - width/2, wday, width, color=BRAND["weekday"], label="Weekday share")
    b2 = ax.bar(x + width/2, wend, width, color=BRAND["weekend"], label="Weekend share")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=12)
    ax.set_ylim(0, 85)
    ax.set_ylabel("Share of period traffic (%)", fontsize=13)
    style_axis(ax)
    ax.legend(loc="upper right", frameon=False, fontsize=12)
    value_labels(ax, b1, lambda v: f"{v:.1f}%", fontsize=13)
    value_labels(ax, b2, lambda v: f"{v:.1f}%", fontsize=13)
    footer(fig)
    save(fig, out_dir, "weekday_weekend_09_traffic_composition_across_covid_eras.png")


def chart_10_cumulative(df: pd.DataFrame, out_dir: Path, meta: Dict):
    fig, ax = start_chart(top=0.82, bottom=0.12)
    fig_header(fig, "Cumulative Traffic Volumes Over Time",
               "Accumulation toward 539.0B detected vehicle movement events")
    ax.plot(df["month_start"], df["cum_weekday"], color=BRAND["weekday"], linewidth=2.4,
            label=f"Cumulative weekday ({billions(meta['weekday_volume'])})")
    ax.plot(df["month_start"], df["cum_weekend"], color=BRAND["weekend"], linewidth=2.4,
            label=f"Cumulative weekend ({billions(meta['weekend_volume'])})")
    ax.plot(df["month_start"], df["cum_total"], color=BRAND["total"], linewidth=2.0, linestyle="--",
            label=f"Cumulative total ({billions(meta['total_volume'])})")
    ax.yaxis.set_major_formatter(FuncFormatter(y_billions))
    ax.set_ylabel("Cumulative vehicle movement events", fontsize=13)
    style_axis(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=12)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    footer(fig)
    save(fig, out_dir, "weekday_weekend_10_cumulative_traffic_volumes_over_time.png")


# Dashboard helpers

def card(fig, rect, title, subtitle=None):
    x, y, w, h = rect
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.006",
                           transform=fig.transFigure, facecolor=BRAND["card"], edgecolor=BRAND["border"], linewidth=0.8)
    fig.patches.append(patch)
    fig.text(x + 0.015*w, y + h - 0.030*h, title, ha="left", va="top",
             fontsize=10.5, fontweight="bold", color="#0B3470")
    if subtitle:
        fig.text(x + 0.015*w, y + h - 0.083*h, subtitle, ha="left", va="top",
                 fontsize=8.0, color=BRAND["muted"])
    # axes area with enough top clearance for title/subtitle
    ax = fig.add_axes([x + 0.075*w, y + 0.12*h, w*0.85, h*0.68], zorder=2)
    ax.set_facecolor("white")
    return ax


def mini_style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="y", color=BRAND["grid"], linewidth=0.5, alpha=0.7)
    ax.tick_params(labelsize=6.8)


def dashboard(df: pd.DataFrame, meta: Dict, out_dir: Path):
    fig = plt.figure(figsize=(24, 14), facecolor=BRAND["page"])
    fig.text(0.5, 0.982, "MELBOURNE SCATS TRAFFIC ANALYTICS", ha="center", va="top",
             fontsize=26, fontweight="bold", color="#0B3470")
    fig.text(0.5, 0.946, "WEEKDAY vs WEEKEND TRAFFIC: 12-YEAR BEHAVIOURAL INSIGHTS", ha="center", va="top",
             fontsize=34, fontweight="bold", color="#0B3470")

    margin = 0.016
    gap = 0.014
    top_y = 0.905
    row_h = 0.265
    row2_y = 0.605
    row3_y = 0.305
    row4_y = 0.065
    col_w4 = (1 - 2*margin - 3*gap) / 4
    col_w3 = (1 - 2*margin - 2*gap) / 3

    # Row 1: four cards
    rects1 = [(margin + i*(col_w4+gap), top_y-row_h, col_w4, row_h) for i in range(4)]
    ax1 = card(fig, rects1[0], "1. OVERALL TRAFFIC SHARE", "Proportion of total vehicle movements")
    wedges, _ = ax1.pie([meta["weekday_volume"], meta["weekend_volume"]], startangle=90, counterclock=False,
                        colors=[BRAND["weekday"], BRAND["weekend"]], wedgeprops=dict(width=0.38, edgecolor="white", linewidth=1.2))
    ax1.text(0, 0.08, billions(meta["total_volume"]), ha="center", va="center", fontsize=17, fontweight="bold")
    ax1.text(0, -0.12, "total vehicle\nmovement events", ha="center", va="center", fontsize=7.5, color=BRAND["muted"])
    ax1.legend(wedges, [f"Weekday — {meta['weekday_share']:.2f}%", f"Weekend — {meta['weekend_share']:.2f}%"],
               loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=1, frameon=False, fontsize=7)
    ax1.set_aspect("equal")

    ax2 = card(fig, rects1[1], "2. TOTAL TRAFFIC VOLUME", "Total vehicle movements over the 12-year period")
    vals = [meta["weekday_volume"], meta["weekend_volume"]]
    bars = ax2.bar(["Weekday", "Weekend"], vals, color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax2.yaxis.set_major_formatter(FuncFormatter(y_billions)); ax2.set_ylim(0, max(vals)*1.28); mini_style(ax2)
    for b in bars: ax2.text(b.get_x()+b.get_width()/2, b.get_height()*1.03, billions(b.get_height()), ha="center", fontsize=8, fontweight="bold")

    ax3 = card(fig, rects1[2], "3. AVERAGE DAILY TRAFFIC INTENSITY", "Average vehicle movements per day")
    vals = [meta["weekday_avg_day_volume"], meta["weekend_avg_day_volume"]]
    bars = ax3.bar(["Average\nweekday", "Average\nweekend day"], vals, color=[BRAND["weekday"], BRAND["weekend"]], width=0.55)
    ax3.yaxis.set_major_formatter(FuncFormatter(y_millions)); ax3.set_ylim(0, max(vals)*1.30); mini_style(ax3)
    for b in bars: ax3.text(b.get_x()+b.get_width()/2, b.get_height()*1.03, millions(b.get_height()), ha="center", fontsize=8, fontweight="bold")

    ax4 = card(fig, rects1[3], "4. MONTHLY TRAFFIC VOLUMES OVER TIME", "Weekday and weekend vehicle movements per month")
    ax4.plot(df["month_start"], df["weekday"], color=BRAND["weekday"], lw=1.4, label="Weekday")
    ax4.plot(df["month_start"], df["weekend"], color=BRAND["weekend"], lw=1.4, label="Weekend")
    ax4.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.8)
    ax4.yaxis.set_major_formatter(FuncFormatter(y_billions)); mini_style(ax4); ax4.legend(frameon=False, fontsize=6, loc="upper left")
    ax4.xaxis.set_major_locator(mdates.YearLocator(2)); ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Row 2: four cards
    rects2 = [(margin + i*(col_w4+gap), row2_y-row_h, col_w4, row_h) for i in range(4)]
    ax5 = card(fig, rects2[0], "5. WEEKEND SHARE OF TOTAL TRAFFIC", "Weekend traffic as a percentage of total monthly traffic")
    ax5.plot(df["month_start"], df["weekend_share"], color=BRAND["weekend"], lw=0.9, alpha=0.7, label="Monthly")
    ax5.plot(df["month_start"], df["weekend_share_roll12"], color=BRAND["weekday"], lw=2.0, label="12-month avg")
    ax5.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.8); ax5.set_ylim(18, 31.5); mini_style(ax5)
    ax5.legend(frameon=False, fontsize=6, loc="upper left"); ax5.xaxis.set_major_locator(mdates.YearLocator(2)); ax5.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax6 = card(fig, rects2[1], "6. WEEKEND DAILY INTENSITY RELATIVE TO WEEKDAY", "Weekend daily traffic as a % of weekday daily intensity")
    ax6.plot(df["month_start"], df["weekend_intensity_vs_weekday"], color=BRAND["weekend"], lw=1.4)
    ax6.axhline(100, color=BRAND["total"], ls="--", lw=0.8, alpha=0.65)
    ax6.axvspan(COVID_START, COVID_END, color=BRAND["covid_fill"], alpha=0.8); ax6.set_ylim(60, 102); mini_style(ax6)
    ax6.xaxis.set_major_locator(mdates.YearLocator(2)); ax6.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax7 = card(fig, rects2[2], "7. MONTHLY TRAFFIC COMPOSITION", "Weekday and weekend share of total traffic each month")
    ax7.bar(df["month_start"], df["weekday_share"], width=23, color=BRAND["weekday"], label="Weekday")
    ax7.bar(df["month_start"], df["weekend_share"], bottom=df["weekday_share"], width=23, color=BRAND["weekend"], label="Weekend")
    ax7.set_ylim(0, 100); mini_style(ax7); ax7.legend(frameon=False, fontsize=6, loc="upper center", ncol=2)
    ax7.xaxis.set_major_locator(mdates.YearLocator(2)); ax7.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax8 = card(fig, rects2[3], "8. WEEKEND SHARE HEATMAP BY YEAR AND MONTH", "Weekend share (%) of total traffic")
    tmp = df.copy(); tmp["year"] = tmp["month_start"].dt.year; tmp["month"] = tmp["month_start"].dt.month
    pivot = tmp.pivot(index="year", columns="month", values="weekend_share")
    im = ax8.imshow(pivot.values, aspect="auto", cmap="YlOrBr", vmin=np.nanmin(pivot.values), vmax=np.nanmax(pivot.values))
    ax8.set_xticks(range(12)); ax8.set_xticklabels(list("JFMAMJJASOND"), fontsize=6)
    ax8.set_yticks(range(len(pivot.index))); ax8.set_yticklabels(pivot.index.astype(str), fontsize=6)

    # Row 3: 3 cards
    rects3 = [(margin + i*(col_w3+gap), row3_y-row_h, col_w3, row_h) for i in range(3)]
    ax9 = card(fig, rects3[0], "9. TRAFFIC COMPOSITION ACROSS COVID ERAS", "Average weekday and weekend share by period")
    periods = [
        ("Pre-COVID\nJan 2014 – Feb 2020", df["month_start"] < COVID_START),
        ("COVID disruption\nMar 2020 – Oct 2021", (df["month_start"] >= COVID_START) & (df["month_start"] <= COVID_END)),
        ("Recovery / post-COVID\nNov 2021 – Apr 2026", df["month_start"] > COVID_END),
    ]
    labs, wday, wend = [], [], []
    for label, mask in periods:
        sub = df.loc[mask]; total = sub["total"].sum(skipna=True)
        labs.append(label); wday.append(sub["weekday"].sum(skipna=True)/total*100); wend.append(sub["weekend"].sum(skipna=True)/total*100)
    x = np.arange(3); width = 0.32
    ax9.bar(x-width/2, wday, width, color=BRAND["weekday"], label="Weekday share")
    ax9.bar(x+width/2, wend, width, color=BRAND["weekend"], label="Weekend share")
    ax9.set_xticks(x); ax9.set_xticklabels(["Pre-COVID", "COVID", "Recovery"], fontsize=6); ax9.set_ylim(0, 85); mini_style(ax9)
    ax9.legend(frameon=False, fontsize=6, loc="upper right")

    ax10 = card(fig, rects3[1], "10. CUMULATIVE TRAFFIC VOLUMES OVER TIME", "Cumulative vehicle movements since January 2014")
    ax10.plot(df["month_start"], df["cum_weekday"], color=BRAND["weekday"], lw=1.5, label="Cumulative weekday")
    ax10.plot(df["month_start"], df["cum_weekend"], color=BRAND["weekend"], lw=1.5, label="Cumulative weekend")
    ax10.plot(df["month_start"], df["cum_total"], color=BRAND["total"], lw=1.2, ls="--", label="Cumulative total")
    ax10.yaxis.set_major_formatter(FuncFormatter(y_billions)); mini_style(ax10); ax10.legend(frameon=False, fontsize=6, loc="upper left")
    ax10.xaxis.set_major_locator(mdates.YearLocator(2)); ax10.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Takeaway card
    x0, y0, w0, h0 = rects3[2]
    patch = FancyBboxPatch((x0, y0), w0, h0, boxstyle="round,pad=0.006,rounding_size=0.006",
                           transform=fig.transFigure, facecolor=BRAND["card"], edgecolor=BRAND["border"], linewidth=0.8)
    fig.patches.append(patch)
    fig.text(x0+0.04*w0, y0+h0-0.08*h0, "KEY TAKEAWAYS", fontsize=18, fontweight="bold", color="#0B3470", ha="left", va="top")
    takeaways = [
        "75.13% of all vehicle movements occur on weekdays.",
        "Weekend days reach 82.7% of weekday daily intensity.",
        "Weekend share has trended higher through the recovery period.",
        "Melbourne's road network remains highly active every day of the week.",
        "Total analysed archive: 539.0B movement events.",
    ]
    y = y0+h0-0.23*h0
    for t in takeaways:
        fig.text(x0+0.06*w0, y, f"• {t}", fontsize=12, color=BRAND["total"], ha="left", va="top")
        y -= 0.13*h0

    fig.text(0.015, 0.018, SOURCE, ha="left", va="bottom", fontsize=11, color=BRAND["muted"])
    save(fig, out_dir, "weekday_weekend_00_dashboard_infographic.png")


def main():
    parser = argparse.ArgumentParser(description="Generate weekday/weekend split charts V4")
    parser.add_argument("--csv", required=True, type=Path, help="Path to weekday_weekend_split.csv")
    parser.add_argument("--json", required=True, type=Path, help="Path to weekday_weekend_split_final.json")
    parser.add_argument("--out", required=True, type=Path, help="Output directory")
    args = parser.parse_args()

    df, meta = load_data(args.csv, args.json)
    out_dir = args.out

    dashboard(df, meta, out_dir)
    chart_01_donut(meta, out_dir)
    chart_02_total_bar(meta, out_dir)
    chart_03_avg_day(meta, out_dir)
    chart_04_monthly_lines(df, out_dir)
    chart_05_weekend_share(df, out_dir)
    chart_06_intensity(df, out_dir)
    chart_07_composition(df, out_dir)
    chart_08_heatmap(df, out_dir)
    chart_09_covid_eras(df, out_dir)
    chart_10_cumulative(df, out_dir, meta)

    print("\nDone. V4 chart pack created successfully.")


if __name__ == "__main__":
    main()
