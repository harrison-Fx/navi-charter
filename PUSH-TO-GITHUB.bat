@echo off
title Kuching Trip Advisor - put this project on GitHub
cd /d "%~dp0"
set "REPO=kuching-trip-advisor"

echo This puts the project on your GitHub as a PRIVATE repository called %REPO%.
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo Installing Git...
  winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
  echo.
  echo Git installed. Close this window and double-click PUSH-TO-GITHUB.bat again.
  pause
  exit /b
)
where gh >nul 2>nul
if errorlevel 1 (
  echo Installing GitHub CLI...
  winget install -e --id GitHub.cli --accept-source-agreements --accept-package-agreements
  echo.
  echo GitHub CLI installed. Close this window and double-click PUSH-TO-GITHUB.bat again.
  pause
  exit /b
)

gh auth status >nul 2>nul
if errorlevel 1 (
  echo Step 1: sign in to GitHub. Choose "GitHub.com", "HTTPS", "Yes", then "Login with a web browser".
  echo Copy the one-time code it shows, press Enter, and paste the code in the browser.
  echo.
  gh auth login --hostname github.com --git-protocol https --web
  if errorlevel 1 goto failed
)

if not exist .git (
  git init -b main
  git add -A
  git -c user.name="Ming" -c user.email="noreply@github.com" commit -m "Kuching Trip Advisor: hackathon prototype"
)

echo.
echo Step 2: creating the repository and uploading...
gh repo view %REPO% >nul 2>nul
if errorlevel 1 goto create
for /f %%u in ('gh api user --jq .login') do set "GHUSER=%%u"
git remote get-url origin >nul 2>nul
if errorlevel 1 git remote add origin https://github.com/%GHUSER%/%REPO%.git
git push -u origin main
if errorlevel 1 goto failed
goto done

:create
gh repo create %REPO% --private --source=. --remote=origin --push
if errorlevel 1 goto failed

:done

echo.
echo Done. Opening the repository in your browser...
gh repo view %REPO% --web
pause
exit /b

:failed
echo.
echo Something went wrong. Take a screenshot of this window and send it to Claude.
pause
