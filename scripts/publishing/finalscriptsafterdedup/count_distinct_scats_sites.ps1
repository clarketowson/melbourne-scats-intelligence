Write-Host "============================================================"
Write-Host "COUNT DISTINCT SCATS SITES"
Write-Host "============================================================"

$duckdb = "duckdb"

$db1 = "A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
$db2 = "A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
$db3 = "A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"

$outputDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped"
$jsonOutput = Join-Path $outputDir "distinct_sites.json"
$csvOutput  = Join-Path $outputDir "distinct_sites.csv"

$sql = @"
ATTACH '$db2' AS cont;
ATTACH '$db3' AS rec;

WITH all_sites AS (
    SELECT scats_site FROM main.scats_clean WHERE scats_site IS NOT NULL
    UNION
    SELECT scats_site FROM cont.scats_clean WHERE scats_site IS NOT NULL
    UNION
    SELECT scats_site FROM rec.scats_clean WHERE scats_site IS NOT NULL
)
SELECT COUNT(DISTINCT scats_site) AS distinct_sites
FROM all_sites;
"@

Write-Host ""
Write-Host "Running distinct site count query..."
Write-Host ""

$result = & $duckdb $db1 -readonly -csv -c "$sql"

if (-not $result) {
    Write-Host "ERROR: No result returned."
    exit 1
}

$lines = $result -split "`n"
$distinctSites = $lines[1].Trim()

Write-Host ""
Write-Host "Distinct SCATS Sites: $distinctSites"
Write-Host ""

@"
distinct_sites
$distinctSites
"@ | Set-Content -Path $csvOutput

$jsonObject = @{
    metric_name = "distinct_sites"
    distinct_sites = [int]$distinctSites
    generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    source_column = "scats_site"
    source_tables = @(
        "main.scats_clean",
        "cont.scats_clean",
        "rec.scats_clean"
    )
}

$jsonObject | ConvertTo-Json | Set-Content $jsonOutput

Write-Host "Saved:"
Write-Host $csvOutput
Write-Host $jsonOutput
Write-Host ""
Write-Host "============================================================"
Write-Host "DISTINCT SITE COUNT COMPLETE"
Write-Host "============================================================"