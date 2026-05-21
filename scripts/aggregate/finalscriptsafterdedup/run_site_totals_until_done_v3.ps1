<#
run_site_totals_until_done_v3.ps1

PowerShell wrapper for generate_site_totals_chunkedV3.py.
Runs the Python script repeatedly until site_totals_final.json reports is_complete = true.
#>

$ErrorActionPreference = "Stop"

$PythonExe = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$ScriptPath = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_site_totals_chunkedV3.py"
$FinalJson = "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals_final.json"
$LogDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped\logs"
$MaxRuns = 200
$SleepSeconds = 2

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Host "============================================================"
Write-Host "SITE TOTALS V3 WRAPPER"
Write-Host "============================================================"
Write-Host "Python exe    : $PythonExe"
Write-Host "Python script : $ScriptPath"
Write-Host "Final JSON    : $FinalJson"
Write-Host "Max runs      : $MaxRuns"
Write-Host "============================================================"

for ($Run = 1; $Run -le $MaxRuns; $Run++) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Launching site totals V3 run $Run of $MaxRuns"
    Write-Host "============================================================"

    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $LogFile = Join-Path $LogDir "site_totals_v3_run_${Run}_${Timestamp}.log"

    & $PythonExe $ScriptPath 2>&1 | Tee-Object -FilePath $LogFile
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Python script exited with code $ExitCode"
        Write-Host "Log file: $LogFile"
        exit $ExitCode
    }

    if (Test-Path $FinalJson) {
        $Payload = Get-Content $FinalJson -Raw | ConvertFrom-Json
        $Completed = [int]$Payload.months_completed
        $Total = [int]$Payload.months_total
        $IsComplete = [bool]$Payload.is_complete

        Write-Host ""
        Write-Host "Current progress: $Completed / $Total months complete"
        Write-Host "is_complete     : $IsComplete"

        if ($Payload.zero_row_months -and $Payload.zero_row_months.Count -gt 0) {
            Write-Host "Zero-row months : $($Payload.zero_row_months -join ', ')"
        }

        if ($IsComplete) {
            Write-Host ""
            Write-Host "============================================================"
            Write-Host "SITE TOTALS V3 COMPLETE"
            Write-Host "============================================================"
            Write-Host "Rows in CSV        : $($Payload.rows_in_site_totals_csv)"
            Write-Host "Distinct sites     : $($Payload.distinct_sites)"
            Write-Host "Top site           : $($Payload.top_site_id) - $($Payload.top_site_name)"
            Write-Host "Top site volume    : $($Payload.top_site_total_volume)"
            Write-Host "Grand total volume : $($Payload.grand_total_volume)"
            Write-Host "Elapsed seconds    : $($Payload.total_elapsed_seconds)"
            Write-Host "Final JSON         : $FinalJson"
            Write-Host "============================================================"
            exit 0
        }
    }
    else {
        Write-Host "WARNING: Final JSON not found yet: $FinalJson"
    }

    Start-Sleep -Seconds $SleepSeconds
}

Write-Host ""
Write-Host "ERROR: Reached MaxRuns=$MaxRuns before completion."
Write-Host "Check the final JSON and logs in: $LogDir"
exit 1
