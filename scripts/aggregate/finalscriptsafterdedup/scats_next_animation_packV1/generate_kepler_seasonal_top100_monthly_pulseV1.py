#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
from _common_scats_kepler import DEFAULT_REPORTS, DEFAULT_OUTDIR


def find_col(cols, candidates, label):
    lower = {c.lower(): c for c in cols}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    raise ValueError(f'Could not find {label}. Columns: {list(cols)}')


def main() -> int:
    p = argparse.ArgumentParser(description='Create a Kepler.gl monthly/seasonal Top 100 pulse from site_month_totals.csv.')
    p.add_argument('--site-month-csv', default=str(Path(DEFAULT_REPORTS) / 'site_month_totals.csv'))
    p.add_argument('--top100-json', default=str(Path(DEFAULT_REPORTS) / 'top100_scats_ooh_map.json'))
    p.add_argument('--outdir', default=DEFAULT_OUTDIR)
    p.add_argument('--top-n', type=int, default=100)
    args = p.parse_args()

    sm_path = Path(args.site_month_csv)
    top_path = Path(args.top100_json)
    if not sm_path.exists(): raise FileNotFoundError(f'Site-month CSV not found: {sm_path}')
    if not top_path.exists(): raise FileNotFoundError(f'Top100 JSON not found: {top_path}')

    top_data = json.loads(top_path.read_text(encoding='utf-8'))
    top_rows = []
    for i, item in enumerate(top_data[:args.top_n], start=1):
        top_rows.append({'site_id': str(item.get('site_id','')).strip(), 'rank': item.get('rank', i), 'site_name_map': item.get('name',''), 'latitude': item.get('lat'), 'longitude': item.get('lng')})
    top = pd.DataFrame(top_rows).dropna(subset=['latitude','longitude'])

    df = pd.read_csv(sm_path, low_memory=False)
    site_col = find_col(df.columns, ['site_id','scats_site','nb_scats_site','site'], 'site id')
    month_col = find_col(df.columns, ['month_start','month','month_label','date'], 'month')
    vol_col = find_col(df.columns, ['month_total_volume','site_month_total_volume','total_volume','volume'], 'volume')
    name_col = None
    for c in ['site_name','name','friendly_name']:
        if c in df.columns:
            name_col = c
            break
    slim = pd.DataFrame({
        'site_id': df[site_col].astype(str).str.strip(),
        'month_value': df[month_col],
        'volume': pd.to_numeric(df[vol_col], errors='coerce').fillna(0),
        'site_name_csv': df[name_col].astype(str) if name_col else '',
    })
    merged = slim.merge(top, on='site_id', how='inner')
    merged['timestamp'] = pd.to_datetime(merged['month_value'], errors='coerce')
    # If month label is YYYY-MM, coerce to first of month.
    missing = merged['timestamp'].isna()
    if missing.any():
        merged.loc[missing, 'timestamp'] = pd.to_datetime(merged.loc[missing, 'month_value'].astype(str) + '-01', errors='coerce')
    merged = merged.dropna(subset=['timestamp'])
    merged['month_name'] = merged['timestamp'].dt.month_name()
    merged['year'] = merged['timestamp'].dt.year
    merged['site_name'] = np.where(merged['site_name_map'].astype(str).str.len() > 0, merged['site_name_map'], merged['site_name_csv'])
    merged['scaled_volume'] = np.log1p(merged['volume'])
    max_scaled = merged['scaled_volume'].max()
    merged['scaled_volume_0_100'] = merged['scaled_volume'] / max_scaled * 100 if max_scaled > 0 else 0
    merged['rank_tier'] = pd.cut(merged['rank'], bins=[0,10,25,50,100000], labels=['Top 10','Top 25','Top 50','Top 100']).astype(str)
    final = merged[['timestamp','year','month_name','rank','rank_tier','site_id','site_name','latitude','longitude','volume','scaled_volume','scaled_volume_0_100']].sort_values(['timestamp','rank'])
    out = Path(args.outdir) / 'kepler_seasonal_top100_monthly_pulse.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(out, index=False)
    pd.Series({'animation':'seasonal_top100_monthly_pulse','rows':len(final),'top_n':args.top_n,'output_csv':str(out)}).to_json(out.with_name(out.stem + '_summary.json'), indent=2)
    print(f'Wrote: {out}')
    print('Kepler fields: latitude, longitude, timestamp, scaled_volume_0_100, rank_tier')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
