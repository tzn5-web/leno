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
echo 1. Recover/verify ADSP + MAX98357A baselines
echo 2. Install pinned fail-closed MAX98357A driver in mute
echo 3. Fresh PRE-AUDIO proof: SOF + IRQ + IPC3 + HOST topology
echo 4. If PRE-AUDIO passes: WaveRT speaker test, 2 s / 0.5%%
echo 5. Prove STOP/mute and restore both original drivers
echo No automatic reboot. No automatic speaker retry.
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
    echo PHASER360 AUDIO GATE: FAILED / STOPPED SAFELY
    echo The runner attempted no second/retry speaker phase.
)
echo Return code: %RC%
echo Results: %%USERPROFILE%%\Desktop\P360_AUDIO_SAFE
echo ============================================================
echo.
pause
exit /b %RC%
