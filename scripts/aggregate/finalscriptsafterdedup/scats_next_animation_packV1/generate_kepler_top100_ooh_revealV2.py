#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
from _common_scats_kepler import DEFAULT_REPORTS, DEFAULT_OUTDIR


def main() -> int:
    p = argparse.ArgumentParser(description='Create a Kepler.gl reveal CSV for Top 100 SCATS/OOH opportunity nodes.')
    p.add_argument('--top100-json', default=str(Path(DEFAULT_REPORTS) / 'top100_scats_ooh_map.json'))
    p.add_argument('--outdir', default=DEFAULT_OUTDIR)
    p.add_argument('--seconds-per-rank', type=int, default=2)
    args = p.parse_args()

    path = Path(args.top100_json)
    if not path.exists():
        raise FileNotFoundError(f'Top100 JSON not found: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = []
    base = pd.Timestamp('2030-01-01 00:00:00')
    for i, item in enumerate(data, start=1):
        traffic = item.get('traffic', {}) if isinstance(item.get('traffic'), dict) else {}
        parcel = item.get('parcel', {}) if isinstance(item.get('parcel'), dict) else {}
        total = traffic.get('total_12yr', item.get('total', 0))
        daily = traffic.get('daily_avg', np.nan)
        peak = traffic.get('peak_hour', np.nan)
        rank = item.get('rank', i)
        ts = base + pd.Timedelta(seconds=(int(rank)-1) * args.seconds_per_rank)
        rows.append({
            'timestamp': ts,
            'reveal_rank': rank,
            'site_id': str(item.get('site_id','')),
            'site_name': item.get('name',''),
            'latitude': item.get('lat'),
            'longitude': item.get('lng'),
            'volume': total,
            'total_12yr': total,
            'daily_avg': daily,
            'peak_hour_estimate': peak,
            'spi': parcel.get('spi',''),
            'pfi': parcel.get('pfi',''),
            'lot': parcel.get('lot',''),
            'plan': parcel.get('plan',''),
            'traffic_heat': item.get('traffic_heat',''),
            'scaled_volume': np.log1p(float(total or 0)),
        })
    df = pd.DataFrame(rows).dropna(subset=['latitude','longitude'])
    max_scaled = df['scaled_volume'].max()
    df['scaled_volume_0_100'] = df['scaled_volume'] / max_scaled * 100 if max_scaled > 0 else 0
    df['opportunity_tier'] = pd.cut(
        df['reveal_rank'],
        bins=[0,10,25,50,100000],
        labels=['Elite Top 10','Premium Top 25','Strategic Top 50','High-Value Top 100']
    ).astype(str)
    out = Path(args.outdir) / 'kepler_top100_ooh_reveal.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    pd.Series({'animation':'top100_ooh_reveal','rows':len(df),'output_csv':str(out)}).to_json(out.with_name(out.stem + '_summary.json'), indent=2)
    print(f'Wrote: {out}')
    print('Kepler fields: latitude, longitude, timestamp, scaled_volume_0_100, opportunity_tier')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
