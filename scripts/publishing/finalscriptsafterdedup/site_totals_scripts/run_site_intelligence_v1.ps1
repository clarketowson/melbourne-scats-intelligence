# run_site_intelligence_v1.ps1
# Update these paths if your project folder changes.

$PythonScript = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_site_intelligence_v1.py"
$InputCsv     = "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals.csv"
$OutputDir    = "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence"

# Optional: uncomment and set this if you have a SCATS site lookup/location CSV.
# $SiteLookup = "A:\TrafficAnalytics\DATA\SCATS\victorian_traffic_signals.csv"

Write-Host "============================================================"
Write-Host "GENERATE SITE INTELLIGENCE V1"
Write-Host "============================================================"
Write-Host "Python script : $PythonScript"
Write-Host "Input CSV     : $InputCsv"
Write-Host "Output dir    : $OutputDir"
Write-Host "============================================================"

if (-not (Test-Path $PythonScript)) {
    Write-Error "Python script not found: $PythonScript"
    exit 1
}

if (-not (Test-Path $InputCsv)) {
    Write-Error "Input CSV not found: $InputCsv"
    exit 1
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

# With lookup:
# python $PythonScript --input $InputCsv --output-dir $OutputDir --site-lookup $SiteLookup

# Without lookup:
python $PythonScript --input $InputCsv --output-dir $OutputDir

if ($LASTEXITCODE -ne 0) {
    Write-Error "Site intelligence script failed. Exit code: $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Done. Outputs written to: $OutputDir"
