# inspect_existing_csvs_for_weekly_pulseV1.py

from pathlib import Path
import pandas as pd
import json

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
OUT_DIR = REPORT_DIR / "weekly_day_time_pulse_inspection"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_TERMS = [
    "day", "dow", "weekday", "weekend",
    "time_bin", "interval", "bin",
    "volume", "total", "avg", "mean"
]

csv_files = sorted(REPORT_DIR.rglob("*.csv"))

results = []

print("=" * 100)
print("CSV INSPECTION FOR WEEKLY DAY × TIME PULSE ANALYSIS")
print("=" * 100)
print(f"Scanning: {REPORT_DIR}")
print(f"CSV files found: {len(csv_files):,}")
print("=" * 100)

for path in csv_files:
    try:
        df_head = pd.read_csv(path, nrows=20)
        cols = list(df_head.columns)

        lowered = [c.lower() for c in cols]

        has_day = any(x in c for c in lowered for x in ["day", "dow", "weekday"])
        has_time = any(x in c for c in lowered for x in ["time_bin", "interval", "bin", "hh", "minute"])
        has_volume = any(x in c for c in lowered for x in ["volume", "total", "avg", "mean", "count"])

        score = int(has_day) + int(has_time) + int(has_volume)

        rows_estimate = None
        try:
            rows_estimate = sum(1 for _ in open(path, "r", encoding="utf-8", errors="ignore")) - 1
        except Exception:
            pass

        result = {
            "file": str(path),
            "name": path.name,
            "rows_estimate": rows_estimate,
            "columns": cols,
            "has_day_column": has_day,
            "has_time_column": has_time,
            "has_volume_column": has_volume,
            "usefulness_score_0_to_3": score,
        }

        results.append(result)

        if score >= 2:
            print("\nPOSSIBLE MATCH")
            print(f"File: {path}")
            print(f"Rows: {rows_estimate}")
            print(f"Score: {score}/3")
            print("Columns:")
            for c in cols:
                print(f"  - {c}")
            print("Sample:")
            print(df_head.head(5).to_string(index=False))

    except Exception as e:
        results.append({
            "file": str(path),
            "name": path.name,
            "error": str(e),
        })

# Save full inspection
out_json = OUT_DIR / "csv_weekly_pulse_inspection.json"
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

# Save summary CSV
summary_rows = []
for r in results:
    if "error" in r:
        summary_rows.append({
            "file": r["file"],
            "name": r["name"],
            "rows_estimate": None,
            "usefulness_score_0_to_3": None,
            "has_day_column": None,
            "has_time_column": None,
            "has_volume_column": None,
            "columns": "",
            "error": r["error"],
        })
    else:
        summary_rows.append({
            "file": r["file"],
            "name": r["name"],
            "rows_estimate": r["rows_estimate"],
            "usefulness_score_0_to_3": r["usefulness_score_0_to_3"],
            "has_day_column": r["has_day_column"],
            "has_time_column": r["has_time_column"],
            "has_volume_column": r["has_volume_column"],
            "columns": " | ".join(r["columns"]),
            "error": "",
        })

summary_df = pd.DataFrame(summary_rows)
summary_csv = OUT_DIR / "csv_weekly_pulse_inspection_summary.csv"
summary_df.to_csv(summary_csv, index=False)

best = summary_df.sort_values(
    by=["usefulness_score_0_to_3", "rows_estimate"],
    ascending=[False, False],
    na_position="last"
).head(20)

best_csv = OUT_DIR / "top_candidate_csv_files.csv"
best.to_csv(best_csv, index=False)

print("\n" + "=" * 100)
print("TOP CANDIDATE CSV FILES")
print("=" * 100)
print(best[[
    "name",
    "rows_estimate",
    "usefulness_score_0_to_3",
    "has_day_column",
    "has_time_column",
    "has_volume_column"
]].to_string(index=False))

print("\nDONE")
print(f"Full JSON: {out_json}")
print(f"Summary CSV: {summary_csv}")
print(f"Top candidates: {best_csv}")