# run_generate_month_of_year_profile_chunkedV3_until_done.ps1
#
# Relaunches generate_month_of_year_profile_chunkedV3.py until all 148 months are complete.
# Designed for the one-month-per-execution V3 script.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\run_generate_month_of_year_profile_chunkedV3_until_done.ps1

$ErrorActionPreference = "Stop"

$PythonExe = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$Script   = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_month_of_year_profile_chunkedV3.py"

$ReportDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped"
$FinalJson = Join-Path $ReportDir "month_of_year_profile_final.json"
$LogDir    = Join-Path $ReportDir "logs"
$LogFile   = Join-Path $LogDir "month_of_year_profile_chunkedV3_wrapper.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Log-Line {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Get-ProgressSummary {
    if (-not (Test-Path $FinalJson)) {
        return $null
    }

    try {
        $json = Get-Content -Raw -Path $FinalJson | ConvertFrom-Json
        return $json
    }
    catch {
        Log-Line "WARNING: Could not parse final JSON: $($_.Exception.Message)"
        return $null
    }
}

Log-Line "Starting month-of-year profile V3 wrapper"
Log-Line "Python: $PythonExe"
Log-Line "Script: $Script"
Log-Line "Final JSON: $FinalJson"

$worker = 0

while ($true) {
    $summary = Get-ProgressSummary
    if ($summary -and $summary.is_complete -eq $true) {
        Log-Line "Archive already complete: $($summary.months_completed)/$($summary.months_total) months."
        if ($summary.zero_row_months) {
            Log-Line "Zero-row months recorded: $($summary.zero_row_months -join ', ')"
        }
        break
    }

    $worker++
    Log-Line "Launching Python month worker #$worker"

    & $PythonExe $Script
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        Log-Line "ERROR: Python worker failed with exit code $exitCode"
        exit $exitCode
    }

    $summary = Get-ProgressSummary
    if ($summary) {
        Log-Line "Progress: $($summary.months_completed)/$($summary.months_total) months complete; best_month=$($summary.best_month_name); lowest_month=$($summary.lowest_month_name)"
        if ($summary.zero_row_months) {
            Log-Line "Zero-row months recorded: $($summary.zero_row_months -join ', ')"
        }

        if ($summary.is_complete -eq $true) {
            Log-Line "Archive complete."
            break
        }
    }
    else {
        Log-Line "Progress JSON not available yet; continuing."
    }

    Start-Sleep -Seconds 2
}

Log-Line "Wrapper finished."
