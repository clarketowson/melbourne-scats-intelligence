# generate_yearly_totals_charts.py

import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


CSV_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_totals.csv")
JSON_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_totals_final.json")
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\yearly_totals")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

df = pd.read_csv(CSV_PATH)
meta = json.loads(JSON_PATH.read_text(encoding="utf-8"))

df["year"] = df["year"].astype(int)
df["month_total_volume"] = pd.to_numeric(df["month_total_volume"], errors="coerce").fillna(0)
df["avg_daily_volume"] = pd.to_numeric(df["avg_daily_volume"], errors="coerce").fillna(0)
df["days_loaded"] = pd.to_numeric(df["days_loaded"], errors="coerce").fillna(0)

yearly = (
    df.groupby("year", as_index=False)
      .agg(
          total_volume=("month_total_volume", "sum"),
          avg_daily_volume=("avg_daily_volume", "mean"),
          days_loaded=("days_loaded", "sum"),
          months_loaded=("month_label", "count"),
      )
)

yearly["is_partial_year"] = yearly["months_loaded"] < 12
yearly["total_billion"] = yearly["total_volume"] / 1_000_000_000
yearly["avg_daily_million"] = yearly["avg_daily_volume"] / 1_000_000
yearly["yoy_pct"] = yearly["total_volume"].pct_change() * 100
yearly["index_2014_100"] = yearly["total_volume"] / yearly.loc[yearly["year"] == yearly["year"].min(), "total_volume"].iloc[0] * 100
yearly["cumulative_billion"] = yearly["total_volume"].cumsum() / 1_000_000_000

best_year = int(meta.get("best_year", yearly.loc[yearly["total_volume"].idxmax(), "year"]))
lowest_year = int(meta.get("lowest_year", yearly.loc[yearly["total_volume"].idxmin(), "year"]))


# ------------------------------------------------------------
# Colour system
# ------------------------------------------------------------

COLOUR_NORMAL = "#2f6f9f"
COLOUR_RECORD = "#1f9d55"
COLOUR_COVID = "#c0392b"
COLOUR_PARTIAL = "#7f8c8d"
COLOUR_GROWTH = "#1f9d55"
COLOUR_DECLINE = "#c0392b"
COLOUR_LINE = "#1f4e79"
COLOUR_CUMULATIVE = "#6c3483"
COLOUR_GRID = "#d9d9d9"

def yearly_colours():
    colours = []
    for _, row in yearly.iterrows():
        if row["is_partial_year"]:
            colours.append(COLOUR_PARTIAL)
        elif int(row["year"]) == lowest_year:
            colours.append(COLOUR_COVID)
        elif int(row["year"]) == best_year:
            colours.append(COLOUR_RECORD)
        else:
            colours.append(COLOUR_NORMAL)
    return colours

def savefig(name):
    plt.tight_layout()
    plt.savefig(OUT_DIR / name, dpi=180, bbox_inches="tight")
    plt.close()

def add_value_labels_bars(ax, bars, suffix="", decimals=1):
    for bar in bars:
        h = bar.get_height()
        if pd.isna(h):
            continue
        ax.annotate(
            f"{h:.{decimals}f}{suffix}",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=0
        )


# ------------------------------------------------------------
# 1. Flagship yearly totals
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(13, 7))
bars = ax.bar(yearly["year"], yearly["total_billion"], color=yearly_colours())

ax.set_title("Melbourne Total Vehicle Movements by Year", fontsize=18, weight="bold")
ax.set_subtitle = None
ax.set_xlabel("Year")
ax.set_ylabel("Vehicle movements (billions)")
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

add_value_labels_bars(ax, bars, "B", 1)

ax.text(
    0.01, -0.15,
    f"Source: SCATS cleaned 15-minute observations. Range: {meta.get('date_range_start')} to {meta.get('date_range_end')}. "
    f"Completed months: {meta.get('months_completed')}/{meta.get('months_total')}. Grey = partial year.",
    transform=ax.transAxes,
    fontsize=9,
    color="#555555"
)

savefig("yearly_total_vehicle_movements.png")


# ------------------------------------------------------------
# 2. Year-over-year percentage change
# ------------------------------------------------------------

plot_df = yearly.dropna(subset=["yoy_pct"]).copy()
colors = [COLOUR_GROWTH if v >= 0 else COLOUR_DECLINE for v in plot_df["yoy_pct"]]

fig, ax = plt.subplots(figsize=(13, 7))
bars = ax.bar(plot_df["year"], plot_df["yoy_pct"], color=colors)

ax.axhline(0, color="#333333", linewidth=1)
ax.set_title("Year-over-Year Change in Melbourne Vehicle Movements", fontsize=18, weight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Change from previous year (%)")
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

for bar in bars:
    h = bar.get_height()
    ax.annotate(
        f"{h:+.1f}%",
        xy=(bar.get_x() + bar.get_width() / 2, h),
        xytext=(0, 5 if h >= 0 else -14),
        textcoords="offset points",
        ha="center",
        va="bottom" if h >= 0 else "top",
        fontsize=8
    )

savefig("yearly_yoy_percentage_change.png")


# ------------------------------------------------------------
# 3. Indexed growth, first year = 100
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(13, 7))
ax.plot(yearly["year"], yearly["index_2014_100"], marker="o", linewidth=2.5, color=COLOUR_LINE)

ax.axhline(100, color="#777777", linestyle="--", linewidth=1)
ax.set_title(f"Melbourne Traffic Growth Index ({yearly['year'].min()} = 100)", fontsize=18, weight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Index")
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

for _, row in yearly.iterrows():
    ax.annotate(
        f"{row['index_2014_100']:.1f}",
        (row["year"], row["index_2014_100"]),
        textcoords="offset points",
        xytext=(0, 7),
        ha="center",
        fontsize=8
    )

savefig("yearly_index_growth_2014_100.png")


# ------------------------------------------------------------
# 4. Average daily movements by year
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(13, 7))
bars = ax.bar(yearly["year"], yearly["avg_daily_million"], color=yearly_colours())

ax.set_title("Average Daily Vehicle Movements by Year", fontsize=18, weight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Average daily movements (millions)")
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

add_value_labels_bars(ax, bars, "M", 1)

savefig("yearly_average_daily_movements.png")


# ------------------------------------------------------------
# 5. Cumulative movements
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(13, 7))
ax.plot(yearly["year"], yearly["cumulative_billion"], marker="o", linewidth=3, color=COLOUR_CUMULATIVE)

ax.set_title("Cumulative Melbourne Vehicle Movements", fontsize=18, weight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Cumulative movements (billions)")
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

for _, row in yearly.iterrows():
    ax.annotate(
        f"{row['cumulative_billion']:.0f}B",
        (row["year"], row["cumulative_billion"]),
        textcoords="offset points",
        xytext=(0, 7),
        ha="center",
        fontsize=8
    )

savefig("yearly_cumulative_vehicle_movements.png")


# ------------------------------------------------------------
# 6. Record year and COVID low comparison
# ------------------------------------------------------------

comparison = yearly[yearly["year"].isin([lowest_year, best_year])].copy()

fig, ax = plt.subplots(figsize=(9, 6))
colors = [COLOUR_COVID if y == lowest_year else COLOUR_RECORD for y in comparison["year"]]
bars = ax.bar(comparison["year"].astype(str), comparison["avg_daily_million"], color=colors)

ax.set_title(f"COVID Low vs Record Year: {lowest_year} vs {best_year}", fontsize=17, weight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Average daily movements (millions)")
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)

add_value_labels_bars(ax, bars, "M", 1)

diff = (
    comparison.loc[comparison["year"] == best_year, "avg_daily_million"].iloc[0]
    - comparison.loc[comparison["year"] == lowest_year, "avg_daily_million"].iloc[0]
)

ax.text(
    0.5, 0.92,
    f"Difference: +{diff:.1f} million average daily movements",
    transform=ax.transAxes,
    ha="center",
    fontsize=11,
    weight="bold"
)

savefig("yearly_covid_low_vs_record_year.png")


# ------------------------------------------------------------
# 7. Months loaded per year
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(13, 6))
colors = [COLOUR_PARTIAL if p else COLOUR_NORMAL for p in yearly["is_partial_year"]]
bars = ax.bar(yearly["year"], yearly["months_loaded"], color=colors)

ax.set_title("Months Loaded Per Year", fontsize=18, weight="bold")
ax.set_xlabel("Year")
ax.set_ylabel("Months loaded")
ax.set_ylim(0, 13)
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

add_value_labels_bars(ax, bars, "", 0)

savefig("yearly_months_loaded.png")


# ------------------------------------------------------------
# Export summary CSV for page/table use
# ------------------------------------------------------------

summary_path = OUT_DIR / "yearly_totals_summary_for_web.csv"
yearly.to_csv(summary_path, index=False)

print("Created yearly totals chart pack:")
for p in sorted(OUT_DIR.glob("*.png")):
    print(" -", p)

print("\nCreated summary CSV:")
print(" -", summary_path)