$ErrorActionPreference = "Stop"

$PythonExe = "python"
$ScriptPath = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_busiest_day_chunkedV3.py"
$FinalJson = "A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_busiest_day_final.json"
$SleepSeconds = 5
$MaxRuns = 200

Write-Host "============================================================"
Write-Host "BUSIEST DAY CHUNKED WRAPPER V3"
Write-Host "============================================================"
Write-Host "Runs one month per Python launch until the final JSON reports"
Write-Host "is_complete=true. Stops immediately on Python/script errors."
Write-Host "Script: $ScriptPath"
Write-Host "Final : $FinalJson"
Write-Host "============================================================"

for ($Run = 1; $Run -le $MaxRuns; $Run++) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Launching busiest day V3 run $Run of $MaxRuns"
    Write-Host "============================================================"

    & $PythonExe $ScriptPath
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Python exited with code $ExitCode. Wrapper will not retry forever."
        Write-Host "Fix the underlying issue, then re-run this wrapper."
        exit $ExitCode
    }

    if (Test-Path $FinalJson) {
        try {
            $Payload = Get-Content $FinalJson -Raw | ConvertFrom-Json
            $Completed = $Payload.months_completed
            $Total = $Payload.months_total
            $IsComplete = [bool]$Payload.is_complete
            Write-Host "Progress: $Completed/$Total months complete. is_complete=$IsComplete"

            if ($IsComplete) {
                Write-Host ""
                Write-Host "ARCHIVE COMPLETE: busiest day final JSON is complete."
                Write-Host "Final JSON: $FinalJson"
                exit 0
            }
        }
        catch {
            Write-Host ""
            Write-Host "ERROR: Could not read/parse final JSON: $FinalJson"
            Write-Host $_.Exception.Message
            exit 1
        }
    }
    else {
        Write-Host "Final JSON not found yet. Continuing after next successful monthly run."
    }

    Start-Sleep -Seconds $SleepSeconds
}

Write-Host ""
Write-Host "ERROR: Reached MaxRuns=$MaxRuns without is_complete=true."
Write-Host "This prevents accidental infinite looping. Check the monthly CSV/final JSON."
exit 2
