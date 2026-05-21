#!/usr/bin/env python3
"""
generate_time_bin_profile_charts_production.py

Production chart generator for Melbourne SCATS time-bin profile outputs.

Reads:
  - time_bin_profile.csv
  - time_bin_profile_final.json

Writes:
  - media-ready PNG charts
  - aggregated 96-bin CSV
  - chart manifest JSON

Example:
  python generate_time_bin_profile_charts_production.py ^
    --csv "A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv" ^
    --json "A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile_final.json" ^
    --out "A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\time_bin_profile"
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd


# ---------------------------------------------------------------------
# Visual language
# ---------------------------------------------------------------------

COLOURS = {
    "peak": "#d73027",          # red: peak pressure
    "peak_dark": "#a50014",
    "transition": "#fdae61",    # orange: build / decline
    "plateau": "#fee08b",       # yellow: daytime plateau
    "quiet": "#1a9850",         # green: quiet
    "quiet_light": "#a6dba0",
    "analysis": "#2c7bb6",      # blue: structural / analytical
    "anomaly": "#6a3d9a",       # purple: special / anomaly
    "text": "#2b2b2b",
    "muted": "#5d6b7c",
    "grid": "#dbe3ef",
    "border": "#d7dee8",
    "bg": "#ffffff",
}

PERIODS = [
    # name, start inclusive, end exclusive, colour
    ("Overnight Quiet", "00:00", "05:00", COLOURS["quiet"]),
    ("Morning Build", "05:00", "10:00", COLOURS["transition"]),
    ("Business-Day Plateau", "10:00", "15:00", COLOURS["plateau"]),
    ("Afternoon Peak", "15:00", "19:00", COLOURS["peak"]),
    ("Evening Decline", "19:00", "24:00", COLOURS["transition"]),
]

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 160,
    "font.family": "DejaVu Sans",
    "axes.titlesize": 24,
    "axes.titleweight": "bold",
    "axes.labelsize": 14,
    "axes.labelcolor": COLOURS["text"],
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "axes.edgecolor": COLOURS["border"],
    "axes.linewidth": 1,
    "grid.color": COLOURS["grid"],
    "grid.linestyle": "-",
    "grid.linewidth": 1,
    "axes.grid": True,
})


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def read_json(path: Path) -> Dict:
    if not path.exists():
        die(f"JSON file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"Could not read JSON {path}: {exc}")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        die(f"CSV file not found: {path}")
    try:
        return pd.read_csv(path)
    except Exception as exc:
        die(f"Could not read CSV {path}: {exc}")


def find_col(df: pd.DataFrame, candidates: List[str], contains: List[str] | None = None) -> str:
    cols = list(df.columns)
    lower = {c.lower(): c for c in cols}

    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]

    if contains:
        for c in cols:
            lc = c.lower()
            if all(s.lower() in lc for s in contains):
                return c

    die(f"Could not find required column. Candidates={candidates}. Columns={cols}")
    return ""


def time_to_minutes(t: str) -> int:
    parts = str(t).strip().split(":")
    if len(parts) < 2:
        die(f"Invalid time value: {t}")
    return int(parts[0]) * 60 + int(parts[1])


def minutes_to_label(m: int) -> str:
    m = m % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def billions(x: float) -> str:
    if abs(x) >= 1_000_000_000:
        return f"{x / 1_000_000_000:.2f}B"
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if abs(x) >= 1_000:
        return f"{x / 1_000:.1f}K"
    return f"{x:,.0f}"


def axis_billions(x, pos=None) -> str:
    if x == 0:
        return "0"
    if abs(x) >= 1_000_000_000:
        return f"{x / 1_000_000_000:.2f}B"
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    return f"{x:,.0f}"


def axis_daily(x, pos=None) -> str:
    if x == 0:
        return "0"
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if abs(x) >= 1_000:
        return f"{x / 1_000:.0f}K"
    return f"{x:,.0f}"


def nice_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=COLOURS["text"])
    ax.grid(axis="y", alpha=0.95)
    ax.grid(axis="x", alpha=0.25)


def add_title(ax, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", pad=38, color=COLOURS["text"])
    ax.text(
        0.0, 1.022, subtitle,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=13,
        color=COLOURS["muted"],
        clip_on=False,
    )


def save_fig(fig, out: Path) -> None:
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.935])
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def period_for_minutes(minutes: int) -> Tuple[str, str]:
    for name, start, end, colour in PERIODS:
        s = time_to_minutes(start)
        e = 24 * 60 if end == "24:00" else time_to_minutes(end)
        if s <= minutes < e:
            return name, colour
    return "Unknown", COLOURS["muted"]


def prepare_96_bins(df: pd.DataFrame, meta: Dict) -> pd.DataFrame:
    time_col = find_col(df, ["time_bin", "time", "time_of_day"], contains=["time"])
    total_col = find_col(
        df,
        [
            "total_volume",
            "total_vehicle_volume",
            "vehicle_volume",
            "volume",
            "total",
            "bin_total_volume",
            "total_cleaned_volume",
        ],
        contains=["volume"],
    )

    out = df[[time_col, total_col]].copy()
    out.columns = ["time_bin", "total_volume"]

    out["time_bin"] = out["time_bin"].astype(str).str.slice(0, 5)
    out["total_volume"] = pd.to_numeric(out["total_volume"], errors="coerce")
    out = out.dropna(subset=["total_volume"])

    grouped = out.groupby("time_bin", as_index=False)["total_volume"].sum()
    grouped["minutes"] = grouped["time_bin"].map(time_to_minutes)
    grouped = grouped.sort_values("minutes").reset_index(drop=True)

    days = int(meta.get("total_days_loaded", 0) or 0)
    if days <= 0:
        die("JSON total_days_loaded is missing or zero; cannot calculate average daily volume.")

    grouped["avg_daily_volume"] = grouped["total_volume"] / days
    grouped[["period", "period_colour"]] = grouped["minutes"].apply(
        lambda m: pd.Series(period_for_minutes(int(m)))
    )

    return grouped


def validate_run(meta: Dict, bins: pd.DataFrame) -> None:
    if meta.get("is_complete") is not True:
        print("WARNING: JSON says is_complete is not true.", file=sys.stderr)

    months_total = meta.get("months_total")
    months_completed = meta.get("months_completed")
    if months_total is not None and months_completed is not None and months_total != months_completed:
        print(f"WARNING: months_completed={months_completed}, months_total={months_total}", file=sys.stderr)

    if len(bins) != 96:
        print(f"WARNING: expected 96 time bins, found {len(bins)}.", file=sys.stderr)


# ---------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------

def chart_daily_rhythm(bins: pd.DataFrame, meta: Dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(16, 9))
    nice_axes(ax)

    peak_bin = meta.get("busiest_time_bin") or bins.loc[bins["avg_daily_volume"].idxmax(), "time_bin"]
    quiet_bin = meta.get("quietest_time_bin") or bins.loc[bins["avg_daily_volume"].idxmin(), "time_bin"]

    x = bins["minutes"] / 60
    y = bins["avg_daily_volume"]

    # period backgrounds
    for name, start, end, colour in PERIODS:
        s = time_to_minutes(start) / 60
        e = 24 if end == "24:00" else time_to_minutes(end) / 60
        ax.axvspan(s, e, color=colour, alpha=0.10, lw=0)

    ax.fill_between(x, y, color=COLOURS["analysis"], alpha=0.12)
    ax.plot(x, y, color=COLOURS["analysis"], lw=3.2, solid_capstyle="round")

    peak_row = bins[bins["time_bin"] == str(peak_bin)[:5]]
    quiet_row = bins[bins["time_bin"] == str(quiet_bin)[:5]]

    max_y = float(y.max())
    ax.set_ylim(0, max_y * 1.22)
    ax.set_xlim(0, 24)

    if not peak_row.empty:
        px = float(peak_row.iloc[0]["minutes"]) / 60
        py = float(peak_row.iloc[0]["avg_daily_volume"])
        ax.axvline(px, color=COLOURS["peak"], lw=2.5, ls="--", alpha=0.95)
        ax.scatter([px], [py], s=115, color=COLOURS["peak"], zorder=5)
        ax.annotate(
            f"Peak: {peak_bin}\n{py/1_000_000:.1f}M avg/day",
            xy=(px, py),
            xytext=(min(px + 1.1, 21.0), py + max_y * 0.105),
            arrowprops=dict(arrowstyle="->", color=COLOURS["peak"], lw=1.8),
            fontsize=12,
            fontweight="bold",
            color=COLOURS["peak"],
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=COLOURS["peak"], alpha=0.96),
            ha="left",
        )

    if not quiet_row.empty:
        qx = float(quiet_row.iloc[0]["minutes"]) / 60
        qy = float(quiet_row.iloc[0]["avg_daily_volume"])
        ax.axvline(qx, color=COLOURS["quiet"], lw=2.0, ls="--", alpha=0.95)
        ax.scatter([qx], [qy], s=95, color=COLOURS["quiet"], zorder=5)
        ax.annotate(
            f"Quietest: {quiet_bin}",
            xy=(qx, qy),
            xytext=(qx + 2.65, qy + max_y * 0.06),
            arrowprops=dict(arrowstyle="->", color=COLOURS["quiet"], lw=1.8),
            fontsize=12,
            fontweight="bold",
            color=COLOURS["quiet"],
            bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=COLOURS["quiet"], alpha=0.95),
            ha="left",
        )

    ax.set_xticks(list(range(0, 25, 2)))
    ax.set_xticklabels([f"{h:02d}:00" if h < 24 else "00:00" for h in range(0, 25, 2)])
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(axis_daily))
    ax.set_xlabel("Time of day", labelpad=8)
    ax.set_ylabel("Average daily vehicle volume across SCATS network", labelpad=10)

    add_title(
        ax,
        "Melbourne Traffic Daily Rhythm — 15-Minute Profile",
        "Colour meaning: red = peak pressure, orange = transition, yellow = daytime plateau, green = quiet overnight.",
    )

    path = out / "time_bin_daily_rhythm_curve.png"
    save_fig(fig, path)
    return path


def chart_segmented(bins: pd.DataFrame, meta: Dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(16, 9))
    nice_axes(ax)

    max_y = float(bins["avg_daily_volume"].max())
    ax.set_ylim(0, max_y * 1.22)
    ax.set_xlim(0, 24)

    for name, start, end, colour in PERIODS:
        s_min = time_to_minutes(start)
        e_min = 24 * 60 if end == "24:00" else time_to_minutes(end)
        seg = bins[(bins["minutes"] >= s_min) & (bins["minutes"] < e_min)]
        if not seg.empty:
            ax.plot(
                seg["minutes"] / 60,
                seg["avg_daily_volume"],
                color=colour,
                lw=4.0,
                solid_capstyle="round",
                label=name,
            )

    peak_bin = meta.get("busiest_time_bin") or bins.loc[bins["avg_daily_volume"].idxmax(), "time_bin"]
    peak_row = bins[bins["time_bin"] == str(peak_bin)[:5]]
    if not peak_row.empty:
        px = float(peak_row.iloc[0]["minutes"]) / 60
        py = float(peak_row.iloc[0]["avg_daily_volume"])
        ax.scatter([px], [py], s=115, color=COLOURS["peak_dark"], zorder=5)
        ax.annotate(
            f"{peak_bin} peak",
            xy=(px, py),
            xytext=(max(px - 3.4, 0.5), py + max_y * 0.095),
            arrowprops=dict(arrowstyle="->", color=COLOURS["peak_dark"], lw=1.6),
            fontsize=12,
            fontweight="bold",
            color=COLOURS["peak_dark"],
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=COLOURS["peak_dark"], alpha=0.95),
        )

    ax.legend(loc="upper left", frameon=True, framealpha=0.95, fontsize=11)
    ax.set_xticks(list(range(0, 25, 2)))
    ax.set_xticklabels([f"{h:02d}:00" if h < 24 else "00:00" for h in range(0, 25, 2)])
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(axis_daily))
    ax.set_xlabel("Time of day", labelpad=8)
    ax.set_ylabel("Average daily vehicle volume", labelpad=10)

    add_title(
        ax,
        "Melbourne Traffic Day Segments",
        "The same 96-bin profile, coloured by behavioural period rather than a single default line.",
    )

    path = out / "time_bin_daily_rhythm_segmented.png"
    save_fig(fig, path)
    return path


def chart_period_totals(bins: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(14.5, 8.5))
    nice_axes(ax)

    period_df = (
        bins.groupby("period", as_index=False)
        .agg(total_volume=("total_volume", "sum"), colour=("period_colour", "first"))
    )

    order = [p[0] for p in PERIODS]
    period_df["order"] = period_df["period"].map({name: i for i, name in enumerate(order)})
    period_df = period_df.sort_values("order")

    x = list(range(len(period_df)))
    vals = period_df["total_volume"].to_list()
    colours = period_df["colour"].to_list()

    bars = ax.bar(x, vals, color=colours, edgecolor="white", linewidth=1.5)
    max_v = max(vals)
    ax.set_ylim(0, max_v * 1.20)

    for bar, val in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + max_v * 0.018,
            billions(val),
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
            color=COLOURS["text"],
        )

    ax.set_xticks(x)
    ax.set_xticklabels(period_df["period"], rotation=16, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(axis_billions))
    ax.set_ylabel("Total vehicle volume across archive", labelpad=10)

    add_title(
        ax,
        "Traffic Volume by Broad Day Period",
        "Period colours match the same traffic-language used across the page.",
    )

    path = out / "time_bin_broad_period_totals.png"
    save_fig(fig, path)
    return path


def chart_top_bins(bins: pd.DataFrame, out: Path, busiest: bool = True) -> Path:
    fig, ax = plt.subplots(figsize=(15.5, 10))
    nice_axes(ax)

    if busiest:
        data = bins.nlargest(24, "total_volume").copy()
        title = "Top 24 Busiest 15-Minute Traffic Bins"
        subtitle = "Red scale: darker red means stronger peak traffic pressure."
        cmap = plt.cm.Reds
        filename = "time_bin_top24_busiest_bins.png"
    else:
        data = bins.nsmallest(24, "total_volume").copy()
        title = "Top 24 Quietest 15-Minute Traffic Bins"
        subtitle = "Green scale: darker green marks stronger quiet-network conditions."
        cmap = plt.cm.Greens
        filename = "time_bin_top24_quietest_bins.png"

    data = data.sort_values("total_volume", ascending=True)
    values = data["total_volume"].to_list()
    labels = data["time_bin"].to_list()

    n = len(data)
    if busiest:
        colours = [cmap(0.35 + 0.55 * (i / max(n - 1, 1))) for i in range(n)]
    else:
        # darkest at the bottom for the smallest/quietest, but still readable
        colours = [cmap(0.42 + 0.46 * (i / max(n - 1, 1))) for i in range(n)]

    bars = ax.barh(labels, values, color=colours, edgecolor="white", linewidth=1.0)
    max_v = max(values)
    ax.set_xlim(0, max_v * 1.055)

    for bar, val in zip(bars, values):
        ax.text(
            val + max_v * 0.006,
            bar.get_y() + bar.get_height() / 2,
            billions(val),
            va="center",
            ha="left",
            fontsize=10.5,
            color=COLOURS["muted"],
        )

    ax.xaxis.set_major_formatter(mticker.FuncFormatter(axis_billions))
    ax.set_xlabel("Total vehicle volume across full archive", labelpad=8)
    ax.grid(axis="x", alpha=0.95)
    ax.grid(axis="y", alpha=0.0)

    add_title(ax, title, subtitle)

    path = out / filename
    save_fig(fig, path)
    return path


def chart_peak_vs_quiet(bins: pd.DataFrame, meta: Dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(13.5, 8))
    nice_axes(ax)

    peak_bin = str(meta.get("busiest_time_bin") or bins.loc[bins["total_volume"].idxmax(), "time_bin"])[:5]
    quiet_bin = str(meta.get("quietest_time_bin") or bins.loc[bins["total_volume"].idxmin(), "time_bin"])[:5]

    peak_total = float(meta.get("busiest_time_bin_total_volume") or bins.loc[bins["time_bin"] == peak_bin, "total_volume"].iloc[0])
    quiet_total = float(meta.get("quietest_time_bin_total_volume") or bins.loc[bins["time_bin"] == quiet_bin, "total_volume"].iloc[0])
    ratio = peak_total / quiet_total if quiet_total else math.nan

    labels = [f"Quietest\n{quiet_bin}", f"Peak\n{peak_bin}"]
    values = [quiet_total, peak_total]
    colours = [COLOURS["quiet"], COLOURS["peak"]]

    bars = ax.bar(labels, values, color=colours, edgecolor="white", linewidth=1.5)
    max_v = max(values)
    ax.set_ylim(0, max_v * 1.22)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + max_v * 0.022,
            billions(val),
            ha="center",
            va="bottom",
            fontsize=14,
            fontweight="bold",
            color=COLOURS["text"],
        )

    ax.text(
        0.5,
        0.78,
        f"Peak is about {ratio:.1f}× the quietest bin",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=22,
        fontweight="bold",
        color=COLOURS["peak"],
        bbox=dict(boxstyle="round,pad=0.45", fc="white", ec=COLOURS["peak"], alpha=0.96),
    )

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(axis_billions))
    ax.set_ylabel("Total volume across archive", labelpad=10)
    ax.grid(axis="y", alpha=0.95)
    ax.grid(axis="x", alpha=0.0)

    add_title(
        ax,
        "Peak vs Quietest Network Load",
        "A simple media-facing comparison: red peak pressure versus green quiet-network conditions.",
    )

    path = out / "time_bin_peak_vs_quiet_ratio.png"
    save_fig(fig, path)
    return path


def chart_monthly_peak_stability(df: pd.DataFrame, meta: Dict, out: Path) -> Path | None:
    # Need month-level rows. If the CSV is already aggregated to 96 bins only, this chart is skipped.
    month_candidates = ["month", "year_month", "month_local", "yyyymm"]
    month_col = None
    for c in df.columns:
        if c.lower() in month_candidates:
            month_col = c
            break

    if month_col is None:
        return None

    time_col = find_col(df, ["time_bin", "time", "time_of_day"], contains=["time"])
    total_col = find_col(
        df,
        ["total_volume", "total_vehicle_volume", "vehicle_volume", "volume", "total", "total_cleaned_volume"],
        contains=["volume"],
    )

    d = df[[month_col, time_col, total_col]].copy()
    d.columns = ["month", "time_bin", "total_volume"]
    d["time_bin"] = d["time_bin"].astype(str).str.slice(0, 5)
    d["total_volume"] = pd.to_numeric(d["total_volume"], errors="coerce")
    d = d.dropna(subset=["total_volume"])

    idx = d.groupby("month")["total_volume"].idxmax()
    peaks = d.loc[idx].sort_values("month").copy()
    peaks["peak_minutes"] = peaks["time_bin"].map(time_to_minutes)
    peaks["month_dt"] = pd.to_datetime(peaks["month"].astype(str) + "-01", errors="coerce")
    peaks = peaks.dropna(subset=["month_dt"])

    if peaks.empty:
        return None

    archive_peak = str(meta.get("busiest_time_bin") or peaks["time_bin"].mode().iloc[0])[:5]
    archive_peak_minutes = time_to_minutes(archive_peak)
    peaks["is_different"] = peaks["time_bin"] != archive_peak

    fig, ax = plt.subplots(figsize=(16, 8.5))
    nice_axes(ax)

    ax.plot(
        peaks["month_dt"],
        peaks["peak_minutes"],
        color=COLOURS["analysis"],
        lw=2.4,
        marker="o",
        markersize=4,
        label="Monthly peak time",
    )
    ax.axhline(
        archive_peak_minutes,
        color=COLOURS["peak"],
        ls="--",
        lw=2.0,
        label=f"Archive peak: {archive_peak}",
    )

    anomalies = peaks[peaks["is_different"]]
    if not anomalies.empty:
        ax.scatter(
            anomalies["month_dt"],
            anomalies["peak_minutes"],
            color=COLOURS["anomaly"],
            s=54,
            zorder=4,
            label="Different monthly peak",
        )

    ax.set_ylim(0, 24 * 60)
    ax.set_yticks(range(0, 24 * 60 + 1, 120))
    ax.set_yticklabels([minutes_to_label(m) for m in range(0, 24 * 60 + 1, 120)])
    ax.set_ylabel("Peak time of day", labelpad=10)
    ax.set_xlabel("Month", labelpad=8)
    ax.legend(loc="upper left", frameon=True, framealpha=0.95, fontsize=10.5)

    add_title(
        ax,
        "Monthly Peak-Time Stability",
        "Blue shows the month-by-month peak time. Purple marks months where the peak moved away from the dominant peak bin.",
    )

    path = out / "time_bin_monthly_peak_time_stability.png"
    save_fig(fig, path)
    return path


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate production SCATS time-bin profile charts.")
    parser.add_argument("--csv", required=True, help="Path to time_bin_profile.csv")
    parser.add_argument("--json", required=True, help="Path to time_bin_profile_final.json")
    parser.add_argument("--out", required=True, help="Output directory for charts")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    json_path = Path(args.json)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = read_csv(csv_path)
    meta = read_json(json_path)
    bins = prepare_96_bins(raw, meta)
    validate_run(meta, bins)

    aggregated_path = out_dir / "time_bin_profile_aggregated_96_bins.csv"
    bins.to_csv(aggregated_path, index=False)

    chart_paths: List[Path] = []
    chart_paths.append(chart_daily_rhythm(bins, meta, out_dir))
    chart_paths.append(chart_segmented(bins, meta, out_dir))
    chart_paths.append(chart_period_totals(bins, out_dir))
    chart_paths.append(chart_top_bins(bins, out_dir, busiest=True))
    chart_paths.append(chart_top_bins(bins, out_dir, busiest=False))
    chart_paths.append(chart_peak_vs_quiet(bins, meta, out_dir))

    monthly_chart = chart_monthly_peak_stability(raw, meta, out_dir)
    if monthly_chart is not None:
        chart_paths.append(monthly_chart)

    manifest = {
        "metric_name": "time_bin_profile",
        "source_csv": str(csv_path),
        "source_json": str(json_path),
        "output_directory": str(out_dir),
        "date_range_start": meta.get("date_range_start"),
        "date_range_end": meta.get("date_range_end"),
        "months_total": meta.get("months_total"),
        "months_completed": meta.get("months_completed"),
        "is_complete": meta.get("is_complete"),
        "total_days_loaded": meta.get("total_days_loaded"),
        "busiest_time_bin": meta.get("busiest_time_bin"),
        "quietest_time_bin": meta.get("quietest_time_bin"),
        "busiest_time_bin_total_volume": meta.get("busiest_time_bin_total_volume"),
        "quietest_time_bin_total_volume": meta.get("quietest_time_bin_total_volume"),
        "aggregated_96_bins_csv": str(aggregated_path),
        "charts": [str(p) for p in chart_paths],
        "colour_language": {
            "red": "peak pressure",
            "orange": "transition / build / decline",
            "yellow": "business-day plateau",
            "green": "quiet / low flow",
            "blue": "structural analysis",
            "purple": "anomaly / special movement",
        },
    }

    manifest_path = out_dir / "time_bin_profile_chart_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("DONE: generated production time-bin profile charts")
    print(f"Output directory: {out_dir}")
    for p in chart_paths:
        print(f"  - {p.name}")
    print(f"  - {aggregated_path.name}")
    print(f"  - {manifest_path.name}")


if __name__ == "__main__":
    main()
