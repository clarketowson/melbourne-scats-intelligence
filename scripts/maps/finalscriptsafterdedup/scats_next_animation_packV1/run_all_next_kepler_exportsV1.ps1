Write-Host "Running SCATS next Kepler animation export pack V1..." -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

python .\generate_kepler_city_pulse_weekV2.py --start-date 2024-05-13
python .\generate_kepler_never_sleeps_overnightV1.py --start-date 2024-05-13 --days 7
python .\generate_kepler_am_pm_comparisonV1.py --date 2024-05-15
python .\generate_kepler_covid_comparison_daysV1.py
python .\generate_kepler_top100_ooh_revealV2.py
python .\generate_kepler_seasonal_top100_monthly_pulseV1.py

Write-Host "Done. Outputs are in A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports" -ForegroundColor Green
