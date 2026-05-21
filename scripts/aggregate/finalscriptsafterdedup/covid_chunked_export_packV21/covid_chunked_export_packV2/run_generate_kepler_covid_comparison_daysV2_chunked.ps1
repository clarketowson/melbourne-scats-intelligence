$ErrorActionPreference = "Stop"

Write-Host "Running chunked COVID comparison Kepler export V2..." -ForegroundColor Cyan

python .\generate_kepler_covid_comparison_daysV2_chunked.py `
  --memory-limit 20GB `
  --threads 6 `
  --keep-chunks

Write-Host ""
Write-Host "Done." -ForegroundColor Green
