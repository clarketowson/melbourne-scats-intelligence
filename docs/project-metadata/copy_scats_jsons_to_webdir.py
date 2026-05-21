from pathlib import Path
import pandas as pd
import shutil

CSV_INPUT = Path(r"A:\TrafficAnalytics\PROJECTS\scats_relevant_json_files.csv")
WEB_ROOT = Path(r"\\bluemorpho\StatsWebsiteWritable")

df = pd.read_csv(CSV_INPUT)

def target_dir(filename: str) -> Path:
    name = filename.lower()

    if name.startswith("kepler_"):
        return WEB_ROOT / "kepler_animation_exports"

    if "traffic_archetypes" in name:
        return WEB_ROOT / "traffic_archetypes_v4"

    if (
        name.startswith("site_")
        or name.startswith("top_")
        or "rankings" in name
        or "percentile" in name
        or "network" in name
    ):
        return WEB_ROOT / "site_month_charts"

    if "covid" in name:
        return WEB_ROOT / "covid_comparison"

    if "time_bin_behaviour" in name or "time_bin_profile_chart_manifest" in name:
        return WEB_ROOT / "charts" / "time_bin_profile"

    if "chart_manifest" in name or "csv_inventory" in name:
        return WEB_ROOT / "downloads"

    return WEB_ROOT


copied = []
skipped = []
errors = []

for _, row in df.iterrows():
    src = Path(row["full_path"])
    filename = row["filename"]

    if not src.exists():
        skipped.append(str(src))
        print(f"SKIPPED missing: {src}")
        continue

    dst_dir = target_dir(filename)
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / filename

    try:
        shutil.copy2(src, dst)
        copied.append({"filename": filename, "source": str(src), "destination": str(dst)})
        print(f"COPIED: {filename} -> {dst_dir}")
    except Exception as e:
        errors.append({"filename": filename, "source": str(src), "error": str(e)})
        print(f"ERROR: {filename} -> {e}")

pd.DataFrame(copied).to_csv(WEB_ROOT / "json_files_copied_report.csv", index=False)
pd.DataFrame(skipped, columns=["missing_source"]).to_csv(WEB_ROOT / "json_files_skipped_report.csv", index=False)

if errors:
    pd.DataFrame(errors).to_csv(WEB_ROOT / "json_files_errors_report.csv", index=False)

print()
print("======================================")
print(f"Copied : {len(copied)}")
print(f"Skipped: {len(skipped)}")
print(f"Errors : {len(errors)}")
print("======================================")