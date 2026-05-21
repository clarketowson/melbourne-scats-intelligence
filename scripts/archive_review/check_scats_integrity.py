#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import duckdb


DB_PATH = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"


def main() -> int:
    db_path = Path(DB_PATH)

    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        return 1

    print(f"Opening database: {db_path}")
    con = duckdb.connect(str(db_path))

    try:
        print("\n=== CHECK 1: Negative 15-minute interval values ===")
        q1 = """
        SELECT COUNT(*) AS negative_intervals
        FROM scats_15min_long
        WHERE volume_15m < 0
        """
        negative_intervals = con.execute(q1).fetchone()[0]
        print(f"negative_intervals: {negative_intervals}")

        print("\n=== CHECK 2: Negative daily totals ===")
        q2 = """
        SELECT COUNT(*) AS bad_daily_totals
        FROM scats_detector_day
        WHERE volume_24hour < 0
        """
        bad_daily_totals = con.execute(q2).fetchone()[0]
        print(f"bad_daily_totals: {bad_daily_totals}")

        print("\n=== CHECK 3: Duplicate primary keys ===")
        q3_count = """
        SELECT COUNT(*) AS duplicate_groups
        FROM (
            SELECT
                scats_site,
                count_date,
                detector,
                COUNT(*) AS dup_count
            FROM scats_detector_day
            GROUP BY
                scats_site,
                count_date,
                detector
            HAVING COUNT(*) > 1
        ) t
        """
        duplicate_groups = con.execute(q3_count).fetchone()[0]
        print(f"duplicate_groups: {duplicate_groups}")

        print("\n=== SAMPLE DUPLICATES (up to 20 rows) ===")
        q3_sample = """
        SELECT
            scats_site,
            count_date,
            detector,
            COUNT(*) AS dup_count
        FROM scats_detector_day
        GROUP BY
            scats_site,
            count_date,
            detector
        HAVING COUNT(*) > 1
        ORDER BY count_date, scats_site, detector
        LIMIT 20
        """
        rows = con.execute(q3_sample).fetchall()

        if not rows:
            print("No duplicate primary-key groups found.")
        else:
            for row in rows:
                print(row)

        print("\n=== SUMMARY ===")
        if negative_intervals == 0:
            print("CHECK 1 PASSED")
        else:
            print("CHECK 1 FAILED")

        if bad_daily_totals == 0:
            print("CHECK 2 PASSED")
        else:
            print("CHECK 2 FAILED")

        if duplicate_groups == 0:
            print("CHECK 3 PASSED")
        else:
            print("CHECK 3 FAILED")

        return 0

    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())