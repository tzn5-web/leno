@echo off
setlocal
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
echo PHASER360 Production Audio
echo Single production INF/CAT. Same-package self-healing. Final acceptance: WASAPI shared.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_PRODUCTION_INSTALL.ps1" -Mode Install
set RC=%ERRORLEVEL%
echo.
echo Return code: %RC%
pause
exit /b %RC%
