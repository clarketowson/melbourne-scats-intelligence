# Shared config for SCATS cinematic ffmpeg scripts
$ffmpegCandidates = @(
  "E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE",
  "ffmpeg"
)

$ffmpeg = $null
foreach ($candidate in $ffmpegCandidates) {
  try {
    & $candidate -version *> $null
    if ($LASTEXITCODE -eq 0) { $ffmpeg = $candidate; break }
  } catch {}
}
if (-not $ffmpeg) { throw "ffmpeg not found. Edit 00_config.ps1 and set `$ffmpeg manually." }

$videoDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped\animations"
$musicDir = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\scats animation music"
$outDir   = Join-Path $videoDir "cinematic"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Assert-File($path) {
  if (-not (Test-Path $path)) { throw "Missing file: $path" }
}

function Run-FFmpeg($argsArray) {
  Write-Host "ffmpeg $($argsArray -join ' ')" -ForegroundColor Cyan
  & $ffmpeg @argsArray
  if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed with exit code $LASTEXITCODE" }
}
