from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


CSV_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile.csv")
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_charts_v2")
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

BLUE = "#16395f"
RED = "#b00020"
ORANGE = "#fdae61"
GREY = "#7f7f7f"


def fmt_m(x):
    return f"{x / 1_000_000:.1f}M"


def savefig(name):
    path = OUT_DIR / name
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def add_title(title, subtitle=None):
    plt.suptitle(title, fontsize=22, fontweight="bold", y=0.98)
    if subtitle:
        plt.title(subtitle, fontsize=12, color="#555555", pad=18)


def main():
    df = pd.read_csv(CSV_PATH)
    df = df[df["row_type"].eq("day_of_week_month_day_total")].copy()

    df["month_start"] = pd.to_datetime(df["month_start"])
    df["year"] = df["month_start"].dt.year
    df["month"] = df["month_start"].dt.month
    df["day_name"] = pd.Categorical(df["day_name"], categories=DAY_ORDER, ordered=True)

    day_summary = (
        df.groupby(["iso_dow", "day_name"], observed=True)
        .agg(
            total_volume=("day_total_volume", "sum"),
            days_loaded=("days_loaded", "sum"),
        )
        .reset_index()
        .sort_values("iso_dow")
    )
    day_summary["avg_daily_volume"] = day_summary["total_volume"] / day_summary["days_loaded"]

    friday_avg = day_summary.loc[day_summary["day_name"].eq("Friday"), "avg_daily_volume"].iloc[0]
    monday_avg = day_summary.loc[day_summary["day_name"].eq("Monday"), "avg_daily_volume"].iloc[0]
    sunday_avg = day_summary.loc[day_summary["day_name"].eq("Sunday"), "avg_daily_volume"].iloc[0]

    # ------------------------------------------------------------
    # 1. Monday-to-Friday build-up chart
    # ------------------------------------------------------------
    workweek = day_summary[day_summary["day_name"].isin(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])].copy()
    workweek["increase_from_monday_pct"] = (workweek["avg_daily_volume"] / monday_avg - 1) * 100

    plt.figure(figsize=(13, 7))
    bars = plt.bar(
        workweek["day_name"].astype(str),
        workweek["increase_from_monday_pct"],
        color=[DAY_COLOURS[str(d)] for d in workweek["day_name"]],
        edgecolor="#222222",
        linewidth=0.6,
    )

    for bar, val in zip(bars, workweek["increase_from_monday_pct"]):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.4,
            f"+{val:.1f}%",
            ha="center",
            fontsize=11,
            fontweight="bold",
        )

    plt.axhline(0, color="#333333", linewidth=1)
    plt.ylabel("Increase vs Monday (%)")
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "Melbourne’s Workweek Build-Up",
        "Traffic steadily intensifies from Monday through to the Friday peak.",
    )

    savefig("09_workweek_build_up_vs_monday.png")

    # ------------------------------------------------------------
    # 2. Weekend collapse chart
    # ------------------------------------------------------------
    weekend = day_summary[day_summary["day_name"].isin(["Friday", "Saturday", "Sunday"])].copy()
    weekend["drop_from_friday_pct"] = (1 - weekend["avg_daily_volume"] / friday_avg) * 100

    plt.figure(figsize=(11, 7))
    bars = plt.bar(
        weekend["day_name"].astype(str),
        weekend["drop_from_friday_pct"],
        color=[DAY_COLOURS[str(d)] for d in weekend["day_name"]],
        edgecolor="#222222",
        linewidth=0.6,
    )

    for bar, val in zip(bars, weekend["drop_from_friday_pct"]):
        label = "Peak" if abs(val) < 0.01 else f"-{val:.1f}%"
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.8,
            label,
            ha="center",
            fontsize=12,
            fontweight="bold",
        )

    plt.ylabel("Drop from Friday (%)")
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "The Weekend Traffic Collapse",
        "Melbourne falls sharply from Friday intensity into Saturday and Sunday rest-state movement.",
    )

    savefig("10_weekend_collapse_from_friday.png")

    # ------------------------------------------------------------
    # 3. Pre-COVID vs COVID vs Post-COVID weekday profile
    # ------------------------------------------------------------
    def period_for_year(y):
        if y <= 2019:
            return "Pre-COVID\n2014–2019"
        if y in [2020, 2021]:
            return "COVID Shock\n2020–2021"
        return "Recovery / New Normal\n2022–2026"

    df["period"] = df["year"].apply(period_for_year)

    period = (
        df.groupby(["period", "iso_dow", "day_name"], observed=True)
        .agg(total_volume=("day_total_volume", "sum"), days_loaded=("days_loaded", "sum"))
        .reset_index()
    )
    period["avg_daily_volume"] = period["total_volume"] / period["days_loaded"]

    plt.figure(figsize=(14, 8))

    period_order = ["Pre-COVID\n2014–2019", "COVID Shock\n2020–2021", "Recovery / New Normal\n2022–2026"]
    colours = ["#16395f", "#b00020", "#fdae61"]

    for p, c in zip(period_order, colours):
        sub = period[period["period"].eq(p)].sort_values("iso_dow")
        plt.plot(
            sub["day_name"].astype(str),
            sub["avg_daily_volume"],
            marker="o",
            linewidth=3,
            markersize=8,
            label=p,
            color=c,
        )

    plt.ylabel("Average Daily Network Volume")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()

    add_title(
        "Day-of-Week Behaviour Before, During and After COVID",
        "Compares Melbourne’s weekly traffic rhythm across three major behavioural eras.",
    )

    savefig("11_pre_covid_covid_recovery_weekly_profiles.png")

    # ------------------------------------------------------------
    # 4. Indexed version of pre/COVID/recovery
    # ------------------------------------------------------------
    indexed = period.copy()
    indexed["period_friday"] = indexed.groupby("period")["avg_daily_volume"].transform(
        lambda s: float(s[indexed.loc[s.index, "day_name"].astype(str).eq("Friday")].iloc[0])
    )
    indexed["friday_index"] = indexed["avg_daily_volume"] / indexed["period_friday"] * 100

    plt.figure(figsize=(14, 8))

    for p, c in zip(period_order, colours):
        sub = indexed[indexed["period"].eq(p)].sort_values("iso_dow")
        plt.plot(
            sub["day_name"].astype(str),
            sub["friday_index"],
            marker="o",
            linewidth=3,
            markersize=8,
            label=p,
            color=c,
        )

    plt.axhline(100, color="#333333", linestyle="--", linewidth=1)
    plt.ylabel("Index — Friday = 100 within each period")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()

    add_title(
        "Weekly Shape Index Across Melbourne Traffic Eras",
        "Normalises each era against its own Friday peak to expose behavioural shape changes.",
    )

    savefig("12_weekly_shape_index_by_era.png")

    # ------------------------------------------------------------
    # 5. Yearly Friday dominance trend
    # ------------------------------------------------------------
    yearly = (
        df.groupby(["year", "day_name"], observed=True)
        .agg(total_volume=("day_total_volume", "sum"), days_loaded=("days_loaded", "sum"))
        .reset_index()
    )
    yearly["avg_daily_volume"] = yearly["total_volume"] / yearly["days_loaded"]

    yp = yearly.pivot(index="year", columns="day_name", values="avg_daily_volume")
    yp = yp[DAY_ORDER]
    yp["Friday_vs_Monday_pct"] = (yp["Friday"] / yp["Monday"] - 1) * 100
    yp["Friday_vs_Sunday_pct"] = (yp["Friday"] / yp["Sunday"] - 1) * 100

    plt.figure(figsize=(14, 7))
    plt.plot(yp.index, yp["Friday_vs_Monday_pct"], marker="o", linewidth=3, color=BLUE, label="Friday vs Monday")
    plt.plot(yp.index, yp["Friday_vs_Sunday_pct"], marker="o", linewidth=3, color=RED, label="Friday vs Sunday")

    plt.ylabel("Friday Premium (%)")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()

    add_title(
        "Friday Dominance Over Time",
        "Tracks how much stronger Friday traffic was compared with Monday and Sunday each year.",
    )

    savefig("13_friday_dominance_by_year.png")

    # ------------------------------------------------------------
    # 6. Monday weakness over time
    # ------------------------------------------------------------
    yp["Monday_vs_weekday_avg_pct"] = (
        yp["Monday"] / yp[["Tuesday", "Wednesday", "Thursday", "Friday"]].mean(axis=1) - 1
    ) * 100

    plt.figure(figsize=(14, 7))
    plt.plot(
        yp.index,
        yp["Monday_vs_weekday_avg_pct"],
        marker="o",
        linewidth=3,
        color=BLUE,
    )

    plt.axhline(0, color="#333333", linestyle="--", linewidth=1)
    plt.ylabel("Monday vs Tue–Fri Average (%)")
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "Monday Weakness Over Time",
        "Shows whether Monday traffic is structurally weaker than the rest of the working week.",
    )

    savefig("14_monday_weakness_over_time.png")

    # ------------------------------------------------------------
    # 7. Annual weekday/weekend share trend
    # ------------------------------------------------------------
    yearly_share = yearly.copy()
    yearly_share["group"] = np.where(yearly_share["day_name"].astype(str).isin(["Saturday", "Sunday"]), "Weekend", "Weekday")

    share = (
        yearly_share.groupby(["year", "group"], observed=True)
        .agg(total_volume=("total_volume", "sum"))
        .reset_index()
    )
    share["year_total"] = share.groupby("year")["total_volume"].transform("sum")
    share["share_pct"] = share["total_volume"] / share["year_total"] * 100

    sp = share.pivot(index="year", columns="group", values="share_pct")

    plt.figure(figsize=(14, 7))
    plt.plot(sp.index, sp["Weekday"], marker="o", linewidth=3, color=BLUE, label="Weekday")
    plt.plot(sp.index, sp["Weekend"], marker="o", linewidth=3, color=ORANGE, label="Weekend")

    plt.ylabel("Share of Annual Traffic (%)")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()

    add_title(
        "Weekday vs Weekend Share Over Time",
        "Tracks whether Melbourne’s traffic has become more weekday-driven or weekend-driven.",
    )

    savefig("15_weekday_weekend_share_by_year.png")

    # ------------------------------------------------------------
    # 8. Month x day seasonal heatmap
    # ------------------------------------------------------------
    monthly = (
        df.groupby(["month", "day_name"], observed=True)
        .agg(total_volume=("day_total_volume", "sum"), days_loaded=("days_loaded", "sum"))
        .reset_index()
    )
    monthly["avg_daily_volume"] = monthly["total_volume"] / monthly["days_loaded"]

    mp = monthly.pivot(index="month", columns="day_name", values="avg_daily_volume")
    mp = mp[DAY_ORDER]

    plt.figure(figsize=(12, 8))
    plt.imshow(mp.values, aspect="auto", cmap="YlOrRd")
    plt.colorbar(label="Average Daily Volume")

    plt.xticks(np.arange(len(DAY_ORDER)), DAY_ORDER, rotation=35, ha="right")
    plt.yticks(
        np.arange(12),
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    )

    add_title(
        "Seasonal Day-of-Week Traffic Heatmap",
        "Shows how weekday behaviour changes across the calendar year.",
    )

    savefig("16_month_by_day_heatmap.png")

    # ------------------------------------------------------------
    # 9. Weekly cumulative contribution curve
    # ------------------------------------------------------------
    cumulative = day_summary.copy()
    cumulative["share_pct"] = cumulative["total_volume"] / cumulative["total_volume"].sum() * 100
    cumulative["cumulative_share_pct"] = cumulative["share_pct"].cumsum()

    plt.figure(figsize=(13, 7))
    plt.plot(
        cumulative["day_name"].astype(str),
        cumulative["cumulative_share_pct"],
        marker="o",
        linewidth=4,
        markersize=9,
        color=BLUE,
    )

    for x, y in zip(cumulative["day_name"].astype(str), cumulative["cumulative_share_pct"]):
        plt.text(x, y + 1.2, f"{y:.1f}%", ha="center", fontweight="bold")

    plt.ylim(0, 105)
    plt.ylabel("Cumulative Weekly Traffic Share (%)")
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "Cumulative Weekly Traffic Contribution",
        "Shows how much of Melbourne’s weekly movement has occurred by each day of the week.",
    )

    savefig("17_cumulative_weekly_contribution.png")

    # ------------------------------------------------------------
    # 10. Day-of-week volatility by month
    # ------------------------------------------------------------
    volatility = (
        df.groupby(["day_name"], observed=True)
        .agg(
            mean_volume=("avg_daily_volume", "mean"),
            std_volume=("avg_daily_volume", "std"),
        )
        .reset_index()
    )
    volatility["coefficient_of_variation_pct"] = volatility["std_volume"] / volatility["mean_volume"] * 100
    volatility["day_name"] = pd.Categorical(volatility["day_name"], categories=DAY_ORDER, ordered=True)
    volatility = volatility.sort_values("day_name")

    plt.figure(figsize=(13, 7))
    bars = plt.bar(
        volatility["day_name"].astype(str),
        volatility["coefficient_of_variation_pct"],
        color=[DAY_COLOURS[str(d)] for d in volatility["day_name"]],
        edgecolor="#222222",
        linewidth=0.6,
    )

    for bar, val in zip(bars, volatility["coefficient_of_variation_pct"]):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.25,
            f"{val:.1f}%",
            ha="center",
            fontsize=10,
            fontweight="bold",
        )

    plt.ylabel("Monthly Volatility — Coefficient of Variation (%)")
    plt.grid(axis="y", alpha=0.25)

    add_title(
        "Which Days Are Most Volatile?",
        "Measures how much each weekday fluctuates month-to-month across the full SCATS dataset.",
    )

    savefig("18_day_of_week_volatility.png")

    # Save helper tables
    day_summary.to_csv(OUT_DIR / "v2_day_summary.csv", index=False)
    yp.reset_index().to_csv(OUT_DIR / "v2_yearly_day_metrics.csv", index=False)

    print("\nDone.")
    print(f"Output folder: {OUT_DIR}")


if __name__ == "__main__":
    main()