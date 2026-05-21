# ==========================================================================================
# MELBOURNE WEEKLY TRAFFIC HEARTBEAT CINEMATIC ANIMATION V1
# ==========================================================================================
#
# Creates a cinematic MP4 animation from day-of-week SCATS insights.
#
# Features:
#   - Weekly heartbeat line animation
#   - Friday peak highlight
#   - Sunday rest-state collapse
#   - Smooth frame interpolation
#   - Cinematic typography
#   - COVID annotation support placeholder
#
# Output:
#   A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\
#       melbourne_weekly_heartbeat.mp4
#
# ==========================================================================================

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.animation import FFMpegWriter

# ==========================================================================================
# CONFIG
# ==========================================================================================

CSV_FILE = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile.csv"

OUTPUT_DIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\animations"
OUTPUT_MP4 = os.path.join(
    OUTPUT_DIR,
    "melbourne_weekly_heartbeat.mp4"
)

FPS = 30
DURATION_SECONDS = 20
TOTAL_FRAMES = FPS * DURATION_SECONDS

WIDTH = 16
HEIGHT = 9

# ==========================================================================================
# LOAD DATA
# ==========================================================================================

df = pd.read_csv(CSV_FILE)

# expected columns:
# weekday, average_daily_volume

weekday_order = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday"
]

df["weekday"] = pd.Categorical(
    df["weekday"],
    categories=weekday_order,
    ordered=True
)

df = df.sort_values("weekday")

days = df["weekday"].tolist()
values = df["average_daily_volume"].tolist()

x = np.arange(len(days))

# ==========================================================================================
# INTERPOLATED FRAMES
# ==========================================================================================

frames_per_segment = TOTAL_FRAMES // (len(values) - 1)

interp_x = []
interp_y = []

for i in range(len(values) - 1):

    x_start = x[i]
    x_end = x[i + 1]

    y_start = values[i]
    y_end = values[i + 1]

    x_segment = np.linspace(
        x_start,
        x_end,
        frames_per_segment
    )

    y_segment = np.linspace(
        y_start,
        y_end,
        frames_per_segment
    )

    interp_x.extend(x_segment)
    interp_y.extend(y_segment)

interp_x = np.array(interp_x)
interp_y = np.array(interp_y)

# ==========================================================================================
# FIGURE
# ==========================================================================================

plt.style.use("default")

fig, ax = plt.subplots(figsize=(WIDTH, HEIGHT))

fig.patch.set_facecolor("#111111")
ax.set_facecolor("#111111")

# ==========================================================================================
# AXIS STYLING
# ==========================================================================================

ax.spines["bottom"].set_color("white")
ax.spines["top"].set_color("white")
ax.spines["left"].set_color("white")
ax.spines["right"].set_color("white")

ax.tick_params(colors="white", labelsize=16)

ax.set_xticks(x)
ax.set_xticklabels(days, fontsize=18, color="white")

ax.set_ylabel(
    "Average Daily Network Volume",
    fontsize=18,
    color="white",
    labelpad=20
)

ax.grid(
    alpha=0.15,
    linestyle="--",
    color="white"
)

# ==========================================================================================
# TITLES
# ==========================================================================================

title = ax.set_title(
    "Melbourne's Weekly Traffic Heartbeat",
    fontsize=34,
    color="white",
    weight="bold",
    pad=30
)

subtitle = fig.text(
    0.5,
    0.90,
    "SCATS network movement intensity by weekday, 2014–2026",
    ha="center",
    fontsize=20,
    color="#bbbbbb"
)

# ==========================================================================================
# Y LIMITS
# ==========================================================================================

y_min = min(values) * 0.92
y_max = max(values) * 1.08

ax.set_ylim(y_min, y_max)

# ==========================================================================================
# MAIN LINE
# ==========================================================================================

line, = ax.plot(
    [],
    [],
    linewidth=5,
    color="#4da3ff"
)

points = ax.scatter(
    [],
    [],
    s=220,
    color="#4da3ff",
    zorder=5
)

# ==========================================================================================
# ANNOTATIONS
# ==========================================================================================

annotation = ax.text(
    0,
    0,
    "",
    fontsize=18,
    color="white",
    weight="bold"
)

footer = fig.text(
    0.5,
    0.03,
    "Friday dominates Melbourne's traffic rhythm while Sunday represents the network rest state.",
    ha="center",
    fontsize=18,
    color="#bbbbbb"
)

# ==========================================================================================
# UPDATE FUNCTION
# ==========================================================================================

def update(frame):

    current_x = interp_x[:frame + 1]
    current_y = interp_y[:frame + 1]

    line.set_data(current_x, current_y)

    # completed weekdays
    completed_indices = np.where(x <= current_x[-1])[0]

    scatter_x = x[completed_indices]
    scatter_y = np.array(values)[completed_indices]

    # colors
    scatter_colors = []

    for idx in completed_indices:

        if idx == 4:
            scatter_colors.append("#ff0033")   # Friday
        elif idx == 5:
            scatter_colors.append("#ffb347")   # Saturday
        elif idx == 6:
            scatter_colors.append("#888888")   # Sunday
        else:
            scatter_colors.append("#4da3ff")

    points.set_offsets(np.c_[scatter_x, scatter_y])
    points.set_color(scatter_colors)

    # annotation
    current_day_idx = min(
        int(round(current_x[-1])),
        len(days) - 1
    )

    current_day = days[current_day_idx]
    current_value = values[current_day_idx]

    annotation.set_text(
        f"{current_day}: {current_value / 1_000_000:.1f}M"
    )

    annotation.set_position(
        (current_day_idx, current_value * 1.02)
    )

    # Friday cinematic emphasis
    if current_day == "Friday":
        line.set_color("#ff0033")
    elif current_day == "Sunday":
        line.set_color("#888888")
    else:
        line.set_color("#4da3ff")

    return (
        line,
        points,
        annotation
    )

# ==========================================================================================
# ANIMATION
# ==========================================================================================

anim = FuncAnimation(
    fig,
    update,
    frames=len(interp_x),
    interval=1000 / FPS,
    blit=False
)

# ==========================================================================================
# SAVE
# ==========================================================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

writer = FFMpegWriter(
    fps=FPS,
    bitrate=8000
)

print("=" * 80)
print("Rendering cinematic weekly heartbeat animation...")
print("=" * 80)

anim.save(
    OUTPUT_MP4,
    writer=writer
)

print("=" * 80)
print("DONE")
print(f"Output: {OUTPUT_MP4}")
print("=" * 80)