#!/usr/bin/env python3
"""
generate_time_bin_behaviour_charts.py

Derived behavioural analytics for the Melbourne SCATS time-bin profile.

This script uses the completed time-bin profile CSV/JSON and creates extra
insight charts that do not require re-running the 40+ hour database job.

Inputs:
  --csv   time_bin_profile.csv
  --json  time_bin_profile_final.json
  --out   output directory

Example PowerShell one-liner:
  python generate_time_bin_behaviour_charts.py --csv "A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv" --json "A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile_final.json" --out "A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\time_bin_behaviour"

Outputs:
  - time_bin_peak_window_share.png
  - time_bin_cumulative_daily_curve.png
  - time_bin_morning_vs_afternoon_profile.png
  - time_bin_ramp_decay_curve.png
  - time_bin_plateau_threshold_analysis.png
  - time_bin_top_bins_cluster.png
  - time_bin_behaviour_summary.json
  - time_bin_behaviour_metrics.csv
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


COLOURS = {
    "peak": "#d73027",
    "peak_dark": "#a50014",
    "morning": "#fdae61",
    "midday": "#fee08b",
    "quiet": "#1a9850",
    "analysis": "#2c7bb6",
    "purple": "#6a3d9a",
    "text": "#2b2b2b",
    "muted": "#5d6b7c",
    "grid": "#dbe3ef",
    "border": "#d7dee8",
}

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


WINDOWS = {
    "Morning Peak Window\n07:00–09:30": ("07:00", "09:30", COLOURS["morning"]),
    "Midday Plateau\n10:00–15:00": ("10:00", "15:00", COLOURS["midday"]),
    "Afternoon Peak Window\n16:00–18:30": ("16:00", "18:30", COLOURS["peak"]),
    "Overnight Baseline\n00:00–05:00": ("00:00", "05:00", COLOURS["quiet"]),
}


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def read_json(path: Path) -> Dict:
    if not path.exists():
        die(f"JSON file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"Could not read JSON: {exc}")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        die(f"CSV file not found: {path}")
    try:
        return pd.read_csv(path)
    except Exception as exc:
        die(f"Could not read CSV: {exc}")


def find_col(df: pd.DataFrame, candidates: List[str], contains: List[str] | None = None) -> str:
    lower = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    if contains:
        for c in df.columns:
            if all(s.lower() in c.lower() for s in contains):
                return c
    die(f"Could not find required column. Candidates={candidates}. Columns={list(df.columns)}")
    return ""


def time_to_minutes(t: str) -> int:
    parts = str(t).strip().split(":")
    if len(parts) < 2:
        die(f"Invalid time value: {t}")
    return int(parts[0]) * 60 + int(parts[1])


def minutes_to_time(m: int) -> str:
    m = int(m) % 1440
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
        return f"{x / 1_000_000_000:.1f}B"
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.0f}M"
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
        0.0,
        1.022,
        subtitle,
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


def prepare_bins(df: pd.DataFrame, meta: Dict) -> pd.DataFrame:
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

    d = df[[time_col, total_col]].copy()
    d.columns = ["time_bin", "total_volume"]
    d["time_bin"] = d["time_bin"].astype(str).str.slice(0, 5)
    d["total_volume"] = pd.to_numeric(d["total_volume"], errors="coerce")
    d = d.dropna(subset=["total_volume"])
    d = d.groupby("time_bin", as_index=False)["total_volume"].sum()
    d["minutes"] = d["time_bin"].map(time_to_minutes)
    d = d.sort_values("minutes").reset_index(drop=True)

    days = int(meta.get("total_days_loaded", 0) or 0)
    if days <= 0:
        die("JSON total_days_loaded missing or zero.")
    d["avg_daily_volume"] = d["total_volume"] / days

    if len(d) != 96:
        print(f"WARNING: expected 96 bins; found {len(d)}", file=sys.stderr)

    d["share_of_day"] = d["total_volume"] / d["total_volume"].sum()
    d["cumulative_share"] = d["share_of_day"].cumsum()
    return d


def window_mask(d: pd.DataFrame, start: str, end: str) -> pd.Series:
    s = time_to_minutes(start)
    e = time_to_minutes(end)
    if e > s:
        return (d["minutes"] >= s) & (d["minutes"] < e)
    return (d["minutes"] >= s) | (d["minutes"] < e)


def window_stats(d: pd.DataFrame, label: str, start: str, end: str) -> Dict:
    mask = window_mask(d, start, end)
    sub = d[mask]
    total = float(sub["total_volume"].sum())
    avg_daily = float(sub["avg_daily_volume"].sum())
    share = float(total / d["total_volume"].sum())
    peak_row = sub.loc[sub["avg_daily_volume"].idxmax()]
    return {
        "window": label.replace("\n", " "),
        "start": start,
        "end": end,
        "bins": int(len(sub)),
        "total_volume": total,
        "avg_daily_volume_sum": avg_daily,
        "share_of_daily_volume": share,
        "strongest_bin": str(peak_row["time_bin"]),
        "strongest_bin_avg_daily_volume": float(peak_row["avg_daily_volume"]),
    }


def interpolate_time_for_cumulative_share(d: pd.DataFrame, target: float) -> str:
    row = d[d["cumulative_share"] >= target].head(1)
    if row.empty:
        return "24:00"
    return str(row.iloc[0]["time_bin"])


def chart_peak_window_share(d: pd.DataFrame, metrics: List[Dict], out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(14.5, 8.5))
    nice_axes(ax)

    labels = [m["window"].replace(" ", "\n", 1) for m in metrics]
    values = [m["share_of_daily_volume"] * 100 for m in metrics]
    colours = [WINDOWS[k][2] for k in WINDOWS.keys()]

    bars = ax.bar(labels, values, color=colours, edgecolor="white", linewidth=1.5)
    max_v = max(values)
    ax.set_ylim(0, max_v * 1.25)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + max_v * 0.025,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=13,
            fontweight="bold",
            color=COLOURS["text"],
        )

    ax.set_ylabel("Share of total daily traffic volume", labelpad=10)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.grid(axis="y", alpha=0.95)
    ax.grid(axis="x", alpha=0.0)

    add_title(
        ax,
        "Peak Window Share of Melbourne Daily Traffic",
        "Shows how much of the average day is concentrated in key behavioural windows.",
    )

    path = out_dir / "time_bin_peak_window_share.png"
    save_fig(fig, path)
    return path


def chart_cumulative_daily_curve(d: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(16, 9))
    nice_axes(ax)

    x = d["minutes"] / 60
    y = d["cumulative_share"] * 100

    ax.plot(x, y, color=COLOURS["analysis"], lw=3.2)
    ax.fill_between(x, y, color=COLOURS["analysis"], alpha=0.12)

    markers = [
        ("09:00", "9AM"),
        ("12:00", "Noon"),
        ("17:00", "5PM"),
        ("19:00", "7PM"),
    ]

    for t, label in markers:
        minute = time_to_minutes(t)
        row = d[d["minutes"] <= minute].tail(1)
        if row.empty:
            continue
        pct = float(row.iloc[0]["cumulative_share"] * 100)
        ax.scatter([minute / 60], [pct], s=80, color=COLOURS["peak"] if t == "17:00" else COLOURS["analysis"], zorder=4)
        ax.annotate(
            f"{label}\n{pct:.1f}%",
            xy=(minute / 60, pct),
            xytext=(minute / 60 + 0.35, pct + 5),
            fontsize=11.5,
            fontweight="bold",
            color=COLOURS["text"],
            arrowprops=dict(arrowstyle="->", lw=1.3, color=COLOURS["muted"]),
            bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=COLOURS["border"], alpha=0.96),
        )

    ax.set_xlim(0, 24)
    ax.set_ylim(0, 105)
    ax.set_xticks(list(range(0, 25, 2)))
    ax.set_xticklabels([f"{h:02d}:00" if h < 24 else "00:00" for h in range(0, 25, 2)])
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_xlabel("Time of day", labelpad=8)
    ax.set_ylabel("Cumulative share of daily traffic", labelpad=10)

    add_title(
        ax,
        "Cumulative Daily Traffic Curve",
        "Shows how quickly Melbourne uses up its daily traffic volume across the day.",
    )

    path = out_dir / "time_bin_cumulative_daily_curve.png"
    save_fig(fig, path)
    return path


def chart_morning_vs_afternoon(d: pd.DataFrame, out_dir: Path) -> Path:
    # Compare 05:00-11:00 against 13:00-19:00, each normalized to hours from start.
    morning = d[window_mask(d, "05:00", "11:00")].copy()
    afternoon = d[window_mask(d, "13:00", "19:00")].copy()

    morning["relative_hour"] = (morning["minutes"] - time_to_minutes("05:00")) / 60
    afternoon["relative_hour"] = (afternoon["minutes"] - time_to_minutes("13:00")) / 60

    fig, ax = plt.subplots(figsize=(16, 9))
    nice_axes(ax)

    ax.plot(
        morning["relative_hour"],
        morning["avg_daily_volume"],
        color=COLOURS["morning"],
        lw=3.2,
        label="Morning build: 05:00–11:00",
    )
    ax.plot(
        afternoon["relative_hour"],
        afternoon["avg_daily_volume"],
        color=COLOURS["peak"],
        lw=3.2,
        label="Afternoon pressure: 13:00–19:00",
    )

    m_peak = float(morning["avg_daily_volume"].max())
    a_peak = float(afternoon["avg_daily_volume"].max())
    dominance = a_peak / m_peak if m_peak else math.nan

    ax.text(
        0.5,
        0.83,
        f"Afternoon peak is {dominance:.2f}× the morning-window peak",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
        color=COLOURS["peak"],
        bbox=dict(boxstyle="round,pad=0.42", fc="white", ec=COLOURS["peak"], alpha=0.96),
    )

    ax.set_xlim(0, 6)
    ax.set_ylim(0, max(m_peak, a_peak) * 1.25)
    ax.set_xlabel("Hours from window start", labelpad=8)
    ax.set_ylabel("Average daily vehicle volume", labelpad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(axis_daily))
    ax.legend(loc="upper left", frameon=True, framealpha=0.95, fontsize=11)

    add_title(
        ax,
        "Morning vs Afternoon Traffic Shape",
        "Compares the daily build-up against the afternoon pressure period using the same 6-hour window length.",
    )

    path = out_dir / "time_bin_morning_vs_afternoon_profile.png"
    save_fig(fig, path)
    return path


def chart_ramp_decay(d: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(16, 9))
    nice_axes(ax)

    focus = d[window_mask(d, "04:00", "23:30")].copy()
    x = focus["minutes"] / 60
    y = focus["avg_daily_volume"]

    ax.plot(x, y, color=COLOURS["analysis"], lw=3.0)
    ax.fill_between(x, y, color=COLOURS["analysis"], alpha=0.10)

    times = ["05:00", "08:00", "17:15", "19:00", "21:00", "23:00"]
    vals = {}
    for t in times:
        row = d[d["time_bin"] == t]
        if not row.empty:
            vals[t] = float(row.iloc[0]["avg_daily_volume"])
            ax.scatter([time_to_minutes(t) / 60], [vals[t]], s=85, color=COLOURS["peak"] if t == "17:15" else COLOURS["analysis"], zorder=4)
            ax.annotate(
                f"{t}\n{vals[t]/1_000_000:.2f}M",
                xy=(time_to_minutes(t) / 60, vals[t]),
                xytext=(time_to_minutes(t) / 60 + 0.25, vals[t] + y.max() * 0.055),
                fontsize=10.5,
                fontweight="bold",
                color=COLOURS["text"],
                arrowprops=dict(arrowstyle="->", lw=1.2, color=COLOURS["muted"]),
                bbox=dict(boxstyle="round,pad=0.24", fc="white", ec=COLOURS["border"], alpha=0.96),
            )

    ramp_ratio = vals.get("08:00", math.nan) / vals.get("05:00", math.nan)
    decay_ratio = vals.get("17:15", math.nan) / vals.get("21:00", math.nan)

    if not math.isnan(ramp_ratio):
        ax.text(
            0.21,
            0.83,
            f"Morning ramp:\n08:00 is {ramp_ratio:.1f}× 05:00",
            transform=ax.transAxes,
            fontsize=14,
            fontweight="bold",
            color=COLOURS["morning"],
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=COLOURS["morning"], alpha=0.96),
        )

    if not math.isnan(decay_ratio):
        ax.text(
            0.63,
            0.83,
            f"Evening decay:\n17:15 is {decay_ratio:.1f}× 21:00",
            transform=ax.transAxes,
            fontsize=14,
            fontweight="bold",
            color=COLOURS["peak"],
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=COLOURS["peak"], alpha=0.96),
        )

    ax.set_xlim(4, 23.5)
    ax.set_ylim(0, y.max() * 1.25)
    ax.set_xticks(list(range(4, 24, 2)))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(4, 24, 2)])
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(axis_daily))
    ax.set_xlabel("Time of day", labelpad=8)
    ax.set_ylabel("Average daily vehicle volume", labelpad=10)

    add_title(
        ax,
        "Morning Ramp-Up and Evening Drop-Off",
        "Quantifies how quickly Melbourne wakes up, peaks, and then releases pressure after the commute.",
    )

    path = out_dir / "time_bin_ramp_decay_curve.png"
    save_fig(fig, path)
    return path


def chart_plateau_threshold(d: pd.DataFrame, out_dir: Path) -> Tuple[Path, Dict]:
    peak = float(d["avg_daily_volume"].max())
    thresholds = [0.70, 0.80, 0.90]
    rows = []

    for threshold in thresholds:
        mask = d["avg_daily_volume"] >= peak * threshold
        sub = d[mask].copy()
        if sub.empty:
            rows.append({"threshold": threshold, "bins": 0, "hours": 0, "start": None, "end": None})
        else:
            rows.append({
                "threshold": threshold,
                "bins": int(len(sub)),
                "hours": float(len(sub) * 0.25),
                "start": str(sub.iloc[0]["time_bin"]),
                "end": str(sub.iloc[-1]["time_bin"]),
            })

    fig, ax = plt.subplots(figsize=(14.5, 8.5))
    nice_axes(ax)

    labels = [f">{int(r['threshold']*100)}% of peak\n{r['start']}–{r['end']}" for r in rows]
    values = [r["hours"] for r in rows]
    colours = [COLOURS["midday"], COLOURS["morning"], COLOURS["peak"]]

    bars = ax.bar(labels, values, color=colours, edgecolor="white", linewidth=1.5)
    max_v = max(values) if values else 1
    ax.set_ylim(0, max_v * 1.32)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + max_v * 0.03,
            f"{val:.1f} hours",
            ha="center",
            va="bottom",
            fontsize=13,
            fontweight="bold",
            color=COLOURS["text"],
        )

    ax.set_ylabel("Hours per day above threshold", labelpad=10)
    ax.grid(axis="y", alpha=0.95)
    ax.grid(axis="x", alpha=0.0)

    add_title(
        ax,
        "Near-Peak Plateau Duration",
        "Measures how long Melbourne remains close to its maximum daily traffic load.",
    )

    path = out_dir / "time_bin_plateau_threshold_analysis.png"
    save_fig(fig, path)

    return path, {"plateau_thresholds": rows}


def chart_top_bins_cluster(d: pd.DataFrame, out_dir: Path) -> Tuple[Path, Dict]:
    top10 = d.nlargest(10, "total_volume").copy().sort_values("minutes")
    cluster_start = str(top10.iloc[0]["time_bin"])
    cluster_end = str(top10.iloc[-1]["time_bin"])
    cluster_span_hours = (int(top10.iloc[-1]["minutes"]) - int(top10.iloc[0]["minutes"])) / 60

    fig, ax = plt.subplots(figsize=(16, 8.5))
    nice_axes(ax)

    x = d["minutes"] / 60
    y = d["avg_daily_volume"]
    ax.plot(x, y, color=COLOURS["analysis"], lw=2.8, alpha=0.55)
    ax.scatter(top10["minutes"] / 60, top10["avg_daily_volume"], s=105, color=COLOURS["peak"], zorder=5, label="Top 10 bins")

    for _, row in top10.iterrows():
        ax.text(
            row["minutes"] / 60,
            row["avg_daily_volume"] + y.max() * 0.025,
            str(row["time_bin"]),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color=COLOURS["peak_dark"],
            rotation=25,
        )

    ax.axvspan(
        time_to_minutes(cluster_start) / 60,
        time_to_minutes(cluster_end) / 60,
        color=COLOURS["peak"],
        alpha=0.10,
        lw=0,
    )

    ax.text(
        0.50,
        0.82,
        f"Top 10 busiest bins cluster from {cluster_start} to {cluster_end}\nSpan: {cluster_span_hours:.1f} hours",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=17,
        fontweight="bold",
        color=COLOURS["peak"],
        bbox=dict(boxstyle="round,pad=0.42", fc="white", ec=COLOURS["peak"], alpha=0.96),
    )

    ax.set_xlim(0, 24)
    ax.set_ylim(0, y.max() * 1.22)
    ax.set_xticks(list(range(0, 25, 2)))
    ax.set_xticklabels([f"{h:02d}:00" if h < 24 else "00:00" for h in range(0, 25, 2)])
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(axis_daily))
    ax.set_xlabel("Time of day", labelpad=8)
    ax.set_ylabel("Average daily vehicle volume", labelpad=10)

    add_title(
        ax,
        "Top 10 Busiest Bins Cluster Analysis",
        "Shows whether the busiest 15-minute intervals are scattered or concentrated in one pressure window.",
    )

    path = out_dir / "time_bin_top_bins_cluster.png"
    save_fig(fig, path)

    return path, {
        "top10_cluster_start": cluster_start,
        "top10_cluster_end": cluster_end,
        "top10_cluster_span_hours": cluster_span_hours,
        "top10_bins": top10[["time_bin", "total_volume", "avg_daily_volume"]].to_dict(orient="records"),
    }


def derive_summary_metrics(d: pd.DataFrame, meta: Dict) -> Dict:
    peak_bin = str(meta.get("busiest_time_bin") or d.loc[d["avg_daily_volume"].idxmax(), "time_bin"])[:5]
    quiet_bin = str(meta.get("quietest_time_bin") or d.loc[d["avg_daily_volume"].idxmin(), "time_bin"])[:5]

    peak_row = d[d["time_bin"] == peak_bin].iloc[0]
    quiet_row = d[d["time_bin"] == quiet_bin].iloc[0]

    values = {}
    for t in ["05:00", "08:00", "12:00", "17:15", "19:00", "21:00", "23:00"]:
        row = d[d["time_bin"] == t]
        if not row.empty:
            values[t] = float(row.iloc[0]["avg_daily_volume"])

    summary = {
        "peak_time_bin": peak_bin,
        "quietest_time_bin": quiet_bin,
        "peak_avg_daily_volume": float(peak_row["avg_daily_volume"]),
        "quietest_avg_daily_volume": float(quiet_row["avg_daily_volume"]),
        "peak_to_quiet_ratio": float(peak_row["total_volume"] / quiet_row["total_volume"]),
        "cumulative_share_by_time": {
            "09:00": float(d[d["minutes"] <= time_to_minutes("09:00")].tail(1).iloc[0]["cumulative_share"]),
            "12:00": float(d[d["minutes"] <= time_to_minutes("12:00")].tail(1).iloc[0]["cumulative_share"]),
            "17:00": float(d[d["minutes"] <= time_to_minutes("17:00")].tail(1).iloc[0]["cumulative_share"]),
            "19:00": float(d[d["minutes"] <= time_to_minutes("19:00")].tail(1).iloc[0]["cumulative_share"]),
        },
        "time_when_25_percent_reached": interpolate_time_for_cumulative_share(d, 0.25),
        "time_when_50_percent_reached": interpolate_time_for_cumulative_share(d, 0.50),
        "time_when_75_percent_reached": interpolate_time_for_cumulative_share(d, 0.75),
        "morning_ramp_08_vs_05_ratio": values.get("08:00", math.nan) / values.get("05:00", math.nan),
        "evening_decay_peak_vs_21_ratio": values.get("17:15", values.get(peak_bin, math.nan)) / values.get("21:00", math.nan),
        "afternoon_vs_morning_peak_ratio": float(
            d[window_mask(d, "13:00", "19:00")]["avg_daily_volume"].max()
            / d[window_mask(d, "05:00", "11:00")]["avg_daily_volume"].max()
        ),
    }

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate derived SCATS time-bin behavioural charts.")
    parser.add_argument("--csv", required=True, help="Path to time_bin_profile.csv")
    parser.add_argument("--json", required=True, help="Path to time_bin_profile_final.json")
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    json_path = Path(args.json)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = read_csv(csv_path)
    meta = read_json(json_path)
    d = prepare_bins(raw, meta)

    summary = derive_summary_metrics(d, meta)

    window_metrics = []
    for label, (start, end, _colour) in WINDOWS.items():
        window_metrics.append(window_stats(d, label, start, end))

    chart_paths = []
    chart_paths.append(chart_peak_window_share(d, window_metrics, out_dir))
    chart_paths.append(chart_cumulative_daily_curve(d, out_dir))
    chart_paths.append(chart_morning_vs_afternoon(d, out_dir))
    chart_paths.append(chart_ramp_decay(d, out_dir))

    plateau_path, plateau_metrics = chart_plateau_threshold(d, out_dir)
    chart_paths.append(plateau_path)

    cluster_path, cluster_metrics = chart_top_bins_cluster(d, out_dir)
    chart_paths.append(cluster_path)

    metrics_rows = []
    for k, v in summary.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                metrics_rows.append({"metric": f"{k}.{kk}", "value": vv})
        else:
            metrics_rows.append({"metric": k, "value": v})

    for wm in window_metrics:
        safe = wm["window"].replace(" ", "_").replace("–", "_")
        for k, v in wm.items():
            metrics_rows.append({"metric": f"window.{safe}.{k}", "value": v})

    for row in plateau_metrics["plateau_thresholds"]:
        threshold = int(row["threshold"] * 100)
        for k, v in row.items():
            metrics_rows.append({"metric": f"plateau_above_{threshold}_percent.{k}", "value": v})

    metrics_csv = out_dir / "time_bin_behaviour_metrics.csv"
    pd.DataFrame(metrics_rows).to_csv(metrics_csv, index=False)

    manifest = {
        "metric_name": "time_bin_behaviour_analytics",
        "source_csv": str(csv_path),
        "source_json": str(json_path),
        "output_directory": str(out_dir),
        "base_run": {
            "date_range_start": meta.get("date_range_start"),
            "date_range_end": meta.get("date_range_end"),
            "months_total": meta.get("months_total"),
            "months_completed": meta.get("months_completed"),
            "is_complete": meta.get("is_complete"),
            "total_days_loaded": meta.get("total_days_loaded"),
            "zero_row_months": meta.get("zero_row_months"),
        },
        "summary": summary,
        "window_metrics": window_metrics,
        "plateau_metrics": plateau_metrics,
        "cluster_metrics": cluster_metrics,
        "charts": [str(p) for p in chart_paths],
        "metrics_csv": str(metrics_csv),
    }

    manifest_path = out_dir / "time_bin_behaviour_summary.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("DONE: generated derived time-bin behaviour charts")
    print(f"Output directory: {out_dir}")
    for p in chart_paths:
        print(f"  - {p.name}")
    print(f"  - {metrics_csv.name}")
    print(f"  - {manifest_path.name}")
    print("")
    print("Headline metrics:")
    print(f"  Peak time bin: {summary['peak_time_bin']}")
    print(f"  Quietest time bin: {summary['quietest_time_bin']}")
    print(f"  Peak-to-quiet ratio: {summary['peak_to_quiet_ratio']:.2f}x")
    print(f"  50% of daily traffic reached by: {summary['time_when_50_percent_reached']}")
    print(f"  75% of daily traffic reached by: {summary['time_when_75_percent_reached']}")


if __name__ == "__main__":
    main()
