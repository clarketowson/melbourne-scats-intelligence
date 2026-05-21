#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
from _common_scats_kepler import *


def main() -> int:
    p = argparse.ArgumentParser(description='Export a 7-day SCATS city pulse CSV for Kepler.gl animation.')
    p.add_argument('--start-date', default='2024-05-13')
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
    end = start + pd.Timedelta(days=6)
    start_s, end_s = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    outdir = Path(args.outdir)

    print('='*90)
    print('KEPLER 7-DAY MELBOURNE CITY PULSE EXPORT V2')
    print('='*90)
    print(f'Start date    : {start_s}')
    print(f'End date      : {end_s}')
    print('Days exported : 7')

    meta = load_metadata(Path(args.metadata))
    con = connect_duckdb(Path(args.main_db), Path(args.cont_db), Path(args.rec_db), Path(args.temp_dir), args.memory_limit, args.threads)
    raw = query_site_time(con, start_s, end_s)
    final = enrich_for_kepler(raw, meta, min_volume=args.min_volume)
    final = final[[
        'timestamp','date_label','day_name','time_label','hour','minute','site_id','site_name','latitude','longitude',
        'volume','scaled_volume','scaled_volume_0_100','intensity_band'
    ]].sort_values(['timestamp','volume'], ascending=[True, False])
    out_csv = outdir / f'kepler_city_pulse_7days_{start_s}_to_{end_s}.csv'
    write_csv_and_summary(final, out_csv, {'animation':'7_day_city_pulse','start_date':start_s,'end_date':end_s,'days':7})
    print('Kepler fields: latitude, longitude, timestamp, volume/scaled_volume_0_100, intensity_band')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
