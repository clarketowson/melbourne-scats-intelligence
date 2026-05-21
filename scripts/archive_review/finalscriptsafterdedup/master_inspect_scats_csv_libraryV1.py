# master_inspect_scats_csv_libraryV1.py
# Scans all computed SCATS CSV outputs, excluding yearly_totals.csv,
# and creates a compact master inventory for ChatGPT analysis.

from pathlib import Path
import pandas as pd
import json
import hashlib
from datetime import datetime

ROOT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
OUT_DIR = ROOT_DIR / "csv_master_inventory"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDE_FILENAMES = {"yearly_totals.csv"}

MAX_SAMPLE_ROWS = 5
MAX_UNIQUE_SAMPLE = 12

def file_hash_quick(path, block_size=1024 * 1024):
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(block_size))
    return h.hexdigest()

def estimate_rows(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return None

def classify_column(col):
    c = col.lower()
    tags = []
    if any(x in c for x in ["date", "month_start", "next_month_start", "timestamp"]):
        tags.append("date/time")
    if any(x in c for x in ["time_bin", "hour", "minute", "interval"]):
        tags.append("time-bin")
    if any(x in c for x in ["day_name", "iso_dow", "weekday", "weekend"]):
        tags.append("day-of-week")
    if any(x in c for x in ["month_of_year", "month_name", "month_label"]):
        tags.append("month/season")
    if any(x in c for x in ["year"]):
        tags.append("year")
    if any(x in c for x in ["site", "scats"]):
        tags.append("site")
    if any(x in c for x in ["volume", "total", "avg", "mean", "share", "pct", "count"]):
        tags.append("metric")
    if any(x in c for x in ["lat", "lon", "lng", "coordinate"]):
        tags.append("spatial")
    if any(x in c for x in ["parcel", "prop_", "spi", "pfi", "lot", "plan"]):
        tags.append("parcel/property")
    if any(x in c for x in ["elapsed", "completed", "runtime", "seconds", "hours"]):
        tags.append("processing/runtime")
    return tags

def infer_dataset_capabilities(columns):
    lowered = [c.lower() for c in columns]
    caps = []

    has_site = any("site" in c or "scats" in c for c in lowered)
    has_volume = any(x in c for c in lowered for x in ["volume", "total", "avg", "mean"])
    has_timebin = any(x in c for c in lowered for x in ["time_bin", "interval", "hour", "minute"])
    has_day = any(x in c for c in lowered for x in ["day_name", "iso_dow", "weekday", "weekend"])
    has_month = any(x in c for c in lowered for x in ["month_label", "month_start", "month_of_year", "month_name"])
    has_year = any("year" in c for c in lowered)
    has_spatial = any(x in c for c in lowered for x in ["latitude", "longitude", "lat", "lng"])
    has_property = any(x in c for c in lowered for x in ["parcel", "prop_", "spi", "pfi", "lot", "plan"])

    if has_volume:
        caps.append("traffic volume analytics")
    if has_timebin:
        caps.append("15-minute / time-of-day analytics")
    if has_day:
        caps.append("day-of-week / weekday-weekend analytics")
    if has_month:
        caps.append("monthly / seasonal analytics")
    if has_year:
        caps.append("yearly trend analytics")
    if has_site:
        caps.append("SCATS site-level analytics")
    if has_site and has_month:
        caps.append("site-by-month trend analysis")
    if has_timebin and has_day:
        caps.append("weekly day-time pulse analysis")
    if has_spatial:
        caps.append("mapping / GIS analysis")
    if has_property:
        caps.append("parcel / OOH opportunity intelligence")
    if has_volume and has_month and has_site:
        caps.append("growth, volatility, concentration and ranking analysis")
    if has_volume and has_timebin and has_day:
        caps.append("busiest/quietest recurring day-time windows")

    return caps

csv_files = sorted([
    p for p in ROOT_DIR.rglob("*.csv")
    if p.name not in EXCLUDE_FILENAMES
])

inventory = []
column_catalog = {}

print("=" * 110)
print("MASTER SCATS CSV LIBRARY INVENTORY V1")
print("=" * 110)
print(f"Root directory: {ROOT_DIR}")
print(f"CSV files found, excluding {EXCLUDE_FILENAMES}: {len(csv_files):,}")
print(f"Generated at: {datetime.now().isoformat(timespec='seconds')}")
print("=" * 110)

for path in csv_files:
    rel = path.relative_to(ROOT_DIR)

    try:
        df = pd.read_csv(path, nrows=MAX_SAMPLE_ROWS)
        columns = list(df.columns)
        row_count = estimate_rows(path)
        size_mb = path.stat().st_size / (1024 * 1024)

        column_info = []
        for col in columns:
            tags = classify_column(col)
            sample_values = []

            try:
                s = df[col].dropna().astype(str).head(MAX_UNIQUE_SAMPLE)
                sample_values = s.tolist()
            except Exception:
                pass

            column_info.append({
                "column": col,
                "tags": tags,
                "sample_values": sample_values,
            })

            column_catalog.setdefault(col, 0)
            column_catalog[col] += 1

        capabilities = infer_dataset_capabilities(columns)

        record = {
            "relative_path": str(rel),
            "absolute_path": str(path),
            "filename": path.name,
            "parent_folder": str(path.parent.relative_to(ROOT_DIR)),
            "size_mb": round(size_mb, 3),
            "rows_estimate": row_count,
            "column_count": len(columns),
            "columns": columns,
            "column_info": column_info,
            "capabilities": capabilities,
            "sample_rows": df.astype(str).to_dict(orient="records"),
            "quick_md5_first_mb": file_hash_quick(path),
            "error": None,
        }

        inventory.append(record)

        print("\n" + "-" * 110)
        print(f"FILE: {rel}")
        print(f"Rows: {row_count:,}" if row_count is not None else "Rows: unknown")
        print(f"Size: {size_mb:.2f} MB")
        print(f"Columns: {len(columns)}")
        print("Capabilities:")
        for cap in capabilities:
            print(f"  - {cap}")
        print("Columns:")
        for c in columns:
            tags = classify_column(c)
            tag_txt = f" [{', '.join(tags)}]" if tags else ""
            print(f"  - {c}{tag_txt}")

    except Exception as e:
        inventory.append({
            "relative_path": str(rel),
            "absolute_path": str(path),
            "filename": path.name,
            "parent_folder": str(path.parent.relative_to(ROOT_DIR)),
            "size_mb": round(path.stat().st_size / (1024 * 1024), 3),
            "rows_estimate": None,
            "column_count": None,
            "columns": [],
            "column_info": [],
            "capabilities": [],
            "sample_rows": [],
            "quick_md5_first_mb": None,
            "error": str(e),
        })
        print("\nERROR:", rel, e)

# Summary tables
summary_rows = []
for r in inventory:
    summary_rows.append({
        "relative_path": r["relative_path"],
        "filename": r["filename"],
        "parent_folder": r["parent_folder"],
        "size_mb": r["size_mb"],
        "rows_estimate": r["rows_estimate"],
        "column_count": r["column_count"],
        "columns": " | ".join(r["columns"]),
        "capabilities": " | ".join(r["capabilities"]),
        "error": r["error"] or "",
    })

summary_df = pd.DataFrame(summary_rows)

column_catalog_df = (
    pd.DataFrame(
        [{"column": k, "file_count": v, "tags": " | ".join(classify_column(k))}
         for k, v in column_catalog.items()]
    )
    .sort_values(["file_count", "column"], ascending=[False, True])
)

capability_rows = []
for r in inventory:
    for cap in r["capabilities"]:
        capability_rows.append({
            "capability": cap,
            "relative_path": r["relative_path"],
            "filename": r["filename"],
            "rows_estimate": r["rows_estimate"],
            "size_mb": r["size_mb"],
        })

capability_df = pd.DataFrame(capability_rows)

if not capability_df.empty:
    capability_summary_df = (
        capability_df.groupby("capability", as_index=False)
        .agg(
            file_count=("relative_path", "count"),
            total_rows_estimate=("rows_estimate", "sum"),
            total_size_mb=("size_mb", "sum"),
            example_files=("relative_path", lambda x: " | ".join(list(x)[:8])),
        )
        .sort_values("file_count", ascending=False)
    )
else:
    capability_summary_df = pd.DataFrame()

# Relationship hints: files that can likely be joined
join_keys = [
    "month_label", "month_start", "next_month_start",
    "time_bin", "day_name", "iso_dow",
    "scats_site", "site", "site_id",
    "year", "month_of_year", "date_label", "count_date"
]

join_rows = []
for key in join_keys:
    matches = []
    for r in inventory:
        if key in r["columns"]:
            matches.append(r["relative_path"])
    if matches:
        join_rows.append({
            "join_key": key,
            "file_count": len(matches),
            "files": " | ".join(matches[:30]),
        })

join_df = pd.DataFrame(join_rows).sort_values("file_count", ascending=False)

# Save outputs
json_out = OUT_DIR / "master_csv_inventory.json"
summary_csv = OUT_DIR / "master_csv_inventory_summary.csv"
columns_csv = OUT_DIR / "master_column_catalog.csv"
capability_csv = OUT_DIR / "master_capability_file_map.csv"
capability_summary_csv = OUT_DIR / "master_capability_summary.csv"
join_csv = OUT_DIR / "master_possible_join_keys.csv"

with open(json_out, "w", encoding="utf-8") as f:
    json.dump({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root_dir": str(ROOT_DIR),
        "excluded_filenames": sorted(EXCLUDE_FILENAMES),
        "csv_file_count": len(csv_files),
        "inventory": inventory,
    }, f, indent=2)

summary_df.to_csv(summary_csv, index=False)
column_catalog_df.to_csv(columns_csv, index=False)
capability_df.to_csv(capability_csv, index=False)
capability_summary_df.to_csv(capability_summary_csv, index=False)
join_df.to_csv(join_csv, index=False)

print("\n" + "=" * 110)
print("MASTER INVENTORY COMPLETE")
print("=" * 110)
print(f"JSON inventory:        {json_out}")
print(f"Summary CSV:           {summary_csv}")
print(f"Column catalog:        {columns_csv}")
print(f"Capability file map:   {capability_csv}")
print(f"Capability summary:    {capability_summary_csv}")
print(f"Possible join keys:    {join_csv}")
print("=" * 110)

print("\nTOP CAPABILITY GROUPS")
if not capability_summary_df.empty:
    print(capability_summary_df.head(30).to_string(index=False))
else:
    print("No capability groups detected.")

print("\nMOST COMMON COLUMNS")
print(column_catalog_df.head(40).to_string(index=False))

print("\nPOSSIBLE JOIN KEYS")
print(join_df.to_string(index=False))