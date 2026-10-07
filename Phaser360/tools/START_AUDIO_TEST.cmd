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
echo 1. Detect/recover any incomplete previous P360 state
echo 2. Install/patch the pinned final ADSP + fail-closed MAX98357A stack
echo 3. Run all SOF/IRQ/IPC/HDA safety gates internally
echo 4. Perform ONE physical WaveRT speaker test: 2 s / 0.5%%
echo 5. If PASS: keep the final audio stack installed and ready for Windows audio
echo 6. If FAIL: automatically roll back to the exact saved baseline
echo No automatic reboot. No automatic second physical test.
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_AUDIO_GATE.ps1" -Mode Audio
set "RC=%errorlevel%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo PHASER360 AUDIO: PASS - FINAL DRIVER STACK REMAINS INSTALLED
) else if "%RC%"=="10" (
    echo PHASER360 BASELINE RECOVERY NEEDS ONE WINDOWS RESTART.
    echo Restart Windows normally. The runner is scheduled to reopen
    echo automatically after login; approve the Administrator prompt.
    echo NO SPEAKER TEST WAS STARTED.
) else (
    echo PHASER360 AUDIO: FAILED - BASELINE ROLLBACK ATTEMPTED
    echo The runner performed no second physical speaker test.
)
echo Return code: %RC%
echo Results: %%USERPROFILE%%\Desktop\P360_AUDIO_SAFE
echo Result ZIP: %%USERPROFILE%%\Desktop\P360_AUDIO_*.zip
echo ============================================================
echo.
pause
exit /b %RC%
