# run_generate_high_impact_scats_chartsV1.ps1
# Generates the third-wave high-impact SCATS charts from existing CSV outputs only.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "generate_high_impact_scats_chartsV1.py"

$ReportsDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped"
$OutDir     = "A:\TrafficAnalytics\PROJECTS\reports\deduped\high_impact_charts"

Write-Host "Running high-impact SCATS chart generation V1..." -ForegroundColor Cyan
Write-Host "Reports dir: $ReportsDir"
Write-Host "Output dir : $OutDir"
Write-Host ""

python $PythonScript --reports-dir $ReportsDir --outdir $OutDir

if ($LASTEXITCODE -ne 0) {
    throw "Python chart generation failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Done. High-impact charts written to:" -ForegroundColor Green
Write-Host $OutDir
