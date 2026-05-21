$ErrorActionPreference = "Stop"

Write-Host "Running COVID comparison Kepler export V4 standalone chunked..." -ForegroundColor Cyan

python .\generate_kepler_covid_comparison_daysV4_standalone_chunked.py `
  --memory-limit 20GB `
  --threads 6 `
  --keep-chunks

if ($LASTEXITCODE -ne 0) {
  throw "Python script failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
