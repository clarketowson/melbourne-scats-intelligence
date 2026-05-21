# run_all_scats_animationsV1.ps1
# Runs the first animation pack.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Running SCATS animation pack V1..." -ForegroundColor Cyan

python "$ScriptDir\generate_daily_totals_animationV1.py"
python "$ScriptDir\generate_monthly_totals_animationV1.py"
python "$ScriptDir\generate_time_bin_breathing_animationV1.py"
python "$ScriptDir\generate_seasonal_metabolism_animationV1.py"
python "$ScriptDir\generate_top100_ooh_reveal_animationV1.py"

Write-Host "Done. Outputs should be in A:\TrafficAnalytics\PROJECTS\reports\deduped\animations" -ForegroundColor Green
