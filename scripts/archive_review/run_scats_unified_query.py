#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb


DEFAULT_ORIGINAL_DB = Path(r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb")
DEFAULT_CONTINUATION_DB = Path(r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb")
DEFAULT_RECOVERY_DB = Path(r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb")
DEFAULT_TEMP_DIR = Path(r"C:\TrafficAnalyticsTemp")


def parse_args():
    p = argparse.ArgumentParser(
        description="Attach SCATS DBs in place, create unified deduped views, and optionally run a query."
    )
    p.add_argument("--original-db", type=Path, default=DEFAULT_ORIGINAL_DB)
    p.add_argument("--continuation-db", type=Path, default=DEFAULT_CONTINUATION_DB)
    p.add_argument("--recovery-db", type=Path, default=DEFAULT_RECOVERY_DB)
    p.add_argument("--temp-dir", type=Path, default=DEFAULT_TEMP_DIR)

    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--memory-limit", default="48GB")
    p.add_argument("--max-temp-directory-size", default="170GiB")

    p.add_argument("--query-file", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--summary-only", action="store_true")

    return p.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def configure_duckdb(con, args):
    temp_dir = str(args.temp_dir)

    con.execute(f"PRAGMA threads={args.threads}")
    con.execute(f"PRAGMA memory_limit='{args.memory_limit}'")
    con.execute(f"PRAGMA temp_directory='{temp_dir}'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET max_temp_directory_size='{args.max_temp_directory_size}'")


def attach_databases(con, args):
    con.execute(f"ATTACH '{args.original_db}' AS orig")
    con.execute(f"ATTACH '{args.continuation_db}' AS cont")
    con.execute(f"ATTACH '{args.recovery_db}' AS rec")


def validate_required_objects(con) -> None:
    checks = [
        ("orig.scats_detector_day", "SELECT 1 FROM orig.scats_detector_day LIMIT 1"),
        ("orig.scats_clean", "SELECT 1 FROM orig.scats_clean LIMIT 1"),
        ("cont.scats_detector_day", "SELECT 1 FROM cont.scats_detector_day LIMIT 1"),
        ("cont.scats_clean", "SELECT 1 FROM cont.scats_clean LIMIT 1"),
        ("rec.scats_detector_day", "SELECT 1 FROM rec.scats_detector_day LIMIT 1"),
        ("rec.scats_clean", "SELECT 1 FROM rec.scats_clean LIMIT 1"),
    ]
    for label, sql in checks:
        try:
            con.execute(sql)
        except Exception as e:
            raise RuntimeError(f"Required object missing or unreadable: {label}: {e}") from e


def create_unified_views(con):
    con.execute("""
    CREATE OR REPLACE TEMP VIEW scats_all_detector_day_union AS

    SELECT
        scats_site, count_date, detector,
        region_code, ct_records, volume_24hour, alarm_24hour, source_file_id,
        v00, v01, v02, v03, v04, v05, v06, v07, v08, v09,
        v10, v11, v12, v13, v14, v15, v16, v17, v18, v19,
        v20, v21, v22, v23, v24, v25, v26, v27, v28, v29,
        v30, v31, v32, v33, v34, v35, v36, v37, v38, v39,
        v40, v41, v42, v43, v44, v45, v46, v47, v48, v49,
        v50, v51, v52, v53, v54, v55, v56, v57, v58, v59,
        v60, v61, v62, v63, v64, v65, v66, v67, v68, v69,
        v70, v71, v72, v73, v74, v75, v76, v77, v78, v79,
        v80, v81, v82, v83, v84, v85, v86, v87, v88, v89,
        v90, v91, v92, v93, v94, v95,
        2 AS source_priority,
        'orig' AS source_db
    FROM orig.scats_detector_day

    UNION ALL

    SELECT
        scats_site, count_date, detector,
        region_code, ct_records, volume_24hour, alarm_24hour, source_file_id,
        v00, v01, v02, v03, v04, v05, v06, v07, v08, v09,
        v10, v11, v12, v13, v14, v15, v16, v17, v18, v19,
        v20, v21, v22, v23, v24, v25, v26, v27, v28, v29,
        v30, v31, v32, v33, v34, v35, v36, v37, v38, v39,
        v40, v41, v42, v43, v44, v45, v46, v47, v48, v49,
        v50, v51, v52, v53, v54, v55, v56, v57, v58, v59,
        v60, v61, v62, v63, v64, v65, v66, v67, v68, v69,
        v70, v71, v72, v73, v74, v75, v76, v77, v78, v79,
        v80, v81, v82, v83, v84, v85, v86, v87, v88, v89,
        v90, v91, v92, v93, v94, v95,
        3 AS source_priority,
        'cont' AS source_db
    FROM cont.scats_detector_day

    UNION ALL

    SELECT
        scats_site, count_date, detector,
        region_code, ct_records, volume_24hour, alarm_24hour, source_file_id,
        v00, v01, v02, v03, v04, v05, v06, v07, v08, v09,
        v10, v11, v12, v13, v14, v15, v16, v17, v18, v19,
        v20, v21, v22, v23, v24, v25, v26, v27, v28, v29,
        v30, v31, v32, v33, v34, v35, v36, v37, v38, v39,
        v40, v41, v42, v43, v44, v45, v46, v47, v48, v49,
        v50, v51, v52, v53, v54, v55, v56, v57, v58, v59,
        v60, v61, v62, v63, v64, v65, v66, v67, v68, v69,
        v70, v71, v72, v73, v74, v75, v76, v77, v78, v79,
        v80, v81, v82, v83, v84, v85, v86, v87, v88, v89,
        v90, v91, v92, v93, v94, v95,
        1 AS source_priority,
        'rec' AS source_db
    FROM rec.scats_detector_day
    """)

    con.execute("""
    CREATE OR REPLACE TEMP VIEW scats_all_detector_day_dedup AS

    SELECT *
    EXCLUDE rn

    FROM (
        SELECT *,
            ROW_NUMBER() OVER (
                PARTITION BY
                    scats_site,
                    count_date,
                    detector
                ORDER BY source_priority, source_db
            ) AS rn
        FROM scats_all_detector_day_union
    )

    WHERE rn = 1
    """)

    con.execute("""
    CREATE OR REPLACE TEMP VIEW scats_all_clean_union AS

    SELECT
        scats_site, count_date, detector, region_code, source_file_id,
        interval_index, time_bin, volume_15m,
        2 AS source_priority,
        'orig' AS source_db
    FROM orig.scats_clean

    UNION ALL

    SELECT
        scats_site, count_date, detector, region_code, source_file_id,
        interval_index, time_bin, volume_15m,
        3 AS source_priority,
        'cont' AS source_db
    FROM cont.scats_clean

    UNION ALL

    SELECT
        scats_site, count_date, detector, region_code, source_file_id,
        interval_index, time_bin, volume_15m,
        1 AS source_priority,
        'rec' AS source_db
    FROM rec.scats_clean
    """)

    con.execute("""
    CREATE OR REPLACE TEMP VIEW scats_all_clean_dedup AS

    SELECT *
    EXCLUDE rn

    FROM (
        SELECT *,
            ROW_NUMBER() OVER (
                PARTITION BY
                    scats_site,
                    count_date,
                    detector,
                    interval_index
                ORDER BY source_priority, source_db
            ) AS rn
        FROM scats_all_clean_union
    )

    WHERE rn = 1
    """)


def print_summary(con):
    print("\n=== Unified Clean Summary ===")

    row = con.execute("""
        SELECT
            COUNT(*) AS rows,
            COUNT(*) FILTER (WHERE volume_15m IS NULL) AS null_rows,
            COUNT(*) FILTER (WHERE volume_15m < 0) AS negative_rows,
            MIN(count_date) AS min_date,
            MAX(count_date) AS max_date
        FROM scats_all_clean_dedup
    """).fetchone()

    print(f"rows          = {row[0]}")
    print(f"null_rows     = {row[1]}")
    print(f"negative_rows = {row[2]}")
    print(f"min_date      = {row[3]}")
    print(f"max_date      = {row[4]}")


def run_query(con, args):
    if not args.query_file:
        return

    if not args.query_file.exists():
        raise FileNotFoundError(f"Query file not found: {args.query_file}")

    sql = args.query_file.read_text(encoding="utf-8")
    df = con.execute(sql).fetchdf()

    if df.empty:
        print("\nQuery returned 0 rows.")
    else:
        print("\n=== Query Result (top 10 rows) ===")
        print(df.head(10).to_string(index=False))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)

        if args.output.suffix.lower() == ".csv":
            df.to_csv(args.output, index=False)
        elif args.output.suffix.lower() == ".parquet":
            df.to_parquet(args.output, index=False)
        else:
            raise ValueError("Output must end in .csv or .parquet")

        print(f"\nSaved result: {args.output}")


def main():
    args = parse_args()

    ensure_exists(args.original_db, "Original DB")
    ensure_exists(args.continuation_db, "Continuation DB")
    ensure_exists(args.recovery_db, "Recovery DB")

    args.temp_dir.mkdir(parents=True, exist_ok=True)
    ensure_exists(args.temp_dir, "Temp dir")

    con = duckdb.connect(":memory:")

    try:
        configure_duckdb(con, args)
        attach_databases(con, args)
        validate_required_objects(con)
        create_unified_views(con)
        print_summary(con)

        if args.summary_only:
            print("\nSummary-only run complete.")
            return 0

        run_query(con, args)
        return 0

    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())