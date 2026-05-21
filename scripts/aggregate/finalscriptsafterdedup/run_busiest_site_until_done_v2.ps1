$ErrorActionPreference = 'Stop'

$PythonExe  = 'A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe'
$ScriptPath = 'A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_busiest_site_chunkedV3.py'
$MonthlyCsv = 'A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_busiest_site_monthly.csv'
$DateStart  = Get-Date '2014-01-01'
$DateEnd    = Get-Date '2026-04-01'
$TotalMonths = (($DateEnd.Year - $DateStart.Year) * 12) + ($DateEnd.Month - $DateStart.Month) + 1

$RepeatThreshold = 3
$SleepSeconds = 5

function Get-CompletedMonthsCount {
    param([string]$CsvPath)

    if (-not (Test-Path $CsvPath)) {
        return 0
    }

    try {
        $rows = Import-Csv -Path $CsvPath
        if ($null -eq $rows) {
            return 0
        }

        return ($rows |
            Where-Object { $_.month_label -and $_.month_label.Trim() -ne '' } |
            Select-Object -ExpandProperty month_label -Unique).Count
    }
    catch {
        Write-Warning "Could not read monthly CSV yet: $($_.Exception.Message)"
        return 0
    }
}

$lastCompleted = -1
$stalledLoops = 0

while ($true) {
    $completedBefore = Get-CompletedMonthsCount -CsvPath $MonthlyCsv

    Write-Host '============================================================'
    Write-Host 'BUSIEST SITE WRAPPER V2'
    Write-Host '============================================================'
    Write-Host "Completed months: $completedBefore / $TotalMonths"

    if ($completedBefore -ge $TotalMonths) {
        Write-Host 'All months complete. Wrapper exiting.'
        break
    }

    Write-Host 'Launching busiest site month...'
    Write-Host $PythonExe

    & $PythonExe $ScriptPath
    $exitCode = $LASTEXITCODE

    Write-Host "Script exit code: $exitCode"

    if ($exitCode -ne 0) {
        throw "Python script failed with exit code $exitCode"
    }

    $completedAfter = Get-CompletedMonthsCount -CsvPath $MonthlyCsv
    Write-Host "Completed months after run: $completedAfter / $TotalMonths"

    if ($completedAfter -gt $completedBefore) {
        $stalledLoops = 0
        $lastCompleted = $completedAfter
    }
    else {
        if ($completedAfter -eq $lastCompleted) {
            $stalledLoops++
        }
        else {
            $stalledLoops = 1
            $lastCompleted = $completedAfter
        }

        Write-Warning "No progress detected this run. Stalled loop count: $stalledLoops / $RepeatThreshold"

        if ($stalledLoops -ge $RepeatThreshold) {
            throw "Wrapper stopped after $stalledLoops consecutive no-progress runs. Check logs / CSV lock / SQL filters before continuing."
        }
    }

    if ($completedAfter -ge $TotalMonths) {
        Write-Host 'All months complete. Wrapper exiting.'
        break
    }

    Write-Host "Sleeping for $SleepSeconds seconds..."
    Start-Sleep -Seconds $SleepSeconds
}
