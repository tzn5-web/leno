@echo off
setlocal
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
echo PHASER360 FULL AUDIO DRIVER INSTALL
echo Installs ADSP + SOF + WaveRT + MAX98357A + Windows speaker endpoint.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_FULL_INSTALL.ps1" -Mode Install
set RC=%ERRORLEVEL%
echo.
echo Return code: %RC%
pause
exit /b %RC%
