# generate_database_diagnostics_v3_month_audit.py

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

OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\database_diagnostics")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_LIMIT = "40GB"
THREADS = 10
TEMP_DIR = r"A:\TrafficAnalytics\DATA\TEMP"

AUDIT_START = "2014-01-01"
AUDIT_END = "2026-04-07"

KNOWN_UNAVAILABLE_MONTHS = {
    "2018-12": "One monthly ingest source was unavailable and is disclosed transparently."
}


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


def expected_months(start_date, end_date):
    months = pd.period_range(
        pd.to_datetime(start_date).to_period("M"),
        pd.to_datetime(end_date).to_period("M"),
        freq="M"
    )
    return pd.DataFrame({
        "month_label": [str(m) for m in months],
        "year": [m.year for m in months],
        "month": [m.month for m in months],
    })


start_all = time.time()
errors = []
timings = []
frames = []

for db_name, db_path in DB_PATHS.items():
    print(f"\n==============================")
    print(f"Auditing database: {db_name}")
    print(db_path)
    print(f"==============================")

    if not Path(db_path).exists():
        errors.append(f"{db_name}: database not found: {db_path}")
        continue

    con = duckdb.connect(db_path, read_only=True)
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    con.execute(f"SET threads={THREADS}")
    con.execute(f"SET temp_directory='{TEMP_DIR}'")
    con.execute("SET preserve_insertion_order=false")

    sql = f"""
    SELECT
        '{db_name}' AS database_name,
        STRFTIME(count_date, '%Y-%m') AS month_label,
        EXTRACT(year FROM count_date)::INTEGER AS year,
        EXTRACT(month FROM count_date)::INTEGER AS month,
        COUNT(*) AS detector_day_rows,
        COUNT(DISTINCT count_date) AS days_present,
        COUNT(DISTINCT scats_site) AS distinct_scats_sites,
        COUNT(DISTINCT detector) AS distinct_detectors,
        COUNT(DISTINCT CAST(scats_site AS VARCHAR) || ':' || CAST(detector AS VARCHAR)) AS distinct_site_detector_pairs,
        SUM(volume_24hour) AS total_volume_24hour_sum,
        MIN(count_date) AS min_count_date,
        MAX(count_date) AS max_count_date
    FROM {TABLE_NAME}
    GROUP BY 1, 2, 3, 4
    ORDER BY 2
    """

    df, err, elapsed = safe_query(con, sql, f"{db_name}: monthly audit source scan")
    timings.append({
        "database_name": db_name,
        "query": "monthly_audit_source_scan",
        "elapsed_seconds": elapsed,
    })

    if err:
        errors.append(err)
    else:
        frames.append(df)

    con.close()


raw_months = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
raw_months.to_csv(OUT_DIR / "database_diagnostics_v3_month_audit_by_db.csv", index=False)

expected = expected_months(AUDIT_START, AUDIT_END)

if raw_months.empty:
    combined_months = expected.copy()
    combined_months["detected"] = False
else:
    combined_detected = (
        raw_months.groupby(["month_label", "year", "month"], as_index=False)
        .agg(
            database_sources_present=("database_name", lambda x: ",".join(sorted(set(map(str, x))))),
            source_count=("database_name", "nunique"),
            detector_day_rows=("detector_day_rows", "sum"),
            days_present=("days_present", "max"),
            distinct_scats_sites_sum=("distinct_scats_sites", "sum"),
            distinct_detectors_sum=("distinct_detectors", "sum"),
            distinct_site_detector_pairs_sum=("distinct_site_detector_pairs", "sum"),
            total_volume_24hour_sum=("total_volume_24hour_sum", "sum"),
            min_count_date=("min_count_date", "min"),
            max_count_date=("max_count_date", "max"),
        )
    )

    combined_months = expected.merge(
        combined_detected,
        on=["month_label", "year", "month"],
        how="left"
    )

    combined_months["detected"] = combined_months["source_count"].notna()

combined_months["known_unavailable"] = combined_months["month_label"].isin(KNOWN_UNAVAILABLE_MONTHS.keys())
combined_months["known_unavailable_note"] = combined_months["month_label"].map(KNOWN_UNAVAILABLE_MONTHS).fillna("")
combined_months["is_final_partial_month"] = combined_months["month_label"] == pd.to_datetime(AUDIT_END).strftime("%Y-%m")

combined_months["audit_status"] = "Detected"
combined_months.loc[~combined_months["detected"], "audit_status"] = "Missing"
combined_months.loc[combined_months["known_unavailable"], "audit_status"] = "Known unavailable"
combined_months.loc[combined_months["is_final_partial_month"] & combined_months["detected"], "audit_status"] = "Detected partial final month"

combined_months.to_csv(OUT_DIR / "database_diagnostics_v3_month_audit_combined.csv", index=False)

missing_months = combined_months[
    (~combined_months["detected"]) | (combined_months["known_unavailable"])
].copy()
missing_months.to_csv(OUT_DIR / "database_diagnostics_v3_missing_or_unavailable_months.csv", index=False)

year_audit = (
    combined_months.groupby("year", as_index=False)
    .agg(
        expected_months=("month_label", "count"),
        detected_months=("detected", "sum"),
        known_unavailable_months=("known_unavailable", "sum"),
        detector_day_rows=("detector_day_rows", "sum"),
        total_volume_24hour_sum=("total_volume_24hour_sum", "sum"),
    )
)

year_audit["valid_months_detected"] = year_audit["detected_months"] - year_audit["known_unavailable_months"]
year_audit["missing_unexplained_months"] = (
    year_audit["expected_months"]
    - year_audit["detected_months"]
    - year_audit["known_unavailable_months"]
)

year_audit["is_partial_year"] = year_audit["year"] == pd.to_datetime(AUDIT_END).year
year_audit["audit_note"] = ""

year_audit.loc[
    year_audit["year"] == 2018,
    "audit_note"
] = "2018 includes known unavailable monthly ingest source: 2018-12."

year_audit.loc[
    year_audit["is_partial_year"],
    "audit_note"
] = "Final year is naturally partial because the current dataset ends on 2026-04-07."

year_audit.to_csv(OUT_DIR / "database_diagnostics_v3_year_audit.csv", index=False)

summary = {
    "metric_name": "database_diagnostics_v3_month_audit",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "table_name": TABLE_NAME,
    "audit_start": AUDIT_START,
    "audit_end": AUDIT_END,
    "databases_requested": len(DB_PATHS),
    "databases_processed": int(raw_months["database_name"].nunique()) if not raw_months.empty else 0,
    "expected_months_total": int(combined_months.shape[0]),
    "detected_months_total": int(combined_months["detected"].sum()),
    "known_unavailable_months": list(KNOWN_UNAVAILABLE_MONTHS.keys()),
    "known_unavailable_count": int(combined_months["known_unavailable"].sum()),
    "missing_unexplained_months_count": int(
        ((~combined_months["detected"]) & (~combined_months["known_unavailable"])).sum()
    ),
    "total_elapsed_seconds": round(time.time() - start_all, 3),
    "errors": errors,
    "timings": timings,
    "outputs": {
        "month_audit_by_db_csv": str(OUT_DIR / "database_diagnostics_v3_month_audit_by_db.csv"),
        "month_audit_combined_csv": str(OUT_DIR / "database_diagnostics_v3_month_audit_combined.csv"),
        "missing_or_unavailable_months_csv": str(OUT_DIR / "database_diagnostics_v3_missing_or_unavailable_months.csv"),
        "year_audit_csv": str(OUT_DIR / "database_diagnostics_v3_year_audit.csv"),
        "summary_json": str(OUT_DIR / "database_diagnostics_v3_summary.json"),
    }
}

with open(OUT_DIR / "database_diagnostics_v3_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\n=== Database Diagnostics V3 Month Audit Complete ===")
print(json.dumps(summary, indent=2))