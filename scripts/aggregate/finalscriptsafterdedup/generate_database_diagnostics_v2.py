# generate_database_diagnostics_v2.py

import json
import time
from pathlib import Path
from datetime import datetime

import duckdb
import pandas as pd


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

PRIMARY_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"

OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\database_diagnostics")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_LIMIT = "50GB"
THREADS = 10
TEMP_DIR = r"A:\TrafficAnalytics\DATA\TEMP"

VIEW_NAME = "scats_all_clean_dedup"
LONG_VIEW_NAME = "scats_15min_long"


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def safe_query(con, sql, label):
    print(f"\n--- {label} ---")
    start = time.time()
    try:
        df = con.execute(sql).fetchdf()
        elapsed = round(time.time() - start, 3)
        print(f"OK: {label} ({elapsed}s, {len(df):,} rows)")
        return df, None, elapsed
    except Exception as e:
        elapsed = round(time.time() - start, 3)
        err = f"{label}: {type(e).__name__}: {e}"
        print("ERROR:", err)
        return pd.DataFrame(), err, elapsed


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

start_all = time.time()
errors = []
timings = []

con = duckdb.connect(PRIMARY_DB, read_only=True)

con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
con.execute(f"SET threads={THREADS}")
con.execute(f"SET temp_directory='{TEMP_DIR}'")
con.execute("SET preserve_insertion_order=false")


# ------------------------------------------------------------
# 1. Overall coverage summary
# ------------------------------------------------------------

coverage_sql = f"""
SELECT
    MIN(count_date) AS min_count_date,
    MAX(count_date) AS max_count_date,
    COUNT(*) AS detector_day_rows,
    COUNT(DISTINCT scats_site) AS distinct_scats_sites,
    COUNT(DISTINCT detector) AS distinct_detectors,
    COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
    COUNT(DISTINCT DATE_TRUNC('month', count_date)) AS distinct_months,
    COUNT(DISTINCT count_date) AS distinct_dates,
    SUM(volume_24hour) AS total_volume_24hour_sum
FROM {VIEW_NAME}
"""

coverage_df, err, elapsed = safe_query(con, coverage_sql, "overall coverage summary")
timings.append({"query": "overall_coverage_summary", "elapsed_seconds": elapsed})
if err:
    errors.append(err)
else:
    coverage_df.to_csv(OUT_DIR / "database_diagnostics_v2_coverage_summary.csv", index=False)


# ------------------------------------------------------------
# 2. Monthly coverage
# ------------------------------------------------------------

monthly_sql = f"""
SELECT
    STRFTIME(count_date, '%Y-%m') AS month_label,
    DATE_TRUNC('month', count_date) AS month_start,
    COUNT(*) AS detector_day_rows,
    COUNT(DISTINCT count_date) AS days_present,
    COUNT(DISTINCT scats_site) AS distinct_scats_sites,
    COUNT(DISTINCT detector) AS distinct_detectors,
    COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
    SUM(volume_24hour) AS total_volume_24hour_sum
FROM {VIEW_NAME}
GROUP BY 1, 2
ORDER BY 2
"""

monthly_df, err, elapsed = safe_query(con, monthly_sql, "monthly coverage")
timings.append({"query": "monthly_coverage", "elapsed_seconds": elapsed})
if err:
    errors.append(err)
else:
    monthly_df.to_csv(OUT_DIR / "database_diagnostics_v2_monthly_coverage.csv", index=False)


# ------------------------------------------------------------
# 3. Yearly structural coverage
# ------------------------------------------------------------

yearly_sql = f"""
SELECT
    EXTRACT(year FROM count_date)::INTEGER AS year,
    COUNT(*) AS detector_day_rows,
    COUNT(DISTINCT count_date) AS days_present,
    COUNT(DISTINCT DATE_TRUNC('month', count_date)) AS months_present,
    COUNT(DISTINCT scats_site) AS distinct_scats_sites,
    COUNT(DISTINCT detector) AS distinct_detectors,
    COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
    SUM(volume_24hour) AS total_volume_24hour_sum
FROM {VIEW_NAME}
GROUP BY 1
ORDER BY 1
"""

yearly_df, err, elapsed = safe_query(con, yearly_sql, "yearly structural coverage")
timings.append({"query": "yearly_structural_coverage", "elapsed_seconds": elapsed})
if err:
    errors.append(err)
else:
    yearly_df.to_csv(OUT_DIR / "database_diagnostics_v2_yearly_structural_coverage.csv", index=False)


# ------------------------------------------------------------
# 4. Region coverage
# ------------------------------------------------------------

region_sql = f"""
SELECT
    region_code,
    COUNT(*) AS detector_day_rows,
    COUNT(DISTINCT scats_site) AS distinct_scats_sites,
    COUNT(DISTINCT detector) AS distinct_detectors,
    COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
    MIN(count_date) AS min_count_date,
    MAX(count_date) AS max_count_date,
    SUM(volume_24hour) AS total_volume_24hour_sum
FROM {VIEW_NAME}
GROUP BY 1
ORDER BY detector_day_rows DESC
"""

region_df, err, elapsed = safe_query(con, region_sql, "region coverage")
timings.append({"query": "region_coverage", "elapsed_seconds": elapsed})
if err:
    errors.append(err)
else:
    region_df.to_csv(OUT_DIR / "database_diagnostics_v2_region_coverage.csv", index=False)


# ------------------------------------------------------------
# 5. 15-minute interval structural check
# ------------------------------------------------------------

interval_columns = [f"v{i:02d}" for i in range(96)]

interval_exprs = ",\n    ".join([
    f"SUM(CASE WHEN {col} IS NOT NULL THEN 1 ELSE 0 END) AS {col}_non_null"
    for col in interval_columns
])

interval_sql = f"""
SELECT
    COUNT(*) AS detector_day_rows,
    {interval_exprs}
FROM {VIEW_NAME}
"""

interval_df, err, elapsed = safe_query(con, interval_sql, "15-minute interval non-null structural check")
timings.append({"query": "interval_non_null_check", "elapsed_seconds": elapsed})
if err:
    errors.append(err)
else:
    interval_df.to_csv(OUT_DIR / "database_diagnostics_v2_interval_non_null_counts.csv", index=False)

    # Convert wide interval result into long format for easier charting
    rows = []
    total_rows = int(interval_df["detector_day_rows"].iloc[0])
    for i in range(96):
        col = f"v{i:02d}_non_null"
        non_null = int(interval_df[col].iloc[0])
        rows.append({
            "interval_index": i,
            "time_bin": f"{i // 4:02d}:{(i % 4) * 15:02d}",
            "non_null_count": non_null,
            "detector_day_rows": total_rows,
            "coverage_pct": (non_null / total_rows * 100) if total_rows else None,
        })

    pd.DataFrame(rows).to_csv(
        OUT_DIR / "database_diagnostics_v2_interval_non_null_counts_long.csv",
        index=False
    )


# ------------------------------------------------------------
# 6. Source file structural summary, if source_file_id exists
# ------------------------------------------------------------

source_sql = f"""
SELECT
    source_file_id,
    COUNT(*) AS detector_day_rows,
    MIN(count_date) AS min_count_date,
    MAX(count_date) AS max_count_date,
    COUNT(DISTINCT scats_site) AS distinct_scats_sites,
    SUM(volume_24hour) AS total_volume_24hour_sum
FROM {VIEW_NAME}
GROUP BY 1
ORDER BY detector_day_rows DESC
"""

source_df, err, elapsed = safe_query(con, source_sql, "source file structural summary")
timings.append({"query": "source_file_structural_summary", "elapsed_seconds": elapsed})
if err:
    errors.append(err)
else:
    source_df.to_csv(OUT_DIR / "database_diagnostics_v2_source_file_summary.csv", index=False)


# ------------------------------------------------------------
# 7. Optional long-view check
# ------------------------------------------------------------

long_view_sql = f"""
SELECT
    MIN(count_date) AS min_count_date,
    MAX(count_date) AS max_count_date,
    COUNT(*) AS long_interval_rows,
    COUNT(DISTINCT scats_site) AS distinct_scats_sites,
    COUNT(DISTINCT detector) AS distinct_detectors,
    COUNT(DISTINCT interval_index) AS distinct_interval_indexes,
    MIN(interval_index) AS min_interval_index,
    MAX(interval_index) AS max_interval_index,
    SUM(volume_15m) AS total_volume_15m_sum
FROM {LONG_VIEW_NAME}
"""

long_df, err, elapsed = safe_query(con, long_view_sql, "long 15-minute view summary")
timings.append({"query": "long_view_summary", "elapsed_seconds": elapsed})
if err:
    errors.append(err)
else:
    long_df.to_csv(OUT_DIR / "database_diagnostics_v2_long_view_summary.csv", index=False)


con.close()


# ------------------------------------------------------------
# SUMMARY JSON
# ------------------------------------------------------------

summary = {
    "metric_name": "database_diagnostics_v2",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "primary_database": PRIMARY_DB,
    "view_name": VIEW_NAME,
    "long_view_name": LONG_VIEW_NAME,
    "total_elapsed_seconds": round(time.time() - start_all, 3),
    "errors": errors,
    "timings": timings,
    "outputs": {
        "coverage_summary_csv": str(OUT_DIR / "database_diagnostics_v2_coverage_summary.csv"),
        "monthly_coverage_csv": str(OUT_DIR / "database_diagnostics_v2_monthly_coverage.csv"),
        "yearly_structural_coverage_csv": str(OUT_DIR / "database_diagnostics_v2_yearly_structural_coverage.csv"),
        "region_coverage_csv": str(OUT_DIR / "database_diagnostics_v2_region_coverage.csv"),
        "interval_non_null_counts_csv": str(OUT_DIR / "database_diagnostics_v2_interval_non_null_counts.csv"),
        "interval_non_null_counts_long_csv": str(OUT_DIR / "database_diagnostics_v2_interval_non_null_counts_long.csv"),
        "source_file_summary_csv": str(OUT_DIR / "database_diagnostics_v2_source_file_summary.csv"),
        "long_view_summary_csv": str(OUT_DIR / "database_diagnostics_v2_long_view_summary.csv"),
    }
}

with open(OUT_DIR / "database_diagnostics_v2_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\n=== Database Diagnostics V2 Complete ===")
print(json.dumps(summary, indent=2))