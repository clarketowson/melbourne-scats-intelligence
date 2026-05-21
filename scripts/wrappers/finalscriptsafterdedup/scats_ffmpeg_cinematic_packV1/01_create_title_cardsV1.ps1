. "$PSScriptRoot\00_config.ps1"

# Creates short title/intertitle MP4 cards that can be concatenated into documentary-style videos.
# Uses ffmpeg color source + drawtext. Arial is usually available on Windows.

$font = "C\:/Windows/Fonts/arial.ttf"
$cards = @(
  @{name="title_melbourne_breathes.mp4"; title="MELBOURNE BREATHES"; sub="A 15-minute pulse of a living city"; dur=4},
  @{name="title_seasonal_metabolism.mp4"; title="SEASONAL METABOLISM"; sub="How Melbourne moves across the year"; dur=4},
  @{name="title_top100_network.mp4"; title="TOP 100 TRAFFIC EMPIRE"; sub="The dominant SCATS nodes powering Melbourne"; dur=4},
  @{name="title_city_machine.mp4"; title="THE CITY MACHINE"; sub="SCATS traffic intelligence, 2014-2026"; dur=5}
)

foreach ($c in $cards) {
  $out = Join-Path $outDir $c.name
  $vf = "drawtext=fontfile='$font':text='$($c.title)':fontcolor=white:fontsize=72:x=(w-text_w)/2:y=(h/2)-80,drawtext=fontfile='$font':text='$($c.sub)':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=(h/2)+20,fade=t=in:st=0:d=0.8,fade=t=out:st=$($c.dur-0.8):d=0.8"
  Run-FFmpeg @("-y","-f","lavfi","-i","color=c=0x06111f:s=1920x1080:r=30:d=$($c.dur)","-vf",$vf,"-c:v","libx264","-crf","18","-pix_fmt","yuv420p",$out)
  Write-Host "Wrote $out" -ForegroundColor Green
}
