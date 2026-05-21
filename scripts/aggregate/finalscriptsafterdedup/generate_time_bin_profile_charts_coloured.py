#!/usr/bin/env python3
"""
generate_time_bin_profile_charts_coloured.py

Generate media-ready, consistently colour-coded charts from the completed
SCATS time-bin profile CSV + final JSON summary.

Inputs expected from generate_time_bin_profile_chunkedV3.py:
  - time_bin_profile.csv
  - time_bin_profile_final.json

Example:
  python3 generate_time_bin_profile_charts_coloured.py \
    --csv time_bin_profile.csv \
    --json time_bin_profile_final.json \
    --out charts/time_bin_profile

Outputs:
  - time_bin_daily_rhythm_curve.png
  - time_bin_daily_rhythm_segmented.png
  - time_bin_top24_busiest_bins.png
  - time_bin_top24_quietest_bins.png
  - time_bin_broad_period_totals.png
  - time_bin_monthly_peak_time_stability.png
  - time_bin_peak_vs_quiet_ratio.png
  - time_bin_profile_aggregated_96_bins.csv
  - time_bin_profile_chart_manifest.json

Colour language:
  Red    = peak / congestion pressure
  Orange = rising or transition periods
  Yellow = mid / neutral traffic
  Green  = low / quiet traffic
  Blue   = analytical structure / stability
  Purple = anomaly / special insight
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Consistent colour system
# -----------------------------------------------------------------------------
COLORS = {
    "peak_red": "#d73027",
    "peak_red_dark": "#8b0000",
    "transition_orange": "#fdae61",
    "mid_yellow": "#fee08b",
    "quiet_green": "#1a9850",
    "quiet_green_dark": "#006837",
    "analysis_blue": "#2c7bb6",
    "breakthrough_purple": "#6a3d9a",
    "text": "#222222",
    "muted": "#5d6b7c",
    "grid": "#dbe3ef",
    "background": "#ffffff",
}

PERIOD_COLOURS = {
    "Overnight Quiet": COLORS["quiet_green"],
    "Morning Build": COLORS["transition_orange"],
    "Business-Day Plateau": COLORS["mid_yellow"],
    "Afternoon Peak": COLORS["peak_red"],
    "Evening Decline": COLORS["transition_orange"],
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def fail(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def load_json(path: Path) -> Dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        fail(f"JSON file not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"Could not parse JSON file {path}: {exc}")


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Accept likely variants while preserving the real generated column names."""
    mapping = {c.lower().strip(): c for c in df.columns}

    def get_col(candidates: Iterable[str]) -> str:
        for cand in candidates:
            if cand in mapping:
                return mapping[cand]
        fail(f"Missing required column. Tried: {', '.join(candidates)}. Columns found: {list(df.columns)}")

    month_col = get_col(["month_label", "month", "month_name"])
    time_col = get_col(["time_bin", "time", "timebin", "interval_start"])
    volume_col = get_col(["month_time_bin_volume", "volume", "total_volume", "vehicles", "vehicle_volume"])

    days_col = None
    for cand in ["days_in_month_loaded", "days_loaded", "days"]:
        if cand in mapping:
            days_col = mapping[cand]
            break

    out = pd.DataFrame({
        "month_label": df[month_col].astype(str),
        "time_bin": df[time_col].astype(str),
        "volume": pd.to_numeric(df[volume_col], errors="coerce"),
    })
    if days_col:
        out["days_in_month_loaded"] = pd.to_numeric(df[days_col], errors="coerce")
    else:
        out["days_in_month_loaded"] = np.nan

    out = out.dropna(subset=["volume"])
    return out


def time_to_minutes(t: str) -> int:
    try:
        h, m = str(t).strip().split(":")[:2]
        return int(h) * 60 + int(m)
    except Exception:
        fail(f"Invalid time_bin value: {t!r}. Expected HH:MM.")


def hhmm_from_minutes(minutes: float) -> str:
    minutes = int(round(minutes / 15) * 15) % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def period_for_minutes(minutes: int) -> str:
    """Deliberately simple, readable media-facing day periods."""
    if 0 <= minutes < 5 * 60:
        return "Overnight Quiet"
    if 5 * 60 <= minutes < 10 * 60:
        return "Morning Build"
    if 10 * 60 <= minutes < 15 * 60:
        return "Business-Day Plateau"
    if 15 * 60 <= minutes < 19 * 60:
        return "Afternoon Peak"
    return "Evening Decline"


def format_big(n: float) -> str:
    if abs(n) >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{n:,.0f}"


def setup_plot(title: str, subtitle: str | None = None, figsize: Tuple[int, int] = (14, 8)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(COLORS["background"])
    ax.set_facecolor(COLORS["background"])
    ax.set_title(title, loc="left", fontsize=18, fontweight="bold", color=COLORS["text"], pad=18)
    if subtitle:
        ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=11, color=COLORS["muted"], va="bottom")
    ax.grid(True, axis="y", color=COLORS["grid"], linewidth=0.8, alpha=0.85)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.tick_params(axis="both", labelsize=10, colors=COLORS["text"])
    return fig, ax


def save(fig, out_path: Path) -> None:
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def validate_summary(summary: Dict) -> List[str]:
    warnings: List[str] = []
    if summary.get("metric_name") not in (None, "time_bin_profile"):
        warnings.append(f"Unexpected metric_name: {summary.get('metric_name')}")
    if summary.get("is_complete") is not True:
        warnings.append("JSON says is_complete is not true.")
    if summary.get("months_completed") != summary.get("months_total"):
        warnings.append("months_completed does not equal months_total.")
    if summary.get("zero_row_months"):
        warnings.append(f"Zero-row months present: {summary.get('zero_row_months')}")
    return warnings


# -----------------------------------------------------------------------------
# Aggregation
# -----------------------------------------------------------------------------
def build_aggregates(df: pd.DataFrame, summary: Dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["minutes"] = df["time_bin"].map(time_to_minutes)
    df["period"] = df["minutes"].map(period_for_minutes)

    total_days = float(summary.get("total_days_loaded") or 0)
    if total_days <= 0:
        # Fallback: sum unique days across months is impossible without daily data;
        # use mean days loaded across months * unique month count as a rough fallback.
        if df["days_in_month_loaded"].notna().any():
            total_days = df.groupby("month_label")["days_in_month_loaded"].max().sum()
        else:
            total_days = np.nan

    agg96 = (
        df.groupby(["time_bin", "minutes", "period"], as_index=False)
          .agg(total_volume=("volume", "sum"))
          .sort_values("minutes")
    )
    agg96["average_daily_volume"] = agg96["total_volume"] / total_days if total_days and not math.isnan(total_days) else np.nan
    agg96["rank_busiest"] = agg96["total_volume"].rank(method="dense", ascending=False).astype(int)
    agg96["rank_quietest"] = agg96["total_volume"].rank(method="dense", ascending=True).astype(int)

    period = (
        agg96.groupby("period", as_index=False)
             .agg(total_volume=("total_volume", "sum"), average_daily_volume=("average_daily_volume", "sum"))
    )
    order = ["Overnight Quiet", "Morning Build", "Business-Day Plateau", "Afternoon Peak", "Evening Decline"]
    period["order"] = period["period"].map({p: i for i, p in enumerate(order)})
    period = period.sort_values("order")

    monthly_peak = (
        df.loc[df.groupby("month_label")["volume"].idxmax(), ["month_label", "time_bin", "minutes", "volume"]]
          .sort_values("month_label")
          .reset_index(drop=True)
    )
    monthly_peak["month_index"] = np.arange(len(monthly_peak))

    return agg96, period, monthly_peak


# -----------------------------------------------------------------------------
# Charts
# -----------------------------------------------------------------------------
def chart_daily_rhythm_curve(agg96: pd.DataFrame, summary: Dict, out: Path) -> Dict:
    peak_time = summary.get("busiest_time_bin") or agg96.loc[agg96["total_volume"].idxmax(), "time_bin"]
    quiet_time = summary.get("quietest_time_bin") or agg96.loc[agg96["total_volume"].idxmin(), "time_bin"]
    peak_minutes = time_to_minutes(peak_time)
    quiet_minutes = time_to_minutes(quiet_time)

    fig, ax = setup_plot(
        "Melbourne Traffic Daily Rhythm — 15-Minute Profile",
        "Colour meaning: red = peak pressure, orange = transition, yellow = daytime plateau, green = quiet overnight.",
        figsize=(15, 8),
    )

    # Light period background bands
    bands = [
        (0, 5*60, "Overnight Quiet"),
        (5*60, 10*60, "Morning Build"),
        (10*60, 15*60, "Business-Day Plateau"),
        (15*60, 19*60, "Afternoon Peak"),
        (19*60, 24*60, "Evening Decline"),
    ]
    for start, end, label in bands:
        ax.axvspan(start, end, color=PERIOD_COLOURS[label], alpha=0.10, linewidth=0)

    ax.plot(agg96["minutes"], agg96["average_daily_volume"], color=COLORS["analysis_blue"], linewidth=3.0)
    ax.fill_between(agg96["minutes"], agg96["average_daily_volume"], alpha=0.10, color=COLORS["analysis_blue"])

    peak_row = agg96.loc[agg96["time_bin"] == peak_time].iloc[0]
    quiet_row = agg96.loc[agg96["time_bin"] == quiet_time].iloc[0]

    ax.axvline(peak_minutes, color=COLORS["peak_red"], linewidth=2.5, linestyle="--")
    ax.scatter([peak_minutes], [peak_row["average_daily_volume"]], s=95, color=COLORS["peak_red"], zorder=5)
    ax.annotate(
        f"Peak: {peak_time}\n{format_big(peak_row['average_daily_volume'])} avg/day",
        xy=(peak_minutes, peak_row["average_daily_volume"]),
        xytext=(peak_minutes - 250, peak_row["average_daily_volume"] * 1.05),
        arrowprops=dict(arrowstyle="->", color=COLORS["peak_red"], lw=1.5),
        fontsize=11,
        fontweight="bold",
        color=COLORS["peak_red"],
        ha="right",
    )

    ax.axvline(quiet_minutes, color=COLORS["quiet_green"], linewidth=2.0, linestyle="--")
    ax.scatter([quiet_minutes], [quiet_row["average_daily_volume"]], s=85, color=COLORS["quiet_green"], zorder=5)
    ax.annotate(
        f"Quietest: {quiet_time}",
        xy=(quiet_minutes, quiet_row["average_daily_volume"]),
        xytext=(quiet_minutes + 160, quiet_row["average_daily_volume"] * 1.7),
        arrowprops=dict(arrowstyle="->", color=COLORS["quiet_green"], lw=1.5),
        fontsize=11,
        fontweight="bold",
        color=COLORS["quiet_green"],
    )

    ticks = list(range(0, 24 * 60 + 1, 120))
    ax.set_xticks(ticks)
    ax.set_xticklabels([hhmm_from_minutes(t) for t in ticks], rotation=0)
    ax.set_xlim(0, 24 * 60)
    ax.set_ylabel("Average daily vehicle volume across SCATS network", fontsize=11)
    ax.set_xlabel("Time of day", fontsize=11)
    ax.yaxis.set_major_formatter(lambda x, pos: format_big(x))

    path = out / "time_bin_daily_rhythm_curve.png"
    save(fig, path)
    return {"file": path.name, "title": "Daily rhythm curve", "type": "line", "colour_meaning": "Blue structure line with red peak, green quiet point and period background bands."}


def chart_segmented_rhythm(agg96: pd.DataFrame, summary: Dict, out: Path) -> Dict:
    fig, ax = setup_plot(
        "Melbourne Traffic Day Segments",
        "The same 96-bin profile, coloured by behavioural period rather than a single default line.",
        figsize=(15, 8),
    )
    for period, group in agg96.groupby("period", sort=False):
        group = group.sort_values("minutes")
        ax.plot(group["minutes"], group["average_daily_volume"], color=PERIOD_COLOURS[period], linewidth=4.0, label=period)

    peak_time = summary.get("busiest_time_bin") or agg96.loc[agg96["total_volume"].idxmax(), "time_bin"]
    peak_minutes = time_to_minutes(peak_time)
    peak_row = agg96.loc[agg96["time_bin"] == peak_time].iloc[0]
    ax.scatter([peak_minutes], [peak_row["average_daily_volume"]], s=110, color=COLORS["peak_red_dark"], zorder=6)
    ax.annotate(f"{peak_time} peak", xy=(peak_minutes, peak_row["average_daily_volume"]), xytext=(peak_minutes - 210, peak_row["average_daily_volume"] * 1.04), arrowprops=dict(arrowstyle="->", color=COLORS["peak_red_dark"]), color=COLORS["peak_red_dark"], fontweight="bold")

    ticks = list(range(0, 24 * 60 + 1, 120))
    ax.set_xticks(ticks)
    ax.set_xticklabels([hhmm_from_minutes(t) for t in ticks])
    ax.set_xlim(0, 24 * 60)
    ax.set_ylabel("Average daily vehicle volume", fontsize=11)
    ax.set_xlabel("Time of day", fontsize=11)
    ax.yaxis.set_major_formatter(lambda x, pos: format_big(x))
    ax.legend(loc="upper left", frameon=True, fontsize=9)

    path = out / "time_bin_daily_rhythm_segmented.png"
    save(fig, path)
    return {"file": path.name, "title": "Segmented daily rhythm", "type": "line", "colour_meaning": "Green quiet, orange transitions, yellow plateau, red peak pressure."}


def chart_ranked_bins(agg96: pd.DataFrame, out: Path, busiest: bool = True, n: int = 24) -> Dict:
    if busiest:
        data = agg96.sort_values("total_volume", ascending=False).head(n).sort_values("total_volume")
        title = "Top 24 Busiest 15-Minute Traffic Bins"
        subtitle = "Red scale: darker red means stronger peak traffic pressure."
        cmap = plt.cm.Reds
        fname = "time_bin_top24_busiest_bins.png"
        colour_text = "Red ranking scale for peak pressure."
    else:
        data = agg96.sort_values("total_volume", ascending=True).head(n).sort_values("total_volume", ascending=False)
        title = "Top 24 Quietest 15-Minute Traffic Bins"
        subtitle = "Green scale: darker green means quieter network conditions."
        cmap = plt.cm.Greens
        fname = "time_bin_top24_quietest_bins.png"
        colour_text = "Green ranking scale for quiet network periods."

    vals = data["total_volume"].to_numpy(dtype=float)
    if vals.max() == vals.min():
        norm_vals = np.ones_like(vals) * 0.6
    else:
        norm_vals = (vals - vals.min()) / (vals.max() - vals.min())
    colours = [cmap(0.35 + 0.55 * v) for v in norm_vals]

    fig, ax = setup_plot(title, subtitle, figsize=(13, 9))
    bars = ax.barh(data["time_bin"], data["total_volume"], color=colours, edgecolor="white", linewidth=0.8)
    ax.set_xlabel("Total vehicle volume across full archive", fontsize=11)
    ax.xaxis.set_major_formatter(lambda x, pos: format_big(x))
    ax.grid(True, axis="x", color=COLORS["grid"], linewidth=0.8, alpha=0.85)
    ax.grid(False, axis="y")

    for bar, val in zip(bars, data["total_volume"]):
        ax.text(bar.get_width() * 1.003, bar.get_y() + bar.get_height() / 2, format_big(val), va="center", fontsize=9, color=COLORS["muted"])

    path = out / fname
    save(fig, path)
    return {"file": path.name, "title": title, "type": "barh", "colour_meaning": colour_text}


def chart_period_totals(period: pd.DataFrame, out: Path) -> Dict:
    fig, ax = setup_plot(
        "Traffic Volume by Broad Day Period",
        "Period colours match the same traffic-language used across the page.",
        figsize=(13, 8),
    )
    colours = [PERIOD_COLOURS[p] for p in period["period"]]
    bars = ax.bar(period["period"], period["total_volume"], color=colours, edgecolor="white", linewidth=1.0)
    ax.set_ylabel("Total vehicle volume across archive", fontsize=11)
    ax.yaxis.set_major_formatter(lambda x, pos: format_big(x))
    ax.tick_params(axis="x", rotation=20)
    for bar, val in zip(bars, period["total_volume"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01, format_big(val), ha="center", va="bottom", fontsize=10, fontweight="bold", color=COLORS["text"])

    path = out / "time_bin_broad_period_totals.png"
    save(fig, path)
    return {"file": path.name, "title": "Broad period totals", "type": "bar", "colour_meaning": "Green quiet, orange transition, yellow plateau, red peak."}


def chart_monthly_peak_stability(monthly_peak: pd.DataFrame, summary: Dict, out: Path) -> Dict:
    fig, ax = setup_plot(
        "Monthly Peak-Time Stability",
        "Blue shows the month-by-month peak time. Purple marks months where the peak moved away from the dominant peak bin.",
        figsize=(15, 8),
    )
    dominant_peak = summary.get("busiest_time_bin") or monthly_peak["time_bin"].mode().iloc[0]
    dominant_minutes = time_to_minutes(dominant_peak)

    ax.plot(monthly_peak["month_index"], monthly_peak["minutes"], color=COLORS["analysis_blue"], linewidth=2.2, marker="o", markersize=3.5)
    ax.axhline(dominant_minutes, color=COLORS["peak_red"], linewidth=2.0, linestyle="--", label=f"Archive peak: {dominant_peak}")

    anomalies = monthly_peak[monthly_peak["time_bin"] != dominant_peak]
    if not anomalies.empty:
        ax.scatter(anomalies["month_index"], anomalies["minutes"], color=COLORS["breakthrough_purple"], s=42, zorder=5, label="Different monthly peak")

    step = max(1, len(monthly_peak) // 12)
    tick_idx = list(range(0, len(monthly_peak), step))
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(monthly_peak.loc[tick_idx, "month_label"], rotation=45, ha="right")

    y_ticks = list(range(0, 24 * 60 + 1, 120))
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([hhmm_from_minutes(t) for t in y_ticks])
    ax.set_ylim(0, 24 * 60)
    ax.set_ylabel("Peak time of day", fontsize=11)
    ax.set_xlabel("Month", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)

    path = out / "time_bin_monthly_peak_time_stability.png"
    save(fig, path)
    return {"file": path.name, "title": "Monthly peak-time stability", "type": "line", "colour_meaning": "Blue analytical stability line, red archive peak, purple anomalies."}


def chart_peak_vs_quiet_ratio(agg96: pd.DataFrame, summary: Dict, out: Path) -> Dict:
    peak_time = summary.get("busiest_time_bin") or agg96.loc[agg96["total_volume"].idxmax(), "time_bin"]
    quiet_time = summary.get("quietest_time_bin") or agg96.loc[agg96["total_volume"].idxmin(), "time_bin"]
    peak = float(agg96.loc[agg96["time_bin"] == peak_time, "total_volume"].iloc[0])
    quiet = float(agg96.loc[agg96["time_bin"] == quiet_time, "total_volume"].iloc[0])
    ratio = peak / quiet if quiet else np.nan

    fig, ax = setup_plot(
        "Peak vs Quietest Network Load",
        "A simple media-facing comparison: red peak pressure versus green quiet-network conditions.",
        figsize=(10, 7),
    )
    labels = [f"Quietest\n{quiet_time}", f"Peak\n{peak_time}"]
    values = [quiet, peak]
    bars = ax.bar(labels, values, color=[COLORS["quiet_green"], COLORS["peak_red"]], edgecolor="white", linewidth=1.0)
    ax.set_ylabel("Total volume across archive", fontsize=11)
    ax.yaxis.set_major_formatter(lambda x, pos: format_big(x))
    ax.text(0.5, 0.88, f"Peak is about {ratio:.1f}× the quietest bin", transform=ax.transAxes, ha="center", fontsize=16, fontweight="bold", color=COLORS["peak_red"])
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.01, format_big(val), ha="center", va="bottom", fontsize=11, fontweight="bold")

    path = out / "time_bin_peak_vs_quiet_ratio.png"
    save(fig, path)
    return {"file": path.name, "title": "Peak versus quietest ratio", "type": "bar", "colour_meaning": "Red peak pressure contrasted with green quiet traffic."}


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate colour-coded SCATS time-bin profile charts.")
    parser.add_argument("--csv", required=True, help="Path to time_bin_profile.csv")
    parser.add_argument("--json", required=True, help="Path to time_bin_profile_final.json")
    parser.add_argument("--out", required=True, help="Output directory for charts and manifest")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    json_path = Path(args.json)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        fail(f"CSV file not found: {csv_path}")

    raw = pd.read_csv(csv_path)
    df = normalise_columns(raw)
    summary = load_json(json_path)
    warnings = validate_summary(summary)

    agg96, period, monthly_peak = build_aggregates(df, summary)

    # Data outputs
    agg_path = out_dir / "time_bin_profile_aggregated_96_bins.csv"
    agg96.to_csv(agg_path, index=False)

    chart_entries = []
    chart_entries.append(chart_daily_rhythm_curve(agg96, summary, out_dir))
    chart_entries.append(chart_segmented_rhythm(agg96, summary, out_dir))
    chart_entries.append(chart_ranked_bins(agg96, out_dir, busiest=True, n=24))
    chart_entries.append(chart_ranked_bins(agg96, out_dir, busiest=False, n=24))
    chart_entries.append(chart_period_totals(period, out_dir))
    chart_entries.append(chart_monthly_peak_stability(monthly_peak, summary, out_dir))
    chart_entries.append(chart_peak_vs_quiet_ratio(agg96, summary, out_dir))

    peak_time = summary.get("busiest_time_bin") or agg96.loc[agg96["total_volume"].idxmax(), "time_bin"]
    quiet_time = summary.get("quietest_time_bin") or agg96.loc[agg96["total_volume"].idxmin(), "time_bin"]
    peak_total = float(agg96.loc[agg96["time_bin"] == peak_time, "total_volume"].iloc[0])
    quiet_total = float(agg96.loc[agg96["time_bin"] == quiet_time, "total_volume"].iloc[0])

    manifest = {
        "generated_by": "generate_time_bin_profile_charts_coloured.py",
        "input_csv": str(csv_path),
        "input_json": str(json_path),
        "date_range_start": summary.get("date_range_start"),
        "date_range_end": summary.get("date_range_end"),
        "months_completed": summary.get("months_completed"),
        "months_total": summary.get("months_total"),
        "is_complete": summary.get("is_complete"),
        "total_days_loaded": summary.get("total_days_loaded"),
        "zero_row_months": summary.get("zero_row_months", []),
        "busiest_time_bin": peak_time,
        "busiest_time_bin_total_volume": peak_total,
        "quietest_time_bin": quiet_time,
        "quietest_time_bin_total_volume": quiet_total,
        "peak_to_quiet_ratio": peak_total / quiet_total if quiet_total else None,
        "colour_language": COLORS,
        "period_colours": PERIOD_COLOURS,
        "warnings": warnings,
        "data_outputs": [agg_path.name],
        "charts": chart_entries,
    }

    manifest_path = out_dir / "time_bin_profile_chart_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("Generated colour-coded time-bin profile charts:")
    for entry in chart_entries:
        print(f"  - {out_dir / entry['file']}")
    print(f"  - {agg_path}")
    print(f"  - {manifest_path}")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
