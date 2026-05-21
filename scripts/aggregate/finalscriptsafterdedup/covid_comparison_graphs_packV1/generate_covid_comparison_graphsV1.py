#!/usr/bin/env python3
r"""
generate_covid_comparison_graphsV1.py

Creates static graphs from the completed COVID comparison Kepler export.

Input:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\covid_comparison

Graphs created:
  01_total_volume_by_period.png
  02_total_volume_recovery_index.png
  03_24_hour_traffic_shape_overlay.png
  04_time_bin_period_heatmap.png
  05_hourly_percent_change_vs_2019_baseline.png
  06_top_30_site_absolute_collapse_2020_vs_2019.png
  07_top_30_site_recovery_growth_2025_vs_2019.png
  08_site_recovery_scatter_2020_vs_2025.png
  09_distinct_active_sites_by_period.png
  10_period_summary_dashboard.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_INPUT = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\covid_comparison"

PERIOD_ORDER = [
    "Pre-COVID baseline",
    "Lockdown / COVID shock",
    "Extended disruption",
    "Recovery phase",
    "Recent normal",
    "Busiest day detected",
]

PERIOD_SHORT = {
    "Pre-COVID baseline": "2019 baseline",
    "Lockdown / COVID shock": "2020 lockdown",
    "Extended disruption": "2021 disruption",
    "Recovery phase": "2022 recovery",
    "Recent normal": "2024 normal",
    "Busiest day detected": "2025 busiest",
}

PERIOD_COLORS = {
    "Pre-COVID baseline": "#16395f",
    "Lockdown / COVID shock": "#b00020",
    "Extended disruption": "#d97706",
    "Recovery phase": "#007bff",
    "Recent normal": "#0f766e",
    "Busiest day detected": "#16a34a",
}


def fmt_int(x) -> str:
    try:
        return f"{int(round(float(x))):,}"
    except Exception:
        return str(x)


def fmt_millions(x) -> str:
    return f"{float(x) / 1_000_000:.1f}M"


def ensure_outdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def savefig(outdir: Path, filename: str) -> Path:
    path = outdir / filename
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")
    return path


def order_periods(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    found = [p for p in PERIOD_ORDER if p in set(df["comparison_period"])]
    extras = [p for p in df["comparison_period"].dropna().unique().tolist() if p not in found]
    order = found + extras
    df["comparison_period"] = pd.Categorical(df["comparison_period"], categories=order, ordered=True)
    return df


def load_data(path: Path) -> pd.DataFrame:
    print("=" * 90)
    print("COVID COMPARISON GRAPHS V1")
    print("=" * 90)
    print(f"Input CSV: {path}")

    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    df = pd.read_csv(path, low_memory=False)
    print(f"Loaded rows: {fmt_int(len(df))}")
    print(f"Columns: {list(df.columns)}")

    required = {
        "comparison_period", "time_label", "hour", "minute",
        "site_id", "site_name", "latitude", "longitude", "volume"
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(0).astype(int)
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce").fillna(0).astype(int)
    df["time_minutes"] = df["hour"] * 60 + df["minute"]
    df["time_label"] = df["time_label"].astype(str).str.slice(0, 5)
    df["site_id"] = df["site_id"].astype(str)
    df["comparison_period"] = df["comparison_period"].astype(str)

    df = order_periods(df)

    print(f"Periods: {df['comparison_period'].dropna().unique().tolist()}")
    print(f"Distinct sites: {fmt_int(df['site_id'].nunique())}")
    print(f"Total volume: {fmt_int(df['volume'].sum())}")
    print("=" * 90)
    return df


def graph_total_volume_by_period(df: pd.DataFrame, outdir: Path):
    period = (
        df.groupby("comparison_period", observed=True)
        .agg(total_volume=("volume", "sum"), active_sites=("site_id", "nunique"))
        .reset_index()
    )

    colors = [PERIOD_COLORS.get(str(p), "#64748b") for p in period["comparison_period"]]

    plt.figure(figsize=(15, 8))
    bars = plt.bar(
        [PERIOD_SHORT.get(str(p), str(p)) for p in period["comparison_period"]],
        period["total_volume"] / 1_000_000,
        color=colors,
    )
    plt.title("Melbourne Traffic Volume Across COVID Comparison Days", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("Same SCATS network, selected historical comparison days", y=0.93, fontsize=12, color="#475569")
    plt.ylabel("Total Vehicle Movements (Millions)")
    plt.xlabel("Comparison Period")
    plt.grid(axis="y", alpha=0.25)

    for bar, val in zip(bars, period["total_volume"]):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            fmt_millions(val),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    plt.xticks(rotation=20, ha="right")
    savefig(outdir, "01_total_volume_by_period.png")
    return period


def graph_recovery_index(period: pd.DataFrame, outdir: Path):
    baseline_rows = period[period["comparison_period"].astype(str).eq("Pre-COVID baseline")]
    if baseline_rows.empty:
        print("Skipping recovery index: no Pre-COVID baseline period found.")
        return

    baseline = float(baseline_rows["total_volume"].iloc[0])
    data = period.copy()
    data["baseline_index"] = data["total_volume"] / baseline * 100

    colors = [PERIOD_COLORS.get(str(p), "#64748b") for p in data["comparison_period"]]

    plt.figure(figsize=(15, 8))
    plt.plot(
        [PERIOD_SHORT.get(str(p), str(p)) for p in data["comparison_period"]],
        data["baseline_index"],
        marker="o",
        linewidth=3,
        color="#16395f",
    )
    plt.scatter(
        [PERIOD_SHORT.get(str(p), str(p)) for p in data["comparison_period"]],
        data["baseline_index"],
        s=120,
        color=colors,
        zorder=3,
    )
    plt.axhline(100, linestyle="--", linewidth=1.5, color="#64748b")
    plt.title("COVID Traffic Recovery Index", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("2019 baseline = 100. Lower values show collapse; higher values show recovery/growth.", y=0.93, fontsize=12, color="#475569")
    plt.ylabel("Index: 2019 baseline = 100")
    plt.xlabel("Comparison Period")
    plt.grid(alpha=0.25)

    for x, y in zip([PERIOD_SHORT.get(str(p), str(p)) for p in data["comparison_period"]], data["baseline_index"]):
        plt.text(x, y + 2, f"{y:.1f}", ha="center", fontsize=10, fontweight="bold")

    plt.xticks(rotation=20, ha="right")
    savefig(outdir, "02_total_volume_recovery_index.png")


def graph_24h_overlay(df: pd.DataFrame, outdir: Path):
    tb = (
        df.groupby(["comparison_period", "time_minutes", "time_label"], observed=True)
        .agg(total_volume=("volume", "sum"))
        .reset_index()
        .sort_values(["comparison_period", "time_minutes"])
    )

    plt.figure(figsize=(16, 8))

    for period in tb["comparison_period"].cat.categories if hasattr(tb["comparison_period"], "cat") else tb["comparison_period"].unique():
        sub = tb[tb["comparison_period"].astype(str).eq(str(period))]
        if sub.empty:
            continue
        plt.plot(
            sub["time_minutes"] / 60,
            sub["total_volume"] / 1_000_000,
            linewidth=2.8 if str(period) in ["Pre-COVID baseline", "Lockdown / COVID shock", "Busiest day detected"] else 2,
            color=PERIOD_COLORS.get(str(period), None),
            label=PERIOD_SHORT.get(str(period), str(period)),
            alpha=0.95,
        )

    plt.title("24-Hour Melbourne Traffic Shape: COVID Comparison Days", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("Each line shows total SCATS volume by 15-minute bin across the selected day.", y=0.93, fontsize=12, color="#475569")
    plt.xlabel("Hour of Day")
    plt.ylabel("Vehicle Movements per 15-Minute Bin (Millions)")
    plt.xticks(range(0, 25, 2))
    plt.grid(alpha=0.25)
    plt.legend(ncol=3, fontsize=10)
    savefig(outdir, "03_24_hour_traffic_shape_overlay.png")
    return tb


def graph_heatmap(tb: pd.DataFrame, outdir: Path):
    pivot = tb.pivot_table(
        index="comparison_period",
        columns="time_minutes",
        values="total_volume",
        aggfunc="sum",
        observed=True,
    )

    labels = [PERIOD_SHORT.get(str(p), str(p)) for p in pivot.index]
    xcols = pivot.columns.tolist()
    xtick_positions = [i for i, m in enumerate(xcols) if m % 120 == 0]
    xtick_labels = [f"{int(xcols[i] // 60):02d}:00" for i in xtick_positions]

    plt.figure(figsize=(16, 7))
    plt.imshow(pivot.values / 1_000_000, aspect="auto", cmap="YlOrRd")
    plt.colorbar(label="Vehicle Movements per 15-Minute Bin (Millions)")
    plt.title("Melbourne COVID Traffic Heartbeat Heatmap", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("Rows are historical comparison days; columns are 15-minute time bins.", y=0.94, fontsize=12, color="#475569")
    plt.yticks(range(len(labels)), labels)
    plt.xticks(xtick_positions, xtick_labels, rotation=45)
    plt.xlabel("Time of Day")
    plt.ylabel("Comparison Period")
    savefig(outdir, "04_time_bin_period_heatmap.png")


def graph_hourly_percent_change(df: pd.DataFrame, outdir: Path):
    hourly = (
        df.groupby(["comparison_period", "hour"], observed=True)
        .agg(total_volume=("volume", "sum"))
        .reset_index()
    )

    base = hourly[hourly["comparison_period"].astype(str).eq("Pre-COVID baseline")][["hour", "total_volume"]].rename(columns={"total_volume": "baseline_volume"})
    if base.empty:
        print("Skipping hourly percent change: no baseline found.")
        return

    comp = hourly.merge(base, on="hour", how="inner")
    comp = comp[~comp["comparison_period"].astype(str).eq("Pre-COVID baseline")].copy()
    comp["pct_change_vs_baseline"] = (comp["total_volume"] - comp["baseline_volume"]) / comp["baseline_volume"] * 100

    plt.figure(figsize=(16, 8))
    for period in comp["comparison_period"].cat.categories if hasattr(comp["comparison_period"], "cat") else comp["comparison_period"].unique():
        sub = comp[comp["comparison_period"].astype(str).eq(str(period))]
        if sub.empty:
            continue
        plt.plot(
            sub["hour"],
            sub["pct_change_vs_baseline"],
            marker="o",
            linewidth=2.4,
            label=PERIOD_SHORT.get(str(period), str(period)),
            color=PERIOD_COLORS.get(str(period), None),
        )

    plt.axhline(0, linestyle="--", color="#64748b", linewidth=1.5)
    plt.title("Hourly Traffic Change vs 2019 Baseline", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("Shows which hours of the day collapsed or exceeded the pre-COVID reference day.", y=0.93, fontsize=12, color="#475569")
    plt.xlabel("Hour of Day")
    plt.ylabel("% Change vs 2019 Baseline")
    plt.xticks(range(0, 24, 1))
    plt.grid(alpha=0.25)
    plt.legend(ncol=3, fontsize=10)
    savefig(outdir, "05_hourly_percent_change_vs_2019_baseline.png")


def site_period_totals(df: pd.DataFrame) -> pd.DataFrame:
    site = (
        df.groupby(["comparison_period", "site_id", "site_name"], observed=True)
        .agg(
            site_volume=("volume", "sum"),
            latitude=("latitude", "first"),
            longitude=("longitude", "first"),
        )
        .reset_index()
    )
    return site


def graph_top_collapse(site: pd.DataFrame, outdir: Path):
    pivot = site.pivot_table(
        index=["site_id", "site_name"],
        columns="comparison_period",
        values="site_volume",
        aggfunc="sum",
        observed=True,
    ).reset_index()

    if "Pre-COVID baseline" not in pivot.columns or "Lockdown / COVID shock" not in pivot.columns:
        print("Skipping site collapse graph: missing baseline or lockdown period.")
        return

    pivot["absolute_collapse"] = pivot["Pre-COVID baseline"].fillna(0) - pivot["Lockdown / COVID shock"].fillna(0)
    pivot["pct_collapse"] = np.where(
        pivot["Pre-COVID baseline"].fillna(0) > 0,
        pivot["absolute_collapse"] / pivot["Pre-COVID baseline"] * 100,
        np.nan,
    )
    top = pivot.sort_values("absolute_collapse", ascending=False).head(30).copy()
    top["label"] = top["site_name"].fillna(top["site_id"]).astype(str).str.slice(0, 34)

    plt.figure(figsize=(15, 12))
    plt.barh(top["label"][::-1], top["absolute_collapse"][::-1] / 1_000_000, color="#b00020")
    plt.title("Top 30 SCATS Sites by Absolute Traffic Collapse", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("2020 lockdown comparison day vs 2019 baseline day.", y=0.91, fontsize=12, color="#475569")
    plt.xlabel("Absolute Volume Loss (Millions)")
    plt.ylabel("SCATS Site")
    plt.grid(axis="x", alpha=0.25)
    savefig(outdir, "06_top_30_site_absolute_collapse_2020_vs_2019.png")


def graph_top_recovery_growth(site: pd.DataFrame, outdir: Path):
    pivot = site.pivot_table(
        index=["site_id", "site_name"],
        columns="comparison_period",
        values="site_volume",
        aggfunc="sum",
        observed=True,
    ).reset_index()

    if "Pre-COVID baseline" not in pivot.columns or "Busiest day detected" not in pivot.columns:
        print("Skipping recovery growth graph: missing baseline or busiest day period.")
        return

    pivot["growth_vs_baseline"] = pivot["Busiest day detected"].fillna(0) - pivot["Pre-COVID baseline"].fillna(0)
    pivot["growth_pct_vs_baseline"] = np.where(
        pivot["Pre-COVID baseline"].fillna(0) > 0,
        pivot["growth_vs_baseline"] / pivot["Pre-COVID baseline"] * 100,
        np.nan,
    )
    top = pivot.sort_values("growth_vs_baseline", ascending=False).head(30).copy()
    top["label"] = top["site_name"].fillna(top["site_id"]).astype(str).str.slice(0, 34)

    plt.figure(figsize=(15, 12))
    plt.barh(top["label"][::-1], top["growth_vs_baseline"][::-1] / 1_000_000, color="#16a34a")
    plt.title("Top 30 SCATS Sites by Post-COVID Growth", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("2025 busiest detected day vs 2019 baseline day.", y=0.91, fontsize=12, color="#475569")
    plt.xlabel("Growth Above 2019 Baseline (Millions)")
    plt.ylabel("SCATS Site")
    plt.grid(axis="x", alpha=0.25)
    savefig(outdir, "07_top_30_site_recovery_growth_2025_vs_2019.png")


def graph_recovery_scatter(site: pd.DataFrame, outdir: Path):
    pivot = site.pivot_table(
        index=["site_id", "site_name"],
        columns="comparison_period",
        values="site_volume",
        aggfunc="sum",
        observed=True,
    ).reset_index()

    needed = ["Pre-COVID baseline", "Lockdown / COVID shock", "Busiest day detected"]
    if not all(n in pivot.columns for n in needed):
        print("Skipping recovery scatter: missing one of baseline/lockdown/busiest.")
        return

    p = pivot.copy()
    base = p["Pre-COVID baseline"].replace(0, np.nan)
    p["lockdown_index"] = p["Lockdown / COVID shock"] / base * 100
    p["busiest_index"] = p["Busiest day detected"] / base * 100
    p = p.replace([np.inf, -np.inf], np.nan).dropna(subset=["lockdown_index", "busiest_index"])

    plt.figure(figsize=(13, 9))
    plt.scatter(
        p["lockdown_index"],
        p["busiest_index"],
        s=18,
        alpha=0.45,
        color="#007bff",
        edgecolors="none",
    )
    plt.axvline(100, linestyle="--", color="#64748b", linewidth=1)
    plt.axhline(100, linestyle="--", color="#64748b", linewidth=1)
    plt.title("SCATS Site Shock vs Recovery Scatter", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("Each dot is a SCATS site. X = lockdown level vs 2019; Y = 2025 busiest day vs 2019.", y=0.93, fontsize=12, color="#475569")
    plt.xlabel("2020 Lockdown Index (2019 = 100)")
    plt.ylabel("2025 Busiest Day Index (2019 = 100)")
    plt.grid(alpha=0.25)
    savefig(outdir, "08_site_recovery_scatter_2020_vs_2025.png")


def graph_active_sites(period: pd.DataFrame, outdir: Path):
    colors = [PERIOD_COLORS.get(str(p), "#64748b") for p in period["comparison_period"]]

    plt.figure(figsize=(15, 8))
    bars = plt.bar(
        [PERIOD_SHORT.get(str(p), str(p)) for p in period["comparison_period"]],
        period["active_sites"],
        color=colors,
    )
    plt.title("Active Mapped SCATS Sites by Comparison Day", fontsize=22, fontweight="bold", color="#16395f")
    plt.suptitle("Number of mapped SCATS sites with non-zero volume after coordinate join.", y=0.93, fontsize=12, color="#475569")
    plt.ylabel("Active Mapped Sites")
    plt.xlabel("Comparison Period")
    plt.grid(axis="y", alpha=0.25)

    for bar, val in zip(bars, period["active_sites"]):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), fmt_int(val), ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.xticks(rotation=20, ha="right")
    savefig(outdir, "09_distinct_active_sites_by_period.png")


def graph_dashboard(period: pd.DataFrame, outdir: Path):
    baseline = float(period[period["comparison_period"].astype(str).eq("Pre-COVID baseline")]["total_volume"].iloc[0]) if any(period["comparison_period"].astype(str).eq("Pre-COVID baseline")) else np.nan
    lockdown = float(period[period["comparison_period"].astype(str).eq("Lockdown / COVID shock")]["total_volume"].iloc[0]) if any(period["comparison_period"].astype(str).eq("Lockdown / COVID shock")) else np.nan
    busiest = float(period[period["comparison_period"].astype(str).eq("Busiest day detected")]["total_volume"].iloc[0]) if any(period["comparison_period"].astype(str).eq("Busiest day detected")) else np.nan

    lockdown_change = (lockdown - baseline) / baseline * 100 if baseline and not np.isnan(lockdown) else np.nan
    busiest_change = (busiest - baseline) / baseline * 100 if baseline and not np.isnan(busiest) else np.nan

    plt.figure(figsize=(16, 9))
    ax = plt.gca()
    ax.axis("off")
    ax.set_facecolor("#ffffff")

    ax.text(0.04, 0.92, "COVID Traffic Comparison Dashboard", fontsize=28, fontweight="bold", color="#16395f", transform=ax.transAxes)
    ax.text(0.04, 0.865, "Selected SCATS comparison days converted into high-level transport intelligence.", fontsize=13, color="#475569", transform=ax.transAxes)

    cards = [
        ("2019 Baseline", fmt_millions(baseline), "Reference day before COVID disruption", "#16395f"),
        ("2020 Lockdown", fmt_millions(lockdown), f"{lockdown_change:.1f}% vs baseline", "#b00020"),
        ("2025 Busiest Day", fmt_millions(busiest), f"{busiest_change:+.1f}% vs baseline", "#16a34a"),
        ("Active Sites", fmt_int(period["active_sites"].max()), "Maximum mapped active sites in comparison set", "#007bff"),
    ]

    x_positions = [0.04, 0.28, 0.52, 0.76]
    for x, (title, value, subtitle, color) in zip(x_positions, cards):
        rect = plt.Rectangle((x, 0.62), 0.20, 0.17, transform=ax.transAxes, facecolor="#f8fafc", edgecolor="#dbe3ef", linewidth=1.2)
        ax.add_patch(rect)
        ax.text(x + 0.015, 0.735, title, fontsize=13, fontweight="bold", color=color, transform=ax.transAxes)
        ax.text(x + 0.015, 0.685, value, fontsize=24, fontweight="bold", color="#111827", transform=ax.transAxes)
        ax.text(x + 0.015, 0.645, subtitle, fontsize=10.5, color="#64748b", transform=ax.transAxes)

    # small table
    rows = period.copy()
    rows["short"] = rows["comparison_period"].astype(str).map(lambda x: PERIOD_SHORT.get(x, x))
    rows["volume_m"] = rows["total_volume"] / 1_000_000
    rows["index"] = rows["total_volume"] / baseline * 100 if baseline and not np.isnan(baseline) else np.nan

    y = 0.52
    ax.text(0.04, y, "Period Summary", fontsize=17, fontweight="bold", color="#16395f", transform=ax.transAxes)
    y -= 0.045
    ax.text(0.04, y, "Period", fontsize=11, fontweight="bold", color="#334155", transform=ax.transAxes)
    ax.text(0.35, y, "Volume", fontsize=11, fontweight="bold", color="#334155", transform=ax.transAxes)
    ax.text(0.53, y, "Index", fontsize=11, fontweight="bold", color="#334155", transform=ax.transAxes)
    ax.text(0.68, y, "Active Sites", fontsize=11, fontweight="bold", color="#334155", transform=ax.transAxes)

    for _, r in rows.iterrows():
        y -= 0.045
        ax.text(0.04, y, str(r["short"]), fontsize=11, color="#111827", transform=ax.transAxes)
        ax.text(0.35, y, f"{r['volume_m']:.1f}M", fontsize=11, color="#111827", transform=ax.transAxes)
        ax.text(0.53, y, f"{r['index']:.1f}", fontsize=11, color="#111827", transform=ax.transAxes)
        ax.text(0.68, y, fmt_int(r["active_sites"]), fontsize=11, color="#111827", transform=ax.transAxes)

    savefig(outdir, "10_period_summary_dashboard.png")


def write_summary(outdir: Path, period: pd.DataFrame, df: pd.DataFrame):
    summary = {
        "script": "generate_covid_comparison_graphsV1.py",
        "rows_used": int(len(df)),
        "distinct_sites": int(df["site_id"].nunique()),
        "total_volume": float(df["volume"].sum()),
        "comparison_periods": period.assign(comparison_period=period["comparison_period"].astype(str)).to_dict(orient="records"),
        "graphs_created": [
            "01_total_volume_by_period.png",
            "02_total_volume_recovery_index.png",
            "03_24_hour_traffic_shape_overlay.png",
            "04_time_bin_period_heatmap.png",
            "05_hourly_percent_change_vs_2019_baseline.png",
            "06_top_30_site_absolute_collapse_2020_vs_2019.png",
            "07_top_30_site_recovery_growth_2025_vs_2019.png",
            "08_site_recovery_scatter_2020_vs_2025.png",
            "09_distinct_active_sites_by_period.png",
            "10_period_summary_dashboard.png",
        ],
    }
    path = outdir / "covid_comparison_graphs_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    ensure_outdir(outdir)

    df = load_data(Path(args.input))

    period = graph_total_volume_by_period(df, outdir)
    graph_recovery_index(period, outdir)
    tb = graph_24h_overlay(df, outdir)
    graph_heatmap(tb, outdir)
    graph_hourly_percent_change(df, outdir)

    site = site_period_totals(df)
    graph_top_collapse(site, outdir)
    graph_top_recovery_growth(site, outdir)
    graph_recovery_scatter(site, outdir)
    graph_active_sites(period, outdir)
    graph_dashboard(period, outdir)

    write_summary(outdir, period, df)

    print("")
    print("=" * 90)
    print("DONE")
    print("=" * 90)
    print(f"Charts written to: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
