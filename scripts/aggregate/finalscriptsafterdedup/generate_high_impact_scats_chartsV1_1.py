#!/usr/bin/env python3
r"""
generate_high_impact_scats_chartsV1_1.py

Third-wave high-impact Melbourne SCATS chart generator V1.1.

Purpose:
  Build the 10 most valuable follow-on charts from already-generated CSV files,
  without querying DuckDB again.

Designed for:
  A:\TrafficAnalytics\PROJECTS\reports\deduped

Inputs expected where available:
  site_month_totals.csv
  monthly_totals.csv
  daily_totals.csv
  site_totals.csv
  time_bin_profile.csv
  all_scats_sites_map_data_audit.csv

Outputs:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\high_impact_charts

Charts produced:
  01 traffic momentum index
  02 rising sites
  03 declining sites
  04 network stability index
  05 traffic concentration curve
  06 commercial value ranking
  07 weekday profile
  08 monthly seasonality profile
  09 site lifecycle clusters
  10 shock detection timeline

Notes:
  - This script is intentionally tolerant of slightly different column names.
  - It uses existing aggregate CSVs only.
  - Missing optional CSVs will skip only the charts that need them.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker


# -----------------------------
# Styling
# -----------------------------

TRAFFIC_RED = "#C62828"
TRAFFIC_ORANGE = "#EF6C00"
TRAFFIC_AMBER = "#F9A825"
TRAFFIC_GREEN = "#2E7D32"
TRAFFIC_BLUE = "#1565C0"
TRAFFIC_NAVY = "#0D47A1"
TRAFFIC_PURPLE = "#6A1B9A"
TRAFFIC_GREY = "#607D8B"
TRAFFIC_LIGHT_GREY = "#ECEFF1"
TRAFFIC_DARK = "#263238"

RANK_COLOURS = [TRAFFIC_RED, TRAFFIC_ORANGE, TRAFFIC_AMBER, TRAFFIC_GREY]


def apply_chart_theme() -> None:
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#B0BEC5",
        "axes.labelcolor": TRAFFIC_DARK,
        "axes.titlecolor": TRAFFIC_DARK,
        "xtick.color": TRAFFIC_DARK,
        "ytick.color": TRAFFIC_DARK,
        "grid.color": "#CFD8DC",
        "grid.alpha": 0.65,
        "font.size": 10,
        "axes.titlesize": 17,
        "axes.titleweight": "bold",
        "axes.labelsize": 12,
        "legend.fontsize": 9,
        "savefig.facecolor": "white",
        "savefig.bbox": "tight",
        "savefig.dpi": 180,
    })


def fmt_big(x: float, _pos=None) -> str:
    if pd.isna(x):
        return ""
    ax = abs(float(x))
    if ax >= 1_000_000_000:
        return f"{x / 1_000_000_000:.1f}B"
    if ax >= 1_000_000:
        return f"{x / 1_000_000:.0f}M"
    if ax >= 1_000:
        return f"{x / 1_000:.0f}K"
    return f"{x:.0f}"


def fmt_pct(x: float, _pos=None) -> str:
    if pd.isna(x):
        return ""
    return f"{x:.0f}%"


def save(fig, path: Path) -> None:
    fig.savefig(path)
    plt.close(fig)
    print(f"Wrote {path}")


def add_footer(fig, text: str = "Source: Melbourne SCATS cleaned/deduplicated aggregate CSV outputs, 2014–2026.") -> None:
    fig.text(0.01, 0.01, text, ha="left", va="bottom", fontsize=8, color=TRAFFIC_GREY)


def pick_column(df: pd.DataFrame, candidates: Iterable[str], label: str, required: bool = True) -> str | None:
    lower = {c.lower().strip(): c for c in df.columns}
    for c in candidates:
        if c in lower:
            return lower[c]
    if required:
        raise ValueError(f"Could not find {label} column. Available columns: {list(df.columns)}")
    return None


def read_csv_optional(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        print(f"SKIP: missing {path.name}")
        return None
    print(f"Reading {path}")
    return pd.read_csv(path, low_memory=False)


def clean_label_text(text: str, max_len: int = 52) -> str:
    text = str(text or "").strip()
    if re.match(r"^\d{4}-\d{2}(-\d{2})?$", text):
        return ""
    if re.match(r"^\d+(\.0)?$", text):
        return ""
    if text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return ""
    text = " ".join(text.replace("_", " ").split()).upper()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def site_label(site_id: str, site_name: str | None = None, rank: int | None = None) -> str:
    name = clean_label_text(site_name or "")
    base = f"{name} ({site_id})" if name else f"SCATS {site_id} (network node)"
    return f"#{rank} {base}" if rank is not None else base


def load_site_lookup(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["site_id", "lookup_site_name"])

    raw = pd.read_csv(path, low_memory=False)
    site_col = pick_column(raw, ["site_id", "site_no", "scats_site", "nb_scats_site", "site"], "site ID", required=False)
    if not site_col:
        return pd.DataFrame(columns=["site_id", "lookup_site_name"])

    lower = {c.lower().strip(): c for c in raw.columns}
    name = pd.Series([""] * len(raw), index=raw.index, dtype="object")

    for candidate in ["friendly_name", "site_name", "site_name_from_volume_csv", "location", "description", "name"]:
        if candidate in lower:
            s = raw[lower[candidate]].fillna("").astype(str).str.strip()
            name = name.mask(name.eq(""), s)

    lookup = pd.DataFrame({
        "site_id": raw[site_col].astype(str).str.strip(),
        "lookup_site_name": name.fillna("").astype(str).str.strip(),
    })
    lookup["lookup_site_name"] = lookup["lookup_site_name"].map(clean_label_text)
    lookup = lookup[lookup["lookup_site_name"].ne("")]
    return lookup.drop_duplicates("site_id", keep="first")


def normalise_site_month(df: pd.DataFrame, lookup: pd.DataFrame | None = None) -> pd.DataFrame:
    site_col = pick_column(df, ["site_id", "site_no", "nb_scats_site", "scats_site", "site"], "site ID")
    month_col = pick_column(df, ["month_label", "year_month", "month", "month_start", "date_month"], "month")
    vol_col = pick_column(df, ["month_site_volume", "total_volume", "volume", "monthly_volume", "vehicles", "sum_volume"], "volume")
    name_col = pick_column(df, ["friendly_name", "site_name", "location", "description", "name"], "site name", required=False)

    out = pd.DataFrame({
        "site_id": df[site_col].astype(str).str.strip(),
        "month": pd.to_datetime(df[month_col].astype(str), errors="coerce"),
        "volume": pd.to_numeric(df[vol_col], errors="coerce"),
    })
    out["site_name"] = df[name_col].fillna("").astype(str).str.strip() if name_col else ""
    out["site_name"] = out["site_name"].map(clean_label_text)

    out = out.dropna(subset=["month", "volume", "site_id"])
    out["month"] = out["month"].dt.to_period("M").dt.to_timestamp()
    out["volume"] = out["volume"].fillna(0).astype("int64")
    out = out.groupby(["site_id", "month"], as_index=False).agg(
        volume=("volume", "sum"),
        site_name=("site_name", lambda s: next((x for x in s if str(x).strip()), "")),
    )

    if lookup is not None and not lookup.empty:
        out = out.merge(lookup, on="site_id", how="left")
        out["site_name"] = out["site_name"].mask(out["site_name"].eq(""), out["lookup_site_name"].fillna(""))
        out = out.drop(columns=["lookup_site_name"], errors="ignore")

    return out


def normalise_monthly(df: pd.DataFrame) -> pd.DataFrame:
    month_col = pick_column(df, ["month_label", "year_month", "month", "month_start", "date_month"], "month")
    vol_col = pick_column(df, ["month_total_volume", "total_volume", "monthly_volume", "volume", "vehicles", "sum_volume", "month_volume"], "volume")
    out = pd.DataFrame({
        "month": pd.to_datetime(df[month_col].astype(str), errors="coerce"),
        "volume": pd.to_numeric(df[vol_col], errors="coerce"),
    }).dropna()
    out["month"] = out["month"].dt.to_period("M").dt.to_timestamp()
    return out.groupby("month", as_index=False)["volume"].sum().sort_values("month")


def normalise_daily(df: pd.DataFrame) -> pd.DataFrame:
    date_col = pick_column(df, ["count_date", "date", "day", "traffic_date", "date_value"], "date")
    vol_col = pick_column(df, ["day_total_volume", "daily_volume", "total_volume", "volume", "vehicles", "sum_volume"], "volume")
    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_col], errors="coerce"),
        "volume": pd.to_numeric(df[vol_col], errors="coerce"),
    }).dropna()
    return out.groupby("date", as_index=False)["volume"].sum().sort_values("date")


def normalise_site_totals(df: pd.DataFrame, site_month: pd.DataFrame | None = None, lookup: pd.DataFrame | None = None) -> pd.DataFrame:
    # If site_totals.csv is actually a site-month file, derive totals from it.
    lower = {c.lower().strip(): c for c in df.columns}
    if "month_site_volume" in lower or "month_label" in lower:
        sm = normalise_site_month(df, lookup)
        return sm.groupby("site_id", as_index=False).agg(
            total_volume=("volume", "sum"),
            site_name=("site_name", "first"),
        )

    site_col = pick_column(df, ["site_id", "site_no", "nb_scats_site", "scats_site", "site"], "site ID")
    vol_col = pick_column(df, ["total_cleaned_volume", "total_volume", "volume", "site_total_volume", "vehicles"], "volume")
    name_col = pick_column(df, ["friendly_name", "site_name", "location", "description", "name"], "site name", required=False)

    out = pd.DataFrame({
        "site_id": df[site_col].astype(str).str.strip(),
        "total_volume": pd.to_numeric(df[vol_col], errors="coerce"),
        "site_name": df[name_col].fillna("").astype(str).str.strip() if name_col else "",
    }).dropna(subset=["total_volume"])
    out["site_name"] = out["site_name"].map(clean_label_text)

    if lookup is not None and not lookup.empty:
        out = out.merge(lookup, on="site_id", how="left")
        out["site_name"] = out["site_name"].mask(out["site_name"].eq(""), out["lookup_site_name"].fillna(""))
        out = out.drop(columns=["lookup_site_name"], errors="ignore")

    return out.groupby("site_id", as_index=False).agg(
        total_volume=("total_volume", "sum"),
        site_name=("site_name", "first"),
    )


def prepare_monthly_from_best(monthly_raw: pd.DataFrame | None, site_month: pd.DataFrame | None) -> pd.DataFrame | None:
    if monthly_raw is not None:
        try:
            return normalise_monthly(monthly_raw)
        except Exception as exc:
            print(f"WARNING: could not normalise monthly file, falling back to site_month: {exc}")
    if site_month is not None:
        return site_month.groupby("month", as_index=False)["volume"].sum().sort_values("month")
    return None


# -----------------------------
# Charts
# -----------------------------

def chart_01_momentum(monthly: pd.DataFrame, outdir: Path) -> None:
    m = monthly.sort_values("month").copy()
    # Drop last month if obviously partial compared with previous 6-month median.
    if len(m) > 8 and m.iloc[-1]["volume"] < 0.75 * m.iloc[-7:-1]["volume"].median():
        m = m.iloc[:-1].copy()

    m["mom_pct"] = m["volume"].pct_change() * 100.0
    m["momentum_3m"] = m["mom_pct"].rolling(3).mean()
    m.to_csv(outdir / "traffic_momentum_index.csv", index=False)

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.axhline(0, color=TRAFFIC_GREY, linewidth=1.2)
    ax.plot(m["month"], m["momentum_3m"], color=TRAFFIC_BLUE, linewidth=2.5)
    ax.fill_between(m["month"], m["momentum_3m"], 0, where=m["momentum_3m"] >= 0, color=TRAFFIC_GREEN, alpha=0.18)
    ax.fill_between(m["month"], m["momentum_3m"], 0, where=m["momentum_3m"] < 0, color=TRAFFIC_RED, alpha=0.18)
    ax.set_title("Melbourne Traffic Momentum Index — 3-Month Rolling Change")
    ax.set_xlabel("X-axis: month")
    ax.set_ylabel("Y-axis: rolling monthly change (%)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_pct))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(True, axis="y")
    ax.spines[["top", "right"]].set_visible(False)
    add_footer(fig, "Momentum method: month-to-month percentage change, smoothed with a 3-month rolling average.")
    save(fig, outdir / "01_traffic_momentum_index.png")


def growth_table(site_month: pd.DataFrame) -> pd.DataFrame:
    sm = site_month.sort_values(["site_id", "month"]).copy()
    first = sm.groupby("site_id").head(12).groupby("site_id", as_index=False).agg(
        first_avg=("volume", "mean"), site_name=("site_name", "first")
    )
    last = sm.groupby("site_id").tail(12).groupby("site_id", as_index=False).agg(last_avg=("volume", "mean"))
    g = first.merge(last, on="site_id", how="inner")
    g = g[(g["first_avg"] > 1000) & (g["last_avg"] > 1000)].copy()
    g["absolute_growth"] = g["last_avg"] - g["first_avg"]
    g["growth_pct"] = (g["absolute_growth"] / g["first_avg"]) * 100.0
    return g


def chart_02_rising(site_month: pd.DataFrame, outdir: Path, top_n: int = 20) -> None:
    g = growth_table(site_month).sort_values("absolute_growth", ascending=False).head(top_n).reset_index(drop=True)
    g["rank"] = g.index + 1
    g.to_csv(outdir / "rising_sites_top20.csv", index=False)

    plot = g.iloc[::-1].copy()
    labels = [site_label(r.site_id, r.site_name, int(r.rank)) for r in plot.itertuples(index=False)]

    fig, ax = plt.subplots(figsize=(14, 10))
    ax.barh(labels, plot["absolute_growth"], color=TRAFFIC_GREEN)
    ax.set_title("Top 20 Rising SCATS Sites / Network Nodes — Long-Term Monthly Growth")
    ax.set_xlabel("X-axis: average monthly vehicle movement increase")
    ax.set_ylabel("Y-axis: ranked SCATS site / network node")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt_big))
    ax.grid(True, axis="x")
    ax.spines[["top", "right"]].set_visible(False)
    xmax = plot["absolute_growth"].max()
    for y, val in enumerate(plot["absolute_growth"]):
        ax.text(val + xmax * 0.008, y, fmt_big(val), va="center", fontsize=8, color=TRAFFIC_DARK)
    add_footer(fig, "Growth method: last 12 observed months compared with first 12 observed months per site.")
    save(fig, outdir / "02_top20_rising_sites.png")


def chart_03_declining(site_month: pd.DataFrame, outdir: Path, top_n: int = 20) -> None:
    g = growth_table(site_month).sort_values("absolute_growth", ascending=True).head(top_n).reset_index(drop=True)
    g["rank"] = g.index + 1
    g.to_csv(outdir / "declining_sites_top20.csv", index=False)

    plot = g.iloc[::-1].copy()
    labels = [site_label(r.site_id, r.site_name, int(r.rank)) for r in plot.itertuples(index=False)]

    fig, ax = plt.subplots(figsize=(14, 10))
    ax.barh(labels, plot["absolute_growth"], color=TRAFFIC_RED)
    ax.axvline(0, color=TRAFFIC_GREY, linewidth=1)
    ax.set_title("Top 20 Declining SCATS Sites / Network Nodes — Long-Term Monthly Change")
    ax.set_xlabel("X-axis: average monthly vehicle movement change")
    ax.set_ylabel("Y-axis: ranked SCATS site / network node")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt_big))
    ax.grid(True, axis="x")
    ax.spines[["top", "right"]].set_visible(False)
    xmin = abs(plot["absolute_growth"].min())
    for y, val in enumerate(plot["absolute_growth"]):
        ax.text(val - xmin * 0.03, y, fmt_big(val), va="center", ha="right", fontsize=8, color=TRAFFIC_DARK)
    add_footer(fig, "Decline method: last 12 observed months compared with first 12 observed months per site.")
    save(fig, outdir / "03_top20_declining_sites.png")


def chart_04_stability(site_month: pd.DataFrame, outdir: Path) -> None:
    sm = site_month.copy()
    monthly = sm.groupby("month").agg(
        mean_site_volume=("volume", "mean"),
        std_site_volume=("volume", "std"),
        active_sites=("site_id", "nunique"),
    ).reset_index()
    monthly["network_cv"] = monthly["std_site_volume"] / monthly["mean_site_volume"]
    monthly.to_csv(outdir / "network_stability_index.csv", index=False)

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(monthly["month"], monthly["network_cv"], color=TRAFFIC_PURPLE, linewidth=2.4)
    ax.fill_between(monthly["month"], monthly["network_cv"], color=TRAFFIC_PURPLE, alpha=0.14)
    ax.set_title("Network Stability Index — Variation Across SCATS Sites Each Month")
    ax.set_xlabel("X-axis: month")
    ax.set_ylabel("Y-axis: coefficient of variation across sites")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(True, axis="y")
    ax.spines[["top", "right"]].set_visible(False)
    add_footer(fig, "Stability method: monthly standard deviation across site volumes divided by monthly mean site volume.")
    save(fig, outdir / "04_network_stability_index.png")


def chart_05_concentration(site_totals: pd.DataFrame, outdir: Path) -> None:
    s = site_totals.sort_values("total_volume", ascending=False).reset_index(drop=True).copy()
    s["rank"] = s.index + 1
    s["cum_volume"] = s["total_volume"].cumsum()
    total = s["total_volume"].sum()
    s["cum_share"] = s["cum_volume"] / total * 100
    s["site_share"] = s["rank"] / len(s) * 100
    s.to_csv(outdir / "traffic_concentration_curve.csv", index=False)

    # capture milestone points
    milestones = []
    for pct in [10, 20, 50, 80]:
        nsites = int((s["cum_share"] >= pct).idxmax() + 1)
        milestones.append((pct, nsites, nsites / len(s) * 100))
    pd.DataFrame(milestones, columns=["traffic_pct", "sites_needed", "site_pct"]).to_csv(
        outdir / "traffic_concentration_milestones.csv", index=False
    )

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.plot(s["site_share"], s["cum_share"], color=TRAFFIC_RED, linewidth=2.8)
    ax.plot([0, 100], [0, 100], color=TRAFFIC_GREY, linestyle="--", linewidth=1.2, alpha=0.7)
    for pct, nsites, spct in milestones:
        ax.scatter([spct], [pct], color=TRAFFIC_NAVY, s=40, zorder=3)
        ax.text(spct + 1.2, pct, f"{pct}% traffic\n{nsites:,} sites", fontsize=8, color=TRAFFIC_DARK, va="center")
    ax.set_title("Traffic Concentration Curve — How Much Volume Is Carried by Top Sites?")
    ax.set_xlabel("X-axis: cumulative share of SCATS sites (%)")
    ax.set_ylabel("Y-axis: cumulative share of vehicle movements (%)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.grid(True)
    ax.spines[["top", "right"]].set_visible(False)
    add_footer(fig, "Concentration method: sites ranked by total observed volume, then cumulative share calculated.")
    save(fig, outdir / "05_traffic_concentration_curve.png")


def chart_06_commercial_value(site_month: pd.DataFrame, site_totals: pd.DataFrame, outdir: Path, top_n: int = 25) -> None:
    g = growth_table(site_month)[["site_id", "absolute_growth", "growth_pct"]]
    vol = site_totals[["site_id", "total_volume", "site_name"]].copy()

    stability = site_month.groupby("site_id", as_index=False).agg(
        mean_volume=("volume", "mean"),
        std_volume=("volume", "std"),
    )
    stability["cv"] = stability["std_volume"] / stability["mean_volume"]
    x = vol.merge(g, on="site_id", how="left").merge(stability[["site_id", "cv"]], on="site_id", how="left")
    x["absolute_growth"] = x["absolute_growth"].fillna(0)
    x["cv"] = x["cv"].replace([np.inf, -np.inf], np.nan)

    def percentile(s: pd.Series, high_good: bool = True) -> pd.Series:
        r = s.rank(pct=True)
        return r if high_good else 1 - r

    x["volume_score"] = percentile(x["total_volume"], True)
    x["growth_score"] = percentile(x["absolute_growth"], True)
    x["stability_score"] = percentile(x["cv"], False).fillna(0.5)

    # OOH-style score: exposure is dominant, growth important, stability useful.
    x["commercial_value_score"] = (
        x["volume_score"] * 0.55 +
        x["growth_score"] * 0.25 +
        x["stability_score"] * 0.20
    ) * 100

    top = x.sort_values("commercial_value_score", ascending=False).head(top_n).reset_index(drop=True)
    top["rank"] = top.index + 1
    top.to_csv(outdir / "commercial_value_ranking_top25.csv", index=False)

    plot = top.iloc[::-1].copy()
    labels = [site_label(r.site_id, r.site_name, int(r.rank)) for r in plot.itertuples(index=False)]

    fig, ax = plt.subplots(figsize=(14, 11))
    colours = [TRAFFIC_GREY] * len(plot)
    colours[-1] = TRAFFIC_RED
    colours[-2] = TRAFFIC_ORANGE
    colours[-3] = TRAFFIC_AMBER
    ax.barh(labels, plot["commercial_value_score"], color=colours)
    ax.set_title("Commercial Traffic Value Ranking — Volume + Growth + Stability")
    ax.set_xlabel("X-axis: commercial value score / 100")
    ax.set_ylabel("Y-axis: ranked SCATS site / network node")
    ax.set_xlim(0, 100)
    ax.grid(True, axis="x")
    ax.spines[["top", "right"]].set_visible(False)
    for y, val in enumerate(plot["commercial_value_score"]):
        ax.text(val + 0.7, y, f"{val:.1f}", va="center", fontsize=8, color=TRAFFIC_DARK)
    add_footer(fig, "Commercial score: 55% total volume, 25% growth, 20% stability. For ranking, not official pricing.")
    save(fig, outdir / "06_commercial_value_ranking.png")


def chart_07_weekday_profile(daily: pd.DataFrame, outdir: Path) -> None:
    d = daily.copy()
    d["weekday"] = d["date"].dt.day_name()
    d["weekday_num"] = d["date"].dt.weekday
    profile = d.groupby(["weekday_num", "weekday"], as_index=False).agg(avg_volume=("volume", "mean"))
    profile = profile.sort_values("weekday_num")
    profile.to_csv(outdir / "weekday_profile.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 6))
    colours = [TRAFFIC_BLUE if i < 5 else TRAFFIC_ORANGE for i in profile["weekday_num"]]
    ax.bar(profile["weekday"], profile["avg_volume"], color=colours)
    ax.set_title("Weekday vs Weekend Traffic Fingerprint — Average Daily Volume")
    ax.set_xlabel("X-axis: day of week")
    ax.set_ylabel("Y-axis: average daily vehicle movements")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_big))
    ax.grid(True, axis="y")
    ax.spines[["top", "right"]].set_visible(False)
    for x, val in enumerate(profile["avg_volume"]):
        ax.text(x, val, fmt_big(val), ha="center", va="bottom", fontsize=8)
    add_footer(fig, "Weekday profile method: average total daily network volume by day of week.")
    save(fig, outdir / "07_weekday_weekend_fingerprint.png")


def chart_08_month_seasonality(monthly: pd.DataFrame, outdir: Path) -> None:
    m = monthly.copy()
    if len(m) > 8 and m.iloc[-1]["volume"] < 0.75 * m.iloc[-7:-1]["volume"].median():
        m = m.iloc[:-1].copy()
    m["month_num"] = m["month"].dt.month
    m["month_name"] = m["month"].dt.strftime("%b")
    prof = m.groupby(["month_num", "month_name"], as_index=False).agg(avg_volume=("volume", "mean"))
    prof = prof.sort_values("month_num")
    prof.to_csv(outdir / "month_of_year_profile_from_monthly_totals.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 6))
    vals = prof["avg_volume"].values
    norm = (vals - vals.min()) / (vals.max() - vals.min() if vals.max() > vals.min() else 1)
    colours = []
    for n in norm:
        if n > 0.75:
            colours.append(TRAFFIC_RED)
        elif n > 0.5:
            colours.append(TRAFFIC_ORANGE)
        elif n > 0.25:
            colours.append(TRAFFIC_AMBER)
        else:
            colours.append(TRAFFIC_GREEN)
    ax.bar(prof["month_name"], prof["avg_volume"], color=colours)
    ax.set_title("Monthly Seasonality Fingerprint — Which Months Run Hotter?")
    ax.set_xlabel("X-axis: calendar month")
    ax.set_ylabel("Y-axis: average monthly vehicle movements")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_big))
    ax.grid(True, axis="y")
    ax.spines[["top", "right"]].set_visible(False)
    add_footer(fig, "Seasonality method: average monthly total by calendar month across the archive.")
    save(fig, outdir / "08_monthly_seasonality_fingerprint.png")


def chart_09_lifecycle(site_month: pd.DataFrame, outdir: Path) -> None:
    g = growth_table(site_month)
    stability = site_month.groupby("site_id", as_index=False).agg(
        mean_volume=("volume", "mean"),
        std_volume=("volume", "std"),
        site_name=("site_name", "first"),
    )
    stability["cv"] = stability["std_volume"] / stability["mean_volume"]
    x = g.merge(stability[["site_id", "cv", "mean_volume", "site_name"]], on=["site_id", "site_name"], how="left")

    conditions = [
        x["absolute_growth"] > x["absolute_growth"].quantile(0.80),
        x["absolute_growth"] < x["absolute_growth"].quantile(0.20),
        x["cv"] > x["cv"].quantile(0.80),
    ]
    choices = ["Growth", "Decline", "Volatile"]
    x["lifecycle_type"] = np.select(conditions, choices, default="Stable")
    summary = x.groupby("lifecycle_type", as_index=False).agg(
        sites=("site_id", "count"),
        avg_monthly_growth=("absolute_growth", "mean"),
        avg_cv=("cv", "mean"),
        avg_mean_volume=("mean_volume", "mean"),
    )
    summary.to_csv(outdir / "site_lifecycle_cluster_summary.csv", index=False)
    x.to_csv(outdir / "site_lifecycle_cluster_assignments.csv", index=False)

    order = ["Growth", "Stable", "Volatile", "Decline"]
    summary["lifecycle_type"] = pd.Categorical(summary["lifecycle_type"], categories=order, ordered=True)
    summary = summary.sort_values("lifecycle_type")

    colours = {
        "Growth": TRAFFIC_GREEN,
        "Stable": TRAFFIC_BLUE,
        "Volatile": TRAFFIC_PURPLE,
        "Decline": TRAFFIC_RED,
    }
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(summary["lifecycle_type"].astype(str), summary["sites"], color=[colours.get(v, TRAFFIC_GREY) for v in summary["lifecycle_type"].astype(str)])
    ax.set_title("SCATS Site Lifecycle Clusters — Growth, Stability, Volatility and Decline")
    ax.set_xlabel("X-axis: lifecycle category")
    ax.set_ylabel("Y-axis: number of SCATS sites / network nodes")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_big))
    ax.grid(True, axis="y")
    ax.spines[["top", "right"]].set_visible(False)
    for xidx, val in enumerate(summary["sites"]):
        ax.text(xidx, val, f"{int(val):,}", ha="center", va="bottom", fontsize=9)
    add_footer(fig, "Lifecycle method: sites categorised by growth and volatility percentiles from site-month totals.")
    save(fig, outdir / "09_site_lifecycle_clusters.png")


def chart_10_shock_detection(monthly: pd.DataFrame, outdir: Path) -> None:
    m = monthly.sort_values("month").copy()
    if len(m) > 8 and m.iloc[-1]["volume"] < 0.75 * m.iloc[-7:-1]["volume"].median():
        m = m.iloc[:-1].copy()

    m["rolling_median_12m"] = m["volume"].rolling(12, min_periods=6).median()
    m["rolling_std_12m"] = m["volume"].rolling(12, min_periods=6).std()
    m["z_score"] = (m["volume"] - m["rolling_median_12m"]) / m["rolling_std_12m"]
    m["shock_type"] = np.where(m["z_score"] <= -2.0, "Negative shock", np.where(m["z_score"] >= 2.0, "Positive shock", "Normal"))
    m.to_csv(outdir / "shock_detection_timeline.csv", index=False)

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(m["month"], m["volume"], color=TRAFFIC_BLUE, linewidth=2.1, label="Monthly volume")
    ax.plot(m["month"], m["rolling_median_12m"], color=TRAFFIC_GREY, linewidth=1.5, linestyle="--", label="12-month rolling median")

    neg = m[m["shock_type"] == "Negative shock"]
    pos = m[m["shock_type"] == "Positive shock"]
    ax.scatter(neg["month"], neg["volume"], color=TRAFFIC_RED, s=42, zorder=4, label="Negative shock")
    ax.scatter(pos["month"], pos["volume"], color=TRAFFIC_GREEN, s=42, zorder=4, label="Positive shock")

    ax.set_title("Traffic Shock Detection Timeline — Months That Break the Pattern")
    ax.set_xlabel("X-axis: month")
    ax.set_ylabel("Y-axis: monthly vehicle movements")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_big))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(True, axis="y")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    add_footer(fig, "Shock method: monthly total compared with rolling 12-month median and standard deviation; |z| >= 2 flagged.")
    save(fig, outdir / "10_traffic_shock_detection_timeline.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
    parser.add_argument("--outdir", default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped\high_impact_charts")
    args = parser.parse_args()

    reports = Path(args.reports_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    apply_chart_theme()

    lookup = load_site_lookup(reports / "all_scats_sites_map_data_audit.csv")

    site_month_raw = read_csv_optional(reports / "site_month_totals.csv")
    monthly_raw = read_csv_optional(reports / "monthly_totals.csv")
    daily_raw = read_csv_optional(reports / "daily_totals.csv")
    site_totals_raw = read_csv_optional(reports / "site_totals.csv")

    site_month = normalise_site_month(site_month_raw, lookup) if site_month_raw is not None else None
    monthly = prepare_monthly_from_best(monthly_raw, site_month)
    daily = normalise_daily(daily_raw) if daily_raw is not None else None

    site_totals = None
    if site_totals_raw is not None:
        site_totals = normalise_site_totals(site_totals_raw, site_month, lookup)
    elif site_month is not None:
        site_totals = site_month.groupby("site_id", as_index=False).agg(
            total_volume=("volume", "sum"),
            site_name=("site_name", "first"),
        )

    print("")
    print("Prepared inputs:")
    print(f"  site_month rows : {0 if site_month is None else len(site_month):,}")
    print(f"  monthly rows    : {0 if monthly is None else len(monthly):,}")
    print(f"  daily rows      : {0 if daily is None else len(daily):,}")
    print(f"  site totals rows: {0 if site_totals is None else len(site_totals):,}")
    print("")

    made = []

    if monthly is not None and len(monthly) > 3:
        chart_01_momentum(monthly, outdir); made.append("01")
        chart_08_month_seasonality(monthly, outdir); made.append("08")
        chart_10_shock_detection(monthly, outdir); made.append("10")

    if site_month is not None and len(site_month) > 0:
        chart_02_rising(site_month, outdir); made.append("02")
        chart_03_declining(site_month, outdir); made.append("03")
        chart_04_stability(site_month, outdir); made.append("04")
        chart_09_lifecycle(site_month, outdir); made.append("09")

    if site_totals is not None and len(site_totals) > 0:
        chart_05_concentration(site_totals, outdir); made.append("05")

    if site_month is not None and site_totals is not None and len(site_month) > 0 and len(site_totals) > 0:
        chart_06_commercial_value(site_month, site_totals, outdir); made.append("06")

    if daily is not None and len(daily) > 0:
        chart_07_weekday_profile(daily, outdir); made.append("07")

    print("")
    print(f"Complete. Charts generated: {', '.join(made)}")
    print(f"Output directory: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
