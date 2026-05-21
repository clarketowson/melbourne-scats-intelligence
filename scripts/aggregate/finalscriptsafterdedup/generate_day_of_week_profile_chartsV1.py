import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


CSV_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile.csv")
JSON_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile_final.json")
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_charts")

OUT_DIR.mkdir(parents=True, exist_ok=True)

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DAY_COLOURS = {
    "Monday": "#6baed6",
    "Tuesday": "#4292c6",
    "Wednesday": "#2171b5",
    "Thursday": "#08519c",
    "Friday": "#b00020",
    "Saturday": "#fdae61",
    "Sunday": "#7f7f7f",
}

WEEKDAY_COLOUR = "#16395f"
WEEKEND_COLOUR = "#fdae61"
FRIDAY_COLOUR = "#b00020"
SUNDAY_COLOUR = "#7f7f7f"


def savefig(name: str):
    path = OUT_DIR / name
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def add_title(title, subtitle=None):
    plt.suptitle(title, fontsize=20, fontweight="bold", y=0.98)
    if subtitle:
        plt.title(subtitle, fontsize=11, color="#555555", pad=16)


def fmt_millions(x):
    return f"{x / 1_000_000:.1f}M"


def main():
    df = pd.read_csv(CSV_PATH)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)

    df = df[df["row_type"].eq("day_of_week_month_day_total")].copy()
    df["month_start"] = pd.to_datetime(df["month_start"])
    df["year"] = df["month_start"].dt.year
    df["day_name"] = pd.Categorical(df["day_name"], categories=DAY_ORDER, ordered=True)

    # Weighted totals by day across entire dataset
    day_summary = (
        df.groupby(["iso_dow", "day_name"], observed=True)
        .agg(
            total_volume=("day_total_volume", "sum"),
            days_loaded=("days_loaded", "sum"),
            avg_daily_volume=("day_total_volume", "sum"),
        )
        .reset_index()
    )

    day_summary["avg_daily_volume"] = day_summary["total_volume"] / day_summary["days_loaded"]
    day_summary = day_summary.sort_values("iso_dow")

    friday_avg = float(day_summary.loc[day_summary["day_name"].eq("Friday"), "avg_daily_volume"].iloc[0])
    sunday_avg = float(day_summary.loc[day_summary["day_name"].eq("Sunday"), "avg_daily_volume"].iloc[0])
    diff_pct = (friday_avg / sunday_avg - 1) * 100

    # ------------------------------------------------------------------
    # 1. Weekly heartbeat curve
    # ------------------------------------------------------------------
    plt.figure(figsize=(13, 7))
    x = np.arange(len(day_summary))
    y = day_summary["avg_daily_volume"]

    plt.plot(
        x,
        y,
        linewidth=4,
        marker="o",
        markersize=10,
        color=WEEKDAY_COLOUR,
    )

    for i, row in day_summary.iterrows():
        day = str(row["day_name"])
        plt.scatter(
            row["iso_dow"] - 1,
            row["avg_daily_volume"],
            s=180,
            color=DAY_COLOURS[day],
            zorder=5,
        )
        plt.text(
            row["iso_dow"] - 1,
            row["avg_daily_volume"] + 1_200_000,
            fmt_millions(row["avg_daily_volume"]),
            ha="center",
            fontsize=10,
            fontweight="bold",
        )

    plt.xticks(x, DAY_ORDER, fontsize=11)
    plt.ylabel("Average Daily Network Volume", fontsize=11)
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "Melbourne’s Weekly Traffic Heartbeat",
        "Average daily SCATS traffic volume by day of week, 2014–2026",
    )

    plt.figtext(
        0.5,
        -0.02,
        f"Friday is the strongest day: {fmt_millions(friday_avg)} average daily movements. "
        f"Sunday is the weakest: {fmt_millions(sunday_avg)}.",
        ha="center",
        fontsize=10,
        color="#555555",
    )

    savefig("01_weekly_traffic_heartbeat.png")

    # ------------------------------------------------------------------
    # 2. Day-of-week bar chart
    # ------------------------------------------------------------------
    plt.figure(figsize=(13, 7))
    colours = [DAY_COLOURS[str(d)] for d in day_summary["day_name"]]

    bars = plt.bar(
        day_summary["day_name"].astype(str),
        day_summary["avg_daily_volume"],
        color=colours,
        edgecolor="#222222",
        linewidth=0.6,
    )

    for bar, val in zip(bars, day_summary["avg_daily_volume"]):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            val + 1_000_000,
            fmt_millions(val),
            ha="center",
            fontsize=10,
            fontweight="bold",
        )

    plt.ylabel("Average Daily Network Volume", fontsize=11)
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "Average Daily Traffic by Day of Week",
        "Friday dominates Melbourne’s weekly movement pattern; Sunday is the clear rest state.",
    )

    savefig("02_average_daily_volume_by_day.png")

    # ------------------------------------------------------------------
    # 3. Friday vs Sunday differential
    # ------------------------------------------------------------------
    plt.figure(figsize=(10, 7))

    labels = ["Friday", "Sunday"]
    values = [friday_avg, sunday_avg]
    colours = [FRIDAY_COLOUR, SUNDAY_COLOUR]

    bars = plt.bar(labels, values, color=colours, edgecolor="#222222", linewidth=0.8)

    for bar, val in zip(bars, values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            val + 1_000_000,
            fmt_millions(val),
            ha="center",
            fontsize=13,
            fontweight="bold",
        )

    plt.ylabel("Average Daily Network Volume", fontsize=11)
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "Friday vs Sunday: Melbourne at Full Intensity vs Rest State",
        f"Friday traffic is approximately {diff_pct:.1f}% stronger than Sunday.",
    )

    savefig("03_friday_vs_sunday_differential.png")

    # ------------------------------------------------------------------
    # 4. Relative strength index, Friday = 100
    # ------------------------------------------------------------------
    rel = day_summary.copy()
    rel["friday_index"] = rel["avg_daily_volume"] / friday_avg * 100

    plt.figure(figsize=(13, 7))
    bars = plt.bar(
        rel["day_name"].astype(str),
        rel["friday_index"],
        color=[DAY_COLOURS[str(d)] for d in rel["day_name"]],
        edgecolor="#222222",
        linewidth=0.6,
    )

    for bar, val in zip(bars, rel["friday_index"]):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            val + 1,
            f"{val:.1f}",
            ha="center",
            fontsize=10,
            fontweight="bold",
        )

    plt.axhline(100, color=FRIDAY_COLOUR, linewidth=1.5, linestyle="--")
    plt.ylabel("Traffic Strength Index — Friday = 100", fontsize=11)
    plt.ylim(0, 110)
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "Melbourne Day-of-Week Strength Index",
        "Each day indexed against Friday, the strongest day in the completed dataset.",
    )

    savefig("04_day_strength_index_friday_100.png")

    # ------------------------------------------------------------------
    # 5. Weekday vs weekend split
    # ------------------------------------------------------------------
    weekday_total = day_summary[day_summary["iso_dow"].between(1, 5)]["total_volume"].sum()
    weekend_total = day_summary[day_summary["iso_dow"].between(6, 7)]["total_volume"].sum()

    plt.figure(figsize=(9, 9))
    plt.pie(
        [weekday_total, weekend_total],
        labels=["Weekday", "Weekend"],
        autopct="%1.1f%%",
        startangle=90,
        colors=[WEEKDAY_COLOUR, WEEKEND_COLOUR],
        textprops={"fontsize": 12, "fontweight": "bold"},
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    plt.gca().add_artist(plt.Circle((0, 0), 0.58, color="white"))

    add_title(
        "Weekday vs Weekend Traffic Share",
        "Melbourne’s network remains overwhelmingly weekday-driven.",
    )

    savefig("05_weekday_vs_weekend_share_donut.png")

    # ------------------------------------------------------------------
    # 6. Year x day heatmap
    # ------------------------------------------------------------------
    yearly = (
        df.groupby(["year", "day_name"], observed=True)
        .agg(total_volume=("day_total_volume", "sum"), days_loaded=("days_loaded", "sum"))
        .reset_index()
    )
    yearly["avg_daily_volume"] = yearly["total_volume"] / yearly["days_loaded"]

    pivot = yearly.pivot(index="year", columns="day_name", values="avg_daily_volume")
    pivot = pivot[DAY_ORDER]

    plt.figure(figsize=(12, 8))
    plt.imshow(pivot.values, aspect="auto", cmap="YlOrRd")

    plt.colorbar(label="Average Daily Volume")
    plt.xticks(np.arange(len(DAY_ORDER)), DAY_ORDER, rotation=35, ha="right")
    plt.yticks(np.arange(len(pivot.index)), pivot.index)

    add_title(
        "Day-of-Week Traffic Intensity by Year",
        "A yearly heatmap showing how Melbourne’s weekly rhythm evolved from 2014 to 2026.",
    )

    savefig("06_year_by_day_heatmap.png")

    # ------------------------------------------------------------------
    # 7. Monthly Friday/Sunday gap
    # ------------------------------------------------------------------
    monthly_pivot = df.pivot_table(
        index="month_start",
        columns="day_name",
        values="avg_daily_volume",
        aggfunc="mean",
        observed=True,
    )

    monthly_pivot = monthly_pivot.dropna(subset=["Friday", "Sunday"], how="any")
    monthly_pivot["friday_sunday_gap_pct"] = (
        monthly_pivot["Friday"] / monthly_pivot["Sunday"] - 1
    ) * 100

    plt.figure(figsize=(14, 7))
    plt.plot(
        monthly_pivot.index,
        monthly_pivot["friday_sunday_gap_pct"],
        color=FRIDAY_COLOUR,
        linewidth=2.5,
    )
    plt.axhline(
        diff_pct,
        color="#333333",
        linestyle="--",
        linewidth=1.2,
        label=f"Full-period average: {diff_pct:.1f}%",
    )

    plt.ylabel("Friday premium over Sunday (%)", fontsize=11)
    plt.grid(axis="y", alpha=0.25)
    plt.legend()

    add_title(
        "Friday–Sunday Traffic Gap Over Time",
        "Tracks how much stronger Melbourne’s Friday movement was than Sunday movement each month.",
    )

    savefig("07_friday_sunday_gap_over_time.png")

    # ------------------------------------------------------------------
    # 8. Radar chart
    # ------------------------------------------------------------------
    radar_values = day_summary["avg_daily_volume"].to_numpy()
    radar_values = np.concatenate([radar_values, [radar_values[0]]])

    angles = np.linspace(0, 2 * np.pi, len(DAY_ORDER), endpoint=False)
    angles = np.concatenate([angles, [angles[0]]])

    plt.figure(figsize=(9, 9))
    ax = plt.subplot(111, polar=True)

    ax.plot(angles, radar_values, color=WEEKDAY_COLOUR, linewidth=3)
    ax.fill(angles, radar_values, color=WEEKDAY_COLOUR, alpha=0.18)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(DAY_ORDER, fontsize=11)

    ax.set_yticklabels([])
    ax.grid(alpha=0.3)

    plt.suptitle(
        "Melbourne Weekly Traffic Signature",
        fontsize=20,
        fontweight="bold",
        y=0.98,
    )
    plt.title(
        "Radar view of average daily movement intensity by weekday.",
        fontsize=11,
        color="#555555",
        pad=20,
    )

    savefig("08_weekly_signature_radar.png")

    # ------------------------------------------------------------------
    # 9. Write final summary CSV
    # ------------------------------------------------------------------
    summary_path = OUT_DIR / "day_of_week_final_summary.csv"
    day_summary.to_csv(summary_path, index=False)
    print(f"Saved: {summary_path}")

    print("\nDone.")
    print(f"Best day: {meta.get('best_day_name')} — {fmt_millions(meta.get('best_day_avg_daily_volume'))}")
    print(f"Lowest day: {meta.get('lowest_day_name')} — {fmt_millions(meta.get('lowest_day_avg_daily_volume'))}")
    print(f"Output folder: {OUT_DIR}")


if __name__ == "__main__":
    main()