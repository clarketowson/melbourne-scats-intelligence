# generate_database_diagnostics_v1.py

import json
import time
from pathlib import Path
from datetime import datetime

import duckdb
import pandas as pd


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

DB_PATHS = {
    "scats": r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb",
    "scats_continuation": r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb",
    "scats_recovery": r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb",
}

OUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\database_diagnostics")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_LIMIT = "50GB"
THREADS = 10
TEMP_DIR = r"A:\TrafficAnalytics\DATA\TEMP"


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def safe_query(con, sql, label):
    try:
        return con.execute(sql).fetchdf(), None
    except Exception as e:
        return pd.DataFrame(), f"{label}: {type(e).__name__}: {e}"


def file_size_gb(path):
    p = Path(path)
    if not p.exists():
        return None
    return p.stat().st_size / (1024 ** 3)


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

start = time.time()
errors = []

database_rows = []
tables_rows = []
views_rows = []
columns_rows = []
rowcount_rows = []

for db_name, db_path in DB_PATHS.items():
    print(f"\n=== Inspecting {db_name} ===")
    print(db_path)

    if not Path(db_path).exists():
        errors.append(f"{db_name}: database file not found: {db_path}")
        continue

    con = duckdb.connect(db_path, read_only=True)

    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    con.execute(f"SET threads={THREADS}")
    con.execute(f"SET temp_directory='{TEMP_DIR}'")
    con.execute("SET preserve_insertion_order=false")

    database_rows.append({
        "database_name": db_name,
        "database_path": db_path,
        "file_size_gb": file_size_gb(db_path),
        "inspected_at": datetime.now().isoformat(timespec="seconds"),
    })

    # Tables
    tables_df, err = safe_query(con, """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
    """, f"{db_name} tables")
    if err:
        errors.append(err)
    else:
        for _, r in tables_df.iterrows():
            tables_rows.append({
                "database_name": db_name,
                "table_schema": r["table_schema"],
                "table_name": r["table_name"],
            })

    # Views
    views_df, err = safe_query(con, """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'VIEW'
        ORDER BY table_schema, table_name
    """, f"{db_name} views")
    if err:
        errors.append(err)
    else:
        for _, r in views_df.iterrows():
            views_rows.append({
                "database_name": db_name,
                "view_schema": r["table_schema"],
                "view_name": r["table_name"],
            })

    # Columns for all tables and views
    cols_df, err = safe_query(con, """
        SELECT table_schema, table_name, column_name, ordinal_position, data_type
        FROM information_schema.columns
        ORDER BY table_schema, table_name, ordinal_position
    """, f"{db_name} columns")
    if err:
        errors.append(err)
    else:
        for _, r in cols_df.iterrows():
            columns_rows.append({
                "database_name": db_name,
                "table_schema": r["table_schema"],
                "table_name": r["table_name"],
                "column_name": r["column_name"],
                "ordinal_position": int(r["ordinal_position"]),
                "data_type": r["data_type"],
            })

    # Safe row counts for base tables only
    for _, r in tables_df.iterrows():
        schema = r["table_schema"]
        table = r["table_name"]
        quoted = f'"{schema}"."{table}"'

        print(f"Counting rows: {db_name}.{schema}.{table}")

        count_df, err = safe_query(
            con,
            f"SELECT COUNT(*) AS row_count FROM {quoted}",
            f"{db_name}.{schema}.{table} row count"
        )

        if err:
            errors.append(err)
            row_count = None
        else:
            row_count = int(count_df["row_count"].iloc[0])

        rowcount_rows.append({
            "database_name": db_name,
            "table_schema": schema,
            "table_name": table,
            "row_count": row_count,
        })

    con.close()


# ------------------------------------------------------------
# OUTPUTS
# ------------------------------------------------------------

database_df = pd.DataFrame(database_rows)
tables_df = pd.DataFrame(tables_rows)
views_df = pd.DataFrame(views_rows)
columns_df = pd.DataFrame(columns_rows)
rowcounts_df = pd.DataFrame(rowcount_rows)

database_df.to_csv(OUT_DIR / "database_diagnostics_databases.csv", index=False)
tables_df.to_csv(OUT_DIR / "database_diagnostics_tables.csv", index=False)
views_df.to_csv(OUT_DIR / "database_diagnostics_views.csv", index=False)
columns_df.to_csv(OUT_DIR / "database_diagnostics_columns.csv", index=False)
rowcounts_df.to_csv(OUT_DIR / "database_diagnostics_rowcounts.csv", index=False)

summary = {
    "metric_name": "database_diagnostics_v1",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "total_elapsed_seconds": round(time.time() - start, 3),
    "databases_requested": len(DB_PATHS),
    "databases_found": int(database_df.shape[0]),
    "total_database_file_size_gb": round(database_df["file_size_gb"].dropna().sum(), 3) if not database_df.empty else 0,
    "base_tables_found": int(tables_df.shape[0]),
    "views_found": int(views_df.shape[0]),
    "columns_found": int(columns_df.shape[0]),
    "rowcount_records": int(rowcounts_df.shape[0]),
    "errors": errors,
    "outputs": {
        "databases_csv": str(OUT_DIR / "database_diagnostics_databases.csv"),
        "tables_csv": str(OUT_DIR / "database_diagnostics_tables.csv"),
        "views_csv": str(OUT_DIR / "database_diagnostics_views.csv"),
        "columns_csv": str(OUT_DIR / "database_diagnostics_columns.csv"),
        "rowcounts_csv": str(OUT_DIR / "database_diagnostics_rowcounts.csv"),
    }
}

with open(OUT_DIR / "database_diagnostics_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\n=== Database Diagnostics V1 Complete ===")
print(json.dumps(summary, indent=2))