# run_generate_kepler_city_pulse_weekV1.ps1
# Exports 7 consecutive full days of SCATS site-level 15-minute data for Kepler.gl animation.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "generate_kepler_city_pulse_weekV1.py"

# Monday to Sunday example week.
$StartDate = "2024-05-13"

Write-Host "Running Kepler city pulse 7-day export V1..." -ForegroundColor Cyan
Write-Host "Start date: $StartDate"
Write-Host "End date  : automatically start date + 6 days"
Write-Host ""

python $PythonScript --start-date $StartDate

if ($LASTEXITCODE -ne 0) {
    throw "Kepler city pulse 7-day export failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Done. Kepler-ready 7-day CSV written under:" -ForegroundColor Green
Write-Host "A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_city_pulse"
