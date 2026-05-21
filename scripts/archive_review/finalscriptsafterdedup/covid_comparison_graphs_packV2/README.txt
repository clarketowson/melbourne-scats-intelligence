# COVID Comparison Graphs Pack V2

V2 fixes:

- Fixes the broken shock vs recovery scatter plot.
- Uses site_id as the durable site key for pivoting.
- Filters tiny-baseline sites from scatter index calculations.
- Uses sane percentile-based scatter axis limits.
- Fixes title/subtitle overlap on all charts.
- Writes to a new output folder so V1 outputs are preserved.

## Run

```powershell
.\run_generate_covid_comparison_graphsV2.ps1
```

or:

```powershell
python .\generate_covid_comparison_graphsV2.py
```

## Input

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv
```

## Output

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\covid_comparison_v2
```
