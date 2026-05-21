$ErrorActionPreference = "Stop"

Write-Host "Running COVID comparison graph pack V1..." -ForegroundColor Cyan

python .\generate_covid_comparison_graphsV1.py

if ($LASTEXITCODE -ne 0) {
  throw "Python script failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
