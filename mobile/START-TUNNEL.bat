@echo off
title Kuching Trip Advisor - phone app (tunnel)
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Run START-HERE.bat first.
  pause
  exit /b
)
if not exist node_modules call npm install
echo.
echo Starting through a tunnel, for Wi-Fi that blocks phone-to-PC connections.
echo If it asks to install @expo/ngrok, type y and press Enter.
echo.
call npx expo start --tunnel
pause
