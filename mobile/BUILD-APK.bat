@echo off
title Kuching Trip Advisor - build an installable APK
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 goto nonode
call npm install --no-audit --no-fund

echo.
echo This builds an APK in Expo's cloud. You need a free Expo account: https://expo.dev/signup
echo.
echo Step 1 of 2: sign in to Expo
call npx --yes eas-cli@latest whoami >nul 2>nul
if errorlevel 1 call npx --yes eas-cli@latest login

echo.
echo Step 2 of 2: build. The first time it asks two questions - answer Y to both:
echo   - create an EAS project for this app
echo   - generate a new Android keystore
echo The build itself runs in the cloud and takes about 10 to 20 minutes.
echo When it finishes you get a link and a QR code: open it on your phone to download and install the APK.
echo.
call npx --yes eas-cli@latest build -p android --profile preview
echo.
pause
exit /b

:nonode
echo Node.js is not installed. Run OPEN-LAUNCHER.bat first.
pause
