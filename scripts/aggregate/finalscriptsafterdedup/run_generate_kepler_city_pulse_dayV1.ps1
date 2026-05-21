# run_generate_kepler_city_pulse_dayV1.ps1
# Exports one representative weekday of SCATS site-level 15-minute data for Kepler.gl animation.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "generate_kepler_city_pulse_dayV1.py"

$Date = "2024-05-15"

Write-Host "Running Kepler city pulse day export V1..." -ForegroundColor Cyan
Write-Host "Date: $Date"
Write-Host ""

python $PythonScript --date $Date

if ($LASTEXITCODE -ne 0) {
    throw "Kepler city pulse export failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Done. Kepler-ready CSV written under:" -ForegroundColor Green
Write-Host "A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_city_pulse"
