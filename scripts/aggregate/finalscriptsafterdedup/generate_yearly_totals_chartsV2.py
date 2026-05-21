# generate_yearly_totals_charts_v2.py

import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


CSV_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_totals.csv")
JSON_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_totals_final.json")

OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\yearly_totals_v2")
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

zero_row_months = meta.get("zero_row_months", [])
zero_row_note = ""
if zero_row_months:
    zero_row_note = f" Note: {', '.join(zero_row_months)} had a missing/zero-row ingest source and is retained transparently."

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
yearly["cumulative_billion"] = yearly["total_volume"].cumsum() / 1_000_000_000

full_years = yearly[~yearly["is_partial_year"]].copy()
full_years["yoy_pct"] = full_years["total_volume"].pct_change() * 100
base_year = int(full_years["year"].min())
base_volume = full_years.loc[full_years["year"] == base_year, "total_volume"].iloc[0]
full_years["index_base_100"] = full_years["total_volume"] / base_volume * 100

best_year = int(meta.get("best_year", full_years.loc[full_years["avg_daily_volume"].idxmax(), "year"]))
lowest_year = int(meta.get("lowest_year", full_years.loc[full_years["avg_daily_volume"].idxmin(), "year"]))


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
COLOUR_NOTE = "#555555"
COLOUR_WARNING = "#b9770e"


def yearly_colours(dataframe):
    colours = []
    for _, row in dataframe.iterrows():
        year = int(row["year"])
        if row.get("is_partial_year", False):
            colours.append(COLOUR_PARTIAL)
        elif year == lowest_year:
            colours.append(COLOUR_COVID)
        elif year == best_year:
            colours.append(COLOUR_RECORD)
        elif year == 2018 and zero_row_months:
            colours.append(COLOUR_WARNING)
        else:
            colours.append(COLOUR_NORMAL)
    return colours


def savefig(name):
    plt.tight_layout()
    plt.savefig(OUT_DIR / name, dpi=220, bbox_inches="tight")
    plt.close()


def add_footer(ax, extra=""):
    footer = (
        f"Source: SCATS cleaned 15-minute observations. "
        f"Range: {meta.get('date_range_start')} to {meta.get('date_range_end')}. "
        f"Completed months: {meta.get('months_completed')}/{meta.get('months_total')}. "
        f"Grey = partial year. Orange = year affected by missing/zero-row ingest month."
        f"{zero_row_note}"
    )
    if extra:
        footer += " " + extra

    ax.text(
        0.0, -0.16,
        footer,
        transform=ax.transAxes,
        fontsize=9,
        color=COLOUR_NOTE,
        va="top",
        wrap=True
    )


def add_value_labels_bars(ax, bars, suffix="", decimals=1):
    for bar in bars:
        h = bar.get_height()
        if pd.isna(h):
            continue
        ax.annotate(
            f"{h:.{decimals}f}{suffix}",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9
        )


def annotate_2018(ax, x_value, y_value):
    if zero_row_months:
        ax.annotate(
            "2018 includes missing/zero-row\nsource month: " + ", ".join(zero_row_months),
            xy=(x_value, y_value),
            xytext=(0, 35),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=COLOUR_WARNING,
            arrowprops=dict(arrowstyle="->", color=COLOUR_WARNING, lw=1.2)
        )


# ------------------------------------------------------------
# 1. Hero: yearly total vehicle movements
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 9))
bars = ax.bar(yearly["year"], yearly["total_billion"], color=yearly_colours(yearly), width=0.78)

ax.set_title("Melbourne Total Vehicle Movements by Year", fontsize=24, weight="bold", pad=18)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Vehicle movements (billions)", fontsize=13)
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

add_value_labels_bars(ax, bars, "B", 1)

row_2018 = yearly[yearly["year"] == 2018]
if not row_2018.empty:
    annotate_2018(ax, 2018, row_2018["total_billion"].iloc[0])

add_footer(ax)
savefig("yearly_total_vehicle_movements_v2.png")


# ------------------------------------------------------------
# 2. Average daily movements
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 9))
bars = ax.bar(yearly["year"], yearly["avg_daily_million"], color=yearly_colours(yearly), width=0.78)

ax.set_title("Average Daily Vehicle Movements by Year", fontsize=24, weight="bold", pad=18)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Average daily movements (millions)", fontsize=13)
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

add_value_labels_bars(ax, bars, "M", 1)

row_2018 = yearly[yearly["year"] == 2018]
if not row_2018.empty:
    annotate_2018(ax, 2018, row_2018["avg_daily_million"].iloc[0])

add_footer(ax)
savefig("yearly_average_daily_movements_v2.png")


# ------------------------------------------------------------
# 3. Year-over-year percentage change, full years only
# ------------------------------------------------------------

plot_df = full_years.dropna(subset=["yoy_pct"]).copy()
colors = [
    COLOUR_GROWTH if v >= 0 else COLOUR_DECLINE
    for v in plot_df["yoy_pct"]
]

fig, ax = plt.subplots(figsize=(16, 9))
bars = ax.bar(plot_df["year"], plot_df["yoy_pct"], color=colors, width=0.72)

ax.axhline(0, color="#333333", linewidth=1.2)
ax.set_title("Year-over-Year Change in Melbourne Vehicle Movements", fontsize=24, weight="bold", pad=18)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Change from previous full year (%)", fontsize=13)
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

for bar in bars:
    h = bar.get_height()
    ax.annotate(
        f"{h:+.1f}%",
        xy=(bar.get_x() + bar.get_width() / 2, h),
        xytext=(0, 6 if h >= 0 else -16),
        textcoords="offset points",
        ha="center",
        va="bottom" if h >= 0 else "top",
        fontsize=9
    )

ax.text(
    0.0, 1.02,
    "Partial 2026 excluded from this chart to avoid misleading year-over-year comparison.",
    transform=ax.transAxes,
    fontsize=11,
    color=COLOUR_NOTE
)

add_footer(ax, "YoY chart uses full calendar years only.")
savefig("yearly_yoy_percentage_change_v2.png")


# ------------------------------------------------------------
# 4. Indexed growth, full years only
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 9))
ax.plot(
    full_years["year"],
    full_years["index_base_100"],
    marker="o",
    linewidth=3,
    color=COLOUR_LINE
)

ax.axhline(100, color="#777777", linestyle="--", linewidth=1.2)
ax.set_title(f"Melbourne Traffic Growth Index ({base_year} = 100)", fontsize=24, weight="bold", pad=18)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Index", fontsize=13)
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

for _, row in full_years.iterrows():
    ax.annotate(
        f"{row['index_base_100']:.1f}",
        (row["year"], row["index_base_100"]),
        textcoords="offset points",
        xytext=(0, 8),
        ha="center",
        fontsize=9
    )

row_2018 = full_years[full_years["year"] == 2018]
if not row_2018.empty and zero_row_months:
    annotate_2018(ax, 2018, row_2018["index_base_100"].iloc[0])

ax.text(
    0.0, 1.02,
    "Partial 2026 excluded so the long-term index compares complete years only.",
    transform=ax.transAxes,
    fontsize=11,
    color=COLOUR_NOTE
)

add_footer(ax, "Index chart uses full calendar years only.")
savefig("yearly_index_growth_full_years_v2.png")


# ------------------------------------------------------------
# 5. Cumulative vehicle movements
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 9))
ax.plot(
    yearly["year"],
    yearly["cumulative_billion"],
    marker="o",
    linewidth=3.4,
    color=COLOUR_CUMULATIVE
)

ax.set_title("Cumulative Melbourne Vehicle Movements", fontsize=24, weight="bold", pad=18)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Cumulative movements (billions)", fontsize=13)
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

for _, row in yearly.iterrows():
    ax.annotate(
        f"{row['cumulative_billion']:.0f}B",
        (row["year"], row["cumulative_billion"]),
        textcoords="offset points",
        xytext=(0, 8),
        ha="center",
        fontsize=9
    )

add_footer(ax, "Cumulative chart includes partial 2026 because it is additive historical volume.")
savefig("yearly_cumulative_vehicle_movements_v2.png")


# ------------------------------------------------------------
# 6. COVID low vs record year
# ------------------------------------------------------------

comparison = yearly[yearly["year"].isin([lowest_year, best_year])].copy()

fig, ax = plt.subplots(figsize=(11, 7))
colors = [
    COLOUR_COVID if int(y) == lowest_year else COLOUR_RECORD
    for y in comparison["year"]
]
bars = ax.bar(comparison["year"].astype(str), comparison["avg_daily_million"], color=colors, width=0.65)

ax.set_title(f"COVID Low vs Record Year: {lowest_year} vs {best_year}", fontsize=22, weight="bold", pad=18)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Average daily movements (millions)", fontsize=13)
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)

add_value_labels_bars(ax, bars, "M", 1)

low_val = comparison.loc[comparison["year"] == lowest_year, "avg_daily_million"].iloc[0]
best_val = comparison.loc[comparison["year"] == best_year, "avg_daily_million"].iloc[0]
diff = best_val - low_val
pct = (diff / low_val) * 100

ax.text(
    0.5, 0.93,
    f"Difference: +{diff:.1f} million average daily movements (+{pct:.1f}%)",
    transform=ax.transAxes,
    ha="center",
    fontsize=13,
    weight="bold"
)

add_footer(ax, "Comparison uses average daily movements for fair year-to-year comparison.")
savefig("yearly_covid_low_vs_record_year_v2.png")


# ------------------------------------------------------------
# 7. Months loaded per year
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 8))
colors = yearly_colours(yearly)
bars = ax.bar(yearly["year"], yearly["months_loaded"], color=colors, width=0.72)

ax.set_title("Months Loaded Per Year", fontsize=24, weight="bold", pad=18)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Months loaded", fontsize=13)
ax.set_ylim(0, 13)
ax.grid(axis="y", alpha=0.35, color=COLOUR_GRID)
ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

add_value_labels_bars(ax, bars, "", 0)

if zero_row_months:
    ax.text(
        0.5, 0.92,
        "2018 has 12 month labels present, but one source month was missing/zero-row: " + ", ".join(zero_row_months),
        transform=ax.transAxes,
        ha="center",
        fontsize=12,
        weight="bold",
        color=COLOUR_WARNING
    )

add_footer(ax)
savefig("yearly_months_loaded_v2.png")


# ------------------------------------------------------------
# 8. Clean web summary CSV
# ------------------------------------------------------------

summary_path = OUT_DIR / "yearly_totals_summary_for_web_v2.csv"
yearly.to_csv(summary_path, index=False)

print("Created yearly totals V2 chart pack:")
for p in sorted(OUT_DIR.glob("*.png")):
    print(" -", p)

print("\nCreated summary CSV:")
print(" -", summary_path)