$Python       = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$Script       = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_total_cleaned_volume_chunkedV2.py"
$MonthlyCsv   = "A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_total_cleaned_volume_monthly.csv"
$TargetMonths = 148
$SleepSeconds = 5

while ($true) {
    Write-Host "============================================================"
    Write-Host "Checking progress..."
    Write-Host "============================================================"

    $completed = 0
    if (Test-Path $MonthlyCsv) {
        $completed = @(Import-Csv $MonthlyCsv).Count
    }

    Write-Host "Completed months: $completed / $TargetMonths"

    if ($completed -ge $TargetMonths) {
        Write-Host "Target reached. Exiting."
        break
    }

    if (-not (Test-Path $Python)) {
        Write-Host "Python interpreter not found: $Python"
        break
    }

    if (-not (Test-Path $Script)) {
        Write-Host "Script not found: $Script"
        break
    }

    Write-Host "Launching next month with:"
    Write-Host $Python

    & $Python $Script
    $exitCode = $LASTEXITCODE

    Write-Host "Script exit code: $exitCode"

    if ($exitCode -ne 0) {
        Write-Host "Script returned non-zero exit code. Stopping wrapper."
        break
    }

    Write-Host "Run finished. Restarting in $SleepSeconds seconds..."
    Start-Sleep -Seconds $SleepSeconds
}