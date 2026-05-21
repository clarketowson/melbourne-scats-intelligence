. "$PSScriptRoot\00_config.ps1"

# Creates split-screen comparison films from existing animations.
# You can change the file pairs below.

$pairs = @(
  @{left="time_bin_breathing_animation.mp4"; right="seasonal_metabolism_animation.mp4"; out="split_breathing_vs_seasonal.mp4"; title="Daily Rhythm vs Seasonal Metabolism"},
  @{left="daily_total_traffic_animation.mp4"; right="monthly_total_growth_animation.mp4"; out="split_daily_vs_monthly_growth.mp4"; title="Daily Volatility vs Long-Term Growth"}
)

$font = "C\:/Windows/Fonts/arial.ttf"
foreach ($p in $pairs) {
  $left = Join-Path $videoDir $p.left
  $right = Join-Path $videoDir $p.right
  if (-not (Test-Path $left) -or -not (Test-Path $right)) { Write-Host "Skipping missing pair $($p.out)" -ForegroundColor Yellow; continue }
  $out = Join-Path $outDir $p.out
  $filter = "[0:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2[left];[1:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2[right];[left][right]hstack=inputs=2,drawtext=fontfile='$font':text='$($p.title)':fontcolor=white:fontsize=38:x=(w-text_w)/2:y=28:box=1:boxcolor=black@0.55:boxborderw=12,setsar=1"
  Run-FFmpeg @("-y","-i",$left,"-i",$right,"-filter_complex",$filter,"-c:v","libx264","-crf","18","-preset","slow","-pix_fmt","yuv420p","-an","-shortest",$out)
  Write-Host "Wrote $out" -ForegroundColor Green
}
