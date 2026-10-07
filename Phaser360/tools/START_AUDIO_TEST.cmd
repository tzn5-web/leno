@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title PHASER360 AUDIO ONE-SHOT

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Requesting Administrator rights...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo PHASER360 AUDIO ONE-SHOT
echo 1. Recover/verify baseline P360AdspProbe
echo 2. Load final SOF/SSP1 speaker driver
echo 3. Internal speaker tone: 2 seconds, 0.5%% full-scale
echo 4. STOP/mute and verified baseline restore
echo No automatic reboot.
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_AUDIO_GATE.ps1" -Mode Audio
set "RC=%errorlevel%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo PHASER360 AUDIO GATE: PASS
) else if "%RC%"=="10" (
    echo PHASER360 BASELINE RECOVERY NEEDS ONE WINDOWS RESTART.
    echo Restart Windows normally. The runner is scheduled to reopen
    echo automatically after login; approve the Administrator prompt.
    echo NO SPEAKER TEST WAS STARTED.
) else (
    echo PHASER360 FINAL SPEAKER TEST: FAILED / STOPPED SAFELY
    echo The runner attempted no second/retry speaker phase.
)
echo Return code: %RC%
echo Results: %%USERPROFILE%%\Desktop\P360_AUDIO_SAFE
echo ============================================================
echo.
pause
exit /b %RC%
