import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


JSON_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\processing_time")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "processing_time_summary_all_json.csv"
OUT_CHART = OUT_DIR / "processing_time_completed_json_all.png"
OUT_TOP_CHART = OUT_DIR / "processing_time_top_longest_scripts.png"

EXCLUDE_NAMES = {
    "headline_metrics",
    "headline_metrics_merge_status",
}

def hours(seconds):
    return seconds / 3600.0

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

rows = []

for path in sorted(JSON_DIR.glob("*.json")):
    data = load_json(path)
    if not isinstance(data, dict):
        continue

    metric = data.get("metric_name") or path.stem
    elapsed = data.get("total_elapsed_seconds")

    if metric in EXCLUDE_NAMES:
        continue

    if elapsed is None:
        continue

    try:
        elapsed = float(elapsed)
    except Exception:
        continue

    rows.append({
        "file": path.name,
        "metric_name": metric,
        "date_range_start": data.get("date_range_start"),
        "date_range_end": data.get("date_range_end"),
        "months_total": data.get("months_total"),
        "months_completed": data.get("months_completed"),
        "is_complete": data.get("is_complete"),
        "total_elapsed_seconds": elapsed,
        "total_elapsed_hours": hours(elapsed),
        "generated_at_epoch": data.get("generated_at_epoch"),
        "zero_row_months": ",".join(data.get("zero_row_months", [])) if isinstance(data.get("zero_row_months"), list) else "",
    })

df = pd.DataFrame(rows)

if df.empty:
    raise SystemExit("No JSON files with total_elapsed_seconds found.")

df = df.sort_values("total_elapsed_hours", ascending=True)
df.to_csv(OUT_CSV, index=False)

total_hours = df["total_elapsed_hours"].sum()
total_days = total_hours / 24
completed_count = int(df["is_complete"].eq(True).sum())
script_count = len(df)

print("=" * 90)
print("PROCESSING TIME SUMMARY")
print("=" * 90)
print(f"JSON files used       : {script_count}")
print(f"Completed scripts     : {completed_count}")
print(f"Total compute hours   : {total_hours:,.1f}")
print(f"Total compute days    : {total_days:,.1f}")
print(f"CSV written           : {OUT_CSV}")
print("=" * 90)

# ---------------------------------------------------------------------
# Full chart
# ---------------------------------------------------------------------

plt.figure(figsize=(16, max(8, len(df) * 0.55)))

bars = plt.barh(
    df["metric_name"],
    df["total_elapsed_hours"],
    color="#6f4e7c",
    edgecolor="#333333",
    linewidth=0.4,
)

for bar, val in zip(bars, df["total_elapsed_hours"]):
    plt.text(
        val + 0.4,
        bar.get_y() + bar.get_height() / 2,
        f"{val:.1f}h",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="#263238",
    )

plt.title(
    "Processing Time Represented by Completed SCATS JSON Outputs",
    fontsize=22,
    fontweight="bold",
    pad=18,
)
plt.subtitle = None
plt.xlabel("Runtime Hours", fontsize=13)
plt.ylabel("")
plt.grid(axis="x", alpha=0.25)

plt.figtext(
    0.5,
    -0.02,
    f"{script_count} runtime-bearing JSON files | "
    f"{total_hours:,.1f} cumulative compute hours | "
    f"{total_days:,.1f} compute days represented",
    ha="center",
    fontsize=11,
    color="#555555",
)

plt.tight_layout()
plt.savefig(OUT_CHART, dpi=220, bbox_inches="tight")
plt.close()

# ---------------------------------------------------------------------
# Top longest chart
# ---------------------------------------------------------------------

top = df.sort_values("total_elapsed_hours", ascending=False).head(12)
top = top.sort_values("total_elapsed_hours", ascending=True)

plt.figure(figsize=(16, 9))

bars = plt.barh(
    top["metric_name"],
    top["total_elapsed_hours"],
    color="#16395f",
    edgecolor="#333333",
    linewidth=0.4,
)

for bar, val in zip(bars, top["total_elapsed_hours"]):
    plt.text(
        val + 0.4,
        bar.get_y() + bar.get_height() / 2,
        f"{val:.1f}h",
        va="center",
        fontsize=11,
        fontweight="bold",
        color="#263238",
    )

plt.title(
    "Longest-Running Completed SCATS Processing Jobs",
    fontsize=22,
    fontweight="bold",
    pad=18,
)
plt.xlabel("Runtime Hours", fontsize=13)
plt.ylabel("")
plt.grid(axis="x", alpha=0.25)

plt.figtext(
    0.5,
    -0.02,
    "Top 12 longest-running completed processing outputs extracted from final JSON metadata.",
    ha="center",
    fontsize=11,
    color="#555555",
)

plt.tight_layout()
plt.savefig(OUT_TOP_CHART, dpi=220, bbox_inches="tight")
plt.close()

print(f"Full chart written    : {OUT_CHART}")
print(f"Top chart written     : {OUT_TOP_CHART}")
print("=" * 90)

print("\nTop runtimes:")
print(
    df.sort_values("total_elapsed_hours", ascending=False)
      [["metric_name", "total_elapsed_hours", "months_completed", "is_complete"]]
      .head(20)
      .to_string(index=False)
)