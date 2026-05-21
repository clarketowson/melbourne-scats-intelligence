@echo off
setlocal EnableDelayedExpansion

set "SCRIPT=A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_total_cleaned_volume_chunkedV2.py"
set "MONTHLY_CSV=A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_total_cleaned_volume_monthly.csv"
set "TARGET_MONTHS=148"
set "PYTHON=python"

:loop
echo ============================================================
echo Checking progress...
echo ============================================================

set "COMPLETED=0"

if exist "%MONTHLY_CSV%" (
    for /f %%A in ('powershell -NoProfile -Command "(Import-Csv ''%MONTHLY_CSV%'').Count"') do (
        set "COMPLETED=%%A"
    )
)

if not defined COMPLETED set "COMPLETED=0"
if "!COMPLETED!"=="" set "COMPLETED=0"

echo Completed months: !COMPLETED! / %TARGET_MONTHS%

if !COMPLETED! GEQ %TARGET_MONTHS% (
    echo Target reached. Exiting.
    goto :end
)

echo Launching next month...
%PYTHON% "%SCRIPT%"
set "EXITCODE=%ERRORLEVEL%"

echo Script exit code: !EXITCODE!

if not "!EXITCODE!"=="0" (
    echo Script returned non-zero exit code. Stopping wrapper.
    goto :end
)

echo Run finished. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto :loop

:end
echo Wrapper finished.
pause
endlocal