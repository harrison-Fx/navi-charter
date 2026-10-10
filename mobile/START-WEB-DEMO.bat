@echo off
title Kuching Trip Advisor - browser backup demo
cd /d "%~dp0web-demo"
rem Opens the backup demo full-window. Works offline, no server needed.
rem Press S in the page to hide the demo script panel. Press F11 for full screen.
set "PAGE=%CD%\index.html"
where chrome >nul 2>nul && (start "" chrome --new-window --start-fullscreen "%PAGE%" & exit /b)
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --new-window --start-fullscreen "%PAGE%" & exit /b)
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --new-window --start-fullscreen "%PAGE%" & exit /b)
start "" "%PAGE%"
