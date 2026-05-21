# Local 7-Day SCATS Pulse Animation Pack V1

This renders your 7-day Kepler pulse CSV locally using Python and ffmpeg.

It does not use Kepler.gl.

## Input

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_city_pulse_7days_2024-05-13_to_2024-05-19.csv
```

## Run

```powershell
.\run_generate_local_7day_pulse_animationV1.ps1
```

or:

```powershell
python .\generate_local_7day_pulse_animationV1.py
```

## Add music

```powershell
.\add_music_to_local_7day_pulse_animationV1.ps1
```

## Outputs

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\local_7day_pulse_animation.mp4
A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\local_7day_pulse_with_music.mp4
```

## Debug run

To test only the first 20 frames:

```powershell
python .\generate_local_7day_pulse_animationV1.py --max-frames 20 --keep-frames
```
