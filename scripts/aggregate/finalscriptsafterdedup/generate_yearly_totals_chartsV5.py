# generate_yearly_totals_charts_v5.py
#
# V5 fixes:
# - Months Loaded Per Year now shows VALID months loaded, not merely month labels present.
# - Known unavailable/zero-row ingest months such as 2018-12 are subtracted from the display count.
# - 2018 therefore displays 11 valid months, while the unavailable ingest source remains disclosed.
# - Other charts keep the transparent 2018 orange caution colour and partial-year handling.

import json
from pathlib import Path
import textwrap

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


CSV_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_totals.csv")
JSON_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_totals_final.json")

OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\yearly_totals_v5")
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
ingest_note_short = "One monthly ingest source was unavailable (2018-12)."
ingest_note_long = "One monthly ingest source was unavailable (2018-12) and is disclosed transparently."


# ------------------------------------------------------------
# Aggregate yearly data
# ------------------------------------------------------------

yearly = (
    df.groupby("year", as_index=False)
      .agg(
          total_volume=("month_total_volume", "sum"),
          avg_daily_volume=("avg_daily_volume", "mean"),
          days_loaded=("days_loaded", "sum"),
          months_loaded=("month_label", "count"),
      )
)

# IMPORTANT V5 FIX:
# months_loaded counts month labels present in the CSV.
# valid_months_loaded subtracts known unavailable/zero-row ingest months.
yearly["valid_months_loaded"] = yearly["months_loaded"]

for month_label in zero_row_months:
    y = int(str(month_label)[:4])
    yearly.loc[yearly["year"] == y, "valid_months_loaded"] -= 1

yearly["valid_months_loaded"] = yearly["valid_months_loaded"].clip(lower=0)

# Partial year for visual caution: true when valid loaded months are fewer than 12.
# However, 2018 gets its own orange caution colour instead of grey.
yearly["is_partial_year"] = yearly["valid_months_loaded"] < 12

yearly["total_billion"] = yearly["total_volume"] / 1_000_000_000
yearly["avg_daily_million"] = yearly["avg_daily_volume"] / 1_000_000
yearly["cumulative_billion"] = yearly["total_volume"].cumsum() / 1_000_000_000

# For trend charts, exclude the current partial year 2026, but keep disclosed historical years
# such as 2018 in the full-year trend to preserve continuity while flagging it.
current_partial_years = yearly[
    (yearly["valid_months_loaded"] < 12) &
    (~yearly["year"].isin([int(str(m)[:4]) for m in zero_row_months]))
]["year"].tolist()

full_years = yearly[~yearly["year"].isin(current_partial_years)].copy()
full_years["yoy_pct"] = full_years["total_volume"].pct_change() * 100

base_year = int(full_years["year"].min())
base_volume = full_years.loc[full_years["year"] == base_year, "total_volume"].iloc[0]
full_years["index_base_100"] = full_years["total_volume"] / base_volume * 100

best_year = int(meta.get("best_year", full_years.loc[full_years["avg_daily_volume"].idxmax(), "year"]))
lowest_year = int(meta.get("lowest_year", full_years.loc[full_years["avg_daily_volume"].idxmin(), "year"]))


# ------------------------------------------------------------
# Colours
# ------------------------------------------------------------

COLOUR_NORMAL = "#2f6f9f"
COLOUR_RECORD = "#1f9d55"
COLOUR_COVID = "#c0392b"
COLOUR_PARTIAL = "#7f8c8d"
COLOUR_WARNING = "#c47a00"
COLOUR_GROWTH = "#1f9d55"
COLOUR_DECLINE = "#c0392b"
COLOUR_LINE = "#1f4e79"
COLOUR_CUMULATIVE = "#6c3483"
COLOUR_GRID = "#d9d9d9"
COLOUR_NOTE = "#555555"
COLOUR_NOTE_BG = "#fff7e6"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def year_has_unavailable_ingest(year: int) -> bool:
    return any(int(str(m)[:4]) == int(year) for m in zero_row_months)


def chart_colours(dataframe):
    colours = []
    for _, row in dataframe.iterrows():
        year = int(row["year"])

        if year_has_unavailable_ingest(year):
            colours.append(COLOUR_WARNING)
        elif row.get("is_partial_year", False):
            colours.append(COLOUR_PARTIAL)
        elif year == lowest_year:
            colours.append(COLOUR_COVID)
        elif year == best_year:
            colours.append(COLOUR_RECORD)
        else:
            colours.append(COLOUR_NORMAL)

    return colours


def configure_axes(ax):
    ax.grid(axis="y", alpha=0.30, color=COLOUR_GRID)
    ax.spines["top"].set_alpha(0.45)
    ax.spines["right"].set_alpha(0.45)
    ax.tick_params(axis="both", labelsize=11)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))


def title_block(fig, title, subtitle=None):
    fig.suptitle(title, fontsize=25, weight="bold", y=0.972)

    if subtitle:
        fig.text(
            0.5,
            0.925,
            subtitle,
            ha="center",
            va="top",
            fontsize=12,
            color=COLOUR_NOTE
        )


def add_ingest_note_box(fig):
    if not zero_row_months:
        return

    fig.text(
        0.5,
        0.875,
        ingest_note_short,
        ha="center",
        va="center",
        fontsize=10.5,
        color=COLOUR_WARNING,
        bbox=dict(
            boxstyle="round,pad=0.35",
            facecolor=COLOUR_NOTE_BG,
            edgecolor=COLOUR_WARNING,
            linewidth=0.9,
            alpha=0.95
        )
    )


def footer(fig, text):
    wrapped = "\n".join(textwrap.wrap(text, width=170))
    fig.text(
        0.055,
        0.032,
        wrapped,
        ha="left",
        va="bottom",
        fontsize=8.7,
        color=COLOUR_NOTE
    )


def savefig(fig, name):
    fig.subplots_adjust(
        top=0.80,
        bottom=0.16,
        left=0.075,
        right=0.975
    )
    fig.savefig(OUT_DIR / name, dpi=240, bbox_inches="tight")
    plt.close(fig)


def add_value_labels_bars(ax, bars, suffix="", decimals=1, fontsize=9):
    for bar in bars:
        h = bar.get_height()
        if pd.isna(h):
            continue
        ax.annotate(
            f"{h:.{decimals}f}{suffix}",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=fontsize
        )


def standard_footer(extra=""):
    text = (
        f"Source: SCATS cleaned 15-minute observations. "
        f"Range: {meta.get('date_range_start')} to {meta.get('date_range_end')}. "
        f"Completed months: {meta.get('months_completed')}/{meta.get('months_total')}. "
        f"Grey = partial year. Orange = year affected by unavailable monthly ingest source. "
        f"{ingest_note_long}"
    )
    if extra:
        text += " " + extra
    return text


def add_top_padding(ax, values, padding_ratio=0.16):
    ymin = min(0, min(values))
    ymax = max(values)
    span = ymax - ymin
    if span == 0:
        span = max(1, ymax)
    ax.set_ylim(ymin, ymax + span * padding_ratio)


# ------------------------------------------------------------
# 1. Hero: yearly total vehicle movements
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 9))
title_block(
    fig,
    "Melbourne Total Vehicle Movements by Year",
    "Full-year comparison with 2025 highlighted as the record year; 2026 is shown as a partial year."
)
add_ingest_note_box(fig)

bars = ax.bar(yearly["year"], yearly["total_billion"], color=chart_colours(yearly), width=0.76)

ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Vehicle movements (billions)", fontsize=13)
configure_axes(ax)
add_top_padding(ax, yearly["total_billion"], 0.14)
add_value_labels_bars(ax, bars, "B", 1)

footer(fig, standard_footer())
savefig(fig, "yearly_total_vehicle_movements_v5.png")


# ------------------------------------------------------------
# 2. Average daily movements
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 9))
title_block(
    fig,
    "Average Daily Vehicle Movements by Year",
    "Average daily movement levels show the COVID low, recovery phase, and 2025 record year."
)
add_ingest_note_box(fig)

bars = ax.bar(yearly["year"], yearly["avg_daily_million"], color=chart_colours(yearly), width=0.76)

ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Average daily movements (millions)", fontsize=13)
configure_axes(ax)
add_top_padding(ax, yearly["avg_daily_million"], 0.14)
add_value_labels_bars(ax, bars, "M", 1)

footer(fig, standard_footer())
savefig(fig, "yearly_average_daily_movements_v5.png")


# ------------------------------------------------------------
# 3. Year-over-year percentage change
# ------------------------------------------------------------

plot_df = full_years.dropna(subset=["yoy_pct"]).copy()
colors = [COLOUR_GROWTH if v >= 0 else COLOUR_DECLINE for v in plot_df["yoy_pct"]]

fig, ax = plt.subplots(figsize=(16, 9))
title_block(
    fig,
    "Year-over-Year Change in Melbourne Vehicle Movements",
    "Comparable years only; partial 2026 is excluded to avoid a misleading comparison."
)
add_ingest_note_box(fig)

bars = ax.bar(plot_df["year"], plot_df["yoy_pct"], color=colors, width=0.72)

ax.axhline(0, color="#333333", linewidth=1.2)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Change from previous comparable year (%)", fontsize=13)
configure_axes(ax)

ymin = min(plot_df["yoy_pct"].min(), 0)
ymax = max(plot_df["yoy_pct"].max(), 0)
span = ymax - ymin
ax.set_ylim(ymin - span * 0.15, ymax + span * 0.20)

for bar in bars:
    h = bar.get_height()
    ax.annotate(
        f"{h:+.1f}%",
        xy=(bar.get_x() + bar.get_width() / 2, h),
        xytext=(0, 7 if h >= 0 else -17),
        textcoords="offset points",
        ha="center",
        va="bottom" if h >= 0 else "top",
        fontsize=9
    )

footer(fig, standard_footer("YoY chart excludes partial 2026."))
savefig(fig, "yearly_yoy_percentage_change_v5.png")


# ------------------------------------------------------------
# 4. Indexed growth
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 9))
title_block(
    fig,
    f"Melbourne Traffic Growth Index ({base_year} = 100)",
    "Comparable years only; partial 2026 is excluded so the long-term index remains readable."
)
add_ingest_note_box(fig)

ax.plot(
    full_years["year"],
    full_years["index_base_100"],
    marker="o",
    linewidth=3,
    color=COLOUR_LINE
)

ax.axhline(100, color="#777777", linestyle="--", linewidth=1.2)
ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Index", fontsize=13)
configure_axes(ax)

ymin = full_years["index_base_100"].min()
ymax = full_years["index_base_100"].max()
span = ymax - ymin
ax.set_ylim(ymin - span * 0.18, ymax + span * 0.18)

for _, row in full_years.iterrows():
    ax.annotate(
        f"{row['index_base_100']:.1f}",
        (row["year"], row["index_base_100"]),
        textcoords="offset points",
        xytext=(0, 9),
        ha="center",
        fontsize=9
    )

footer(fig, standard_footer("Index chart excludes partial 2026."))
savefig(fig, "yearly_index_growth_comparable_years_v5.png")


# ------------------------------------------------------------
# 5. Cumulative vehicle movements
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 9))
title_block(
    fig,
    "Cumulative Melbourne Vehicle Movements",
    "Running total of cleaned vehicle movements across the full available dataset."
)
add_ingest_note_box(fig)

ax.plot(
    yearly["year"],
    yearly["cumulative_billion"],
    marker="o",
    linewidth=3.4,
    color=COLOUR_CUMULATIVE
)

ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Cumulative movements (billions)", fontsize=13)
configure_axes(ax)
add_top_padding(ax, yearly["cumulative_billion"], 0.14)

for _, row in yearly.iterrows():
    ax.annotate(
        f"{row['cumulative_billion']:.0f}B",
        (row["year"], row["cumulative_billion"]),
        textcoords="offset points",
        xytext=(0, 9),
        ha="center",
        fontsize=9
    )

footer(fig, standard_footer("Cumulative chart includes partial 2026 because it is additive historical volume."))
savefig(fig, "yearly_cumulative_vehicle_movements_v5.png")


# ------------------------------------------------------------
# 6. COVID low vs record year
# ------------------------------------------------------------

comparison = yearly[yearly["year"].isin([lowest_year, best_year])].copy()

fig, ax = plt.subplots(figsize=(12, 8))
title_block(
    fig,
    f"COVID Low vs Record Year: {lowest_year} vs {best_year}",
    "Average daily movements show the scale of Melbourne’s recovery from the COVID-period low."
)

colors = [
    COLOUR_COVID if int(y) == lowest_year else COLOUR_RECORD
    for y in comparison["year"]
]
bars = ax.bar(comparison["year"].astype(str), comparison["avg_daily_million"], color=colors, width=0.62)

ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Average daily movements (millions)", fontsize=13)
configure_axes(ax)
add_top_padding(ax, comparison["avg_daily_million"], 0.22)
add_value_labels_bars(ax, bars, "M", 1, fontsize=10)

low_val = comparison.loc[comparison["year"] == lowest_year, "avg_daily_million"].iloc[0]
best_val = comparison.loc[comparison["year"] == best_year, "avg_daily_million"].iloc[0]
diff = best_val - low_val
pct = (diff / low_val) * 100

ax.text(
    0.5,
    0.92,
    f"+{diff:.1f} million average daily movements (+{pct:.1f}%)",
    transform=ax.transAxes,
    ha="center",
    fontsize=14,
    weight="bold",
    bbox=dict(
        boxstyle="round,pad=0.25",
        facecolor="white",
        edgecolor="none",
        alpha=0.82
    )
)

footer(fig, standard_footer("Comparison uses average daily movements for fair year-to-year comparison."))
savefig(fig, "yearly_covid_low_vs_record_year_v5.png")


# ------------------------------------------------------------
# 7. Valid months loaded per year
# ------------------------------------------------------------

fig, ax = plt.subplots(figsize=(16, 8.5))
title_block(
    fig,
    "Valid Months Loaded Per Year",
    "Coverage check showing valid loaded months, partial 2026, and the disclosed 2018 unavailable ingest source."
)
add_ingest_note_box(fig)

bars = ax.bar(yearly["year"], yearly["valid_months_loaded"], color=chart_colours(yearly), width=0.72)

ax.set_xlabel("Year", fontsize=13)
ax.set_ylabel("Valid months loaded", fontsize=13)
ax.set_ylim(0, 13.4)
configure_axes(ax)
add_value_labels_bars(ax, bars, "", 0)

footer(
    fig,
    standard_footer(
        "This chart shows valid months loaded. 2018 displays 11 valid months because the 2018-12 ingest source was unavailable."
    )
)
savefig(fig, "yearly_valid_months_loaded_v5.png")


# ------------------------------------------------------------
# 8. Clean web summary CSV
# ------------------------------------------------------------

summary_path = OUT_DIR / "yearly_totals_summary_for_web_v5.csv"
yearly.to_csv(summary_path, index=False)

print("Created yearly totals V5 chart pack:")
for p in sorted(OUT_DIR.glob("*.png")):
    print(" -", p)

print("\nCreated summary CSV:")
print(" -", summary_path)

print("\nKnown unavailable/zero-row ingest months:")
print(" - " + ", ".join(zero_row_months) if zero_row_months else " - None")
