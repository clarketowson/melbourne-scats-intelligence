#!/usr/bin/env python3
r"""
generate_daily_totals_charts_v2_2_colour_annotated.py

Colour-enhanced and annotated daily totals chart generator.

Fixes:
- Robust date/volume column detection copied from the working V1 script.
- Keeps all 7 daily charts: 18 to 24.
- Uses a time-temperature colour story:
    early years = cool purple/blue
    later years = warmer orange/yellow/red
- Uses blue/cool tones for quiet days and warm tones for busiest days.
- Uses green/red diverging colours for single-day rises/falls.
- Fixes Matplotlib boxplot deprecation by using tick_labels where available.
- Adds larger publication-friendly fonts.
- Adds COVID disruption shading.
- Adds labels for major anomaly / disruption points.

Input:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals_final.json
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
DAILY_CSV = REPORT_DIR / "daily_totals.csv"
DAILY_FINAL_JSON = REPORT_DIR / "daily_totals_final.json"
CHART_DIR = REPORT_DIR / "charts"
SUMMARY_JSON = REPORT_DIR / "daily_totals_charts_summary.json"

TIME_CMAP = plt.cm.plasma
HOT_CMAP = plt.cm.YlOrRd
COOL_CMAP = plt.cm.Blues

COVID_START = pd.Timestamp("2020-03-01")
COVID_END = pd.Timestamp("2021-10-31")
ANOMALY_DATE = pd.Timestamp("2025-05-27")
REBOUND_DATE = pd.Timestamp("2025-05-28")

plt.rcParams.update({
    "font.size": 12,
    "axes.titlesize": 17,
    "axes.labelsize": 13,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
    "figure.titlesize": 18,
})


def fmt_int(n) -> str:
    if pd.isna(n):
        return "N/A"
    return f"{int(n):,}"


def savefig(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")


def style_axes(title: str, xlabel: str, ylabel: str | None = None) -> None:
    plt.title(title, fontsize=17, pad=12)
    plt.xlabel(xlabel)
    if ylabel:
        plt.ylabel(ylabel)
    plt.grid(True, alpha=0.25)


def shade_covid(ax) -> None:
    ax.axvspan(
        COVID_START,
        COVID_END,
        color="#666666",
        alpha=0.10,
        label="COVID disruption window",
        zorder=0,
    )


def annotate_date(ax, df: pd.DataFrame, when: pd.Timestamp, text: str, y_offset: float = 10) -> None:
    row = df.loc[df["date"] == when]
    if row.empty:
        return
    y = float(row.iloc[0]["total_volume"]) / 1_000_000
    ax.annotate(
        text,
        xy=(when, y),
        xytext=(when, y + y_offset),
        arrowprops=dict(arrowstyle="->", linewidth=1.1, color="#333333"),
        fontsize=11,
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#999999", alpha=0.92),
    )


def detect_column(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    lower_map = {c.lower().strip(): c for c in df.columns}

    for candidate in candidates:
        key = candidate.lower().strip()
        if key in lower_map:
            return lower_map[key]

    raise ValueError(
        f"Could not find {label} column in {DAILY_CSV}.\n"
        f"Columns found: {list(df.columns)}\n"
        f"Tried: {candidates}"
    )


def load_daily_totals() -> pd.DataFrame:
    if not DAILY_CSV.exists():
        raise FileNotFoundError(f"Missing input CSV: {DAILY_CSV}")

    df = pd.read_csv(DAILY_CSV)
    print(f"Loaded CSV columns: {list(df.columns)}")

    date_col = detect_column(
        df,
        ["date_local", "count_date", "date", "day", "traffic_date"],
        "date",
    )

    volume_col = detect_column(
        df,
        [
            "total_volume",
            "daily_total_volume",
            "day_total_volume",
            "cleaned_volume",
            "total_cleaned_volume",
            "daily_cleaned_volume",
            "volume",
            "total",
        ],
        "volume",
    )

    df = df.rename(columns={date_col: "date", volume_col: "total_volume"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["total_volume"] = pd.to_numeric(df["total_volume"], errors="coerce")

    df = df.dropna(subset=["date"])
    df = df.dropna(subset=["total_volume"])
    df = df.sort_values("date").reset_index(drop=True)

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["weekday"] = df["date"].dt.day_name()
    df["day_of_week_num"] = df["date"].dt.dayofweek
    df["rolling_7d"] = df["total_volume"].rolling(7, min_periods=3).mean()
    df["rolling_30d"] = df["total_volume"].rolling(30, min_periods=10).mean()
    df["daily_change"] = df["total_volume"].diff()
    df["daily_change_abs"] = df["daily_change"].abs()
    df["time_rank"] = np.linspace(0, 1, len(df))

    return df


def add_time_colourbar(ax, label: str = "Time progression: cool past → hot present") -> None:
    sm = mpl.cm.ScalarMappable(cmap=TIME_CMAP, norm=mpl.colors.Normalize(vmin=0, vmax=1))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, pad=0.012)
    cbar.set_label(label)
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1])
    cbar.set_ticklabels(["2014", "2017", "2020", "2023", "2026"])


def chart_daily_line(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "18_daily_total_traffic_line.png"

    fig, ax = plt.subplots(figsize=(16, 7))
    x = df["date"].to_numpy()
    y = (df["total_volume"] / 1_000_000).to_numpy()
    t = df["time_rank"].to_numpy()

    for i in range(len(df) - 1):
        ax.plot(x[i:i + 2], y[i:i + 2], color=TIME_CMAP(t[i]), linewidth=1.25, alpha=0.9)

    shade_covid(ax)
    annotate_date(ax, df, ANOMALY_DATE, "2025-05-27\nlikely data anomaly", y_offset=18)

    ax.set_title("Melbourne SCATS Daily Total Traffic — Heat Through Time", fontsize=17, pad=12)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cleaned vehicle movements per day (millions)")
    ax.grid(True, alpha=0.25)
    add_time_colourbar(ax)

    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")
    return path


def chart_7day_rolling(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "19_daily_total_traffic_7day_rolling.png"

    fig, ax = plt.subplots(figsize=(16, 7))

    ax.plot(
        df["date"],
        df["total_volume"] / 1_000_000,
        color="#9ecae1",
        alpha=0.28,
        linewidth=0.8,
        label="Daily total",
    )

    valid = df.dropna(subset=["rolling_7d"]).copy()
    x = valid["date"].to_numpy()
    y = (valid["rolling_7d"] / 1_000_000).to_numpy()
    t = np.linspace(0, 1, len(valid))

    for i in range(len(valid) - 1):
        ax.plot(x[i:i + 2], y[i:i + 2], color=TIME_CMAP(t[i]), linewidth=2.4, alpha=0.95)

    shade_covid(ax)
    annotate_date(ax, df, ANOMALY_DATE, "largest one-day fall\nlikely coverage anomaly", y_offset=18)

    ax.set_title("Melbourne SCATS Daily Traffic — 7-Day Rolling Heat Trend", fontsize=17, pad=12)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cleaned vehicle movements per day (millions)")
    ax.grid(True, alpha=0.25)
    add_time_colourbar(ax)
    ax.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")
    return path


def chart_30day_rolling(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "20_daily_total_traffic_30day_rolling.png"

    fig, ax = plt.subplots(figsize=(16, 7))

    ax.plot(
        df["date"],
        df["total_volume"] / 1_000_000,
        color="#bdd7e7",
        alpha=0.24,
        linewidth=0.8,
        label="Daily total",
    )

    valid = df.dropna(subset=["rolling_30d"]).copy()
    x = valid["date"].to_numpy()
    y = (valid["rolling_30d"] / 1_000_000).to_numpy()
    t = np.linspace(0, 1, len(valid))

    for i in range(len(valid) - 1):
        ax.plot(x[i:i + 2], y[i:i + 2], color=TIME_CMAP(t[i]), linewidth=2.8, alpha=0.98)

    ax.fill_between(valid["date"], y, y.min(), color="#fdd49e", alpha=0.10)
    shade_covid(ax)
    annotate_date(ax, df, ANOMALY_DATE, "sharp isolated drop\ncheck source coverage", y_offset=18)

    ax.set_title("Melbourne SCATS Daily Traffic — 30-Day Rolling Heat Trend", fontsize=17, pad=12)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cleaned vehicle movements per day (millions)")
    ax.grid(True, alpha=0.25)
    add_time_colourbar(ax)
    ax.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")
    return path


def chart_top_50_days(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "21_top_50_busiest_days.png"

    top = df.nlargest(50, "total_volume").copy()
    top = top.sort_values("total_volume", ascending=True)
    norm = mpl.colors.Normalize(vmin=top["total_volume"].min(), vmax=top["total_volume"].max())
    colors = HOT_CMAP(norm(top["total_volume"]))

    plt.figure(figsize=(12, 14))
    plt.barh(top["date"].dt.strftime("%Y-%m-%d"), top["total_volume"] / 1_000_000, color=colors)
    style_axes("Top 50 Busiest Melbourne SCATS Days — Hot Peak Days", "Cleaned vehicle movements (millions)", "Date")
    savefig(path)
    return path


def chart_bottom_50_days(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "22_bottom_50_quietest_days.png"

    bottom = df.nsmallest(50, "total_volume").copy()
    bottom = bottom.sort_values("total_volume", ascending=False)
    norm = mpl.colors.Normalize(vmin=bottom["total_volume"].min(), vmax=bottom["total_volume"].max())
    colors = COOL_CMAP(1 - norm(bottom["total_volume"]))

    plt.figure(figsize=(12, 14))
    plt.barh(bottom["date"].dt.strftime("%Y-%m-%d"), bottom["total_volume"] / 1_000_000, color=colors)
    style_axes("Bottom 50 Quietest Melbourne SCATS Days — Cold / Disrupted Days", "Cleaned vehicle movements (millions)", "Date")
    savefig(path)
    return path


def chart_year_boxplot(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "23_daily_totals_by_year_boxplot.png"

    years = sorted(df["year"].unique())
    data = [df.loc[df["year"] == y, "total_volume"] / 1_000_000 for y in years]
    colors = TIME_CMAP(np.linspace(0, 1, len(years)))

    fig, ax = plt.subplots(figsize=(15, 7))

    try:
        bp = ax.boxplot(data, tick_labels=[str(y) for y in years], showfliers=False, patch_artist=True)
    except TypeError:
        bp = ax.boxplot(data, labels=[str(y) for y in years], showfliers=False, patch_artist=True)

    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.55)
        patch.set_edgecolor("#222222")

    for median in bp["medians"]:
        median.set_color("#111111")
        median.set_linewidth(1.8)

    ax.set_title("Daily Traffic Distribution by Year — Warming Traffic Profile", fontsize=17, pad=12)
    ax.set_xlabel("Year")
    ax.set_ylabel("Daily cleaned vehicle movements (millions)")
    ax.grid(True, axis="y", alpha=0.25)
    plt.xticks(rotation=45)

    sm = mpl.cm.ScalarMappable(cmap=TIME_CMAP, norm=mpl.colors.Normalize(vmin=min(years), vmax=max(years)))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, pad=0.012)
    cbar.set_label("Year: cool past → hot present")

    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")
    return path


def chart_largest_single_day_changes(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "24_largest_single_day_changes.png"

    changes = df.dropna(subset=["daily_change"]).copy()
    changes = changes.nlargest(30, "daily_change_abs").sort_values("daily_change_abs", ascending=True)

    labels = changes["date"].dt.strftime("%Y-%m-%d")
    values = changes["daily_change"] / 1_000_000
    colors = ["#d73027" if v < 0 else "#1a9850" for v in values]

    plt.figure(figsize=(12, 10))
    plt.barh(labels, values, color=colors)
    plt.title("Largest Single-Day Traffic Changes — Red Falls / Green Rebounds", fontsize=17, pad=12)
    plt.xlabel("Change from previous day (millions of cleaned vehicle movements)")
    plt.ylabel("Date")
    plt.axvline(0, linewidth=1.2, color="#333333")
    plt.grid(True, axis="x", alpha=0.25)

    ax = plt.gca()
    if "2025-05-27" in set(labels):
        idx = list(labels).index("2025-05-27")
        ax.annotate(
            "largest fall\nlikely anomaly",
            xy=(values.iloc[idx] if hasattr(values, "iloc") else values[idx], idx),
            xytext=(-118, idx + 1.8),
            arrowprops=dict(arrowstyle="->", linewidth=1.1, color="#333333"),
            fontsize=11,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#999999", alpha=0.92),
        )
    if "2025-05-28" in set(labels):
        idx = list(labels).index("2025-05-28")
        ax.annotate(
            "next-day rebound",
            xy=(values.iloc[idx] if hasattr(values, "iloc") else values[idx], idx),
            xytext=(92, idx - 2.2),
            arrowprops=dict(arrowstyle="->", linewidth=1.1, color="#333333"),
            fontsize=11,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#999999", alpha=0.92),
        )

    savefig(path)
    return path


def write_summary(df: pd.DataFrame, chart_paths: list[Path]) -> None:
    busiest = df.loc[df["total_volume"].idxmax()]
    quietest = df.loc[df["total_volume"].idxmin()]

    changes = df.dropna(subset=["daily_change"]).copy()
    biggest_rise = changes.loc[changes["daily_change"].idxmax()]
    biggest_fall = changes.loc[changes["daily_change"].idxmin()]

    summary = {
        "metric_name": "daily_totals_charts_colour_v2_2_annotated",
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
    print("DAILY TOTALS COLOUR CHART SUMMARY")
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
    print("GENERATE DAILY TOTALS COLOUR CHARTS V2.2 ANNOTATED")
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
