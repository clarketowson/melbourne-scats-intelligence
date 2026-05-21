$ErrorActionPreference = "Stop"

Write-Host "Running All SCATS Sites animation V2 - white institutional style..." -ForegroundColor Cyan

python .\generate_all_scats_sites_animationV2.py

Write-Host ""
Write-Host "Done." -ForegroundColor Green
