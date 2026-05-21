from __future__ import annotations

import re
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np

DEFAULT_MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
DEFAULT_CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
DEFAULT_REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"
DEFAULT_METADATA = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\all_scats_sites_map_data_audit.csv"
DEFAULT_REPORTS = r"A:\TrafficAnalytics\PROJECTS\reports\deduped"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports"


def win_path(path: str | Path) -> str:
    return str(path).replace('\\', '/')


def clean_label_text(text: str, max_len: int = 58) -> str:
    text = str(text or '').strip()
    if re.match(r"^\d{4}-\d{2}(-\d{2})?$", text):
        return ''
    if re.match(r"^\d+(\.0)?$", text):
        return ''
    if text.lower() in {'nan', 'none', 'null', 'na', 'n/a'}:
        return ''
    text = ' '.join(text.replace('_', ' ').split())
    if len(text) > max_len:
        text = text[:max_len-1].rstrip() + '…'
    return text


def load_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")
    meta = pd.read_csv(path, low_memory=False)
    cols = {c.lower(): c for c in meta.columns}
    for required in ['site_id', 'latitude', 'longitude']:
        if required not in cols:
            raise ValueError(f"Metadata missing required column {required}. Columns: {list(meta.columns)}")
    name_col = None
    for candidate in ['friendly_name', 'site_name', 'location', 'description', 'name']:
        if candidate in cols:
            name_col = cols[candidate]
            break
    out = pd.DataFrame({
        'site_id': meta[cols['site_id']].astype(str).str.strip(),
        'latitude': pd.to_numeric(meta[cols['latitude']], errors='coerce'),
        'longitude': pd.to_numeric(meta[cols['longitude']], errors='coerce'),
        'site_name': meta[name_col].fillna('').astype(str).map(clean_label_text) if name_col else '',
    })
    out = out.dropna(subset=['latitude', 'longitude'])
    out = out[(out['latitude'].between(-39.5, -36.0)) & (out['longitude'].between(143.0, 146.5))].copy()
    missing = out['site_name'].eq('')
    out.loc[missing, 'site_name'] = 'SCATS ' + out.loc[missing, 'site_id'] + ' (network node)'
    return out.drop_duplicates(subset=['site_id'], keep='first')


def connect_duckdb(main_db: Path, cont_db: Path, rec_db: Path, temp_dir: Path, memory_limit: str, threads: int):
    if not main_db.exists():
        raise FileNotFoundError(f"Main DuckDB not found: {main_db}")
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(main_db))
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET threads={threads}")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{win_path(temp_dir)}'")
    if cont_db.exists():
        con.execute(f"ATTACH '{win_path(cont_db)}' AS cont")
    else:
        print(f"WARNING: continuation DB not found, skipping: {cont_db}")
    if rec_db.exists():
        con.execute(f"ATTACH '{win_path(rec_db)}' AS rec")
    else:
        print(f"WARNING: recovery DB not found, skipping: {rec_db}")
    return con


def table_exists(con, name: str) -> bool:
    try:
        con.execute(f"SELECT 1 FROM {name} LIMIT 1")
        return True
    except Exception:
        return False


def detect_columns(con, view_name: str) -> dict[str, str]:
    info = con.execute(f"DESCRIBE {view_name}").fetchdf()
    cols = {c.lower(): c for c in info['column_name'].tolist()}
    def pick(cands, label):
        for c in cands:
            if c.lower() in cols:
                return cols[c.lower()]
        raise ValueError(f"Could not find {label} column in {view_name}. Columns: {list(cols.values())}")
    return {
        'site': pick(['site_id', 'nb_scats_site', 'scats_site', 'site'], 'site'),
        'date': pick(['date', 'count_date', 'day', 'traffic_date'], 'date'),
        'time': pick(['time', 'time_bin', 'interval_time', 'time_of_day'], 'time'),
        'volume': pick(['volume', 'volume_15m', 'vehicles', 'count', 'vehicle_count', 'veh_count', 'sum_volume'], 'volume'),
    }


def build_union_sql(con, start_date: str, end_date: str, where_extra: str = '') -> str:
    sources = []
    for view_name in ['scats_clean', 'cont.scats_clean', 'rec.scats_clean']:
        if table_exists(con, view_name):
            c = detect_columns(con, view_name)
            print(f"Detected columns in {view_name}: site={c['site']}, date={c['date']}, time={c['time']}, volume={c['volume']}")
            sources.append(f"""
                SELECT
                    CAST({c['site']} AS VARCHAR) AS site_id,
                    CAST({c['date']} AS DATE) AS count_date,
                    CAST({c['time']} AS VARCHAR) AS time_value,
                    TRY_CAST({c['volume']} AS DOUBLE) AS volume
                FROM {view_name}
                WHERE CAST({c['date']} AS DATE) BETWEEN DATE '{start_date}' AND DATE '{end_date}'
                  AND TRY_CAST({c['volume']} AS DOUBLE) IS NOT NULL
                  AND TRY_CAST({c['volume']} AS DOUBLE) >= 0
                  {where_extra}
            """)
    if not sources:
        raise RuntimeError('No scats_clean views found in main/attached databases.')
    return '\nUNION ALL\n'.join(sources)


def query_site_time(con, start_date: str, end_date: str, where_extra: str = '') -> pd.DataFrame:
    union_sql = build_union_sql(con, start_date, end_date, where_extra=where_extra)
    query = f"""
    WITH raw AS ({union_sql}),
    cleaned AS (
        SELECT
            site_id,
            count_date,
            CASE WHEN LENGTH(time_value) >= 5 THEN SUBSTR(time_value, 1, 5) ELSE time_value END AS time_bin,
            volume
        FROM raw
    )
    SELECT site_id, count_date, time_bin, SUM(volume) AS volume
    FROM cleaned
    GROUP BY site_id, count_date, time_bin
    ORDER BY count_date, time_bin, site_id
    """
    return con.execute(query).fetchdf()


def enrich_for_kepler(df: pd.DataFrame, meta: pd.DataFrame, min_volume: float = 1.0) -> pd.DataFrame:
    df = df.copy()
    df['site_id'] = df['site_id'].astype(str).str.strip()
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
    df = df[df['volume'] >= min_volume].copy()
    merged = df.merge(meta, on='site_id', how='inner')
    merged['timestamp'] = pd.to_datetime(merged['count_date'].astype(str) + ' ' + merged['time_bin'].astype(str), errors='coerce')
    merged = merged.dropna(subset=['timestamp']).copy()
    merged['hour'] = merged['timestamp'].dt.hour
    merged['minute'] = merged['timestamp'].dt.minute
    merged['time_label'] = merged['timestamp'].dt.strftime('%H:%M')
    merged['date_label'] = merged['timestamp'].dt.strftime('%Y-%m-%d')
    merged['day_name'] = merged['timestamp'].dt.day_name()
    merged['scaled_volume'] = np.log1p(merged['volume'])
    max_scaled = merged['scaled_volume'].max()
    merged['scaled_volume_0_100'] = merged['scaled_volume'] / max_scaled * 100 if max_scaled > 0 else 0
    if len(merged):
        q50, q75, q90, q98 = merged['volume'].quantile([0.50, 0.75, 0.90, 0.98])
    else:
        q50 = q75 = q90 = q98 = 0
    def band(v):
        if v >= q98: return 'extreme'
        if v >= q90: return 'very high'
        if v >= q75: return 'high'
        if v >= q50: return 'medium'
        return 'low'
    merged['intensity_band'] = merged['volume'].map(band)
    return merged


def write_csv_and_summary(final: pd.DataFrame, out_csv: Path, summary_extra: dict):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(out_csv, index=False)
    summary = dict(summary_extra)
    summary.update({
        'rows': int(len(final)),
        'distinct_sites': int(final['site_id'].nunique()) if 'site_id' in final.columns else None,
        'total_volume': float(final['volume'].sum()) if 'volume' in final.columns else None,
        'output_csv': str(out_csv),
    })
    pd.Series(summary).to_json(out_csv.with_name(out_csv.stem + '_summary.json'), indent=2)
    print(f"Wrote CSV      : {out_csv}")
    print(f"Rows           : {len(final):,}")
    if 'site_id' in final.columns:
        print(f"Distinct sites : {final['site_id'].nunique():,}")
    if 'volume' in final.columns:
        print(f"Total volume   : {final['volume'].sum():,.0f}")
    print(f"Summary        : {out_csv.with_name(out_csv.stem + '_summary.json')}")
