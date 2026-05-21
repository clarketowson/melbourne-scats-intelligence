SCATS Animation Scripts Pack V1
================================

This pack creates five animation outputs from your completed SCATS analysis CSV/JSON files.

Default input folder:
  A:\TrafficAnalytics\PROJECTS\reports\deduped

Default output folder:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations

Requirements:
  - Python environment with pandas, numpy, matplotlib
  - ffmpeg installed and available on PATH

Scripts included:

1. generate_daily_totals_animationV1.py
   Creates: daily_total_traffic_animation.mp4
   Input: daily_totals.csv
   Concept: 12-year daily Melbourne pulse / COVID shock / recovery timeline.

2. generate_monthly_totals_animationV1.py
   Creates: monthly_total_growth_animation.mp4
   Input: monthly_totals.csv
   Concept: long-term city growth and cumulative traffic volume.

3. generate_time_bin_breathing_animationV1.py
   Creates: time_bin_breathing_animation.mp4
   Input: time_bin_profile.csv
   Concept: Melbourne Breathes, 24-hour radial rhythm.

4. generate_seasonal_metabolism_animationV1.py
   Creates: seasonal_metabolism_animation.mp4
   Input: month_of_year_profile.csv
   Concept: January-to-December traffic metabolism.

5. generate_top100_ooh_reveal_animationV1.py
   Creates: top100_ooh_reveal_animation.mp4
   Input: top100_scats_ooh_map.json
   Concept: Top 100 SCATS / OOH opportunity node reveal.

Run all:
  .\run_all_scats_animationsV1.ps1

Run individually:
  python generate_daily_totals_animationV1.py
  python generate_monthly_totals_animationV1.py
  python generate_time_bin_breathing_animationV1.py
  python generate_seasonal_metabolism_animationV1.py
  python generate_top100_ooh_reveal_animationV1.py

Notes:
  These scripts are deliberately path-configurable.
  Use --input and --outdir if your files are somewhere else.

Example:
  python generate_daily_totals_animationV1.py --input "A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals.csv" --outdir "A:\TrafficAnalytics\PROJECTS\reports\deduped\animations"
