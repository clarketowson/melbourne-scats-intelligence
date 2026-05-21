#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
from _common_scats_kepler import *


def main() -> int:
    p = argparse.ArgumentParser(description='Export overnight SCATS activity for Kepler.gl: Melbourne Never Sleeps.')
    p.add_argument('--start-date', default='2024-05-13')
    p.add_argument('--days', type=int, default=7)
    p.add_argument('--start-hour', type=int, default=0)
    p.add_argument('--end-hour-exclusive', type=int, default=5)
    p.add_argument('--main-db', default=DEFAULT_MAIN_DB)
    p.add_argument('--cont-db', default=DEFAULT_CONT_DB)
    p.add_argument('--rec-db', default=DEFAULT_REC_DB)
    p.add_argument('--metadata', default=DEFAULT_METADATA)
    p.add_argument('--outdir', default=DEFAULT_OUTDIR)
    p.add_argument('--temp-dir', default=r'C:\DuckDBTemp')
    p.add_argument('--memory-limit', default='50GB')
    p.add_argument('--threads', type=int, default=10)
    p.add_argument('--min-volume', type=float, default=1.0)
    args = p.parse_args()

    start = pd.to_datetime(args.start_date)
    end = start + pd.Timedelta(days=args.days-1)
    start_s, end_s = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    where_extra = f"AND TRY_CAST(SUBSTR(CAST({{TIME_COL}} AS VARCHAR),1,2) AS INTEGER) >= {args.start_hour}"
    # We cannot inject TIME_COL here because column names are detected per source, so filter after query.

    print('='*90)
    print('KEPLER MELBOURNE NEVER SLEEPS OVERNIGHT EXPORT V1')
    print('='*90)
    print(f'Date range    : {start_s} to {end_s}')
    print(f'Time window   : {args.start_hour:02d}:00 to {args.end_hour_exclusive:02d}:00 exclusive')

    meta = load_metadata(Path(args.metadata))
    con = connect_duckdb(Path(args.main_db), Path(args.cont_db), Path(args.rec_db), Path(args.temp_dir), args.memory_limit, args.threads)
    raw = query_site_time(con, start_s, end_s)
    raw['hour_tmp'] = pd.to_numeric(raw['time_bin'].astype(str).str.slice(0,2), errors='coerce')
    raw = raw[(raw['hour_tmp'] >= args.start_hour) & (raw['hour_tmp'] < args.end_hour_exclusive)].drop(columns=['hour_tmp'])
    final = enrich_for_kepler(raw, meta, min_volume=args.min_volume)
    final['animation_theme'] = 'Melbourne Never Sleeps'
    final = final[[
        'timestamp','date_label','day_name','time_label','hour','minute','site_id','site_name','latitude','longitude',
        'volume','scaled_volume','scaled_volume_0_100','intensity_band','animation_theme'
    ]].sort_values(['timestamp','volume'], ascending=[True, False])
    out_csv = Path(args.outdir) / f'kepler_never_sleeps_{start_s}_to_{end_s}_{args.start_hour:02d}00_{args.end_hour_exclusive:02d}00.csv'
    write_csv_and_summary(final, out_csv, {'animation':'never_sleeps_overnight','start_date':start_s,'end_date':end_s,'days':args.days})
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
