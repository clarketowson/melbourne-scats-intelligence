. "$PSScriptRoot\00_config.ps1"

# Adds cinematic HUD/stat overlays to selected animations.
$font = "C\:/Windows/Fonts/arial.ttf"

$items = @(
  @{file="time_bin_breathing_with_music.mp4"; out="time_bin_breathing_HUD.mp4"; line1="MELBOURNE BREATHES"; line2="Busiest 15-min bin: 17:15 | Quietest: 03:00"},
  @{file="seasonal_metabolism_with_music.mp4"; out="seasonal_metabolism_HUD.mp4"; line1="SEASONAL METABOLISM"; line2="February peak | January low | 2014-2026"},
  @{file="top100_ooh_reveal_with_music.mp4"; out="top100_reveal_HUD.mp4"; line1="TOP 100 SCATS NODES"; line2="Ranked by 12-year cumulative vehicle movement"},
  @{file="monthly_total_growth_animation.mp4"; out="monthly_growth_HUD.mp4"; line1="12-YEAR MELBOURNE EVOLUTION"; line2="539B cleaned vehicle movements | 2014-2026"}
)

foreach ($it in $items) {
  $in = Join-Path $videoDir $it.file
  if (-not (Test-Path $in)) { Write-Host "Skipping missing $in" -ForegroundColor Yellow; continue }
  $out = Join-Path $outDir $it.out
  $vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,drawtext=fontfile='$font':text='$($it.line1)':fontcolor=white:fontsize=42:x=55:y=45:box=1:boxcolor=black@0.45:boxborderw=12,drawtext=fontfile='$font':text='$($it.line2)':fontcolor=white:fontsize=24:x=55:y=112:box=1:boxcolor=black@0.35:boxborderw=9,drawtext=fontfile='$font':text='Spotswood Trailers SCATS Intelligence':fontcolor=white@0.85:fontsize=22:x=w-text_w-45:y=h-55:box=1:boxcolor=black@0.28:boxborderw=8,setsar=1"
  Run-FFmpeg @("-y","-i",$in,"-vf",$vf,"-c:v","libx264","-crf","18","-preset","slow","-c:a","aac","-b:a","320k","-pix_fmt","yuv420p",$out)
  Write-Host "Wrote $out" -ForegroundColor Green
}
