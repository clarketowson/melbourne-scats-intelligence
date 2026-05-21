SCATS Animation Scripts Pack V2
================================

This is the same basic animation pack as V1, but with a fixed time-bin breathing script.

Main fix
--------
The V1 time-bin breathing script expected columns like:
  avg_daily_volume
  volume

But your completed time_bin_profile.csv actually uses:
  month_label
  month_start
  next_month_start
  time_bin
  month_time_bin_volume
  days_in_month_loaded
  month_elapsed_seconds
  completed_at_epoch
  row_type

V2 now detects month_time_bin_volume and days_in_month_loaded, aggregates all months by time_bin, and calculates:
  avg_daily_volume = sum(month_time_bin_volume) / sum(days_in_month_loaded)

Run all animations
------------------
From PowerShell inside this folder:

  .\run_all_scats_animationsV2.ps1

Run only the fixed breathing animation
--------------------------------------

  .\run_time_bin_breathing_animationV2.ps1

Or directly:

  python .\generate_time_bin_breathing_animationV2.py

Default input
-------------
  A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv

Default outputs
---------------
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\time_bin_breathing_animation.mp4
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\time_bin_breathing_aggregated_profile.csv

Notes
-----
This is still a Python/ffmpeg chart animation pack, not the Kepler.gl export pack.
For the cinematic city map animations, use the Kepler CSV exporters.
