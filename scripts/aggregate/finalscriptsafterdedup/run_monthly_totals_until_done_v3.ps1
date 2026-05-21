# ============================================================
# RUN MONTHLY TOTALS V3 UNTIL DONE
# ============================================================
# Wrapper for generate_monthly_totals_chunkedV3.py
#
# V3 behavior:
# - Relaunches the Python script until monthly_totals_final.json
#   reports is_complete=true.
# - Does not rely on CSV row counts alone.
# - Does not loop forever if the Python script fails.
# - Prints current completion status after each run.
# ============================================================

$ErrorActionPreference = "Stop"

$scriptPath = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_monthly_totals_chunkedV3.py"
$finalJson  = "A:\TrafficAnalytics\PROJECTS\reports\deduped\monthly_totals_final.json"

Write-Host "============================================================"
Write-Host "MONTHLY TOTALS V3 WRAPPER"
Write-Host "============================================================"
Write-Host "Python script : $scriptPath"
Write-Host "Final JSON    : $finalJson"
Write-Host "============================================================"

$run = 0

while ($true) {
    $run++

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Launching monthly totals V3 run $run"
    Write-Host "============================================================"

    python $scriptPath
    $exitCode = $LASTEXITCODE

    Write-Host ""
    Write-Host "Python exit code : $exitCode"

    if ($exitCode -ne 0) {
        Write-Host "Python script failed. Wrapper stopping to avoid looping forever."
        exit $exitCode
    }

    if (-not (Test-Path $finalJson)) {
        Write-Host "Final JSON not found after successful Python run."
        Write-Host "Wrapper stopping to avoid looping forever."
        exit 2
    }

    try {
        $status = Get-Content $finalJson -Raw | ConvertFrom-Json
    }
    catch {
        Write-Host "Could not parse final JSON."
        Write-Host "Wrapper stopping to avoid looping forever."
        exit 3
    }

    $monthsCompleted = $status.months_completed
    $monthsTotal = $status.months_total
    $isComplete = $status.is_complete
    $grandTotal = $status.grand_total_volume
    $elapsed = $status.total_elapsed_seconds

    Write-Host "Months completed : $monthsCompleted / $monthsTotal"
    Write-Host "Is complete      : $isComplete"
    Write-Host "Grand total      : $grandTotal"
    Write-Host "Elapsed seconds  : $elapsed"

    if ($isComplete -eq $true) {
        Write-Host ""
        Write-Host "============================================================"
        Write-Host "MONTHLY TOTALS COMPLETE"
        Write-Host "============================================================"
        Write-Host "Final JSON : $finalJson"
        exit 0
    }

    if ($monthsCompleted -ge $monthsTotal) {
        Write-Host ""
        Write-Host "months_completed >= months_total but is_complete is not true."
        Write-Host "Wrapper stopping so the JSON/CSV can be inspected."
        exit 4
    }

    Write-Host "Continuing to next missing month..."
}
