# COVID Animation Scripts Pack V1

Creates MP4 animations from:

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv
```

## Run all animations

```powershell
.\run_all_covid_animationsV1.ps1
```

## Add music

```powershell
.\add_music_to_covid_animationsV1.ps1
```

## Scripts

- `generate_covid_recovery_map_animationV1.py`
- `generate_covid_24hour_heartbeat_animationV1.py`
- `generate_covid_shock_recovery_scatter_animationV1.py`
- `generate_covid_leaderboard_animationsV1.py`
- `generate_covid_heatmap_reveal_animationV1.py`

## Output folder

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\covid
```

## Outputs

- `covid_recovery_map_animation.mp4`
- `covid_24hour_heartbeat_animation.mp4`
- `covid_shock_recovery_scatter_animation.mp4`
- `covid_top30_collapse_leaderboard_animation.mp4`
- `covid_top30_growth_leaderboard_animation.mp4`
- `covid_heatmap_reveal_animation.mp4`

Music versions are written with `_with_music.mp4`.
