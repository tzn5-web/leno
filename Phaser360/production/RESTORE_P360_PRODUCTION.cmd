@echo off
setlocal
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
echo PHASER360 manual restore
echo This is never invoked automatically by the production installer.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_PRODUCTION_INSTALL.ps1" -Mode Restore
set RC=%ERRORLEVEL%
echo.
echo Return code: %RC%
pause
exit /b %RC%
