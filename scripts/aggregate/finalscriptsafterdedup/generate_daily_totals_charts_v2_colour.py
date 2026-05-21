#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
import numpy as np


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
DAILY_CSV = REPORT_DIR / "daily_totals.csv"
DAILY_FINAL_JSON = REPORT_DIR / "daily_totals_final.json"
CHART_DIR = REPORT_DIR / "charts"
SUMMARY_JSON = REPORT_DIR / "daily_totals_charts_summary.json"

# 🌈 Global color scheme
cmap = plt.cm.plasma


def savefig(path: Path):
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")


def load_daily_totals():

    df = pd.read_csv(DAILY_CSV)

    date_col = None
    for c in ["date_local", "count_date", "date"]:
        if c in df.columns:
            date_col = c
            break

    volume_col = None
    for c in ["total_volume", "daily_total_volume"]:
        if c in df.columns:
            volume_col = c
            break

    df = df.rename(columns={
        date_col: "date",
        volume_col: "total_volume"
    })

    df["date"] = pd.to_datetime(df["date"])
    df["total_volume"] = pd.to_numeric(df["total_volume"])

    df = df.sort_values("date").reset_index(drop=True)

    df["year"] = df["date"].dt.year
    df["rolling_7d"] = df["total_volume"].rolling(7, min_periods=3).mean()
    df["rolling_30d"] = df["total_volume"].rolling(30, min_periods=10).mean()
    df["daily_change"] = df["total_volume"].diff()
    df["daily_change_abs"] = df["daily_change"].abs()

    return df


# --------------------------------------------------
# Chart 18 — Gradient Daily Line
# --------------------------------------------------

def chart_daily_line(df):

    path = CHART_DIR / "18_daily_total_traffic_line.png"

    plt.figure(figsize=(16, 7))

    norm = mpl.colors.Normalize(
        vmin=0,
        vmax=len(df)
    )

    for i in range(len(df) - 1):
        plt.plot(
            df["date"].iloc[i:i+2],
            df["total_volume"].iloc[i:i+2] / 1_000_000,
            color=cmap(norm(i)),
            linewidth=1.5
        )

    plt.title("Melbourne SCATS Daily Total Traffic (Heat Progression)")
    plt.xlabel("Date")
    plt.ylabel("Vehicle movements per day (millions)")
    plt.grid(True, alpha=0.3)

    savefig(path)


# --------------------------------------------------
# Chart 19 — 7 Day Rolling
# --------------------------------------------------

def chart_7day_rolling(df):

    path = CHART_DIR / "19_daily_total_traffic_7day_rolling.png"

    plt.figure(figsize=(16, 7))

    plt.plot(
        df["date"],
        df["rolling_7d"] / 1_000_000,
        linewidth=2.5,
        color="orange"
    )

    plt.fill_between(
        df["date"],
        df["rolling_7d"] / 1_000_000,
        color="orange",
        alpha=0.15
    )

    plt.title("7-Day Rolling Average Traffic")
    plt.xlabel("Date")
    plt.ylabel("Vehicle movements per day (millions)")
    plt.grid(True, alpha=0.3)

    savefig(path)


# --------------------------------------------------
# Chart 20 — 30 Day Rolling
# --------------------------------------------------

def chart_30day_rolling(df):

    path = CHART_DIR / "20_daily_total_traffic_30day_rolling.png"

    plt.figure(figsize=(16, 7))

    plt.plot(
        df["date"],
        df["rolling_30d"] / 1_000_000,
        linewidth=3,
        color="red"
    )

    plt.fill_between(
        df["date"],
        df["rolling_30d"] / 1_000_000,
        color="red",
        alpha=0.12
    )

    plt.title("30-Day Rolling Average Traffic")
    plt.xlabel("Date")
    plt.ylabel("Vehicle movements per day (millions)")
    plt.grid(True, alpha=0.3)

    savefig(path)


# --------------------------------------------------
# Chart 21 — Top 50 Busiest
# --------------------------------------------------

def chart_top_50_days(df):

    path = CHART_DIR / "21_top_50_busiest_days.png"

    top = df.nlargest(50, "total_volume")

    colors = cmap(
        np.linspace(0.5, 1, len(top))
    )

    plt.figure(figsize=(12, 14))

    plt.barh(
        top["date"].dt.strftime("%Y-%m-%d"),
        top["total_volume"] / 1_000_000,
        color=colors
    )

    plt.title("Top 50 Busiest Melbourne SCATS Days")
    plt.xlabel("Vehicle movements (millions)")

    savefig(path)


# --------------------------------------------------
# Chart 22 — Bottom 50 Quietest
# --------------------------------------------------

def chart_bottom_50_days(df):

    path = CHART_DIR / "22_bottom_50_quietest_days.png"

    bottom = df.nsmallest(50, "total_volume")

    colors = plt.cm.Blues(
        np.linspace(0.3, 1, len(bottom))
    )

    plt.figure(figsize=(12, 14))

    plt.barh(
        bottom["date"].dt.strftime("%Y-%m-%d"),
        bottom["total_volume"] / 1_000_000,
        color=colors
    )

    plt.title("Bottom 50 Quietest Melbourne SCATS Days")
    plt.xlabel("Vehicle movements (millions)")

    savefig(path)


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    CHART_DIR.mkdir(parents=True, exist_ok=True)

    df = load_daily_totals()

    chart_daily_line(df)
    chart_7day_rolling(df)
    chart_30day_rolling(df)
    chart_top_50_days(df)
    chart_bottom_50_days(df)

    print("All colourful charts created.")


if __name__ == "__main__":
    main()