from pathlib import Path
from datetime import datetime
import duckdb
import time

DB_PATH = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\scats_clean_outputs_v2")
OUT_DIR.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(DB_PATH)

# Safer settings for very large workloads
con.execute("SET threads=12;")
con.execute("SET memory_limit='28GB';")
con.execute(r"SET temp_directory='A:\TrafficAnalytics\DATA\TEMP';")
con.execute("SET preserve_insertion_order=false;")
con.execute("SET max_temp_directory_size='300GiB';")

# Create clean view
con.execute("""
CREATE OR REPLACE VIEW scats_clean AS
SELECT *
FROM scats_15min_long
WHERE volume_15m >= 0
""")

queries = {
    "01_cleaned_row_count": """
        SELECT COUNT(*) AS cleaned_rows
        FROM scats_clean
    """,
    "02_cleaned_total_volume": """
        SELECT SUM(volume_15m) AS cleaned_total_volume
        FROM scats_clean
    """,
    "03_cleaned_date_range": """
        SELECT
            MIN(count_date) AS min_date,
            MAX(count_date) AS max_date
        FROM scats_clean
    """,
    "04_daily_total_volume": """
        SELECT
            count_date,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY count_date
        ORDER BY count_date
    """,
    "05_top_100_sites_by_total_volume": """
        SELECT
            scats_site,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY scats_site
        ORDER BY total_volume DESC
        LIMIT 100
    """,
    # Much safer replacement for the failed query:
    # first find the top 100 sites, then aggregate detectors only within those sites
    "06_top_site_detector_pairs_within_top_100_sites": """
        WITH top_sites AS (
            SELECT
                scats_site
            FROM scats_clean
            GROUP BY scats_site
            ORDER BY SUM(volume_15m) DESC
            LIMIT 100
        )
        SELECT
            s.scats_site,
            s.detector,
            SUM(s.volume_15m) AS total_volume
        FROM scats_clean s
        INNER JOIN top_sites t
            ON s.scats_site = t.scats_site
        GROUP BY s.scats_site, s.detector
        ORDER BY total_volume DESC
        LIMIT 200
    """,
    "07_site_daily_totals_top_20_sites": """
        WITH top_sites AS (
            SELECT
                scats_site
            FROM scats_clean
            GROUP BY scats_site
            ORDER BY SUM(volume_15m) DESC
            LIMIT 20
        )
        SELECT
            s.count_date,
            s.scats_site,
            SUM(s.volume_15m) AS total_volume
        FROM scats_clean s
        INNER JOIN top_sites t
            ON s.scats_site = t.scats_site
        GROUP BY s.count_date, s.scats_site
        ORDER BY s.count_date, s.scats_site
    """,
    "08_time_bin_profile_network": """
        SELECT
            time_bin,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY time_bin
        ORDER BY time_bin
    """,
    "09_time_bin_profile_top_20_sites": """
        WITH top_sites AS (
            SELECT
                scats_site
            FROM scats_clean
            GROUP BY scats_site
            ORDER BY SUM(volume_15m) DESC
            LIMIT 20
        )
        SELECT
            s.scats_site,
            s.time_bin,
            SUM(s.volume_15m) AS total_volume
        FROM scats_clean s
        INNER JOIN top_sites t
            ON s.scats_site = t.scats_site
        GROUP BY s.scats_site, s.time_bin
        ORDER BY s.scats_site, s.time_bin
    """,
    "10_negative_data_summary_reference": """
        SELECT
            COUNT(*) AS raw_rows,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows,
            SUM(CASE WHEN volume_15m >= 0 THEN 1 ELSE 0 END) AS non_negative_rows,
            SUM(volume_15m) AS raw_total_volume,
            SUM(CASE WHEN volume_15m >= 0 THEN volume_15m ELSE 0 END) AS cleaned_total_volume
        FROM scats_15min_long
    """
}

summary_lines = [
    f"Run timestamp: {datetime.now().isoformat()}",
    f"Database: {DB_PATH}",
    "View created: scats_clean (volume_15m >= 0)",
    "Settings:",
    "  threads=12",
    "  memory_limit=28GB",
    r"  temp_directory=A:\TrafficAnalytics\DATA\TEMP",
    "  preserve_insertion_order=false",
    "  max_temp_directory_size=300GiB",
    ""
]

for name, sql in queries.items():
    print(f"Running: {name}")
    output_csv = OUT_DIR / f"{name}.csv"
    start = time.perf_counter()

    try:
        copy_sql = f"""
            COPY (
                {sql}
            ) TO '{output_csv.as_posix()}' (HEADER, DELIMITER ',');
        """
        con.execute(copy_sql)

        preview_rows = con.execute(sql).fetchmany(10)
        columns = [d[0] for d in con.description]
        elapsed = time.perf_counter() - start

        summary_lines.append(f"=== {name} ===")
        summary_lines.append(f"Saved: {output_csv}")
        summary_lines.append(f"Elapsed seconds: {elapsed:.3f}")
        summary_lines.append("Columns: " + ", ".join(columns))
        for row in preview_rows:
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

con.close()

summary_file = OUT_DIR / "clean_output_summary.txt"
summary_file.write_text("\n".join(summary_lines), encoding="utf-8")

print(f"\nDone. Results saved to: {OUT_DIR}")
print(f"Summary saved to: {summary_file}")