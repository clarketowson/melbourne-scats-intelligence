#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import duckdb


DB_PATHS = [
    Path(r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"),
    Path(r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"),
]


def build_scats_15min_long_view_sql() -> str:
    parts = []
    for i in range(96):
        hour = (i * 15) // 60
        minute = (i * 15) % 60
        time_bin = f"{hour:02d}:{minute:02d}"
        parts.append(
            f"""
            SELECT
                scats_site,
                count_date,
                detector,
                region_code,
                source_file_id,
                {i} AS interval_index,
                '{time_bin}' AS time_bin,
                v{i:02d} AS volume_15m
            FROM scats_detector_day
            """.strip()
        )

    union_sql = "\nUNION ALL\n".join(parts)

    return f"""
    CREATE OR REPLACE VIEW scats_15min_long AS
    {union_sql}
    """.strip()


def ensure_expected_objects(con: duckdb.DuckDBPyConnection) -> None:
    tables = {
        row[0].lower()
        for row in con.execute("SHOW TABLES").fetchall()
    }

    required = {"scats_detector_day", "scats_site", "source_file", "scats_expected_date"}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError(f"Missing required tables: {missing}")


def create_view_for_db(db_path: Path, view_sql: str) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    print(f"\n=== Opening {db_path} ===")
    con = duckdb.connect(str(db_path))

    try:
        ensure_expected_objects(con)
        con.execute(view_sql)
        print("Created or replaced view: scats_15min_long")

        # Quick sanity check
        result = con.execute(
            """
            SELECT
                MIN(interval_index) AS min_interval_index,
                MAX(interval_index) AS max_interval_index,
                COUNT(DISTINCT interval_index) AS distinct_interval_indexes,
                MIN(time_bin) AS min_time_bin,
                MAX(time_bin) AS max_time_bin,
                COUNT(DISTINCT time_bin) AS distinct_time_bins
            FROM scats_15min_long
            """
        ).fetchone()

        print("Sanity check:")
        print(f"  min_interval_index      = {result[0]}")
        print(f"  max_interval_index      = {result[1]}")
        print(f"  distinct_interval_index = {result[2]}")
        print(f"  min_time_bin            = {result[3]}")
        print(f"  max_time_bin            = {result[4]}")
        print(f"  distinct_time_bins      = {result[5]}")

    finally:
        con.close()


def main() -> int:
    view_sql = build_scats_15min_long_view_sql()

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