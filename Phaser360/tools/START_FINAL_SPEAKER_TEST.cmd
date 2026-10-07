@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title PHASER360 FINAL INTERNAL SPEAKER TEST

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Requesting Administrator rights...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo PHASER360 FINAL INTERNAL SPEAKER TEST
echo Direct path: SOF Tone -^> SSP1 -^> MAX98357A
echo Duration: exactly 2 seconds
echo Digital tone amplitude: 0.5%% full-scale ^(below 1%% cap^)
echo Automatic STOP/mute + baseline driver restore
echo No automatic reboot.
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_FINAL_SPEAKER_TEST.ps1" -Mode Audio
set "RC=%errorlevel%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo PHASER360 FINAL SPEAKER TEST: PASS
) else if "%RC%"=="10" (
    echo BASELINE RECOVERY NEEDS ONE NORMAL WINDOWS RESTART.
    echo The launcher is scheduled to reopen after login.
    echo NO NEW SPEAKER TEST WAS STARTED.
) else (
    echo PHASER360 FINAL SPEAKER TEST: FAILED / STOPPED SAFELY
)
echo Return code: %RC%
echo Results: %%USERPROFILE%%\Desktop\P360_AUDIO_SAFE
echo ============================================================
echo.
pause
exit /b %RC%
