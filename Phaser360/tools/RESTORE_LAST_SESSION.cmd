@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title PHASER360 RESTORE

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Requesting Administrator rights...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo PHASER360 RESTORE LAST SESSION
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_AUDIO_GATE.ps1" -Mode Restore
set "RC=%errorlevel%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo RESTORE: PASS
) else (
    echo RESTORE: FAILED - inspect Desktop\P360_AUDIO_SAFE
)
echo Return code: %RC%
echo ============================================================
echo.
pause
exit /b %RC%
