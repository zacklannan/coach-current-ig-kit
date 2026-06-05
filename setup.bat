@echo off
REM Double-click once to set up. (Windows)
cd /d "%~dp0"
echo ============================================
echo   Coach Current IG Kit - Setup
echo ============================================
echo.

REM Find Python (use && chaining to avoid the %errorlevel%-in-block gotcha).
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python is not installed. Get it at https://www.python.org/downloads/
  echo IMPORTANT: on the installer, tick "Add Python to PATH". Then run this again.
  echo.
  pause
  exit /b 1
)
%PY% --version

if not exist ".venv\Scripts\python.exe" (
  echo Creating environment...
  %PY% -m venv .venv
)
echo Installing packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %errorlevel% neq 0 ( echo Install failed. & pause & exit /b 1 )

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo --------------------------------------------
echo   Enter your Instagram credentials
echo   (from your Meta app - see the SOP).
echo   Leave a line BLANK to keep what's already
echo   saved. This is also how you UPDATE them.
echo --------------------------------------------
set "SECRET="
set "TOKEN="
set /p "SECRET=Instagram App Secret: "
set /p "TOKEN=Token: "

if defined SECRET (set "DOSAVE=1")
if defined TOKEN (set "DOSAVE=1")
if defined DOSAVE (
  ".venv\Scripts\python.exe" save_creds.py "%SECRET%" "%TOKEN%"
  echo.
  echo Done. Now double-click run.bat.
) else (
  echo.
  echo No changes. Run setup.bat again any time to update your credentials.
)
echo.
pause
