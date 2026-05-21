$python = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$script = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_peak_shares_chunkedV3.py"
$json   = "A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_peak_shares_final.json"

Write-Host "============================================================"
Write-Host "PEAK SHARES WRAPPER V3"
Write-Host "============================================================"
Write-Host "This wrapper repeatedly launches the V3 one-month-per-run"
Write-Host "peak-share script until all months are complete."
Write-Host ""

while ($true) {
    & $python $script

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Python exited with code $LASTEXITCODE"
        break
    }

    if (-not (Test-Path $json)) {
        Write-Host ""
        Write-Host "Final JSON not found yet: $json"
        Start-Sleep -Seconds 2
        continue
    }

    try {
        $result = Get-Content $json -Raw | ConvertFrom-Json
    }
    catch {
        Write-Host ""
        Write-Host "Could not parse final JSON yet. Retrying..."
        Start-Sleep -Seconds 2
        continue
    }

    Write-Host ""
    Write-Host ("Months completed : {0}/{1}" -f $result.months_completed, $result.months_total)

    if ($null -ne $result.total_volume) {
        Write-Host ("Running total volume : {0:N0}" -f [double]$result.total_volume)
    }
    if ($null -ne $result.am_volume) {
        Write-Host ("Running AM volume    : {0:N0}" -f [double]$result.am_volume)
    }
    if ($null -ne $result.pm_volume) {
        Write-Host ("Running PM volume    : {0:N0}" -f [double]$result.pm_volume)
    }

    Write-Host ("Running AM share     : {0}" -f $result.am_peak_share_formatted)
    Write-Host ("Running PM share     : {0}" -f $result.pm_peak_share_formatted)

    if ($result.is_complete -eq $true) {
        Write-Host ""
        Write-Host "ARCHIVE COMPLETE."
        break
    }

    Write-Host ""
    Write-Host "Launching next month..."
    Start-Sleep -Seconds 1
}
