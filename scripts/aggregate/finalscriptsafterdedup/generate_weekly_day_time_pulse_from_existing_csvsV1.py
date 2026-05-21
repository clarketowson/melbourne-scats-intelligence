# generate_weekly_day_time_pulse_from_existing_csvsV1.py

from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
INPUT_CSV = REPORT_DIR / "kepler_city_pulse" / "kepler_city_pulse_2024-05-13_to_2024-05-19.csv"

OUT_DIR = REPORT_DIR / "weekly_day_time_pulse_from_csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 90)
print("WEEKLY DAY × TIME PULSE FROM EXISTING CSV FILES V1")
print("=" * 90)
print(f"Input:  {INPUT_CSV}")
print(f"Output: {OUT_DIR}")
print("=" * 90)

usecols = ["timestamp", "date_label", "day_name", "time_label", "hour", "minute", "volume"]

df = pd.read_csv(INPUT_CSV, usecols=usecols)

df["time_bin"] = df["hour"].astype(int).astype(str).str.zfill(2) + ":" + df["minute"].astype(int).astype(str).str.zfill(2)

agg = (
    df.groupby(["day_name", "time_bin"], as_index=False)
      .agg(
          total_volume=("volume", "sum"),
          site_rows=("volume", "count"),
          avg_site_volume=("volume", "mean"),
      )
)

day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
agg["day_name"] = pd.Categorical(agg["day_name"], categories=day_order, ordered=True)

agg = agg.sort_values(["day_name", "time_bin"])

busiest = agg.loc[agg["total_volume"].idxmax()]
quietest = agg.loc[agg["total_volume"].idxmin()]

summary = {
    "source_csv": str(INPUT_CSV),
    "method": "Aggregated existing 7-day Kepler city pulse CSV by day_name and 15-minute time_bin.",
    "busiest_observed_day_time": {
        "day_name": str(busiest["day_name"]),
        "time_bin": str(busiest["time_bin"]),
        "total_volume": int(busiest["total_volume"]),
        "site_rows": int(busiest["site_rows"]),
        "avg_site_volume": float(busiest["avg_site_volume"]),
    },
    "quietest_observed_day_time": {
        "day_name": str(quietest["day_name"]),
        "time_bin": str(quietest["time_bin"]),
        "total_volume": int(quietest["total_volume"]),
        "site_rows": int(quietest["site_rows"]),
        "avg_site_volume": float(quietest["avg_site_volume"]),
    },
    "rows_input": int(len(df)),
    "rows_output": int(len(agg)),
}

agg.to_csv(OUT_DIR / "weekly_day_time_pulse_7day_observed.csv", index=False)

ranked = agg.sort_values("total_volume", ascending=False).copy()
ranked["busy_rank"] = range(1, len(ranked) + 1)
ranked.to_csv(OUT_DIR / "weekly_day_time_pulse_7day_ranked.csv", index=False)

with open(OUT_DIR / "weekly_day_time_pulse_7day_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\nBUSIEST OBSERVED DAY/TIME")
print(f"{busiest['day_name']} {busiest['time_bin']} — {busiest['total_volume']:,.0f}")

print("\nQUIETEST OBSERVED DAY/TIME")
print(f"{quietest['day_name']} {quietest['time_bin']} — {quietest['total_volume']:,.0f}")

# ---------------------------------------------------------------------
# CHART 1: Heatmap
# ---------------------------------------------------------------------

heat = agg.pivot(index="day_name", columns="time_bin", values="total_volume").loc[day_order]

plt.figure(figsize=(22, 8))
plt.imshow(heat.values, aspect="auto")
plt.title("Melbourne Weekly Traffic Pulse: Observed Volume by Day and 15-Minute Time Bin", fontsize=20, weight="bold", pad=18)
plt.xlabel("Time of Day")
plt.ylabel("Day of Week")

x_ticks = list(range(0, 96, 4))
x_labels = [f"{h:02d}:00" for h in range(24)]
plt.xticks(x_ticks, x_labels, rotation=45, ha="right")
plt.yticks(range(len(day_order)), day_order)

cbar = plt.colorbar()
cbar.set_label("Observed 15-minute network volume")

plt.tight_layout()
plt.savefig(OUT_DIR / "weekly_day_time_heatmap_observed.png", dpi=180, bbox_inches="tight")
plt.close()

# ---------------------------------------------------------------------
# CHART 2: 672 interval weekly pulse line
# ---------------------------------------------------------------------

line = agg.copy()
line["weekly_index"] = range(len(line))

plt.figure(figsize=(24, 8))
plt.plot(line["weekly_index"], line["total_volume"], linewidth=2)

busiest_idx = line["total_volume"].idxmax()
quietest_idx = line["total_volume"].idxmin()

plt.scatter(line.loc[busiest_idx, "weekly_index"], line.loc[busiest_idx, "total_volume"], s=90, zorder=5)
plt.scatter(line.loc[quietest_idx, "weekly_index"], line.loc[quietest_idx, "total_volume"], s=90, zorder=5)

plt.title("Melbourne Weekly Traffic Heartbeat: 672 Observed 15-Minute Windows", fontsize=20, weight="bold", pad=18)
plt.xlabel("Week progression")
plt.ylabel("Observed 15-minute network volume")
plt.xticks([i * 96 for i in range(7)], day_order)
plt.grid(axis="y", alpha=0.25)

plt.tight_layout()
plt.savefig(OUT_DIR / "weekly_672_interval_pulse_line_observed.png", dpi=180, bbox_inches="tight")
plt.close()

# ---------------------------------------------------------------------
# CHART 3: Top 20 busiest
# ---------------------------------------------------------------------

top20 = agg.sort_values("total_volume", ascending=False).head(20).copy()
top20["label"] = top20["day_name"].astype(str) + " " + top20["time_bin"]
top20 = top20.sort_values("total_volume")

plt.figure(figsize=(14, 10))
plt.barh(top20["label"], top20["total_volume"])
plt.title("Top 20 Busiest Observed Melbourne Day-Time Windows", fontsize=18, weight="bold", pad=16)
plt.xlabel("Observed 15-minute network volume")

for i, v in enumerate(top20["total_volume"]):
    plt.text(v, i, f" {v:,.0f}", va="center", fontsize=9)

plt.tight_layout()
plt.savefig(OUT_DIR / "top20_busiest_observed_day_time_windows.png", dpi=180, bbox_inches="tight")
plt.close()

# ---------------------------------------------------------------------
# CHART 4: Top 20 quietest
# ---------------------------------------------------------------------

bottom20 = agg.sort_values("total_volume", ascending=True).head(20).copy()
bottom20["label"] = bottom20["day_name"].astype(str) + " " + bottom20["time_bin"]
bottom20 = bottom20.sort_values("total_volume", ascending=False)

plt.figure(figsize=(14, 10))
plt.barh(bottom20["label"], bottom20["total_volume"])
plt.title("Top 20 Quietest Observed Melbourne Day-Time Windows", fontsize=18, weight="bold", pad=16)
plt.xlabel("Observed 15-minute network volume")

for i, v in enumerate(bottom20["total_volume"]):
    plt.text(v, i, f" {v:,.0f}", va="center", fontsize=9)

plt.tight_layout()
plt.savefig(OUT_DIR / "top20_quietest_observed_day_time_windows.png", dpi=180, bbox_inches="tight")
plt.close()

print("\nDONE")
print(f"CSV:     {OUT_DIR / 'weekly_day_time_pulse_7day_observed.csv'}")
print(f"Ranked:  {OUT_DIR / 'weekly_day_time_pulse_7day_ranked.csv'}")
print(f"Summary: {OUT_DIR / 'weekly_day_time_pulse_7day_summary.json'}")
print(f"Charts:  {OUT_DIR}")