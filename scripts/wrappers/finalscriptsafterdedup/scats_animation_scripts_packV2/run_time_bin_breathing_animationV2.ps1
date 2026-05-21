# run_time_bin_breathing_animationV2.ps1
# Runs only the fixed V2 Melbourne Breathing animation.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

python "$ScriptDir\generate_time_bin_breathing_animationV2.py"
