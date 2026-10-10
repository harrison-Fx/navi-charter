@echo off
title Kuching Trip Advisor - phone app
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 goto nonode

if exist node_modules goto start
echo Installing the app's packages. First time only, takes a few minutes...
call npm install
if errorlevel 1 goto failed

:start
echo.
echo Starting the app. When the QR code appears, open Expo Go on your phone and scan it.
echo Your phone and this PC must be on the same Wi-Fi.
echo If the phone can't connect, close this window and double-click START-TUNNEL.bat instead.
echo.
call npx expo start
pause
exit /b

:nonode
echo Node.js is not installed. Installing Node.js LTS now with winget...
winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
echo.
echo Done. Close this window, then double-click START-HERE.bat again.
pause
exit /b

:failed
echo.
echo Installing the packages failed. Check your internet connection and try again.
pause
