$ErrorActionPreference = "Stop"

Write-Host "Running Seasonal Top 100 Monthly Pulse Kepler export V2..." -ForegroundColor Cyan

python .\generate_kepler_seasonal_top100_monthly_pulseV2.py

Write-Host ""
Write-Host "Done." -ForegroundColor Green
