# All SCATS Sites Cinematic Animation Pack V1

This pack creates a full-network cinematic animation showing all mapped Melbourne SCATS sites.

## Files

- `generate_all_scats_sites_animationV1.py`
- `run_all_scats_sites_animationV1.ps1`
- `add_music_to_all_scats_sites_animation.ps1`

## Run animation

```powershell
.\run_all_scats_sites_animationV1.ps1
```

Output:

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\all_scats_sites_animation.mp4
```

## Add music

```powershell
.\add_music_to_all_scats_sites_animation.ps1
```

Output:

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\all_scats_sites_with_music.mp4
```

## Default music

Uses:

```text
A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\scats animation music\Traffic Weather Radar.mp3
```

You can change the `$music` variable in the PowerShell script to use another soundtrack.
