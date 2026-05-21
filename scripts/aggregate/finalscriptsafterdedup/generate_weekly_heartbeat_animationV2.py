# ==========================================================================================
# MELBOURNE WEEKLY TRAFFIC HEARTBEAT CINEMATIC ANIMATION V2
# ==========================================================================================
#
# Creates a cinematic MP4 animation from the completed day_of_week_profile.csv.
#
# Fix in V2:
#   - Uses the real day_of_week_profile.csv structure:
#       row_type
#       iso_dow
#       day_name
#       day_total_volume
#       days_loaded
#       avg_daily_volume
#   - Aggregates monthly day-of-week rows into one final Monday-Sunday profile.
#
# Output:
#   A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\melbourne_weekly_heartbeat.mp4
#
# ==========================================================================================

import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter


# ==========================================================================================
# CONFIG
# ==========================================================================================

CSV_FILE = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile.csv")

OUTPUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\animations")
OUTPUT_MP4 = OUTPUT_DIR / "melbourne_weekly_heartbeat.mp4"

FPS = 30
DURATION_SECONDS = 24
TOTAL_FRAMES = FPS * DURATION_SECONDS

WIDTH = 16
HEIGHT = 9

WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

DAY_COLOURS = {
    "Monday": "#4da3ff",
    "Tuesday": "#3b8eea",
    "Wednesday": "#2674c7",
    "Thursday": "#165a9e",
    "Friday": "#ff0033",
    "Saturday": "#ffb347",
    "Sunday": "#888888",
}


# ==========================================================================================
# HELPERS
# ==========================================================================================

def fmt_millions(value: float) -> str:
    return f"{value / 1_000_000:.1f}M"


def smoothstep(t: np.ndarray) -> np.ndarray:
    """Smooth easing from 0 to 1."""
    return t * t * (3 - 2 * t)


# ==========================================================================================
# LOAD AND AGGREGATE DATA
# ==========================================================================================

if not CSV_FILE.exists():
    raise FileNotFoundError(f"CSV not found: {CSV_FILE}")

df = pd.read_csv(CSV_FILE)

required_cols = {
    "row_type",
    "iso_dow",
    "day_name",
    "day_total_volume",
    "days_loaded",
}

missing = required_cols - set(df.columns)
if missing:
    raise ValueError(
        "The CSV does not contain the expected columns. "
        f"Missing: {sorted(missing)}\n"
        f"Available columns: {list(df.columns)}"
    )

# Keep the real monthly day-of-week rows.
df = df[df["row_type"].eq("day_of_week_month_day_total")].copy()

if df.empty:
    raise ValueError("No rows found with row_type == 'day_of_week_month_day_total'.")

summary = (
    df.groupby(["iso_dow", "day_name"], observed=True)
    .agg(
        total_volume=("day_total_volume", "sum"),
        days_loaded=("days_loaded", "sum"),
    )
    .reset_index()
)

summary["avg_daily_volume"] = summary["total_volume"] / summary["days_loaded"]

summary["day_name"] = pd.Categorical(
    summary["day_name"],
    categories=WEEKDAY_ORDER,
    ordered=True,
)

summary = summary.sort_values("day_name").reset_index(drop=True)

days = summary["day_name"].astype(str).tolist()
values = summary["avg_daily_volume"].astype(float).to_numpy()

if days != WEEKDAY_ORDER:
    raise ValueError(f"Unexpected day order: {days}")

friday_value = float(summary.loc[summary["day_name"].astype(str).eq("Friday"), "avg_daily_volume"].iloc[0])
sunday_value = float(summary.loc[summary["day_name"].astype(str).eq("Sunday"), "avg_daily_volume"].iloc[0])
friday_sunday_gap = (friday_value / sunday_value - 1) * 100

x = np.arange(len(days))


# ==========================================================================================
# INTERPOLATE ANIMATION PATH
# ==========================================================================================

segments = len(values) - 1
frames_per_segment = max(1, TOTAL_FRAMES // segments)

interp_x = []
interp_y = []

for i in range(segments):
    t = np.linspace(0, 1, frames_per_segment, endpoint=False)
    eased = smoothstep(t)

    interp_x.extend(x[i] + (x[i + 1] - x[i]) * eased)
    interp_y.extend(values[i] + (values[i + 1] - values[i]) * eased)

interp_x.append(x[-1])
interp_y.append(values[-1])

interp_x = np.array(interp_x)
interp_y = np.array(interp_y)


# ==========================================================================================
# FIGURE SETUP
# ==========================================================================================

fig, ax = plt.subplots(figsize=(WIDTH, HEIGHT))
fig.patch.set_facecolor("#0b0f14")
ax.set_facecolor("#0b0f14")

for spine in ax.spines.values():
    spine.set_color("#9aa4b2")
    spine.set_linewidth(1.2)

ax.tick_params(colors="white", labelsize=15)

ax.set_xticks(x)
ax.set_xticklabels(days, fontsize=17, color="white", fontweight="bold")

ax.set_ylabel(
    "Average Daily Network Volume",
    fontsize=17,
    color="white",
    labelpad=20,
)

y_min = values.min() * 0.90
y_max = values.max() * 1.10
ax.set_ylim(y_min, y_max)
ax.set_xlim(-0.35, len(days) - 0.65)

yticks = ax.get_yticks()
ax.set_yticklabels([fmt_millions(v) for v in yticks], color="white")

ax.grid(
    axis="y",
    alpha=0.18,
    linestyle="--",
    color="white",
)

fig.text(
    0.5,
    0.955,
    "Melbourne's Weekly Traffic Heartbeat",
    ha="center",
    fontsize=34,
    color="white",
    weight="bold",
)

fig.text(
    0.5,
    0.915,
    "Average daily SCATS network movement by weekday, 2014–2026",
    ha="center",
    fontsize=18,
    color="#b8c2cc",
)

footer = fig.text(
    0.5,
    0.035,
    f"Friday is Melbourne's strongest traffic day. Sunday is the rest state. "
    f"Friday is {friday_sunday_gap:.1f}% stronger than Sunday.",
    ha="center",
    fontsize=16,
    color="#b8c2cc",
)

line, = ax.plot([], [], linewidth=5, color="#4da3ff", solid_capstyle="round")
glow_line, = ax.plot([], [], linewidth=12, color="#4da3ff", alpha=0.16, solid_capstyle="round")

points = ax.scatter([], [], s=230, zorder=5)

annotation = ax.text(
    0,
    0,
    "",
    fontsize=18,
    color="white",
    weight="bold",
    ha="center",
    va="bottom",
)

big_day_label = fig.text(
    0.5,
    0.80,
    "",
    ha="center",
    fontsize=30,
    color="white",
    weight="bold",
)

big_volume_label = fig.text(
    0.5,
    0.755,
    "",
    ha="center",
    fontsize=20,
    color="#d8dee9",
)


# ==========================================================================================
# ANIMATION UPDATE
# ==========================================================================================

def update(frame: int):
    current_x = interp_x[: frame + 1]
    current_y = interp_y[: frame + 1]

    current_pos = current_x[-1]
    current_day_idx = min(int(round(current_pos)), len(days) - 1)
    current_day = days[current_day_idx]
    current_day_value = values[current_day_idx]

    if current_day == "Friday":
        current_colour = DAY_COLOURS["Friday"]
        message = "FRIDAY PEAK"
    elif current_day == "Sunday":
        current_colour = DAY_COLOURS["Sunday"]
        message = "SUNDAY REST STATE"
    elif current_day == "Saturday":
        current_colour = DAY_COLOURS["Saturday"]
        message = "WEEKEND DECLINE"
    else:
        current_colour = "#4da3ff"
        message = "WORKWEEK BUILD-UP"

    line.set_data(current_x, current_y)
    line.set_color(current_colour)

    glow_line.set_data(current_x, current_y)
    glow_line.set_color(current_colour)

    completed_indices = np.where(x <= current_pos)[0]
    scatter_x = x[completed_indices]
    scatter_y = values[completed_indices]
    scatter_colours = [DAY_COLOURS[days[i]] for i in completed_indices]

    points.set_offsets(np.c_[scatter_x, scatter_y])
    points.set_color(scatter_colours)

    annotation.set_text(f"{current_day}\n{fmt_millions(current_day_value)}")
    annotation.set_position((current_day_idx, current_day_value + (y_max - y_min) * 0.035))
    annotation.set_color(current_colour if current_day in {"Friday", "Saturday", "Sunday"} else "white")

    big_day_label.set_text(message)
    big_day_label.set_color(current_colour)

    big_volume_label.set_text(f"{current_day}: {fmt_millions(current_day_value)} average daily movements")

    return line, glow_line, points, annotation, big_day_label, big_volume_label


# ==========================================================================================
# SAVE
# ==========================================================================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

anim = FuncAnimation(
    fig,
    update,
    frames=len(interp_x),
    interval=1000 / FPS,
    blit=False,
)

writer = FFMpegWriter(
    fps=FPS,
    bitrate=9000,
)

print("=" * 90)
print("Rendering Melbourne Weekly Traffic Heartbeat animation")
print("=" * 90)
print(f"Input CSV : {CSV_FILE}")
print(f"Output MP4: {OUTPUT_MP4}")
print(f"Frames    : {len(interp_x)}")
print(f"FPS       : {FPS}")
print("=" * 90)

anim.save(str(OUTPUT_MP4), writer=writer)

plt.close(fig)

print("=" * 90)
print("DONE")
print(f"Output: {OUTPUT_MP4}")
print("=" * 90)
