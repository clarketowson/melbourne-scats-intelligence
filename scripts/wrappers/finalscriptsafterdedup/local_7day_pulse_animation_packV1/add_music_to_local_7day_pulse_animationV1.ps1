$ErrorActionPreference = "Stop"

$ffmpeg = "E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE"
if (!(Test-Path $ffmpeg)) {
  $ffmpeg = "ffmpeg"
}

$videoDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped\animations"
$musicDir = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\scats animation music"

$inputVideo = Join-Path $videoDir "local_7day_pulse_animation.mp4"
$music = Join-Path $musicDir "Melbourne Breathes.mp3"
$outputVideo = Join-Path $videoDir "local_7day_pulse_with_music.mp4"

if (!(Test-Path $inputVideo)) {
  throw "Input video not found: $inputVideo"
}
if (!(Test-Path $music)) {
  throw "Music file not found: $music"
}

& $ffmpeg -y `
  -i "$inputVideo" `
  -i "$music" `
  -c:v libx264 `
  -crf 18 `
  -preset slow `
  -c:a aac `
  -b:a 320k `
  -shortest `
  "$outputVideo"

if ($LASTEXITCODE -ne 0) {
  throw "ffmpeg failed"
}

Write-Host ""
Write-Host "Wrote: $outputVideo" -ForegroundColor Green
