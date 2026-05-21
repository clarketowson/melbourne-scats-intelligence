# run_time_bin_breathing_animationV3.ps1
# Runs the fixed V3 Melbourne Breathes animation.

$ErrorActionPreference = "Stop"

Write-Host "Running time-bin breathing animation V3..." -ForegroundColor Cyan

python .\generate_time_bin_breathing_animationV3.py `
  --input-csv "A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv" `
  --outdir "A:\TrafficAnalytics\PROJECTS\reports\deduped\animations" `
  --fps 24 `
  --loops 3 `
  --width 2240 `
  --height 1260

Write-Host "Done." -ForegroundColor Green
