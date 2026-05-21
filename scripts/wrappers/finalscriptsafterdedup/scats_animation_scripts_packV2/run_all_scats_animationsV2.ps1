# run_all_scats_animationsV2.ps1
# Runs the SCATS animation pack with the fixed V2 time-bin breathing animation.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Running SCATS animation pack V2..." -ForegroundColor Cyan

python "$ScriptDir\generate_daily_totals_animationV1.py"
python "$ScriptDir\generate_monthly_totals_animationV1.py"
python "$ScriptDir\generate_time_bin_breathing_animationV2.py"
python "$ScriptDir\generate_seasonal_metabolism_animationV1.py"
python "$ScriptDir\generate_top100_ooh_reveal_animationV1.py"

Write-Host "Done. Outputs should be in A:\TrafficAnalytics\PROJECTS\reports\deduped\animations" -ForegroundColor Green
