from pathlib import Path
from datetime import datetime
import duckdb

DB_PATH = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\scats_priority_answers")
OUT_DIR.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(DB_PATH)

# Safer large-workload settings
con.execute("SET threads=12;")
con.execute("SET memory_limit='28GB';")
con.execute(r"SET temp_directory='A:\TrafficAnalytics\DATA\TEMP';")
con.execute("SET preserve_insertion_order=false;")
con.execute("SET max_temp_directory_size='300GiB';")

# Clean view
con.execute("""
CREATE OR REPLACE VIEW scats_clean AS
SELECT *
FROM scats_15min_long
WHERE volume_15m >= 0
""")

queries = {
    "01_dataset_summary": """
        SELECT
            COUNT(*) AS cleaned_rows,
            COUNT(DISTINCT scats_site) AS distinct_sites,
            MIN(count_date) AS min_date,
            MAX(count_date) AS max_date,
            SUM(volume_15m) AS cleaned_total_volume
        FROM scats_clean
    """,

    "02_busiest_intersections_top_100": """
        SELECT
            scats_site,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY scats_site
        ORDER BY total_volume DESC
        LIMIT 100
    """,

    "03_quietest_intersections_bottom_100": """
        SELECT
            scats_site,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY scats_site
        ORDER BY total_volume ASC
        LIMIT 100
    """,

    "04_busiest_time_of_day_network": """
        SELECT
            time_bin,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY time_bin
        ORDER BY total_volume DESC
        LIMIT 20
    """,

    "05_quietest_time_of_day_network": """
        SELECT
            time_bin,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY time_bin
        ORDER BY total_volume ASC
        LIMIT 20
    """,

    "06_busiest_days_top_100": """
        SELECT
            count_date,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY count_date
        ORDER BY total_volume DESC
        LIMIT 100
    """,

    "07_quietest_days_bottom_100": """
        SELECT
            count_date,
            SUM(volume_15m) AS total_volume
        FROM scats_clean
        GROUP BY count_date
        ORDER BY total_volume ASC
        LIMIT 100
    """,

    "08_weekday_vs_weekend_network": """
        SELECT
            CASE
                WHEN EXTRACT(ISODOW FROM count_date) IN (6, 7) THEN 'Weekend'
                ELSE 'Weekday'
            END AS day_type,
            AVG(daily_total) AS avg_daily_volume
        FROM (
            SELECT
                count_date,
                SUM(volume_15m) AS daily_total
            FROM scats_clean
            GROUP BY count_date
        ) d
        GROUP BY day_type
        ORDER BY day_type
    """,

    "09_monday_vs_friday_network": """
        SELECT
            CASE EXTRACT(ISODOW FROM count_date)
                WHEN 1 THEN 'Monday'
                WHEN 5 THEN 'Friday'
            END AS day_name,
            AVG(daily_total) AS avg_daily_volume
        FROM (
            SELECT
                count_date,
                SUM(volume_15m) AS daily_total
            FROM scats_clean
            GROUP BY count_date
        ) d
        WHERE EXTRACT(ISODOW FROM count_date) IN (1, 5)
        GROUP BY day_name
        ORDER BY day_name
    """,

    "10_peak_15min_period_each_site_top_100_by_peak": """
        WITH site_peak AS (
            SELECT
                scats_site,
                time_bin,
                AVG(volume_15m) AS avg_volume,
                ROW_NUMBER() OVER (
                    PARTITION BY scats_site
                    ORDER BY AVG(volume_15m) DESC, time_bin
                ) AS rn
            FROM scats_clean
            GROUP BY scats_site, time_bin
        )
        SELECT
            scats_site,
            time_bin AS peak_time_bin,
            avg_volume AS avg_peak_15m_volume
        FROM site_peak
        WHERE rn = 1
        ORDER BY avg_peak_15m_volume DESC
        LIMIT 100
    """,

    "11_quietest_15min_period_each_site_bottom_100_by_quiet": """
        WITH site_quiet AS (
            SELECT
                scats_site,
                time_bin,
                AVG(volume_15m) AS avg_volume,
                ROW_NUMBER() OVER (
                    PARTITION BY scats_site
                    ORDER BY AVG(volume_15m) ASC, time_bin
                ) AS rn
            FROM scats_clean
            GROUP BY scats_site, time_bin
        )
        SELECT
            scats_site,
            time_bin AS quiet_time_bin,
            avg_volume AS avg_quiet_15m_volume
        FROM site_quiet
        WHERE rn = 1
        ORDER BY avg_quiet_15m_volume ASC
        LIMIT 100
    """,

    "12_typical_daily_pattern_top_50_sites": """
        WITH top_sites AS (
            SELECT
                scats_site
            FROM scats_clean
            GROUP BY scats_site
            ORDER BY SUM(volume_15m) DESC
            LIMIT 50
        )
        SELECT
            s.scats_site,
            s.time_bin,
            AVG(s.volume_15m) AS avg_15m_volume
        FROM scats_clean s
        INNER JOIN top_sites t
            ON s.scats_site = t.scats_site
        GROUP BY s.scats_site, s.time_bin
        ORDER BY s.scats_site, s.time_bin
    """,

    "13_highest_volume_ever_recorded_each_site_top_100": """
        SELECT
            scats_site,
            MAX(volume_15m) AS max_15m_volume
        FROM scats_clean
        GROUP BY scats_site
        ORDER BY max_15m_volume DESC
        LIMIT 100
    """,

    "14_lowest_nonzero_volume_ever_recorded_each_site_bottom_100": """
        SELECT
            scats_site,
            MIN(volume_15m) AS min_nonzero_15m_volume
        FROM scats_clean
        WHERE volume_15m > 0
        GROUP BY scats_site
        ORDER BY min_nonzero_15m_volume ASC
        LIMIT 100
    """,

    "15_long_term_growth_by_site": """
        WITH yearly AS (
            SELECT
                scats_site,
                EXTRACT(YEAR FROM count_date) AS yr,
                SUM(volume_15m) AS yearly_volume
            FROM scats_clean
            GROUP BY scats_site, yr
        ),
        endpoints AS (
            SELECT
                scats_site,
                MIN(yr) AS first_year,
                MAX(yr) AS last_year
            FROM yearly
            GROUP BY scats_site
        )
        SELECT
            e.scats_site,
            e.first_year,
            y1.yearly_volume AS first_year_volume,
            e.last_year,
            y2.yearly_volume AS last_year_volume,
            (y2.yearly_volume - y1.yearly_volume) AS absolute_change,
            CASE
                WHEN y1.yearly_volume > 0
                THEN ROUND(100.0 * (y2.yearly_volume - y1.yearly_volume) / y1.yearly_volume, 2)
                ELSE NULL
            END AS pct_change
        FROM endpoints e
        JOIN yearly y1
          ON e.scats_site = y1.scats_site AND e.first_year = y1.yr
        JOIN yearly y2
          ON e.scats_site = y2.scats_site AND e.last_year = y2.yr
        ORDER BY absolute_change DESC
    """,

    "16_fastest_growth_sites_top_100": """
        WITH yearly AS (
            SELECT
                scats_site,
                EXTRACT(YEAR FROM count_date) AS yr,
                SUM(volume_15m) AS yearly_volume
            FROM scats_clean
            GROUP BY scats_site, yr
        ),
        endpoints AS (
            SELECT
                scats_site,
                MIN(yr) AS first_year,
                MAX(yr) AS last_year
            FROM yearly
            GROUP BY scats_site
        )
        SELECT
            e.scats_site,
            e.first_year,
            y1.yearly_volume AS first_year_volume,
            e.last_year,
            y2.yearly_volume AS last_year_volume,
            (y2.yearly_volume - y1.yearly_volume) AS absolute_change,
            CASE
                WHEN y1.yearly_volume > 0
                THEN ROUND(100.0 * (y2.yearly_volume - y1.yearly_volume) / y1.yearly_volume, 2)
                ELSE NULL
            END AS pct_change
        FROM endpoints e
        JOIN yearly y1
          ON e.scats_site = y1.scats_site AND e.first_year = y1.yr
        JOIN yearly y2
          ON e.scats_site = y2.scats_site AND e.last_year = y2.yr
        ORDER BY absolute_change DESC
        LIMIT 100
    """,

    "17_biggest_decline_sites_bottom_100": """
        WITH yearly AS (
            SELECT
                scats_site,
                EXTRACT(YEAR FROM count_date) AS yr,
                SUM(volume_15m) AS yearly_volume
            FROM scats_clean
            GROUP BY scats_site, yr
        ),
        endpoints AS (
            SELECT
                scats_site,
                MIN(yr) AS first_year,
                MAX(yr) AS last_year
            FROM yearly
            GROUP BY scats_site
        )
        SELECT
            e.scats_site,
            e.first_year,
            y1.yearly_volume AS first_year_volume,
            e.last_year,
            y2.yearly_volume AS last_year_volume,
            (y2.yearly_volume - y1.yearly_volume) AS absolute_change,
            CASE
                WHEN y1.yearly_volume > 0
                THEN ROUND(100.0 * (y2.yearly_volume - y1.yearly_volume) / y1.yearly_volume, 2)
                ELSE NULL
            END AS pct_change
        FROM endpoints e
        JOIN yearly y1
          ON e.scats_site = y1.scats_site AND e.first_year = y1.yr
        JOIN yearly y2
          ON e.scats_site = y2.scats_site AND e.last_year = y2.yr
        ORDER BY absolute_change ASC
        LIMIT 100
    """,

    "18_most_predictable_sites_top_100": """
        WITH daily_site AS (
            SELECT
                scats_site,
                count_date,
                SUM(volume_15m) AS daily_volume
            FROM scats_clean
            GROUP BY scats_site, count_date
        )
        SELECT
            scats_site,
            AVG(daily_volume) AS mean_daily_volume,
            STDDEV_SAMP(daily_volume) AS sd_daily_volume,
            CASE
                WHEN AVG(daily_volume) > 0
                THEN ROUND(STDDEV_SAMP(daily_volume) / AVG(daily_volume), 4)
                ELSE NULL
            END AS cv
        FROM daily_site
        GROUP BY scats_site
        HAVING COUNT(*) >= 100
        ORDER BY cv ASC
        LIMIT 100
    """,

    "19_most_variable_sites_top_100": """
        WITH daily_site AS (
            SELECT
                scats_site,
                count_date,
                SUM(volume_15m) AS daily_volume
            FROM scats_clean
            GROUP BY scats_site, count_date
        )
        SELECT
            scats_site,
            AVG(daily_volume) AS mean_daily_volume,
            STDDEV_SAMP(daily_volume) AS sd_daily_volume,
            CASE
                WHEN AVG(daily_volume) > 0
                THEN ROUND(STDDEV_SAMP(daily_volume) / AVG(daily_volume), 4)
                ELSE NULL
            END AS cv
        FROM daily_site
        GROUP BY scats_site
        HAVING COUNT(*) >= 100
        ORDER BY cv DESC
        LIMIT 100
    """,

    "20_peak_offpeak_overnight_shares_network": """
        WITH totals AS (
            SELECT
                SUM(volume_15m) AS total_volume,
                SUM(CASE WHEN time_bin >= '07:00' AND time_bin < '10:00' THEN volume_15m ELSE 0 END) AS am_peak,
                SUM(CASE WHEN time_bin >= '16:00' AND time_bin < '19:00' THEN volume_15m ELSE 0 END) AS pm_peak,
                SUM(CASE WHEN time_bin >= '00:00' AND time_bin < '06:00' THEN volume_15m ELSE 0 END) AS overnight,
                SUM(CASE WHEN time_bin < '09:00' THEN volume_15m ELSE 0 END) AS before_9am,
                SUM(CASE WHEN time_bin >= '18:00' THEN volume_15m ELSE 0 END) AS after_6pm
            FROM scats_clean
        )
        SELECT
            total_volume,
            am_peak,
            pm_peak,
            overnight,
            before_9am,
            after_6pm,
            ROUND(100.0 * am_peak / total_volume, 2) AS am_peak_pct,
            ROUND(100.0 * pm_peak / total_volume, 2) AS pm_peak_pct,
            ROUND(100.0 * overnight / total_volume, 2) AS overnight_pct,
            ROUND(100.0 * before_9am / total_volume, 2) AS before_9am_pct,
            ROUND(100.0 * after_6pm / total_volume, 2) AS after_6pm_pct
        FROM totals
    """
}

summary_lines = [
    f"Run timestamp: {datetime.now().isoformat()}",
    f"Database: {DB_PATH}",
    "View created: scats_clean (volume_15m >= 0)",
    "Focus: highest-value priority answers from SCATS question set",
    ""
]

for name, sql in queries.items():
    print(f"Running: {name}")
    output_csv = OUT_DIR / f"{name}.csv"

    copy_sql = f"""
        COPY (
            {sql}
        ) TO '{output_csv.as_posix()}' (HEADER, DELIMITER ',');
    """
    con.execute(copy_sql)

    preview = con.execute(sql).fetchmany(10)
    cols = [d[0] for d in con.description]

    summary_lines.append(f"=== {name} ===")
    summary_lines.append(f"Saved: {output_csv}")
    summary_lines.append("Columns: " + ", ".join(cols))
    for row in preview:
        summary_lines.append(str(row))
    summary_lines.append("")

con.close()

summary_file = OUT_DIR / "priority_answers_summary.txt"
summary_file.write_text("\n".join(summary_lines), encoding="utf-8")

print(f"\nDone. Results saved to: {OUT_DIR}")
print(f"Summary saved to: {summary_file}")