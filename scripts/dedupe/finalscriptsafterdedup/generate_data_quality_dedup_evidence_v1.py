# generate_data_quality_dedup_evidence_v1.py

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

OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\data_quality")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_LIMIT = "50GB"
THREADS = 10
TEMP_DIR = r"A:\TrafficAnalytics\DATA\TEMP"

INTERVAL_COLS = [f"v{i:02d}" for i in range(96)]


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


def concat_or_empty(frames):
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


start_all = time.time()
errors = []
timings = []

db_summary_frames = []
interval_quality_frames = []
duplicate_key_frames = []
monthly_quality_frames = []
site_detector_frames = []


for db_name, db_path in DB_PATHS.items():
    print("\n==============================")
    print(f"Data Quality Scan: {db_name}")
    print(db_path)
    print("==============================")

    if not Path(db_path).exists():
        errors.append(f"{db_name}: database not found: {db_path}")
        continue

    con = duckdb.connect(db_path, read_only=True)
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    con.execute(f"SET threads={THREADS}")
    con.execute(f"SET temp_directory='{TEMP_DIR}'")
    con.execute("SET preserve_insertion_order=false")

    # ------------------------------------------------------------
    # 1. Database contribution summary
    # ------------------------------------------------------------

    db_summary_sql = f"""
    SELECT
        '{db_name}' AS database_name,
        COUNT(*) AS detector_day_rows,
        MIN(count_date) AS min_count_date,
        MAX(count_date) AS max_count_date,
        COUNT(DISTINCT count_date) AS distinct_dates,
        COUNT(DISTINCT STRFTIME(count_date, '%Y-%m')) AS distinct_months,
        COUNT(DISTINCT scats_site) AS distinct_scats_sites,
        COUNT(DISTINCT detector) AS distinct_detectors,
        COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
        SUM(volume_24hour) AS total_volume_24hour_sum
    FROM {TABLE_NAME}
    """

    df, err, elapsed = safe_query(con, db_summary_sql, f"{db_name}: database contribution summary")
    timings.append({"database_name": db_name, "query": "database_contribution_summary", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        db_summary_frames.append(df)

    # ------------------------------------------------------------
    # 2. Interval quality: nulls, negative/sentinel values
    # ------------------------------------------------------------

    null_exprs = ",\n        ".join([
        f"SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) AS {c}_null_count"
        for c in INTERVAL_COLS
    ])

    negative_exprs = ",\n        ".join([
        f"SUM(CASE WHEN {c} < 0 THEN 1 ELSE 0 END) AS {c}_negative_count"
        for c in INTERVAL_COLS
    ])

    sentinel_exprs = ",\n        ".join([
        f"SUM(CASE WHEN {c} IN (-1, -2, -3, -4, -5, -9, -99, -999) THEN 1 ELSE 0 END) AS {c}_sentinel_count"
        for c in INTERVAL_COLS
    ])

    interval_quality_sql = f"""
    SELECT
        '{db_name}' AS database_name,
        COUNT(*) AS detector_day_rows,
        {null_exprs},
        {negative_exprs},
        {sentinel_exprs}
    FROM {TABLE_NAME}
    """

    df, err, elapsed = safe_query(con, interval_quality_sql, f"{db_name}: interval null/negative/sentinel scan")
    timings.append({"database_name": db_name, "query": "interval_quality_scan", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        interval_quality_frames.append(df)

    # ------------------------------------------------------------
    # 3. Duplicate detector-day key evidence
    # Key assumption: one row should exist per scats_site + detector + count_date
    # ------------------------------------------------------------

    duplicate_sql = f"""
    WITH key_counts AS (
        SELECT
            scats_site,
            detector,
            count_date,
            COUNT(*) AS key_count
        FROM {TABLE_NAME}
        GROUP BY 1, 2, 3
        HAVING COUNT(*) > 1
    )
    SELECT
        '{db_name}' AS database_name,
        COUNT(*) AS duplicate_keys,
        SUM(key_count) AS duplicate_rows_involved,
        MAX(key_count) AS max_rows_for_single_key
    FROM key_counts
    """

    df, err, elapsed = safe_query(con, duplicate_sql, f"{db_name}: duplicate detector-day key summary")
    timings.append({"database_name": db_name, "query": "duplicate_detector_day_key_summary", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        duplicate_key_frames.append(df)

    # ------------------------------------------------------------
    # 4. Monthly quality and anomaly indicators
    # ------------------------------------------------------------

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
        SUM(volume_24hour) AS total_volume_24hour_sum,
        AVG(volume_24hour) AS avg_volume_24hour_per_detector_day,
        MIN(volume_24hour) AS min_volume_24hour,
        MAX(volume_24hour) AS max_volume_24hour
    FROM {TABLE_NAME}
    GROUP BY 1, 2, 3
    ORDER BY 3
    """

    df, err, elapsed = safe_query(con, monthly_sql, f"{db_name}: monthly quality summary")
    timings.append({"database_name": db_name, "query": "monthly_quality_summary", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        monthly_quality_frames.append(df)

    # ------------------------------------------------------------
    # 5. Site-detector stability summary
    # ------------------------------------------------------------

    site_detector_sql = f"""
    WITH sd AS (
        SELECT
            scats_site,
            detector,
            MIN(count_date) AS first_seen,
            MAX(count_date) AS last_seen,
            COUNT(DISTINCT count_date) AS active_days,
            COUNT(*) AS detector_day_rows,
            SUM(volume_24hour) AS total_volume_24hour_sum
        FROM {TABLE_NAME}
        GROUP BY 1, 2
    )
    SELECT
        '{db_name}' AS database_name,
        COUNT(*) AS site_detector_pairs,
        AVG(active_days) AS avg_active_days,
        MEDIAN(active_days) AS median_active_days,
        MAX(active_days) AS max_active_days,
        MIN(active_days) AS min_active_days,
        SUM(detector_day_rows) AS detector_day_rows,
        SUM(total_volume_24hour_sum) AS total_volume_24hour_sum
    FROM sd
    """

    df, err, elapsed = safe_query(con, site_detector_sql, f"{db_name}: site-detector stability summary")
    timings.append({"database_name": db_name, "query": "site_detector_stability_summary", "elapsed_seconds": elapsed})
    if err:
        errors.append(err)
    else:
        site_detector_frames.append(df)

    con.close()


# ------------------------------------------------------------
# Combine outputs
# ------------------------------------------------------------

db_summary = concat_or_empty(db_summary_frames)
interval_quality = concat_or_empty(interval_quality_frames)
duplicate_keys = concat_or_empty(duplicate_key_frames)
monthly_quality = concat_or_empty(monthly_quality_frames)
site_detector = concat_or_empty(site_detector_frames)


db_summary.to_csv(OUT_DIR / "data_quality_v1_database_contribution_summary.csv", index=False)
interval_quality.to_csv(OUT_DIR / "data_quality_v1_interval_quality_wide_by_db.csv", index=False)
duplicate_keys.to_csv(OUT_DIR / "data_quality_v1_duplicate_detector_day_keys_by_db.csv", index=False)
monthly_quality.to_csv(OUT_DIR / "data_quality_v1_monthly_quality_by_db.csv", index=False)
site_detector.to_csv(OUT_DIR / "data_quality_v1_site_detector_stability_by_db.csv", index=False)


# ------------------------------------------------------------
# Convert interval quality wide result to long format
# ------------------------------------------------------------

interval_long_rows = []

if not interval_quality.empty:
    for _, row in interval_quality.iterrows():
        db_name = row["database_name"]
        detector_day_rows = int(row["detector_day_rows"])

        for i, col in enumerate(INTERVAL_COLS):
            null_count = int(row[f"{col}_null_count"])
            negative_count = int(row[f"{col}_negative_count"])
            sentinel_count = int(row[f"{col}_sentinel_count"])

            interval_long_rows.append({
                "database_name": db_name,
                "interval_index": i,
                "time_bin": f"{i // 4:02d}:{(i % 4) * 15:02d}",
                "interval_column": col,
                "detector_day_rows": detector_day_rows,
                "null_count": null_count,
                "negative_count": negative_count,
                "sentinel_count": sentinel_count,
                "null_pct": null_count / detector_day_rows * 100 if detector_day_rows else None,
                "negative_pct": negative_count / detector_day_rows * 100 if detector_day_rows else None,
                "sentinel_pct": sentinel_count / detector_day_rows * 100 if detector_day_rows else None,
            })

interval_long = pd.DataFrame(interval_long_rows)
interval_long.to_csv(OUT_DIR / "data_quality_v1_interval_quality_long_by_db.csv", index=False)

if not interval_long.empty:
    interval_combined = (
        interval_long.groupby(["interval_index", "time_bin", "interval_column"], as_index=False)
        .agg(
            detector_day_rows=("detector_day_rows", "sum"),
            null_count=("null_count", "sum"),
            negative_count=("negative_count", "sum"),
            sentinel_count=("sentinel_count", "sum"),
        )
    )

    interval_combined["null_pct"] = interval_combined["null_count"] / interval_combined["detector_day_rows"] * 100
    interval_combined["negative_pct"] = interval_combined["negative_count"] / interval_combined["detector_day_rows"] * 100
    interval_combined["sentinel_pct"] = interval_combined["sentinel_count"] / interval_combined["detector_day_rows"] * 100

    interval_combined.to_csv(
        OUT_DIR / "data_quality_v1_interval_quality_combined.csv",
        index=False
    )


# ------------------------------------------------------------
# Combined monthly quality
# ------------------------------------------------------------

if not monthly_quality.empty:
    monthly_combined = (
        monthly_quality.groupby(["month_label", "month_start"], as_index=False)
        .agg(
            detector_day_rows=("detector_day_rows", "sum"),
            days_present=("days_present", "max"),
            distinct_scats_sites=("distinct_scats_sites", "sum"),
            distinct_detectors=("distinct_detectors", "sum"),
            distinct_site_detector_pairs=("distinct_site_detector_pairs", "sum"),
            total_volume_24hour_sum=("total_volume_24hour_sum", "sum"),
            avg_volume_24hour_per_detector_day=("avg_volume_24hour_per_detector_day", "mean"),
            min_volume_24hour=("min_volume_24hour", "min"),
            max_volume_24hour=("max_volume_24hour", "max"),
        )
        .sort_values("month_start")
    )

    # Simple anomaly score using detector-day rows
    mean_rows = monthly_combined["detector_day_rows"].mean()
    std_rows = monthly_combined["detector_day_rows"].std()

    if std_rows and std_rows > 0:
        monthly_combined["detector_day_rows_zscore"] = (
            monthly_combined["detector_day_rows"] - mean_rows
        ) / std_rows
    else:
        monthly_combined["detector_day_rows_zscore"] = 0

    monthly_combined["low_row_count_flag"] = monthly_combined["detector_day_rows_zscore"] < -2
    monthly_combined["high_row_count_flag"] = monthly_combined["detector_day_rows_zscore"] > 2

    monthly_combined.to_csv(
        OUT_DIR / "data_quality_v1_monthly_quality_combined.csv",
        index=False
    )


# ------------------------------------------------------------
# Combined duplicate summary
# ------------------------------------------------------------

combined_duplicate_summary = {}

if not duplicate_keys.empty:
    duplicate_keys["duplicate_keys"] = duplicate_keys["duplicate_keys"].fillna(0)
    duplicate_keys["duplicate_rows_involved"] = duplicate_keys["duplicate_rows_involved"].fillna(0)
    duplicate_keys["max_rows_for_single_key"] = duplicate_keys["max_rows_for_single_key"].fillna(0)

    combined_duplicate_summary = {
        "duplicate_keys": int(duplicate_keys["duplicate_keys"].sum()),
        "duplicate_rows_involved": int(duplicate_keys["duplicate_rows_involved"].sum()),
        "max_rows_for_single_key": int(duplicate_keys["max_rows_for_single_key"].max()),
    }


# ------------------------------------------------------------
# Summary JSON
# ------------------------------------------------------------

combined_interval_summary = {}

if not interval_long.empty:
    combined_interval_summary = {
        "total_null_interval_cells": int(interval_long["null_count"].sum()),
        "total_negative_interval_cells": int(interval_long["negative_count"].sum()),
        "total_sentinel_interval_cells": int(interval_long["sentinel_count"].sum()),
        "max_interval_null_pct": float(interval_long["null_pct"].max()),
        "max_interval_negative_pct": float(interval_long["negative_pct"].max()),
        "max_interval_sentinel_pct": float(interval_long["sentinel_pct"].max()),
    }

combined_db_summary = {}

if not db_summary.empty:
    combined_db_summary = {
        "detector_day_rows": int(db_summary["detector_day_rows"].sum()),
        "total_volume_24hour_sum": float(db_summary["total_volume_24hour_sum"].sum()),
        "min_count_date": str(db_summary["min_count_date"].min()),
        "max_count_date": str(db_summary["max_count_date"].max()),
        "databases_processed": int(db_summary["database_name"].nunique()),
    }

summary = {
    "metric_name": "data_quality_dedup_evidence_v1",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "table_name": TABLE_NAME,
    "databases_requested": len(DB_PATHS),
    "databases_processed": int(db_summary["database_name"].nunique()) if not db_summary.empty else 0,
    "total_elapsed_seconds": round(time.time() - start_all, 3),
    "errors": errors,
    "timings": timings,
    "combined_database_summary": combined_db_summary,
    "combined_duplicate_summary": combined_duplicate_summary,
    "combined_interval_quality_summary": combined_interval_summary,
    "outputs": {
        "database_contribution_summary_csv": str(OUT_DIR / "data_quality_v1_database_contribution_summary.csv"),
        "interval_quality_wide_by_db_csv": str(OUT_DIR / "data_quality_v1_interval_quality_wide_by_db.csv"),
        "interval_quality_long_by_db_csv": str(OUT_DIR / "data_quality_v1_interval_quality_long_by_db.csv"),
        "interval_quality_combined_csv": str(OUT_DIR / "data_quality_v1_interval_quality_combined.csv"),
        "duplicate_detector_day_keys_by_db_csv": str(OUT_DIR / "data_quality_v1_duplicate_detector_day_keys_by_db.csv"),
        "monthly_quality_by_db_csv": str(OUT_DIR / "data_quality_v1_monthly_quality_by_db.csv"),
        "monthly_quality_combined_csv": str(OUT_DIR / "data_quality_v1_monthly_quality_combined.csv"),
        "site_detector_stability_by_db_csv": str(OUT_DIR / "data_quality_v1_site_detector_stability_by_db.csv"),
        "summary_json": str(OUT_DIR / "data_quality_v1_summary.json"),
    }
}

with open(OUT_DIR / "data_quality_v1_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\n=== Data Quality & Deduplication Evidence V1 Complete ===")
print(json.dumps(summary, indent=2))