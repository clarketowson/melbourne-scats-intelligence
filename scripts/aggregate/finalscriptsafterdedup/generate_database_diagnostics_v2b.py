# generate_database_diagnostics_v2b.py

import json
import time
from pathlib import Path
from datetime import datetime

import duckdb
import pandas as pd


DB_PATHS = {
    "scats": r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb",
    "scats_continuation": r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb",
    "scats_recovery": r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb",
}

TABLE_NAME = "scats_detector_day"

OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\database_diagnostics")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_LIMIT = "40GB"
THREADS = 10
TEMP_DIR = r"A:\TrafficAnalytics\DATA\TEMP"


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


start_all = time.time()
errors = []
timings = []

coverage_rows = []
monthly_frames = []
yearly_frames = []
region_frames = []
interval_frames = []
source_frames = []

interval_columns = [f"v{i:02d}" for i in range(96)]


for db_name, db_path in DB_PATHS.items():
    print(f"\n==============================")
    print(f"Inspecting database: {db_name}")
    print(f"{db_path}")
    print(f"==============================")

    if not Path(db_path).exists():
        errors.append(f"{db_name}: database not found: {db_path}")
        continue

    con = duckdb.connect(db_path, read_only=True)
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    con.execute(f"SET threads={THREADS}")
    con.execute(f"SET temp_directory='{TEMP_DIR}'")
    con.execute("SET preserve_insertion_order=false")

    # 1. Overall coverage
    coverage_sql = f"""
    SELECT
        '{db_name}' AS database_name,
        MIN(count_date) AS min_count_date,
        MAX(count_date) AS max_count_date,
        COUNT(*) AS detector_day_rows,
        COUNT(DISTINCT scats_site) AS distinct_scats_sites,
        COUNT(DISTINCT detector) AS distinct_detectors,
        COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
        COUNT(DISTINCT DATE_TRUNC('month', count_date)) AS distinct_months,
        COUNT(DISTINCT count_date) AS distinct_dates,
        SUM(volume_24hour) AS total_volume_24hour_sum
    FROM {TABLE_NAME}
    """

    df, err, elapsed = safe_query(con, coverage_sql, f"{db_name}: overall coverage")
    timings.append({"database_name": db_name, "query": "overall_coverage", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        coverage_rows.append(df)

    # 2. Monthly coverage
    monthly_sql = f"""
    SELECT
        '{db_name}' AS database_name,
        STRFTIME(count_date, '%Y-%m') AS month_label,
        DATE_TRUNC('month', count_date) AS month_start,
        COUNT(*) AS detector_day_rows,
        COUNT(DISTINCT count_date) AS days_present,
        COUNT(DISTINCT scats_site) AS distinct_scats_sites,
        COUNT(DISTINCT detector) AS distinct_detectors,
        COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
        SUM(volume_24hour) AS total_volume_24hour_sum
    FROM {TABLE_NAME}
    GROUP BY 1, 2, 3
    ORDER BY 3
    """

    df, err, elapsed = safe_query(con, monthly_sql, f"{db_name}: monthly coverage")
    timings.append({"database_name": db_name, "query": "monthly_coverage", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        monthly_frames.append(df)

    # 3. Yearly coverage
    yearly_sql = f"""
    SELECT
        '{db_name}' AS database_name,
        EXTRACT(year FROM count_date)::INTEGER AS year,
        COUNT(*) AS detector_day_rows,
        COUNT(DISTINCT count_date) AS days_present,
        COUNT(DISTINCT DATE_TRUNC('month', count_date)) AS months_present,
        COUNT(DISTINCT scats_site) AS distinct_scats_sites,
        COUNT(DISTINCT detector) AS distinct_detectors,
        COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
        SUM(volume_24hour) AS total_volume_24hour_sum
    FROM {TABLE_NAME}
    GROUP BY 1, 2
    ORDER BY 2
    """

    df, err, elapsed = safe_query(con, yearly_sql, f"{db_name}: yearly coverage")
    timings.append({"database_name": db_name, "query": "yearly_coverage", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        yearly_frames.append(df)

    # 4. Region coverage
    region_sql = f"""
    SELECT
        '{db_name}' AS database_name,
        region_code,
        COUNT(*) AS detector_day_rows,
        COUNT(DISTINCT scats_site) AS distinct_scats_sites,
        COUNT(DISTINCT detector) AS distinct_detectors,
        COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
        MIN(count_date) AS min_count_date,
        MAX(count_date) AS max_count_date,
        SUM(volume_24hour) AS total_volume_24hour_sum
    FROM {TABLE_NAME}
    GROUP BY 1, 2
    ORDER BY detector_day_rows DESC
    """

    df, err, elapsed = safe_query(con, region_sql, f"{db_name}: region coverage")
    timings.append({"database_name": db_name, "query": "region_coverage", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        region_frames.append(df)

    # 5. Interval non-null structural check
    interval_exprs = ",\n        ".join([
        f"SUM(CASE WHEN {col} IS NOT NULL THEN 1 ELSE 0 END) AS {col}_non_null"
        for col in interval_columns
    ])

    interval_sql = f"""
    SELECT
        '{db_name}' AS database_name,
        COUNT(*) AS detector_day_rows,
        {interval_exprs}
    FROM {TABLE_NAME}
    """

    df, err, elapsed = safe_query(con, interval_sql, f"{db_name}: 96 interval non-null check")
    timings.append({"database_name": db_name, "query": "interval_non_null_check", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        interval_frames.append(df)

    # 6. Source file summary
    source_sql = f"""
    SELECT
        '{db_name}' AS database_name,
        source_file_id,
        COUNT(*) AS detector_day_rows,
        MIN(count_date) AS min_count_date,
        MAX(count_date) AS max_count_date,
        COUNT(DISTINCT scats_site) AS distinct_scats_sites,
        SUM(volume_24hour) AS total_volume_24hour_sum
    FROM {TABLE_NAME}
    GROUP BY 1, 2
    ORDER BY detector_day_rows DESC
    """

    df, err, elapsed = safe_query(con, source_sql, f"{db_name}: source file summary")
    timings.append({"database_name": db_name, "query": "source_file_summary", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        source_frames.append(df)

    con.close()


def concat_or_empty(frames):
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


coverage_df = concat_or_empty(coverage_rows)
monthly_df = concat_or_empty(monthly_frames)
yearly_df = concat_or_empty(yearly_frames)
region_df = concat_or_empty(region_frames)
interval_df = concat_or_empty(interval_frames)
source_df = concat_or_empty(source_frames)


coverage_df.to_csv(OUT_DIR / "database_diagnostics_v2b_coverage_summary_by_db.csv", index=False)
monthly_df.to_csv(OUT_DIR / "database_diagnostics_v2b_monthly_coverage_by_db.csv", index=False)
yearly_df.to_csv(OUT_DIR / "database_diagnostics_v2b_yearly_coverage_by_db.csv", index=False)
region_df.to_csv(OUT_DIR / "database_diagnostics_v2b_region_coverage_by_db.csv", index=False)
interval_df.to_csv(OUT_DIR / "database_diagnostics_v2b_interval_non_null_counts_by_db.csv", index=False)
source_df.to_csv(OUT_DIR / "database_diagnostics_v2b_source_file_summary_by_db.csv", index=False)


# Combined summaries
if not coverage_df.empty:
    combined_coverage = {
        "combined_detector_day_rows": int(coverage_df["detector_day_rows"].sum()),
        "combined_total_volume_24hour_sum": float(coverage_df["total_volume_24hour_sum"].sum()),
        "min_count_date": str(coverage_df["min_count_date"].min()),
        "max_count_date": str(coverage_df["max_count_date"].max()),
        "databases_processed": int(coverage_df["database_name"].nunique()),
    }
else:
    combined_coverage = {}


if not monthly_df.empty:
    monthly_combined = (
        monthly_df.groupby(["month_label", "month_start"], as_index=False)
        .agg(
            detector_day_rows=("detector_day_rows", "sum"),
            days_present=("days_present", "max"),
            distinct_scats_sites=("distinct_scats_sites", "sum"),
            distinct_detectors=("distinct_detectors", "sum"),
            distinct_site_detector_pairs=("distinct_site_detector_pairs", "sum"),
            total_volume_24hour_sum=("total_volume_24hour_sum", "sum"),
        )
        .sort_values("month_start")
    )
    monthly_combined.to_csv(
        OUT_DIR / "database_diagnostics_v2b_monthly_coverage_combined.csv",
        index=False
    )


if not yearly_df.empty:
    yearly_combined = (
        yearly_df.groupby("year", as_index=False)
        .agg(
            detector_day_rows=("detector_day_rows", "sum"),
            days_present=("days_present", "max"),
            months_present=("months_present", "max"),
            distinct_scats_sites=("distinct_scats_sites", "sum"),
            distinct_detectors=("distinct_detectors", "sum"),
            distinct_site_detector_pairs=("distinct_site_detector_pairs", "sum"),
            total_volume_24hour_sum=("total_volume_24hour_sum", "sum"),
        )
        .sort_values("year")
    )
    yearly_combined.to_csv(
        OUT_DIR / "database_diagnostics_v2b_yearly_coverage_combined.csv",
        index=False
    )


# Long interval coverage table
if not interval_df.empty:
    interval_long_rows = []

    for _, row in interval_df.iterrows():
        db_name = row["database_name"]
        total_rows = int(row["detector_day_rows"])

        for i in range(96):
            col = f"v{i:02d}_non_null"
            non_null = int(row[col])
            interval_long_rows.append({
                "database_name": db_name,
                "interval_index": i,
                "time_bin": f"{i // 4:02d}:{(i % 4) * 15:02d}",
                "non_null_count": non_null,
                "detector_day_rows": total_rows,
                "coverage_pct": (non_null / total_rows * 100) if total_rows else None,
            })

    interval_long_df = pd.DataFrame(interval_long_rows)
    interval_long_df.to_csv(
        OUT_DIR / "database_diagnostics_v2b_interval_non_null_counts_long_by_db.csv",
        index=False
    )

    interval_combined = (
        interval_long_df.groupby(["interval_index", "time_bin"], as_index=False)
        .agg(
            non_null_count=("non_null_count", "sum"),
            detector_day_rows=("detector_day_rows", "sum"),
        )
    )
    interval_combined["coverage_pct"] = (
        interval_combined["non_null_count"]
        / interval_combined["detector_day_rows"]
        * 100
    )
    interval_combined.to_csv(
        OUT_DIR / "database_diagnostics_v2b_interval_non_null_counts_combined.csv",
        index=False
    )


summary = {
    "metric_name": "database_diagnostics_v2b",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "table_name": TABLE_NAME,
    "databases_requested": len(DB_PATHS),
    "databases_processed": int(coverage_df["database_name"].nunique()) if not coverage_df.empty else 0,
    "total_elapsed_seconds": round(time.time() - start_all, 3),
    "combined_coverage": combined_coverage,
    "errors": errors,
    "timings": timings,
    "outputs": {
        "coverage_summary_by_db_csv": str(OUT_DIR / "database_diagnostics_v2b_coverage_summary_by_db.csv"),
        "monthly_coverage_by_db_csv": str(OUT_DIR / "database_diagnostics_v2b_monthly_coverage_by_db.csv"),
        "monthly_coverage_combined_csv": str(OUT_DIR / "database_diagnostics_v2b_monthly_coverage_combined.csv"),
        "yearly_coverage_by_db_csv": str(OUT_DIR / "database_diagnostics_v2b_yearly_coverage_by_db.csv"),
        "yearly_coverage_combined_csv": str(OUT_DIR / "database_diagnostics_v2b_yearly_coverage_combined.csv"),
        "region_coverage_by_db_csv": str(OUT_DIR / "database_diagnostics_v2b_region_coverage_by_db.csv"),
        "interval_non_null_counts_by_db_csv": str(OUT_DIR / "database_diagnostics_v2b_interval_non_null_counts_by_db.csv"),
        "interval_non_null_counts_long_by_db_csv": str(OUT_DIR / "database_diagnostics_v2b_interval_non_null_counts_long_by_db.csv"),
        "interval_non_null_counts_combined_csv": str(OUT_DIR / "database_diagnostics_v2b_interval_non_null_counts_combined.csv"),
        "source_file_summary_by_db_csv": str(OUT_DIR / "database_diagnostics_v2b_source_file_summary_by_db.csv"),
    }
}

with open(OUT_DIR / "database_diagnostics_v2b_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\n=== Database Diagnostics V2B Complete ===")
print(json.dumps(summary, indent=2))