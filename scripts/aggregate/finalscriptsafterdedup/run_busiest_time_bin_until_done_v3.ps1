$python = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$script = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_busiest_time_bin_chunkedV3.py"
$json   = "A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_busiest_time_bin_final.json"

Write-Host "============================================================"
Write-Host "BUSIEST TIME BIN WRAPPER V3"
Write-Host "============================================================"
Write-Host "This version ranks the final winner by average daily volume" 
Write-Host "per time bin so a missed-day / partial-day outlier does not"
Write-Host "distort the result."
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
    Write-Host ("Running busiest time bin : {0}" -f $result.busiest_time_bin)
    Write-Host ("Running raw total volume : {0}" -f ('{0:N0}' -f [double]$result.busiest_time_bin_total_volume))
    if ($null -ne $result.busiest_time_bin_avg_daily_volume) {
        Write-Host ("Running avg/day volume  : {0:N3}" -f [double]$result.busiest_time_bin_avg_daily_volume)
    }

    if ($result.is_complete -eq $true) {
        Write-Host ""
        Write-Host "ARCHIVE COMPLETE."
        break
    }

    Write-Host ""
    Write-Host "Launching next month..."
    Start-Sleep -Seconds 1
}
