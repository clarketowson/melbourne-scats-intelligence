#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import duckdb


DB_PATHS = [
    Path(r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"),
    Path(r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"),
]


def build_scats_clean_view_sql() -> str:
    return """
    CREATE OR REPLACE VIEW scats_clean AS
    SELECT
        scats_site,
        count_date,
        detector,
        region_code,
        source_file_id,
        interval_index,
        time_bin,
        CASE
            WHEN volume_15m < 0 THEN NULL
            ELSE volume_15m
        END AS volume_15m
    FROM scats_15min_long
    """.strip()


def ensure_expected_objects(con: duckdb.DuckDBPyConnection) -> None:
    tables = {
        row[0].lower()
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }

    required_tables = {"scats_detector_day", "scats_site", "source_file", "scats_expected_date"}
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        raise RuntimeError(f"Missing required tables: {missing_tables}")

    con.execute("SELECT 1 FROM scats_15min_long LIMIT 1")


def create_view_for_db(db_path: Path, view_sql: str) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    print(f"\n=== Opening {db_path} ===")
    con = duckdb.connect(str(db_path))

    try:
        ensure_expected_objects(con)
        con.execute(view_sql)
        print("Created or replaced view: scats_clean")

        result = con.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (WHERE volume_15m < 0) AS negative_rows,
                COUNT(*) FILTER (WHERE volume_15m IS NULL) AS null_rows,
                MIN(volume_15m) AS min_volume,
                MAX(volume_15m) AS max_volume
            FROM scats_clean
            """
        ).fetchone()

        print("Sanity check:")
        print(f"  total_rows     = {result[0]}")
        print(f"  negative_rows  = {result[1]}")
        print(f"  null_rows      = {result[2]}")
        print(f"  min_volume     = {result[3]}")
        print(f"  max_volume     = {result[4]}")

    finally:
        con.close()


def main() -> int:
    view_sql = build_scats_clean_view_sql()

    for db_path in DB_PATHS:
        try:
            create_view_for_db(db_path, view_sql)
        except Exception as e:
            print(f"ERROR processing {db_path}: {e}", file=sys.stderr)
            return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())