$python = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$script = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\merge_headline_metricsV3.py"
$json   = "A:\TrafficAnalytics\PROJECTS\reports\deduped\headline_metrics.json"
$status = "A:\TrafficAnalytics\PROJECTS\reports\deduped\headline_metrics_merge_status.json"

Write-Host "============================================================"
Write-Host "MERGE HEADLINE METRICS WRAPPER V3"
Write-Host "============================================================"
Write-Host "This wrapper runs the V3 merge once in strict mode."
Write-Host "It will not loop forever if an expected final JSON is missing"
Write-Host "or incomplete. Check headline_metrics_merge_status.json for"
Write-Host "the exact source status if it stops."
Write-Host ""

& $python $script --strict
$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host ("Python exit code : {0}" -f $exitCode)

if (Test-Path $status) {
    try {
        $result = Get-Content $status -Raw | ConvertFrom-Json
        Write-Host ("All sources present  : {0}" -f $result.all_sources_present)
        Write-Host ("All sources complete : {0}" -f $result.all_sources_complete)

        if ($result.missing_sources.Count -gt 0) {
            Write-Host ("Missing sources      : {0}" -f ($result.missing_sources -join ", "))
        }
        if ($result.incomplete_sources.Count -gt 0) {
            Write-Host ("Incomplete sources   : {0}" -f ($result.incomplete_sources -join ", "))
        }
        if ($result.unreadable_sources.Count -gt 0) {
            Write-Host ("Unreadable sources   : {0}" -f ($result.unreadable_sources -join ", "))
        }
    }
    catch {
        Write-Host "Could not parse diagnostic JSON."
    }
}
else {
    Write-Host "Diagnostic JSON was not created."
}

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "MERGE COMPLETE."
    Write-Host ("Headline JSON : {0}" -f $json)
    exit 0
}
elseif ($exitCode -eq 2) {
    Write-Host ""
    Write-Host "MERGE STOPPED: one or more required final JSON files are missing or incomplete."
    Write-Host "This is a terminal stop condition, not something this wrapper should retry forever."
    Write-Host ("Diagnostic JSON : {0}" -f $status)
    exit 2
}
else {
    Write-Host ""
    Write-Host "MERGE FAILED with unexpected Python exit code."
    exit $exitCode
}
