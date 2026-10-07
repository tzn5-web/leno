@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title PHASER360 AUDIO TEST

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Requesting Administrator rights...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo PHASER360 AUDIO TEST
echo PRE-AUDIO proof first. Speaker only if every gate passes.
echo No automatic reboot.
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_AUDIO_GATE.ps1" -Mode Audio
set "RC=%errorlevel%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo PHASER360 AUDIO GATE: PASS
) else (
    echo PHASER360 AUDIO GATE: FAILED / STOPPED SAFELY
)
echo Return code: %RC%
echo Results: %%USERPROFILE%%\Desktop\P360_AUDIO_SAFE
echo ============================================================
echo.
pause
exit /b %RC%
