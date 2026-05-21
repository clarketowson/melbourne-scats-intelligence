# run_site_month_totals_until_done_V3.ps1
#
# Relaunches generate_site_month_totals_chunkedV3.py until the archive is complete.
# Each Python launch processes exactly one next incomplete month, refreshes the JSON,
# closes DuckDB, and exits.

$ErrorActionPreference = "Stop"

$ScriptDir = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup"
$ReportDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped"
$PythonScript = Join-Path $ScriptDir "generate_site_month_totals_chunkedV3.py"
$FinalJson = Join-Path $ReportDir "site_month_totals_final.json"
$LogDir = Join-Path $ReportDir "logs"
$LogFile = Join-Path $LogDir "site_month_totals_v3_wrapper.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)

    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Get-IsComplete {
    if (-not (Test-Path $FinalJson)) {
        return $false
    }

    try {
        $json = Get-Content $FinalJson -Raw | ConvertFrom-Json
        return [bool]$json.is_complete
    }
    catch {
        Write-Log "WARNING: Could not parse final JSON yet: $($_.Exception.Message)"
        return $false
    }
}

function Show-ProgressFromJson {
    if (-not (Test-Path $FinalJson)) {
        Write-Log "No final JSON exists yet."
        return
    }

    try {
        $json = Get-Content $FinalJson -Raw | ConvertFrom-Json
        $monthsCompleted = $json.months_completed
        $monthsTotal = $json.months_total
        $rows = $json.rows_in_site_month_totals_csv
        $distinctSites = $json.distinct_sites
        $topSite = $json.top_site_id
        $topName = $json.top_site_name
        $zeroRows = @($json.zero_row_months)

        Write-Log "Progress: $monthsCompleted/$monthsTotal months complete; rows=$rows; distinct_sites=$distinctSites; top_site=$topSite - $topName"

        if ($zeroRows.Count -gt 0) {
            Write-Log ("Zero-row months recorded: " + ($zeroRows -join ", "))
        }
    }
    catch {
        Write-Log "WARNING: Could not summarize final JSON: $($_.Exception.Message)"
    }
}

Write-Log "================================================================================"
Write-Log "Starting Site Month Totals V3 wrapper"
Write-Log "ScriptDir : $ScriptDir"
Write-Log "Script    : $PythonScript"
Write-Log "Final JSON: $FinalJson"
Write-Log "Log file  : $LogFile"
Write-Log "================================================================================"

if (-not (Test-Path $PythonScript)) {
    throw "Python script not found: $PythonScript"
}

Set-Location $ScriptDir

$launchCount = 0
$failureCount = 0
$maxFailures = 3

while ($true) {
    if (Get-IsComplete) {
        Write-Log "Archive already complete before next launch."
        Show-ProgressFromJson
        break
    }

    $launchCount++
    Write-Log "Launching Python month worker #$launchCount"

    try {
        python $PythonScript 2>&1 | Tee-Object -FilePath $LogFile -Append
        $exitCode = $LASTEXITCODE

        if ($exitCode -ne 0) {
            $failureCount++
            Write-Log "Python exited with code $exitCode. Failure $failureCount/$maxFailures."

            if ($failureCount -ge $maxFailures) {
                throw "Stopping after $failureCount consecutive failures."
            }

            Start-Sleep -Seconds 10
            continue
        }

        $failureCount = 0
        Show-ProgressFromJson

        if (Get-IsComplete) {
            Write-Log "ARCHIVE COMPLETE."
            break
        }

        Start-Sleep -Seconds 2
    }
    catch {
        Write-Log "ERROR: $($_.Exception.Message)"
        throw
    }
}

Write-Log "Finished Site Month Totals V3 wrapper."
