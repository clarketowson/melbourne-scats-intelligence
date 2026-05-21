from pathlib import Path
from datetime import datetime
import duckdb

DB_PATH = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\scats_volume_audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)

queries = {
    "01_volume_min_max": """
        SELECT
            MIN(volume_15m) AS min_volume,
            MAX(volume_15m) AS max_volume
        FROM scats_15min_long
    """,
    "02_negative_row_count": """
        SELECT
            COUNT(*) AS negative_rows
        FROM scats_15min_long
        WHERE volume_15m < 0
    """,
    "03_negative_values_frequency_top_20": """
        SELECT
            volume_15m,
            COUNT(*) AS rows
        FROM scats_15min_long
        WHERE volume_15m < 0
        GROUP BY volume_15m
        ORDER BY rows DESC
        LIMIT 20
    """,
    "04_zero_row_count": """
        SELECT
            COUNT(*) AS zero_rows
        FROM scats_15min_long
        WHERE volume_15m = 0
    """,
    "05_negative_rows_by_date_top_20": """
        SELECT
            count_date,
            COUNT(*) AS negative_rows
        FROM scats_15min_long
        WHERE volume_15m < 0
        GROUP BY count_date
        ORDER BY negative_rows DESC, count_date
        LIMIT 20
    """,
    "06_negative_rows_by_site_top_20": """
        SELECT
            scats_site,
            COUNT(*) AS negative_rows
        FROM scats_15min_long
        WHERE volume_15m < 0
        GROUP BY scats_site
        ORDER BY negative_rows DESC, scats_site
        LIMIT 20
    """,
    "07_raw_vs_cleaned_totals": """
        SELECT
            SUM(volume_15m) AS raw_total_volume,
            SUM(CASE WHEN volume_15m >= 0 THEN volume_15m ELSE 0 END) AS non_negative_total_volume,
            COUNT(*) AS total_rows,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows
        FROM scats_15min_long
    """,
    "08_negative_rows_by_source_file_top_50": """
        SELECT
            source_file_id,
            COUNT(*) AS negative_rows
        FROM scats_15min_long
        WHERE volume_15m < 0
        GROUP BY source_file_id
        ORDER BY negative_rows DESC, source_file_id
        LIMIT 50
    """,
    "09_site_level_raw_vs_cleaned_top_50_gap": """
        SELECT
            scats_site,
            SUM(volume_15m) AS raw_total_volume,
            SUM(CASE WHEN volume_15m >= 0 THEN volume_15m ELSE 0 END) AS cleaned_total_volume,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows
        FROM scats_15min_long
        GROUP BY scats_site
        ORDER BY (SUM(CASE WHEN volume_15m >= 0 THEN volume_15m ELSE 0 END) - SUM(volume_15m)) DESC
        LIMIT 50
    """,
    "10_daily_raw_vs_cleaned_top_50_gap": """
        SELECT
            count_date,
            SUM(volume_15m) AS raw_total_volume,
            SUM(CASE WHEN volume_15m >= 0 THEN volume_15m ELSE 0 END) AS cleaned_total_volume,
            SUM(CASE WHEN volume_15m < 0 THEN 1 ELSE 0 END) AS negative_rows
        FROM scats_15min_long
        GROUP BY count_date
        ORDER BY (SUM(CASE WHEN volume_15m >= 0 THEN volume_15m ELSE 0 END) - SUM(volume_15m)) DESC
        LIMIT 50
    """,
}

summary_lines = [
    f"Run timestamp: {datetime.now().isoformat()}",
    f"Database: {DB_PATH}",
    ""
]

con = duckdb.connect(DB_PATH)
con.execute("SET threads=20;")
con.execute("SET memory_limit='40GB';")
con.execute(r"SET temp_directory='A:\TrafficAnalytics\DATA\TEMP';")

for name, sql in queries.items():
    print(f"Running: {name}")
    output_csv = OUT_DIR / f"{name}.csv"

    copy_sql = f"""
        COPY (
            {sql}
        ) TO '{output_csv.as_posix()}' (HEADER, DELIMITER ',');
    """
    con.execute(copy_sql)

    preview_rows = con.execute(sql).fetchmany(10)
    columns = [d[0] for d in con.description]

    summary_lines.append(f"=== {name} ===")
    summary_lines.append(f"Saved: {output_csv}")
    summary_lines.append("Columns: " + ", ".join(columns))
    for row in preview_rows:
        summary_lines.append(str(row))
    summary_lines.append("")

con.close()

summary_file = OUT_DIR / "audit_summary.txt"
summary_file.write_text("\n".join(summary_lines), encoding="utf-8")

print(f"\nDone. Results saved to: {OUT_DIR}")
print(f"Summary saved to: {summary_file}")