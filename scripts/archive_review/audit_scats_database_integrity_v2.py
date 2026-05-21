from pathlib import Path
from datetime import datetime
import duckdb
import time

DB_PATH = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\scats_db_audit_v2")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY_PATH = OUT_DIR / "database_audit_summary.txt"

con = duckdb.connect(DB_PATH)

# Safer settings for very large audits
con.execute("SET threads=8;")
con.execute("SET memory_limit='20GB';")
con.execute(r"SET temp_directory='A:\TrafficAnalytics\DATA\TEMP';")
con.execute("SET preserve_insertion_order=false;")
con.execute("SET max_temp_directory_size='300GiB';")

queries = {
    "01_tables": """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """,

    "02_row_counts_by_table": """
        SELECT 'scats_15min_long' AS table_name, COUNT(*) AS row_count FROM scats_15min_long
        UNION ALL
        SELECT 'scats_detector_day', COUNT(*) FROM scats_detector_day
        UNION ALL
        SELECT 'scats_expected_date', COUNT(*) FROM scats_expected_date
        UNION ALL
        SELECT 'scats_missing_dates', COUNT(*) FROM scats_missing_dates
        UNION ALL
        SELECT 'scats_site', COUNT(*) FROM scats_site
        UNION ALL
        SELECT 'source_file', COUNT(*) FROM source_file
        ORDER BY table_name
    """,

    "03_main_date_range": """
        SELECT
            MIN(count_date) AS min_date,
            MAX(count_date) AS max_date,
            COUNT(DISTINCT count_date) AS distinct_dates
        FROM scats_15min_long
    """,

    "04_main_distinct_sites_detectors": """
        SELECT
            COUNT(DISTINCT scats_site) AS distinct_sites_in_main,
            COUNT(DISTINCT detector) AS distinct_detector_codes,
            COUNT(DISTINCT source_file_id) AS distinct_source_files_in_main
        FROM scats_15min_long
    """,

    "05_null_check_main": """
        SELECT
            SUM(CASE WHEN scats_site IS NULL THEN 1 ELSE 0 END) AS null_scats_site,
            SUM(CASE WHEN count_date IS NULL THEN 1 ELSE 0 END) AS null_count_date,
            SUM(CASE WHEN detector IS NULL THEN 1 ELSE 0 END) AS null_detector,
            SUM(CASE WHEN interval_index IS NULL THEN 1 ELSE 0 END) AS null_interval_index,
            SUM(CASE WHEN time_bin IS NULL THEN 1 ELSE 0 END) AS null_time_bin,
            SUM(CASE WHEN volume_15m IS NULL THEN 1 ELSE 0 END) AS null_volume_15m,
            SUM(CASE WHEN source_file_id IS NULL THEN 1 ELSE 0 END) AS null_source_file_id
        FROM scats_15min_long
    """,

    # Much cheaper first-pass duplicate signal:
    # compare total rows against distinct composite keys using concatenation
    "06_duplicate_row_excess_estimate": """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT
                CAST(scats_site AS VARCHAR) || '|' ||
                CAST(count_date AS VARCHAR) || '|' ||
                CAST(detector AS VARCHAR) || '|' ||
                CAST(interval_index AS VARCHAR)
            ) AS distinct_composite_keys,
            COUNT(*) -
            COUNT(DISTINCT
                CAST(scats_site AS VARCHAR) || '|' ||
                CAST(count_date AS VARCHAR) || '|' ||
                CAST(detector AS VARCHAR) || '|' ||
                CAST(interval_index AS VARCHAR)
            ) AS duplicate_row_excess
        FROM scats_15min_long
    """,

    # Small sample of actual duplicate groups, if any
    "07_duplicate_groups_sample": """
        SELECT
            scats_site,
            count_date,
            detector,
            interval_index,
            COUNT(*) AS c
        FROM scats_15min_long
        GROUP BY scats_site, count_date, detector, interval_index
        HAVING COUNT(*) > 1
        ORDER BY c DESC, count_date, scats_site, detector, interval_index
        LIMIT 100
    """,

    "08_interval_index_range": """
        SELECT
            MIN(interval_index) AS min_interval_index,
            MAX(interval_index) AS max_interval_index,
            COUNT(DISTINCT interval_index) AS distinct_interval_indexes
        FROM scats_15min_long
    """,

    "09_bad_interval_index_rows": """
        SELECT COUNT(*) AS bad_interval_rows
        FROM scats_15min_long
        WHERE interval_index NOT BETWEEN 1 AND 96
           OR interval_index IS NULL
    """,

    "10_time_bin_coverage": """
        SELECT
            COUNT(DISTINCT time_bin) AS distinct_time_bins,
            MIN(time_bin) AS min_time_bin,
            MAX(time_bin) AS max_time_bin
        FROM scats_15min_long
    """,

    "11_time_bin_values": """
        SELECT time_bin, COUNT(*) AS rows
        FROM scats_15min_long
        GROUP BY time_bin
        ORDER BY time_bin
    """,

    "12_volume_distribution": """
        SELECT
            MIN(volume_15m) AS min_volume,
            MAX(volume_15m) AS max_volume,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows,
            SUM(CASE WHEN volume_15m = 0 THEN 1 ELSE 0 END) AS zero_rows,
            SUM(CASE WHEN volume_15m > 0 THEN 1 ELSE 0 END) AS positive_rows
        FROM scats_15min_long
    """,

    "13_negative_value_frequency_top_20": """
        SELECT volume_15m, COUNT(*) AS rows
        FROM scats_15min_long
        WHERE volume_15m < 0
        GROUP BY volume_15m
        ORDER BY rows DESC
        LIMIT 20
    """,

    "14_daily_row_counts": """
        SELECT
            count_date,
            COUNT(*) AS rows,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows
        FROM scats_15min_long
        GROUP BY count_date
        ORDER BY count_date
    """,

    "15_daily_row_count_lowest_30": """
        SELECT
            count_date,
            COUNT(*) AS rows,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows
        FROM scats_15min_long
        GROUP BY count_date
        ORDER BY rows ASC, count_date
        LIMIT 30
    """,

    "16_daily_row_count_highest_30": """
        SELECT
            count_date,
            COUNT(*) AS rows,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows
        FROM scats_15min_long
        GROUP BY count_date
        ORDER BY rows DESC, count_date
        LIMIT 30
    """,

    "17_missing_dates_table": """
        SELECT *
        FROM scats_missing_dates
        ORDER BY count_date
    """,

    "18_expected_dates_vs_actual": """
        SELECT
            (SELECT COUNT(*) FROM scats_expected_date) AS expected_dates,
            (SELECT COUNT(DISTINCT count_date) FROM scats_15min_long) AS actual_dates,
            (SELECT COUNT(*) FROM scats_missing_dates) AS missing_dates
    """,

    "19_orphan_sites_in_main": """
        SELECT COUNT(DISTINCT m.scats_site) AS orphan_sites
        FROM scats_15min_long m
        LEFT JOIN scats_site s
          ON m.scats_site = s.scats_site
        WHERE s.scats_site IS NULL
    """,

    "20_orphan_source_files_in_main": """
        SELECT COUNT(DISTINCT m.source_file_id) AS orphan_source_files
        FROM scats_15min_long m
        LEFT JOIN source_file f
          ON m.source_file_id = f.source_file_id
        WHERE f.source_file_id IS NULL
    """,

    "21_main_sites_not_in_metadata_top_50": """
        SELECT DISTINCT m.scats_site
        FROM scats_15min_long m
        LEFT JOIN scats_site s
          ON m.scats_site = s.scats_site
        WHERE s.scats_site IS NULL
        ORDER BY m.scats_site
        LIMIT 50
    """,

    "22_source_file_usage_top_50": """
        SELECT
            source_file_id,
            COUNT(*) AS rows
        FROM scats_15min_long
        GROUP BY source_file_id
        ORDER BY rows DESC
        LIMIT 50
    """,

    "23_detector_day_date_range": """
        SELECT
            MIN(count_date) AS min_date,
            MAX(count_date) AS max_date,
            COUNT(*) AS rows
        FROM scats_detector_day
    """,

    "24_detector_day_duplicate_excess_estimate": """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT
                CAST(scats_site AS VARCHAR) || '|' ||
                CAST(count_date AS VARCHAR) || '|' ||
                CAST(detector AS VARCHAR)
            ) AS distinct_composite_keys,
            COUNT(*) -
            COUNT(DISTINCT
                CAST(scats_site AS VARCHAR) || '|' ||
                CAST(count_date AS VARCHAR) || '|' ||
                CAST(detector AS VARCHAR)
            ) AS duplicate_row_excess
        FROM scats_detector_day
    """,

    "25_detector_day_nulls": """
        SELECT
            SUM(CASE WHEN scats_site IS NULL THEN 1 ELSE 0 END) AS null_scats_site,
            SUM(CASE WHEN count_date IS NULL THEN 1 ELSE 0 END) AS null_count_date,
            SUM(CASE WHEN detector IS NULL THEN 1 ELSE 0 END) AS null_detector
        FROM scats_detector_day
    """,

    "26_summary_signal": """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT count_date) AS distinct_dates,
            COUNT(DISTINCT scats_site) AS distinct_sites,
            SUM(CASE WHEN volume_15m >= 0 THEN 1 ELSE 0 END) AS non_negative_rows,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows
        FROM scats_15min_long
    """
}

summary_lines = [
    f"Run timestamp: {datetime.now().isoformat()}",
    f"Database: {DB_PATH}",
    "",
    "Purpose: SCATS database integrity audit after continuation ingest.",
    "Settings:",
    "  threads=8",
    "  memory_limit=20GB",
    r"  temp_directory=A:\TrafficAnalytics\DATA\TEMP",
    "  preserve_insertion_order=false",
    "  max_temp_directory_size=300GiB",
    ""
]

def save_query(name: str, sql: str):
    output_csv = OUT_DIR / f"{name}.csv"
    start = time.perf_counter()

    try:
        copy_sql = f"""
            COPY (
                {sql}
            ) TO '{output_csv.as_posix()}' (HEADER, DELIMITER ',');
        """
        con.execute(copy_sql)

        preview = con.execute(sql).fetchmany(15)
        cols = [d[0] for d in con.description]
        elapsed = time.perf_counter() - start

        summary_lines.append(f"=== {name} ===")
        summary_lines.append(f"Saved: {output_csv}")
        summary_lines.append(f"Elapsed seconds: {elapsed:.3f}")
        summary_lines.append("Columns: " + ", ".join(cols))
        for row in preview:
            summary_lines.append(str(row))
        summary_lines.append("")
    except Exception as e:
        elapsed = time.perf_counter() - start
        summary_lines.append(f"=== {name} ===")
        summary_lines.append(f"FAILED after {elapsed:.3f} seconds")
        summary_lines.append(str(e))
        summary_lines.append("")
        print(f"FAILED: {name}")
        print(e)

for name, sql in queries.items():
    print(f"Running: {name}")
    save_query(name, sql)

summary_lines.append("=== audit_verdict ===")

try:
    main_summary = con.execute("""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT count_date) AS distinct_dates,
            COUNT(DISTINCT scats_site) AS distinct_sites,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows
        FROM scats_15min_long
    """).fetchone()

    dup_excess = con.execute("""
        SELECT
            COUNT(*) -
            COUNT(DISTINCT
                CAST(scats_site AS VARCHAR) || '|' ||
                CAST(count_date AS VARCHAR) || '|' ||
                CAST(detector AS VARCHAR) || '|' ||
                CAST(interval_index AS VARCHAR)
            ) AS duplicate_row_excess
        FROM scats_15min_long
    """).fetchone()[0]

    bad_intervals = con.execute("""
        SELECT COUNT(*)
        FROM scats_15min_long
        WHERE interval_index NOT BETWEEN 1 AND 96
           OR interval_index IS NULL
    """).fetchone()[0]

    orphan_sites = con.execute("""
        SELECT COUNT(DISTINCT m.scats_site)
        FROM scats_15min_long m
        LEFT JOIN scats_site s
          ON m.scats_site = s.scats_site
        WHERE s.scats_site IS NULL
    """).fetchone()[0]

    orphan_files = con.execute("""
        SELECT COUNT(DISTINCT m.source_file_id)
        FROM scats_15min_long m
        LEFT JOIN source_file f
          ON m.source_file_id = f.source_file_id
        WHERE f.source_file_id IS NULL
    """).fetchone()[0]

    missing_dates = con.execute("""
        SELECT COUNT(*) FROM scats_missing_dates
    """).fetchone()[0]

    summary_lines.append(f"total_rows={main_summary[0]:,}")
    summary_lines.append(f"distinct_dates={main_summary[1]:,}")
    summary_lines.append(f"distinct_sites={main_summary[2]:,}")
    summary_lines.append(f"negative_rows={main_summary[3]:,}")
    summary_lines.append(f"duplicate_row_excess={dup_excess:,}")
    summary_lines.append(f"bad_interval_rows={bad_intervals:,}")
    summary_lines.append(f"orphan_sites={orphan_sites:,}")
    summary_lines.append(f"orphan_source_files={orphan_files:,}")
    summary_lines.append(f"missing_dates_table_rows={missing_dates:,}")
    summary_lines.append("")

    issues = []
    if dup_excess > 0:
        issues.append(f"{dup_excess:,} duplicate-row excess in main table")
    if bad_intervals > 0:
        issues.append(f"{bad_intervals:,} rows with invalid interval_index")
    if orphan_sites > 0:
        issues.append(f"{orphan_sites:,} orphan sites not found in scats_site")
    if orphan_files > 0:
        issues.append(f"{orphan_files:,} orphan source_file_ids not found in source_file")
    if missing_dates > 0:
        issues.append(f"{missing_dates:,} rows present in scats_missing_dates")

    if issues:
        summary_lines.append("Potential issues detected:")
        for issue in issues:
            summary_lines.append(f"- {issue}")
    else:
        summary_lines.append("No major structural integrity issues detected by this audit.")

except Exception as e:
    summary_lines.append("Verdict generation failed:")
    summary_lines.append(str(e))

summary_lines.append("")
summary_lines.append("Recommended next manual checks:")
summary_lines.append("- Review 15_daily_row_count_lowest_30.csv for likely partial-ingest or failed-date days.")
summary_lines.append("- Review 13_negative_value_frequency_top_20.csv to confirm sentinel values remain expected.")
summary_lines.append("- Review 17_missing_dates_table.csv against known failed CSV files.")
summary_lines.append("- Review 21_main_sites_not_in_metadata_top_50.csv if orphan site count is non-zero.")
summary_lines.append("- Review 07_duplicate_groups_sample.csv only if duplicate_row_excess is above zero.")

con.close()

SUMMARY_PATH.write_text("\n".join(summary_lines), encoding="utf-8")

print("")
print(f"Done. Audit outputs saved to: {OUT_DIR}")
print(f"Summary saved to: {SUMMARY_PATH}")