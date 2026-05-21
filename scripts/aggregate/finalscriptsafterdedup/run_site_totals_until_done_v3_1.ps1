# run_site_totals_until_done_v3_1.ps1
# Wrapper for generate_site_totals_chunkedV3_1.py

$ErrorActionPreference = "Stop"

$PythonExe = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$ScriptPath = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_site_totals_chunkedV3_1.py"
$FinalJson = "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals_final.json"
$LogFile = "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals_v3_1_wrapper.log"
$MaxRuns = 200

Write-Host "============================================================"
Write-Host "SITE TOTALS V3.1 WRAPPER"
Write-Host "============================================================"
Write-Host "Python exe    : $PythonExe"
Write-Host "Python script : $ScriptPath"
Write-Host "Final JSON    : $FinalJson"
Write-Host "Log file      : $LogFile"
Write-Host "Max runs      : $MaxRuns"
Write-Host "============================================================"

if (!(Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

if (!(Test-Path $ScriptPath)) {
    throw "Python script not found: $ScriptPath"
}

$logDir = Split-Path $LogFile -Parent
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

"==== SITE TOTALS V3.1 WRAPPER START $(Get-Date -Format o) ====" | Out-File -FilePath $LogFile -Encoding utf8 -Append

for ($i = 1; $i -le $MaxRuns; $i++) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Launching site totals V3.1 run $i of $MaxRuns"
    Write-Host "============================================================"

    "==== RUN $i START $(Get-Date -Format o) ====" | Out-File -FilePath $LogFile -Encoding utf8 -Append

    # Capture stdout + stderr properly. This avoids PowerShell hiding the useful Python traceback.
    & $PythonExe $ScriptPath *>&1 | Tee-Object -FilePath $LogFile -Append

    $exitCode = $LASTEXITCODE
    "==== RUN $i EXIT CODE $exitCode $(Get-Date -Format o) ====" | Out-File -FilePath $LogFile -Encoding utf8 -Append

    if ($exitCode -ne 0) {
        Write-Host ""
        Write-Host "Python script failed with exit code $exitCode"
        Write-Host "Showing last 120 log lines:"
        Write-Host "------------------------------------------------------------"
        Get-Content $LogFile -Tail 120
        Write-Host "------------------------------------------------------------"
        throw "Site totals V3.1 failed. See log: $LogFile"
    }

    if (!(Test-Path $FinalJson)) {
        Write-Host "Final JSON does not exist yet. Continuing..."
        Start-Sleep -Seconds 2
        continue
    }

    $json = Get-Content $FinalJson -Raw | ConvertFrom-Json

    Write-Host ""
    Write-Host "Current progress: $($json.months_completed) / $($json.months_total) months complete"
    Write-Host "is_complete     : $($json.is_complete)"

    if ($json.is_complete -eq $true) {
        Write-Host ""
        Write-Host "============================================================"
        Write-Host "SITE TOTALS V3.1 COMPLETE"
        Write-Host "============================================================"
        Write-Host "Distinct sites     : $($json.distinct_sites)"
        Write-Host "Top site           : $($json.top_site_id) - $($json.top_site_name)"
        Write-Host "Top site volume    : $($json.top_site_total_volume)"
        Write-Host "Grand total volume : $($json.grand_total_volume)"
        Write-Host "Zero-row months    : $($json.zero_row_months -join ', ')"
        Write-Host "============================================================"
        break
    }

    Start-Sleep -Seconds 2
}

"==== SITE TOTALS V3.1 WRAPPER END $(Get-Date -Format o) ====" | Out-File -FilePath $LogFile -Encoding utf8 -Append
