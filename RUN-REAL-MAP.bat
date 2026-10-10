@echo off
title Kuching Trip Advisor - real Greater Kuching map run
cd /d "%~dp0"
echo.
echo This runs the traffic model on the real Greater Kuching road map (OpenStreetMap).
echo The first run downloads the map once (needs internet, a few minutes), then it works offline.
echo The whole thing can take 30 to 90 minutes. Leave this window open.
echo.

set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY goto nopython

echo [1/6] Installing Python packages (numpy, networkx, matplotlib, osmnx)...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto pipfail

set OUT=outputs\real-map
if not exist "%OUT%" mkdir "%OUT%"

echo [2/6] Main results on the real map (downloads the map the first time)...
%PY% kuching_advisor.py --osm > "%OUT%\main_osm.txt" 2>&1
if errorlevel 1 goto runfail

echo [3/6] Same run without traffic from outside Kuching...
%PY% kuching_advisor.py --osm --commuters 0 > "%OUT%\main_osm_no_commuters.txt" 2>&1

echo [4/6] Leave-time scan (does leaving at 07:30 instead of 07:00 help?)...
%PY% kuching_advisor.py --osm --wave-scan --days 20 --seeds 2 > "%OUT%\wavescan_osm.txt" 2>&1

echo [5/6] Noise scan (how robust are the predictions to bad data?)...
%PY% kuching_advisor.py --osm --noise-scan --days 15 --seeds 2 > "%OUT%\noisescan_osm.txt" 2>&1

for %%F in (results_osm.csv warnings_osm.csv ledger1_osm.png calibration_osm.png wave_scan_osm.csv noise_scan_osm.csv) do if exist %%F move /y %%F "%OUT%\" >nul
%PY% pitch_numbers.py osm "%OUT%" > "%OUT%\pitch_numbers_osm.md" 2>&1

echo [6/6] Zipping results...
powershell -NoProfile -Command "Compress-Archive -Force -Path '%OUT%\*' -DestinationPath 'real-map-results.zip'"
echo.
echo Done. Results are in %OUT% and in real-map-results.zip.
echo Send real-map-results.zip to Claude (attach it in the chat).
echo.
pause
exit /b

:nopython
echo Python is not installed. Get it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), then run this again.
pause
exit /b

:pipfail
echo Installing the Python packages failed. Check your internet connection and try again.
pause
exit /b

:runfail
echo The real-map run stopped with an error. The details are in %OUT%\main_osm.txt - send that file to Claude.
pause
exit /b
