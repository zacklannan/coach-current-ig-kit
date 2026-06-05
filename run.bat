@echo off
REM Double-click to pull your Instagram data and build the export. (Windows)
cd /d "%~dp0"
echo ============================================
echo   Coach Current IG Kit - Export
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
if not exist ".env" (
  echo No .env found. Run setup.bat first, then add your credentials.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" ig_export.py
set "STATUS=%errorlevel%"
echo.
if "%STATUS%"=="0" (
  echo Your export is in the "export" folder.
  echo Next: open this folder as a Cowork project and ask the
  echo social-analyst skill to analyze the export.
) else (
  echo Something went wrong ^(see above^). Most common fix: re-check .env.
)
echo.
pause
