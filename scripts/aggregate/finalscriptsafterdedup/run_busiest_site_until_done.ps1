$Python       = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$Script       = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_busiest_site_chunkedV2.py"
$MonthlyCsv   = "A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_busiest_site_monthly.csv"
$TargetMonths = 148
$SleepSeconds = 5

while ($true) {
    Write-Host "============================================================"
    Write-Host "BUSIEST SITE WRAPPER"
    Write-Host "============================================================"

    $completed = 0

    if (Test-Path $MonthlyCsv) {
        $completed = (
            Import-Csv $MonthlyCsv |
            Group-Object month_label |
            Measure-Object
        ).Count
    }

    Write-Host "Completed months: $completed / $TargetMonths"

    if ($completed -ge $TargetMonths) {
        Write-Host "All months completed. Exiting wrapper."
        break
    }

    if (-not (Test-Path $Python)) {
        Write-Host "Python interpreter not found:"
        Write-Host $Python
        break
    }

    if (-not (Test-Path $Script)) {
        Write-Host "Script not found:"
        Write-Host $Script
        break
    }

    Write-Host "Launching busiest site month..."
    Write-Host $Python

    & $Python $Script
    $exitCode = $LASTEXITCODE

    Write-Host "Script exit code: $exitCode"

    if ($exitCode -ne 0) {
        Write-Host "Non-zero exit code detected. Stopping wrapper."
        break
    }

    Write-Host "Sleeping for $SleepSeconds seconds..."
    Start-Sleep -Seconds $SleepSeconds
}