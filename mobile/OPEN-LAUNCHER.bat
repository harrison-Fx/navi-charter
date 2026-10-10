@echo off
title Kuching Trip Advisor - launcher
cd /d "%~dp0"

set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (python --version >nul 2>nul && set "PY=python")
if not defined PY goto nopython

%PY% -c "import customtkinter, qrcode, PIL" >nul 2>nul
if errorlevel 1 (
  echo Setting up the launcher. First time only, takes a minute...
  %PY% -m pip install --user --quiet --disable-pip-version-check customtkinter qrcode pillow
)
echo Opening the launcher. Keep this window open while you use it.
%PY% launcher.py
if errorlevel 1 pause
exit /b

:nopython
echo Python is not installed. Installing Python 3.12 with winget...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
echo.
echo Done. Close this window, then double-click OPEN-LAUNCHER.bat again.
pause
