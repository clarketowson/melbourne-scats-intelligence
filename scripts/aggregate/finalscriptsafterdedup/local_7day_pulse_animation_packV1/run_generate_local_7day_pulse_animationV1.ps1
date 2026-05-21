$ErrorActionPreference = "Stop"

Write-Host "Running local 7-day SCATS pulse animation renderer V1..." -ForegroundColor Cyan

python .\generate_local_7day_pulse_animationV1.py

if ($LASTEXITCODE -ne 0) {
  throw "Python renderer failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Optional next step: .\add_music_to_local_7day_pulse_animationV1.ps1" -ForegroundColor Yellow
