#!/usr/bin/env python3
r"""
generate_covid_comparison_graphsV2.py

V2 fixes:
  - Fixes the SCATS shock vs recovery scatter plot bug.
  - Uses clean string comparison-period labels before pivoting.
  - Filters extremely tiny-baseline sites from the scatter so ratios are meaningful.
  - Adds robust axis bounds for the scatter plot.
  - Fixes title/subtitle overlap by using a consistent figure layout helper.
  - Writes all graphs into a V2 output folder.

Input:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\covid_comparison_v2
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_INPUT = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\covid_comparison_v2"

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


def make_fig(width=16, height=9, top=0.82, bottom=0.12, left=0.08, right=0.96):
    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    fig.subplots_adjust(top=top, bottom=bottom, left=left, right=right)
    return fig, ax


def title_block(fig, title: str, subtitle: str | None = None):
    fig.suptitle(title, fontsize=24, fontweight="bold", color="#16395f", y=0.965)
    if subtitle:
        fig.text(
            0.5,
            0.918,
            subtitle,
            ha="center",
            va="top",
            fontsize=12.5,
            color="#475569",
        )


def savefig(outdir: Path, filename: str) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / filename
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")
    return path


def load_data(path: Path) -> pd.DataFrame:
    print("=" * 90)
    print("COVID COMPARISON GRAPHS V2")
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

    df["comparison_period"] = df["comparison_period"].astype(str)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(0).astype(int)
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce").fillna(0).astype(int)
    df["time_minutes"] = df["hour"] * 60 + df["minute"]
    df["time_label"] = df["time_label"].astype(str).str.slice(0, 5)
    df["site_id"] = df["site_id"].astype(str)
    df["site_name"] = df["site_name"].fillna("").astype(str)

    found = [p for p in PERIOD_ORDER if p in set(df["comparison_period"])]
    extras = [p for p in df["comparison_period"].dropna().unique().tolist() if p not in found]
    order = found + extras
    df["comparison_period_cat"] = pd.Categorical(df["comparison_period"], categories=order, ordered=True)

    print(f"Periods: {order}")
    print(f"Distinct sites: {fmt_int(df['site_id'].nunique())}")
    print(f"Total volume: {fmt_int(df['volume'].sum())}")
    print("=" * 90)
    return df


def period_summary(df: pd.DataFrame) -> pd.DataFrame:
    period = (
        df.groupby("comparison_period", observed=True)
        .agg(total_volume=("volume", "sum"), active_sites=("site_id", "nunique"))
        .reset_index()
    )
    order_map = {p: i for i, p in enumerate(PERIOD_ORDER)}
    period["sort_order"] = period["comparison_period"].map(lambda x: order_map.get(x, 999))
    period = period.sort_values("sort_order").drop(columns=["sort_order"])
    return period


def graph_total_volume_by_period(df: pd.DataFrame, outdir: Path):
    period = period_summary(df)
    colors = [PERIOD_COLORS.get(str(p), "#64748b") for p in period["comparison_period"]]
    labels = [PERIOD_SHORT.get(str(p), str(p)) for p in period["comparison_period"]]

    fig, ax = make_fig(top=0.82, bottom=0.20)
    title_block(
        fig,
        "Melbourne Traffic Volume Across COVID Comparison Days",
        "Same SCATS network, selected historical comparison days."
    )

    bars = ax.bar(labels, period["total_volume"] / 1_000_000, color=colors)
    ax.set_ylabel("Total Vehicle Movements (Millions)")
    ax.set_xlabel("Comparison Period")
    ax.grid(axis="y", alpha=0.25)

    for bar, val in zip(bars, period["total_volume"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            fmt_millions(val),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    ax.tick_params(axis="x", rotation=20)
    for label in ax.get_xticklabels():
        label.set_ha("right")

    savefig(outdir, "01_total_volume_by_period.png")
    return period


def graph_recovery_index(period: pd.DataFrame, outdir: Path):
    baseline_rows = period[period["comparison_period"].eq("Pre-COVID baseline")]
    if baseline_rows.empty:
        print("Skipping recovery index: no Pre-COVID baseline period found.")
        return

    baseline = float(baseline_rows["total_volume"].iloc[0])
    data = period.copy()
    data["baseline_index"] = data["total_volume"] / baseline * 100

    labels = [PERIOD_SHORT.get(str(p), str(p)) for p in data["comparison_period"]]
    colors = [PERIOD_COLORS.get(str(p), "#64748b") for p in data["comparison_period"]]

    fig, ax = make_fig(top=0.82, bottom=0.20)
    title_block(
        fig,
        "COVID Traffic Recovery Index",
        "2019 baseline = 100. Lower values show collapse; higher values show recovery/growth."
    )

    ax.plot(labels, data["baseline_index"], marker="o", linewidth=3, color="#16395f")
    ax.scatter(labels, data["baseline_index"], s=120, color=colors, zorder=3)
    ax.axhline(100, linestyle="--", linewidth=1.5, color="#64748b")
    ax.set_ylabel("Index: 2019 baseline = 100")
    ax.set_xlabel("Comparison Period")
    ax.grid(alpha=0.25)

    for x, y in zip(labels, data["baseline_index"]):
        ax.text(x, y + 1.5, f"{y:.1f}", ha="center", fontsize=10, fontweight="bold")

    ax.tick_params(axis="x", rotation=20)
    for label in ax.get_xticklabels():
        label.set_ha("right")

    savefig(outdir, "02_total_volume_recovery_index.png")


def time_bin_summary(df: pd.DataFrame) -> pd.DataFrame:
    tb = (
        df.groupby(["comparison_period", "time_minutes", "time_label"], observed=True)
        .agg(total_volume=("volume", "sum"))
        .reset_index()
    )
    order_map = {p: i for i, p in enumerate(PERIOD_ORDER)}
    tb["sort_order"] = tb["comparison_period"].map(lambda x: order_map.get(x, 999))
    tb = tb.sort_values(["sort_order", "time_minutes"]).drop(columns=["sort_order"])
    return tb


def graph_24h_overlay(df: pd.DataFrame, outdir: Path):
    tb = time_bin_summary(df)

    fig, ax = make_fig(top=0.82, bottom=0.13)
    title_block(
        fig,
        "24-Hour Melbourne Traffic Shape: COVID Comparison Days",
        "Each line shows total SCATS volume by 15-minute bin across the selected day."
    )

    for period in [p for p in PERIOD_ORDER if p in set(tb["comparison_period"])]:
        sub = tb[tb["comparison_period"].eq(period)]
        ax.plot(
            sub["time_minutes"] / 60,
            sub["total_volume"] / 1_000_000,
            linewidth=3.0 if period in ["Pre-COVID baseline", "Lockdown / COVID shock", "Busiest day detected"] else 2.2,
            color=PERIOD_COLORS.get(period),
            label=PERIOD_SHORT.get(period, period),
            alpha=0.95,
        )

    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Vehicle Movements per 15-Minute Bin (Millions)")
    ax.set_xticks(range(0, 25, 2))
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, fontsize=10, loc="lower center", bbox_to_anchor=(0.5, 0.02), framealpha=0.95)

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
    ordered_index = [p for p in PERIOD_ORDER if p in pivot.index] + [p for p in pivot.index if p not in PERIOD_ORDER]
    pivot = pivot.loc[ordered_index]

    labels = [PERIOD_SHORT.get(str(p), str(p)) for p in pivot.index]
    xcols = pivot.columns.tolist()
    xtick_positions = [i for i, m in enumerate(xcols) if m % 120 == 0]
    xtick_labels = [f"{int(xcols[i] // 60):02d}:00" for i in xtick_positions]

    fig, ax = make_fig(width=16, height=7.5, top=0.80, bottom=0.18, left=0.12, right=0.90)
    title_block(
        fig,
        "Melbourne COVID Traffic Heartbeat Heatmap",
        "Rows are historical comparison days; columns are 15-minute time bins."
    )

    im = ax.imshow(pivot.values / 1_000_000, aspect="auto", cmap="YlOrRd")
    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.035)
    cbar.set_label("Vehicle Movements per 15-Minute Bin (Millions)")

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xticks(xtick_positions)
    ax.set_xticklabels(xtick_labels, rotation=45, ha="right")
    ax.set_xlabel("Time of Day")
    ax.set_ylabel("Comparison Period")

    savefig(outdir, "04_time_bin_period_heatmap.png")


def graph_hourly_percent_change(df: pd.DataFrame, outdir: Path):
    hourly = (
        df.groupby(["comparison_period", "hour"], observed=True)
        .agg(total_volume=("volume", "sum"))
        .reset_index()
    )

    base = hourly[hourly["comparison_period"].eq("Pre-COVID baseline")][["hour", "total_volume"]].rename(columns={"total_volume": "baseline_volume"})
    if base.empty:
        print("Skipping hourly percent change: no baseline found.")
        return

    comp = hourly.merge(base, on="hour", how="inner")
    comp = comp[~comp["comparison_period"].eq("Pre-COVID baseline")].copy()
    comp["pct_change_vs_baseline"] = (comp["total_volume"] - comp["baseline_volume"]) / comp["baseline_volume"] * 100

    fig, ax = make_fig(top=0.80, bottom=0.12)
    title_block(
        fig,
        "Hourly Traffic Change vs 2019 Baseline",
        "Shows which hours of the day collapsed or exceeded the pre-COVID reference day."
    )

    for period in [p for p in PERIOD_ORDER if p in set(comp["comparison_period"])]:
        if period == "Pre-COVID baseline":
            continue
        sub = comp[comp["comparison_period"].eq(period)]
        if sub.empty:
            continue
        ax.plot(
            sub["hour"],
            sub["pct_change_vs_baseline"],
            marker="o",
            linewidth=2.4,
            label=PERIOD_SHORT.get(period, period),
            color=PERIOD_COLORS.get(period),
        )

    ax.axhline(0, linestyle="--", color="#64748b", linewidth=1.5)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("% Change vs 2019 Baseline")
    ax.set_xticks(range(0, 24, 1))
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, fontsize=10, loc="upper left", framealpha=0.95)

    savefig(outdir, "05_hourly_percent_change_vs_2019_baseline.png")


def site_period_totals(df: pd.DataFrame) -> pd.DataFrame:
    # Use site_id as the durable key. Site names are carried as first non-empty.
    site = (
        df.groupby(["comparison_period", "site_id"], observed=True)
        .agg(
            site_volume=("volume", "sum"),
            site_name=("site_name", lambda s: next((x for x in s.astype(str) if x.strip()), "")),
            latitude=("latitude", "first"),
            longitude=("longitude", "first"),
        )
        .reset_index()
    )
    return site


def site_pivot(site: pd.DataFrame) -> pd.DataFrame:
    vol = site.pivot_table(
        index="site_id",
        columns="comparison_period",
        values="site_volume",
        aggfunc="sum",
        observed=True,
    ).reset_index()

    names = (
        site.groupby("site_id", as_index=False)
        .agg(site_name=("site_name", "first"), latitude=("latitude", "first"), longitude=("longitude", "first"))
    )

    out = names.merge(vol, on="site_id", how="left")
    return out


def graph_top_collapse(site: pd.DataFrame, outdir: Path):
    pivot = site_pivot(site)
    if "Pre-COVID baseline" not in pivot.columns or "Lockdown / COVID shock" not in pivot.columns:
        print("Skipping site collapse graph: missing baseline or lockdown period.")
        return

    pivot["absolute_collapse"] = pivot["Pre-COVID baseline"].fillna(0) - pivot["Lockdown / COVID shock"].fillna(0)
    pivot["pct_collapse"] = np.where(
        pivot["Pre-COVID baseline"].fillna(0) > 0,
        pivot["absolute_collapse"] / pivot["Pre-COVID baseline"] * 100,
        np.nan,
    )

    top = pivot[pivot["absolute_collapse"] > 0].sort_values("absolute_collapse", ascending=False).head(30).copy()
    top["label"] = top["site_name"].fillna(top["site_id"]).astype(str).map(lambda x: textwrap.shorten(x, width=38, placeholder="…"))

    fig, ax = make_fig(width=15, height=12, top=0.86, bottom=0.08, left=0.28, right=0.96)
    title_block(
        fig,
        "Top 30 SCATS Sites by Absolute Traffic Collapse",
        "2020 lockdown comparison day vs 2019 baseline day."
    )

    ax.barh(top["label"][::-1], top["absolute_collapse"][::-1] / 1_000_000, color="#b00020")
    ax.set_xlabel("Absolute Volume Loss (Millions)")
    ax.set_ylabel("SCATS Site")
    ax.grid(axis="x", alpha=0.25)

    savefig(outdir, "06_top_30_site_absolute_collapse_2020_vs_2019.png")


def graph_top_recovery_growth(site: pd.DataFrame, outdir: Path):
    pivot = site_pivot(site)
    if "Pre-COVID baseline" not in pivot.columns or "Busiest day detected" not in pivot.columns:
        print("Skipping recovery growth graph: missing baseline or busiest day period.")
        return

    pivot["growth_vs_baseline"] = pivot["Busiest day detected"].fillna(0) - pivot["Pre-COVID baseline"].fillna(0)
    pivot["growth_pct_vs_baseline"] = np.where(
        pivot["Pre-COVID baseline"].fillna(0) > 0,
        pivot["growth_vs_baseline"] / pivot["Pre-COVID baseline"] * 100,
        np.nan,
    )

    top = pivot[pivot["growth_vs_baseline"] > 0].sort_values("growth_vs_baseline", ascending=False).head(30).copy()
    top["label"] = top["site_name"].fillna(top["site_id"]).astype(str).map(lambda x: textwrap.shorten(x, width=38, placeholder="…"))

    fig, ax = make_fig(width=15, height=12, top=0.86, bottom=0.08, left=0.28, right=0.96)
    title_block(
        fig,
        "Top 30 SCATS Sites by Post-COVID Growth",
        "2025 busiest detected day vs 2019 baseline day."
    )

    ax.barh(top["label"][::-1], top["growth_vs_baseline"][::-1] / 1_000_000, color="#16a34a")
    ax.set_xlabel("Growth Above 2019 Baseline (Millions)")
    ax.set_ylabel("SCATS Site")
    ax.grid(axis="x", alpha=0.25)

    savefig(outdir, "07_top_30_site_recovery_growth_2025_vs_2019.png")


def graph_recovery_scatter(site: pd.DataFrame, outdir: Path):
    pivot = site_pivot(site)

    needed = ["Pre-COVID baseline", "Lockdown / COVID shock", "Busiest day detected"]
    if not all(n in pivot.columns for n in needed):
        print("Skipping recovery scatter: missing one of baseline/lockdown/busiest.")
        return

    p = pivot.copy()
    p["baseline_volume"] = pd.to_numeric(p["Pre-COVID baseline"], errors="coerce")
    p["lockdown_volume"] = pd.to_numeric(p["Lockdown / COVID shock"], errors="coerce")
    p["busiest_volume"] = pd.to_numeric(p["Busiest day detected"], errors="coerce")

    # Avoid meaningless huge ratios from tiny baseline sites.
    baseline_min = max(1000.0, float(p["baseline_volume"].quantile(0.10)))
    p = p[p["baseline_volume"] >= baseline_min].copy()

    p["lockdown_index"] = p["lockdown_volume"] / p["baseline_volume"] * 100.0
    p["busiest_index"] = p["busiest_volume"] / p["baseline_volume"] * 100.0

    p = p.replace([np.inf, -np.inf], np.nan).dropna(subset=["lockdown_index", "busiest_index"])
    p = p[(p["lockdown_index"] >= 0) & (p["busiest_index"] >= 0)].copy()

    # Use percentile-based axis limits so outliers do not wreck the view.
    x_max = max(120, min(250, float(p["lockdown_index"].quantile(0.995)) * 1.08))
    y_max = max(150, min(350, float(p["busiest_index"].quantile(0.995)) * 1.08))

    fig, ax = make_fig(width=13.5, height=9, top=0.82, bottom=0.12)
    title_block(
        fig,
        "SCATS Site Shock vs Recovery Scatter",
        "Each dot is a SCATS site. X = 2020 lockdown index vs 2019; Y = 2025 busiest day index vs 2019."
    )

    sizes = np.clip(np.sqrt(p["baseline_volume"]) / 5, 8, 90)

    ax.scatter(
        p["lockdown_index"],
        p["busiest_index"],
        s=sizes,
        alpha=0.38,
        color="#007bff",
        edgecolors="none",
    )

    ax.axvline(100, linestyle="--", color="#64748b", linewidth=1.2)
    ax.axhline(100, linestyle="--", color="#64748b", linewidth=1.2)

    ax.set_xlim(0, x_max)
    ax.set_ylim(0, y_max)

    ax.set_xlabel("2020 Lockdown Index (2019 = 100)")
    ax.set_ylabel("2025 Busiest Day Index (2019 = 100)")
    ax.grid(alpha=0.25)

    # Quadrant labels
    ax.text(5, y_max * 0.94, "Collapsed hard,\nthen over-recovered", fontsize=10, color="#475569", va="top")
    ax.text(x_max * 0.60, y_max * 0.94, "Resilient through lockdown,\nthen over-recovered", fontsize=10, color="#475569", va="top")
    ax.text(5, y_max * 0.10, f"Filtered tiny-baseline sites\nbaseline min ≈ {fmt_int(baseline_min)} vehicles/day", fontsize=9, color="#64748b", va="bottom")

    savefig(outdir, "08_site_recovery_scatter_2020_vs_2025.png")


def graph_active_sites(period: pd.DataFrame, outdir: Path):
    colors = [PERIOD_COLORS.get(str(p), "#64748b") for p in period["comparison_period"]]
    labels = [PERIOD_SHORT.get(str(p), str(p)) for p in period["comparison_period"]]

    fig, ax = make_fig(top=0.82, bottom=0.20)
    title_block(
        fig,
        "Active Mapped SCATS Sites by Comparison Day",
        "Number of mapped SCATS sites with non-zero volume after coordinate join."
    )

    bars = ax.bar(labels, period["active_sites"], color=colors)
    ax.set_ylabel("Active Mapped Sites")
    ax.set_xlabel("Comparison Period")
    ax.grid(axis="y", alpha=0.25)

    for bar, val in zip(bars, period["active_sites"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            fmt_int(val),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    ax.tick_params(axis="x", rotation=20)
    for label in ax.get_xticklabels():
        label.set_ha("right")

    savefig(outdir, "09_distinct_active_sites_by_period.png")


def graph_dashboard(period: pd.DataFrame, outdir: Path):
    baseline = float(period[period["comparison_period"].eq("Pre-COVID baseline")]["total_volume"].iloc[0]) if any(period["comparison_period"].eq("Pre-COVID baseline")) else np.nan
    lockdown = float(period[period["comparison_period"].eq("Lockdown / COVID shock")]["total_volume"].iloc[0]) if any(period["comparison_period"].eq("Lockdown / COVID shock")) else np.nan
    busiest = float(period[period["comparison_period"].eq("Busiest day detected")]["total_volume"].iloc[0]) if any(period["comparison_period"].eq("Busiest day detected")) else np.nan

    lockdown_change = (lockdown - baseline) / baseline * 100 if baseline and not np.isnan(lockdown) else np.nan
    busiest_change = (busiest - baseline) / baseline * 100 if baseline and not np.isnan(busiest) else np.nan

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.03, right=0.98, top=0.94, bottom=0.05)
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

    rows = period.copy()
    rows["short"] = rows["comparison_period"].map(lambda x: PERIOD_SHORT.get(x, x))
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
        "script": "generate_covid_comparison_graphsV2.py",
        "rows_used": int(len(df)),
        "distinct_sites": int(df["site_id"].nunique()),
        "total_volume": float(df["volume"].sum()),
        "comparison_periods": period.to_dict(orient="records"),
        "v2_fixes": [
            "fixed title/subtitle overlap",
            "fixed scatter plot index calculation",
            "site pivot now uses site_id as durable key",
            "scatter filters tiny-baseline sites",
            "scatter uses percentile axis bounds",
        ],
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
    outdir.mkdir(parents=True, exist_ok=True)

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
