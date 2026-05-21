#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from _common_scats_kepler import *

DEFAULT_DATES = [
    ('2019-05-15', 'Pre-COVID baseline'),
    ('2020-08-05', 'Lockdown / COVID shock'),
    ('2021-08-05', 'Extended disruption'),
    ('2022-05-18', 'Recovery phase'),
    ('2024-05-15', 'Recent normal'),
    ('2025-12-12', 'Busiest day detected'),
]


def parse_dates(value: str):
    # Format: YYYY-MM-DD:Label,YYYY-MM-DD:Label
    out = []
    if not value:
        return DEFAULT_DATES
    for part in value.split(','):
        if ':' in part:
            d, label = part.split(':', 1)
        else:
            d, label = part, part
        out.append((pd.to_datetime(d.strip()).strftime('%Y-%m-%d'), label.strip()))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description='Export selected comparison days for Kepler.gl COVID collapse/recovery animation.')
    p.add_argument('--dates', default='', help='Comma list: YYYY-MM-DD:Label,YYYY-MM-DD:Label')
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

    dates = parse_dates(args.dates)
    min_d = min(d for d, _ in dates)
    max_d = max(d for d, _ in dates)
    label_map = dict(dates)

    print('='*90)
    print('KEPLER COVID COLLAPSE / RECOVERY COMPARISON DAYS EXPORT V1')
    print('='*90)
    print('Selected days:')
    for d, label in dates:
        print(f'  {d} - {label}')

    meta = load_metadata(Path(args.metadata))
    con = connect_duckdb(Path(args.main_db), Path(args.cont_db), Path(args.rec_db), Path(args.temp_dir), args.memory_limit, args.threads)
    raw = query_site_time(con, min_d, max_d)
    raw['date_s'] = pd.to_datetime(raw['count_date']).dt.strftime('%Y-%m-%d')
    raw = raw[raw['date_s'].isin(label_map)].drop(columns=['date_s'])
    final = enrich_for_kepler(raw, meta, min_volume=args.min_volume)
    final['comparison_period'] = final['date_label'].map(label_map)
    # Give each comparison day a sequential synthetic date so Kepler can animate them evenly.
    sequence_map = {d: i for i, (d, _) in enumerate(dates)}
    final['comparison_sequence'] = final['date_label'].map(sequence_map)
    base = pd.Timestamp('2030-01-01')
    final['animation_timestamp'] = [base + pd.Timedelta(days=int(seq)) + pd.Timedelta(hours=int(h), minutes=int(m)) for seq,h,m in zip(final['comparison_sequence'], final['hour'], final['minute'])]
    final = final[[
        'animation_timestamp','timestamp','date_label','comparison_sequence','comparison_period','time_label','hour','minute',
        'site_id','site_name','latitude','longitude','volume','scaled_volume','scaled_volume_0_100','intensity_band'
    ]].sort_values(['animation_timestamp','volume'], ascending=[True, False])
    out_csv = Path(args.outdir) / 'kepler_covid_collapse_recovery_comparison_days.csv'
    write_csv_and_summary(final, out_csv, {'animation':'covid_collapse_recovery_comparison','selected_dates':','.join(label_map.keys())})
    print('Kepler tip: use animation_timestamp as time field; colour by comparison_period.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
