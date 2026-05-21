# Chunked COVID Comparison Kepler Export V2

This is a safer rewrite of `generate_kepler_covid_comparison_daysV1.py`.

## Why this version is better

V1 queried from the earliest comparison date to the latest comparison date, then filtered selected days in pandas. For dates spanning 2019 to 2025 this could force a very large scan and high memory use.

V2 processes one selected date at a time:

1. Query one day
2. Enrich with metadata
3. Write one chunk CSV
4. Print progress
5. Move to the next date
6. Merge chunks at the end

## Run

```powershell
python .\generate_kepler_covid_comparison_daysV2_chunked.py
```

or:

```powershell
.\run_generate_kepler_covid_comparison_daysV2_chunked.ps1
```

## Resume

If it stops partway through, rerun with:

```powershell
python .\generate_kepler_covid_comparison_daysV2_chunked.py --resume --keep-chunks
```

## Output

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv
```

## Kepler.gl

Use:

- time field: `animation_timestamp`
- latitude: `latitude`
- longitude: `longitude`
- size: `scaled_volume_0_100`
- colour: `comparison_period`
