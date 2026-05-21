#!/usr/bin/env python3
r"""
generate_second_wave_scats_charts_v1_colour.py

Second-wave colour chart generator for the Melbourne SCATS template.

Designed to create the next group of high-impact charts that can be generated NOW
from completed outputs already in the reporting directory.

Primary inputs, if present:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\monthly_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\peak_shares_final.json
    A:\TrafficAnalytics\PROJECTS\reports\deduped\busiest_time_bin_final.json

Outputs:
    charts\25_daily_calendar_heatmap.png
    charts\26_monthly_year_heatmap.png
    charts\27_weekday_weekend_evolution.png
    charts\28_average_traffic_by_weekday.png
    charts\29_day_of_year_seasonality.png
    charts\30_yearly_daily_percentile_bands.png
    charts\31_monthly_yoy_growth_rate.png
    charts\32_top_20_busiest_weeks.png
    charts\33_network_time_of_day_profile.png
    charts\34_peak_window_share_bar.png
    second_wave_scats_charts_summary.json

Notes:
- Uses colour intentionally:
  - Time/growth charts: cool past -> hot present
  - Heatmaps: low volume cool -> high volume hot
  - Growth: green positive, red negative
  - Peak windows: AM/PM highlighted in warm colours
- The script skips optional charts if the required source file is not present.
"""

from __future__ import annotations

import calendar
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
CHART_DIR = REPORT_DIR / "charts"
SUMMARY_JSON = REPORT_DIR / "second_wave_scats_charts_summary.json"

DAILY_CSV = REPORT_DIR / "daily_totals.csv"
MONTHLY_CSV = REPORT_DIR / "monthly_totals.csv"
TIME_BIN_CSV = REPORT_DIR / "time_bin_profile.csv"
PEAK_SHARES_JSON = REPORT_DIR / "peak_shares_final.json"
BUSIEST_TIME_BIN_JSON = REPORT_DIR / "busiest_time_bin_final.json"

TIME_CMAP = plt.cm.plasma
HEAT_CMAP = plt.cm.inferno
COOL_CMAP = plt.cm.Blues
GREEN = "#1a9850"
RED = "#d73027"
AM_COLOUR = "#fdae61"
PM_COLOUR = "#d73027"
NEUTRAL = "#9ecae1"

COVID_START = pd.Timestamp("2020-03-01")
COVID_END = pd.Timestamp("2021-10-31")

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
    if n is None or pd.isna(n):
        return "N/A"
    return f"{int(round(float(n))):,}"


def savefig(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")


def detect_column(df: pd.DataFrame, candidates: list[str], label: str, path: Path) -> str:
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    for candidate in candidates:
        key = candidate.lower().strip()
        if key in lower_map:
            return lower_map[key]
    raise ValueError(
        f"Could not find {label} column in {path}.\n"
        f"Columns found: {list(df.columns)}\n"
        f"Tried: {candidates}"
    )


def shade_covid(ax) -> None:
    ax.axvspan(
        COVID_START,
        COVID_END,
        color="#666666",
        alpha=0.10,
        label="COVID disruption window",
        zorder=0,
    )


def load_daily() -> pd.DataFrame:
    if not DAILY_CSV.exists():
        raise FileNotFoundError(f"Missing daily totals CSV: {DAILY_CSV}")

    df = pd.read_csv(DAILY_CSV)
    print(f"Daily CSV columns: {list(df.columns)}")

    date_col = detect_column(
        df,
        ["date_local", "count_date", "date", "day", "traffic_date"],
        "date",
        DAILY_CSV,
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
        DAILY_CSV,
    )

    df = df.rename(columns={date_col: "date", volume_col: "total_volume"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["total_volume"] = pd.to_numeric(df["total_volume"], errors="coerce")
    df = df.dropna(subset=["date", "total_volume"]).sort_values("date").reset_index(drop=True)

    df["year"] = df["date"].dt.year
    df["month_num"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.month_name().str.slice(stop=3)
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["iso_year"] = df["date"].dt.isocalendar().year.astype(int)
    df["weekday_num"] = df["date"].dt.dayofweek
    df["weekday"] = df["date"].dt.day_name()
    df["is_weekend"] = df["weekday_num"].isin([5, 6])
    df["day_of_year"] = df["date"].dt.dayofyear
    df["volume_millions"] = df["total_volume"] / 1_000_000
    return df


def load_monthly() -> pd.DataFrame | None:
    if not MONTHLY_CSV.exists():
        print(f"Skipping monthly charts: missing {MONTHLY_CSV}")
        return None

    df = pd.read_csv(MONTHLY_CSV)
    print(f"Monthly CSV columns: {list(df.columns)}")

    month_col = detect_column(
        df,
        ["month_label", "month", "year_month"],
        "month",
        MONTHLY_CSV,
    )
    volume_col = detect_column(
        df,
        [
            "month_total_volume",
            "monthly_total_volume",
            "total_volume",
            "total_cleaned_volume",
            "cleaned_volume",
            "volume",
            "month_volume",
        ],
        "monthly volume",
        MONTHLY_CSV,
    )

    df = df.rename(columns={month_col: "month_label", volume_col: "total_volume"})
    df["month_start"] = pd.to_datetime(df["month_label"].astype(str) + "-01", errors="coerce")
    df["total_volume"] = pd.to_numeric(df["total_volume"], errors="coerce")
    df = df.dropna(subset=["month_start", "total_volume"]).sort_values("month_start").reset_index(drop=True)

    df["year"] = df["month_start"].dt.year
    df["month_num"] = df["month_start"].dt.month
    df["volume_billions"] = df["total_volume"] / 1_000_000_000
    df["yoy_growth_pct"] = df["total_volume"].pct_change(12) * 100
    return df


def load_time_bin() -> pd.DataFrame | None:
    candidates = [
        TIME_BIN_CSV,
        REPORT_DIR / "time_bin_profile_final.csv",
        REPORT_DIR / "busiest_time_bin.csv",
        REPORT_DIR / "time_bin_totals.csv",
    ]

    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        print("Skipping time-of-day charts: no time-bin CSV found.")
        return None

    df = pd.read_csv(path)
    print(f"Time-bin CSV: {path}")
    print(f"Time-bin columns: {list(df.columns)}")

    time_col = detect_column(
        df,
        ["time_bin", "time", "hhmm", "interval_time"],
        "time bin",
        path,
    )

    volume_col = None
    for group in [
        ["avg_daily_volume", "average_daily_volume", "mean_daily_volume", "avg_volume"],
        ["total_volume", "total_cleaned_volume", "volume", "time_bin_total_volume"],
    ]:
        try:
            volume_col = detect_column(df, group, "time-bin volume", path)
            break
        except ValueError:
            pass

    if volume_col is None:
        raise ValueError(f"Could not find a usable volume column in {path}: {list(df.columns)}")

    df = df.rename(columns={time_col: "time_bin", volume_col: "volume"})
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["time_bin", "volume"]).copy()

    def parse_time_to_minutes(x):
        s = str(x).strip()
        if len(s) >= 5 and ":" in s:
            h, m = s[:5].split(":")
            return int(h) * 60 + int(m)
        if s.isdigit():
            val = int(s)
            if val < 96:
                return val * 15
        return np.nan

    df["minute_of_day"] = df["time_bin"].apply(parse_time_to_minutes)
    df = df.dropna(subset=["minute_of_day"]).sort_values("minute_of_day").reset_index(drop=True)
    df["hour"] = (df["minute_of_day"] // 60).astype(int)
    return df


def chart_daily_calendar_heatmap(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "25_daily_calendar_heatmap.png"

    years = sorted(df["year"].unique())
    n_years = len(years)
    max_weeks = 54

    fig, axes = plt.subplots(n_years, 1, figsize=(16, max(9, n_years * 0.75)), sharex=True)
    if n_years == 1:
        axes = [axes]

    vmin = df["volume_millions"].quantile(0.02)
    vmax = df["volume_millions"].quantile(0.98)

    for ax, year in zip(axes, years):
        sub = df[df["year"] == year].copy()
        grid = np.full((7, max_weeks), np.nan)

        for _, row in sub.iterrows():
            week = int(row["date"].isocalendar().week)
            weekday = int(row["weekday_num"])
            if 1 <= week <= max_weeks:
                grid[weekday, week - 1] = row["volume_millions"]

        ax.imshow(grid, aspect="auto", cmap=HEAT_CMAP, vmin=vmin, vmax=vmax)
        ax.set_ylabel(str(year), rotation=0, ha="right", va="center", labelpad=25, fontsize=11)
        ax.set_yticks([0, 1, 2, 3, 4, 5, 6])
        ax.set_yticklabels(["M", "T", "W", "T", "F", "S", "S"], fontsize=8)

    axes[-1].set_xlabel("ISO week of year")
    axes[-1].set_xticks(list(range(0, max_weeks, 4)))
    axes[-1].set_xticklabels([str(x + 1) for x in range(0, max_weeks, 4)])

    fig.suptitle("Melbourne SCATS Daily Traffic Calendar Heatmap — Cold Days to Hot Days", y=0.995)
    sm = mpl.cm.ScalarMappable(cmap=HEAT_CMAP, norm=mpl.colors.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, orientation="vertical", fraction=0.012, pad=0.012)
    cbar.set_label("Daily cleaned movements (millions)")

    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {path}")
    return path


def chart_monthly_year_heatmap(monthly: pd.DataFrame) -> Path:
    path = CHART_DIR / "26_monthly_year_heatmap.png"

    pivot = monthly.pivot_table(index="year", columns="month_num", values="volume_billions", aggfunc="sum")
    pivot = pivot.reindex(columns=list(range(1, 13)))

    fig, ax = plt.subplots(figsize=(14, 7))
    im = ax.imshow(pivot.values, aspect="auto", cmap=HEAT_CMAP)

    ax.set_title("Monthly Traffic Heatmap — Year by Month")
    ax.set_xlabel("Month")
    ax.set_ylabel("Year")
    ax.set_xticks(range(12))
    ax.set_xticklabels([calendar.month_abbr[i] for i in range(1, 13)])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(y) for y in pivot.index])

    cbar = fig.colorbar(im, ax=ax, pad=0.012)
    cbar.set_label("Monthly cleaned movements (billions)")

    savefig(path)
    return path


def chart_weekday_weekend_evolution(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "27_weekday_weekend_evolution.png"

    daily_year = (
        df.groupby(["year", "is_weekend"])["volume_millions"]
        .mean()
        .reset_index()
        .pivot(index="year", columns="is_weekend", values="volume_millions")
    )

    fig, ax = plt.subplots(figsize=(14, 7))
    years = daily_year.index.to_numpy()

    if False in daily_year.columns:
        ax.plot(years, daily_year[False], marker="o", linewidth=2.8, color="#f46d43", label="Weekday average")
    if True in daily_year.columns:
        ax.plot(years, daily_year[True], marker="o", linewidth=2.8, color="#3288bd", label="Weekend average")

    ax.axvspan(2020, 2021, color="#666666", alpha=0.10, label="COVID disruption years")
    ax.set_title("Weekday vs Weekend Traffic Evolution")
    ax.set_xlabel("Year")
    ax.set_ylabel("Average daily cleaned movements (millions)")
    ax.grid(True, alpha=0.25)
    ax.legend()

    savefig(path)
    return path


def chart_average_traffic_by_weekday(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "28_average_traffic_by_weekday.png"

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_avg = df.groupby("weekday")["volume_millions"].mean().reindex(order)
    norm = mpl.colors.Normalize(vmin=weekday_avg.min(), vmax=weekday_avg.max())
    colors = HEAT_CMAP(norm(weekday_avg.values))

    plt.figure(figsize=(12, 7))
    plt.bar(weekday_avg.index, weekday_avg.values, color=colors)
    plt.title("Average Melbourne SCATS Traffic by Day of Week")
    plt.xlabel("Day of week")
    plt.ylabel("Average daily cleaned movements (millions)")
    plt.grid(True, axis="y", alpha=0.25)
    plt.xticks(rotation=25)

    savefig(path)
    return path


def chart_day_of_year_seasonality(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "29_day_of_year_seasonality.png"

    season = df.groupby("day_of_year")["volume_millions"].mean().reset_index()
    season["rolling_14d"] = season["volume_millions"].rolling(14, min_periods=3, center=True).mean()

    fig, ax = plt.subplots(figsize=(16, 7))
    ax.plot(season["day_of_year"], season["volume_millions"], color="#fdae61", alpha=0.28, linewidth=1.0, label="Daily average")
    ax.plot(season["day_of_year"], season["rolling_14d"], color="#d73027", linewidth=3.0, label="14-day smoothed seasonality")

    ax.set_title("Melbourne Traffic Seasonality Profile — Average Day of Year")
    ax.set_xlabel("Day of year")
    ax.set_ylabel("Average cleaned movements (millions)")
    ax.grid(True, alpha=0.25)
    ax.legend()

    month_starts = pd.date_range("2024-01-01", "2024-12-01", freq="MS")
    ax.set_xticks([d.dayofyear for d in month_starts])
    ax.set_xticklabels([d.strftime("%b") for d in month_starts])

    savefig(path)
    return path


def chart_yearly_daily_percentile_bands(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "30_yearly_daily_percentile_bands.png"

    stats = (
        df.groupby("year")["volume_millions"]
        .quantile([0.10, 0.25, 0.50, 0.75, 0.90])
        .unstack()
        .rename(columns={0.10: "p10", 0.25: "p25", 0.50: "median", 0.75: "p75", 0.90: "p90"})
    )

    fig, ax = plt.subplots(figsize=(14, 7))
    years = stats.index.to_numpy()

    ax.fill_between(years, stats["p10"], stats["p90"], color="#fdae61", alpha=0.22, label="10th–90th percentile")
    ax.fill_between(years, stats["p25"], stats["p75"], color="#d73027", alpha=0.26, label="25th–75th percentile")
    ax.plot(years, stats["median"], color="#7f0000", linewidth=3, marker="o", label="Median daily volume")

    ax.axvspan(2020, 2021, color="#666666", alpha=0.10, label="COVID disruption years")
    ax.set_title("Yearly Daily Traffic Percentile Bands")
    ax.set_xlabel("Year")
    ax.set_ylabel("Daily cleaned movements (millions)")
    ax.grid(True, alpha=0.25)
    ax.legend()

    savefig(path)
    return path


def chart_monthly_yoy_growth(monthly: pd.DataFrame) -> Path:
    path = CHART_DIR / "31_monthly_yoy_growth_rate.png"

    data = monthly.dropna(subset=["yoy_growth_pct"]).copy()

    fig, ax = plt.subplots(figsize=(16, 7))
    colors = [GREEN if v >= 0 else RED for v in data["yoy_growth_pct"]]
    ax.bar(data["month_start"], data["yoy_growth_pct"], width=25, color=colors, alpha=0.9)

    shade_covid(ax)
    ax.axhline(0, color="#333333", linewidth=1.2)
    ax.set_title("Monthly Year-on-Year Traffic Growth Rate")
    ax.set_xlabel("Month")
    ax.set_ylabel("Year-on-year growth (%)")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper left")

    savefig(path)
    return path


def chart_top_20_busiest_weeks(df: pd.DataFrame) -> Path:
    path = CHART_DIR / "32_top_20_busiest_weeks.png"

    weeks = (
        df.groupby(["iso_year", "week"])["total_volume"]
        .sum()
        .reset_index()
        .sort_values("total_volume", ascending=False)
        .head(20)
        .sort_values("total_volume", ascending=True)
    )
    weeks["label"] = weeks["iso_year"].astype(str) + "-W" + weeks["week"].astype(str).str.zfill(2)
    weeks["volume_billions"] = weeks["total_volume"] / 1_000_000_000

    norm = mpl.colors.Normalize(vmin=weeks["volume_billions"].min(), vmax=weeks["volume_billions"].max())
    colors = HEAT_CMAP(norm(weeks["volume_billions"]))

    plt.figure(figsize=(12, 9))
    plt.barh(weeks["label"], weeks["volume_billions"], color=colors)
    plt.title("Top 20 Busiest Melbourne SCATS Weeks")
    plt.xlabel("Cleaned vehicle movements (billions)")
    plt.ylabel("ISO week")
    plt.grid(True, axis="x", alpha=0.25)

    savefig(path)
    return path


def chart_network_time_of_day_profile(timebin: pd.DataFrame) -> Path:
    path = CHART_DIR / "33_network_time_of_day_profile.png"

    fig, ax = plt.subplots(figsize=(16, 7))

    x = timebin["minute_of_day"] / 60
    y = timebin["volume"]

    # Convert to millions if values look like raw large movement totals.
    ylabel = "Average daily movements"
    if y.max() > 10_000_000:
        y = y / 1_000_000
        ylabel = "Movements (millions)"
    elif y.max() > 10_000:
        y = y / 1_000_000
        ylabel = "Average daily movements (millions)"

    norm = mpl.colors.Normalize(vmin=y.min(), vmax=y.max())
    colors = HEAT_CMAP(norm(y))

    ax.bar(x, y, width=0.22, color=colors, align="center")

    ax.axvspan(7, 10, color=AM_COLOUR, alpha=0.16, label="AM peak 07:00–10:00")
    ax.axvspan(16, 19, color=PM_COLOUR, alpha=0.13, label="PM peak 16:00–19:00")

    ax.set_title("Network Load Curve — Traffic by Time of Day")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(0, 25, 1))
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()

    savefig(path)
    return path


def chart_peak_window_share_bar(timebin: pd.DataFrame | None) -> Path:
    path = CHART_DIR / "34_peak_window_share_bar.png"

    peak_payload = {}
    if PEAK_SHARES_JSON.exists():
        try:
            peak_payload = json.loads(PEAK_SHARES_JSON.read_text(encoding="utf-8"))
        except Exception:
            peak_payload = {}

    labels = []
    values = []

    # Try JSON first.
    for key, label in [
        ("am_peak_share_pct", "AM peak\n07:00–10:00"),
        ("pm_peak_share_pct", "PM peak\n16:00–19:00"),
        ("combined_peak_share_pct", "Combined peak\n6 hours"),
    ]:
        if key in peak_payload and peak_payload[key] is not None:
            labels.append(label)
            values.append(float(peak_payload[key]))

    # Fall back to time-bin profile if JSON fields are unavailable.
    if not values and timebin is not None:
        t = timebin.copy()
        total = t["volume"].sum()
        am = t[(t["minute_of_day"] >= 7 * 60) & (t["minute_of_day"] < 10 * 60)]["volume"].sum()
        pm = t[(t["minute_of_day"] >= 16 * 60) & (t["minute_of_day"] < 19 * 60)]["volume"].sum()
        labels = ["AM peak\n07:00–10:00", "PM peak\n16:00–19:00", "Combined peak\n6 hours"]
        values = [am / total * 100, pm / total * 100, (am + pm) / total * 100]

    if not values:
        raise FileNotFoundError("No peak share JSON and no time-bin data available for peak share chart.")

    colors = [AM_COLOUR, PM_COLOUR, "#7f0000"][:len(values)]

    plt.figure(figsize=(10, 7))
    bars = plt.bar(labels, values, color=colors)
    plt.title("Peak Window Share of Total Traffic")
    plt.ylabel("Share of total cleaned movements (%)")
    plt.grid(True, axis="y", alpha=0.25)

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{value:.2f}%",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )

    savefig(path)
    return path


def main() -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("GENERATE SECOND-WAVE SCATS COLOUR CHARTS V1")
    print("=" * 80)
    print(f"Report dir : {REPORT_DIR}")
    print(f"Chart dir  : {CHART_DIR}")
    print("=" * 80)

    chart_paths: list[Path] = []
    skipped: list[str] = []

    daily = load_daily()
    monthly = load_monthly()
    timebin = load_time_bin()

    jobs = [
        ("25_daily_calendar_heatmap", lambda: chart_daily_calendar_heatmap(daily)),
        ("26_monthly_year_heatmap", lambda: chart_monthly_year_heatmap(monthly) if monthly is not None else None),
        ("27_weekday_weekend_evolution", lambda: chart_weekday_weekend_evolution(daily)),
        ("28_average_traffic_by_weekday", lambda: chart_average_traffic_by_weekday(daily)),
        ("29_day_of_year_seasonality", lambda: chart_day_of_year_seasonality(daily)),
        ("30_yearly_daily_percentile_bands", lambda: chart_yearly_daily_percentile_bands(daily)),
        ("31_monthly_yoy_growth_rate", lambda: chart_monthly_yoy_growth(monthly) if monthly is not None else None),
        ("32_top_20_busiest_weeks", lambda: chart_top_20_busiest_weeks(daily)),
        ("33_network_time_of_day_profile", lambda: chart_network_time_of_day_profile(timebin) if timebin is not None else None),
        ("34_peak_window_share_bar", lambda: chart_peak_window_share_bar(timebin)),
    ]

    for name, fn in jobs:
        try:
            result = fn()
            if result is None:
                skipped.append(name)
            else:
                chart_paths.append(result)
        except Exception as e:
            print(f"Skipped {name}: {e}")
            skipped.append(name)

    summary = {
        "metric_name": "second_wave_scats_charts_colour_v1",
        "charts_created": [str(p) for p in chart_paths],
        "charts_skipped": skipped,
        "daily_rows_used": int(len(daily)),
        "daily_date_range_start": daily["date"].min().date().isoformat(),
        "daily_date_range_end": daily["date"].max().date().isoformat(),
        "daily_total_volume": int(daily["total_volume"].sum()),
        "monthly_source_present": monthly is not None,
        "time_bin_source_present": timebin is not None,
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print("SECOND-WAVE CHART SUMMARY")
    print("=" * 80)
    print(f"Charts created : {len(chart_paths)}")
    print(f"Charts skipped : {len(skipped)}")
    print(f"Daily rows     : {fmt_int(summary['daily_rows_used'])}")
    print(f"Date range     : {summary['daily_date_range_start']} to {summary['daily_date_range_end']}")
    print(f"Total volume   : {fmt_int(summary['daily_total_volume'])}")
    print(f"Summary JSON   : {SUMMARY_JSON}")
    if skipped:
        print("Skipped charts :")
        for item in skipped:
            print(f"  - {item}")
    print("=" * 80)
    print("Done.")


if __name__ == "__main__":
    main()
