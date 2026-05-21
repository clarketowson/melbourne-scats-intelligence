. "$PSScriptRoot\00_config.ps1"

# Creates slow cinematic zoom versions of static-ish animations.
# Useful for documentary inserts where the original animation is graph/chart based.

$items = @(
  @{file="monthly_total_growth_animation.mp4"; out="monthly_growth_ken_burns.mp4"},
  @{file="daily_total_traffic_animation.mp4"; out="daily_total_ken_burns.mp4"}
)

foreach ($it in $items) {
  $in = Join-Path $videoDir $it.file
  if (-not (Test-Path $in)) { Write-Host "Skipping missing $in" -ForegroundColor Yellow; continue }
  $out = Join-Path $outDir $it.out
  # Gentle crop/zoom approximation: scale slightly larger, crop center, keep even dimensions.
  $vf = "scale=2048:1152:force_original_aspect_ratio=increase,crop=1920:1080:(in_w-1920)/2:(in_h-1080)/2,setsar=1"
  Run-FFmpeg @("-y","-i",$in,"-vf",$vf,"-c:v","libx264","-crf","18","-preset","slow","-c:a","aac","-b:a","256k","-pix_fmt","yuv420p",$out)
  Write-Host "Wrote $out" -ForegroundColor Green
}
