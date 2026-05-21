$ErrorActionPreference = "Stop"

Write-Host "Running All SCATS Sites cinematic animation V1..." -ForegroundColor Cyan

python .\generate_all_scats_sites_animationV1.py

Write-Host ""
Write-Host "Done." -ForegroundColor Green
