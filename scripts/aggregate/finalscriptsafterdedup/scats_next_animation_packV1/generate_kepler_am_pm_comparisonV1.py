#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
from _common_scats_kepler import *


def main() -> int:
    p = argparse.ArgumentParser(description='Export AM vs PM peak comparison data for Kepler.gl.')
    p.add_argument('--date', default='2024-05-15')
    p.add_argument('--main-db', default=DEFAULT_MAIN_DB)
    p.add_argument('--cont-db', default=DEFAULT_CONT_DB)
    p.add_argument('--rec-db', default=DEFAULT_REC_DB)
    p.add_argument('--metadata', default=DEFAULT_METADATA)
    p.add_argument('--outdir', default=DEFAULT_OUTDIR)
    p.add_argument('--temp-dir', default=r'C:\DuckDBTemp')
    p.add_argument('--memory-limit', default='50GB')
    p.add_argument('--threads', type=int, default=10)
    p.add_argument('--min-volume', type=float, default=1.0)
    p.add_argument('--longitude-offset', type=float, default=0.34, help='Offset copies so AM and PM can be shown side by side.')
    args = p.parse_args()

    date_s = pd.to_datetime(args.date).strftime('%Y-%m-%d')
    meta = load_metadata(Path(args.metadata))
    con = connect_duckdb(Path(args.main_db), Path(args.cont_db), Path(args.rec_db), Path(args.temp_dir), args.memory_limit, args.threads)
    raw = query_site_time(con, date_s, date_s)
    raw['hour_tmp'] = pd.to_numeric(raw['time_bin'].astype(str).str.slice(0,2), errors='coerce')
    raw = raw[((raw['hour_tmp'] >= 7) & (raw['hour_tmp'] < 10)) | ((raw['hour_tmp'] >= 16) & (raw['hour_tmp'] < 19))].drop(columns=['hour_tmp'])
    final = enrich_for_kepler(raw, meta, min_volume=args.min_volume)
    final['peak_period'] = np.where(final['hour'].between(7,9), 'AM Peak 07:00-10:00', 'PM Peak 16:00-19:00')
    final['comparison_longitude'] = final['longitude'] + np.where(final['peak_period'].str.startswith('AM'), -args.longitude_offset, args.longitude_offset)
    final['comparison_latitude'] = final['latitude']
    final = final[[
        'timestamp','date_label','time_label','hour','minute','peak_period','site_id','site_name',
        'latitude','longitude','comparison_latitude','comparison_longitude','volume','scaled_volume','scaled_volume_0_100','intensity_band'
    ]].sort_values(['timestamp','peak_period','volume'], ascending=[True, True, False])
    out_csv = Path(args.outdir) / f'kepler_am_pm_comparison_{date_s}.csv'
    write_csv_and_summary(final, out_csv, {'animation':'am_pm_comparison','date':date_s})
    print('Kepler side-by-side mode: use comparison_latitude and comparison_longitude.')
    print('Kepler true-location mode: use latitude and longitude, colour by peak_period.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
