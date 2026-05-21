$python = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$script = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_time_bin_profile_chunkedV3.py"
$finalJson = "A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile_final.json"

$maxRuns = 200

Write-Host "============================================================"
Write-Host "TIME BIN PROFILE V3 WRAPPER"
Write-Host "============================================================"
Write-Host "Python script : $script"
Write-Host "Final JSON    : $finalJson"
Write-Host "Max runs      : $maxRuns"
Write-Host "============================================================"

for ($i = 1; $i -le $maxRuns; $i++) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Launching time-bin profile V3 run $i of $maxRuns"
    Write-Host "============================================================"

    & $python $script
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Python script exited with code $exitCode"
        exit $exitCode
    }

    if (Test-Path $finalJson) {
        try {
            $json = Get-Content $finalJson -Raw | ConvertFrom-Json

            Write-Host ""
            Write-Host "Current progress: $($json.months_completed) / $($json.months_total) months complete"
            Write-Host "is_complete     : $($json.is_complete)"

            if ($json.is_complete -eq $true) {
                Write-Host ""
                Write-Host "============================================================"
                Write-Host "TIME BIN PROFILE V3 COMPLETE"
                Write-Host "============================================================"
                Write-Host "Busiest time bin  : $($json.busiest_time_bin)"
                Write-Host "Busiest bin volume: $($json.busiest_time_bin_total_volume)"
                Write-Host "Total days loaded : $($json.total_days_loaded)"
                Write-Host "Zero-row months   : $($json.zero_row_months -join ', ')"
                Write-Host "============================================================"
                exit 0
            }
        }
        catch {
            Write-Host "WARNING: Could not parse final JSON yet. Continuing."
        }
    }
    else {
        Write-Host "WARNING: Final JSON not found yet. Continuing."
    }

    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "WARNING: Reached maxRuns=$maxRuns before completion."
exit 1
