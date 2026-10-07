@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title PHASER360 FINAL SPEAKER RESTORE

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "SESSION=%~1"
if "%SESSION%"=="" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_FINAL_SPEAKER_TEST.ps1" -Mode Restore
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_FINAL_SPEAKER_TEST.ps1" -Mode Restore -SessionPath "%SESSION%"
)
set "RC=%errorlevel%"
echo.
echo Restore return code: %RC%
pause
exit /b %RC%
