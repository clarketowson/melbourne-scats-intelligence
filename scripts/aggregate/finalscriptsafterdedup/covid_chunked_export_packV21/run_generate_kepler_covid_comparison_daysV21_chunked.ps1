$ErrorActionPreference = "Stop"

Write-Host "Running chunked COVID comparison Kepler export V2.1..." -ForegroundColor Cyan

# Run from this script's folder, but V2.1 can also find _common_scats_kepler.py in parent directories.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

python .\generate_kepler_covid_comparison_daysV21_chunked.py `
  --memory-limit 20GB `
  --threads 6 `
  --keep-chunks

Write-Host ""
Write-Host "Done." -ForegroundColor Green
