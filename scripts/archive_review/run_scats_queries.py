from pathlib import Path
import duckdb
from datetime import datetime

DB_PATH = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\scats_query_outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

queries = {
    "01_row_count": """
        SELECT COUNT(*) AS row_count
        FROM scats_15min_long
    """,
    "02_date_range": """
        SELECT
            MIN(count_date) AS min_date,
            MAX(count_date) AS max_date
        FROM scats_15min_long
    """,
    "03_distinct_sites_in_long": """
        SELECT COUNT(DISTINCT scats_site) AS distinct_sites
        FROM scats_15min_long
    """,
    "04_distinct_detectors": """
        SELECT COUNT(DISTINCT detector) AS distinct_detectors
        FROM scats_15min_long
    """,
    "05_total_volume": """
        SELECT SUM(volume_15m) AS total_volume
        FROM scats_15min_long
    """,
    "06_top_20_sites_by_volume": """
        SELECT
            scats_site,
            SUM(volume_15m) AS total_volume
        FROM scats_15min_long
        GROUP BY scats_site
        ORDER BY total_volume DESC
        LIMIT 20
    """,
    "07_daily_total_volume": """
        SELECT
            count_date,
            SUM(volume_15m) AS total_volume
        FROM scats_15min_long
        GROUP BY count_date
        ORDER BY count_date
    """,
}

summary_lines = []
summary_lines.append(f"Run timestamp: {datetime.now().isoformat()}")
summary_lines.append(f"Database: {DB_PATH}")
summary_lines.append("")

con = duckdb.connect(DB_PATH)
con.execute("SET threads=20;")
con.execute("SET memory_limit='40GB';")
con.execute(r"SET temp_directory='A:\TrafficAnalytics\DATA\TEMP';")

for name, sql in queries.items():
    print(f"Running: {name}")
    output_csv = OUT_DIR / f"{name}.csv"

    # Save to CSV
    copy_sql = f"""
        COPY (
            {sql}
        ) TO '{output_csv.as_posix()}' (HEADER, DELIMITER ',');
    """
    con.execute(copy_sql)

    # Also capture a small preview for the summary file
    preview = con.execute(sql).fetchmany(10)
    cols = [d[0] for d in con.description]

    summary_lines.append(f"=== {name} ===")
    summary_lines.append(f"Saved: {output_csv}")
    summary_lines.append("Columns: " + ", ".join(cols))
    for row in preview:
        summary_lines.append(str(row))
    summary_lines.append("")

con.close()

summary_file = OUT_DIR / "query_summary.txt"
summary_file.write_text("\n".join(summary_lines), encoding="utf-8")

print(f"\nDone. Results saved to: {OUT_DIR}")
print(f"Summary saved to: {summary_file}")