@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title PHASER360 AUDIO SELF-HEALING

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Requesting Administrator rights...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo PHASER360 AUDIO SELF-HEALING
echo 1. Detect clean baseline or resume persistent P360 repair state
echo 2. Install/reuse final ADSP + fail-closed MAX98357A stack
echo 3. Diagnose and repair PnP/SOF/IRQ/IPC/topology/endpoint failures
echo 4. Preflight WaveRT silently before any physical sample buffer
echo 5. Run bounded 2 s / 0.5%% playback; retry only after proved quiesce
echo 6. If PASS: keep the final audio stack installed for Windows audio
echo 7. If unresolved: preserve repair state; NO automatic baseline rollback
echo No automatic reboot. Restore is manual only.
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_AUDIO_GATE.ps1" -Mode Audio
set "RC=%errorlevel%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo PHASER360 AUDIO: PASS - FINAL DRIVER STACK REMAINS INSTALLED
) else if "%RC%"=="10" (
    echo PHASER360: ONE NORMAL WINDOWS RESTART IS REQUIRED.
    echo The runner is scheduled to reopen after login.
) else if "%RC%"=="4" (
    echo PHASER360: HARD STOP - MUTE OR STREAM QUIESCE COULD NOT BE PROVED.
    echo Do not force another playback attempt. Send the result ZIP.
) else if "%RC%"=="3" (
    echo PHASER360: DETERMINISTIC FAILURE - DRIVER PATCH REQUIRED.
    echo The P360 repair state was preserved. Send the result ZIP.
) else (
    echo PHASER360: NOT READY YET - REPAIR STATE PRESERVED, NO ROLLBACK.
)
echo Return code: %RC%
echo Results: %USERPROFILE%\Desktop\P360_AUDIO_SAFE
echo Result ZIP: %USERPROFILE%\Desktop\P360_AUDIO_*.zip
echo ============================================================
echo.
pause
exit /b %RC%
