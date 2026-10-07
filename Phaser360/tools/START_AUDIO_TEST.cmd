@echo off
setlocal EnableExtensions EnableDelayedExpansion
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

set "RECOVERY_SESSION="
if exist "%USERPROFILE%\Desktop\P360_AUDIO_SAFE" (
    for /f "delims=" %%D in ('dir /b /ad /o-d "%USERPROFILE%\Desktop\P360_AUDIO_SAFE\P360_AUDIO_*" 2^>nul') do (
        if not defined RECOVERY_SESSION (
            if exist "%USERPROFILE%\Desktop\P360_AUDIO_SAFE\%%D\STATE.json" (
                set "RECOVERY_SESSION=%USERPROFILE%\Desktop\P360_AUDIO_SAFE\%%D"
            )
        )
    )
)

if defined RECOVERY_SESSION (
    echo Previous hardware session found:
    echo !RECOVERY_SESSION!
    echo Running fail-closed baseline recovery first...
    echo.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_AUDIO_GATE.ps1" -Mode Restore -SessionPath "!RECOVERY_SESSION!"
    set "RRC=!errorlevel!"
    if not "!RRC!"=="0" (
        echo.
        echo ============================================================
        echo RECOVERY FAILED / BASELINE NOT PROVED.
        echo Audio test will NOT start.
        echo If the log says a Windows restart is required, restart Windows
        echo once and double-click START_AUDIO_TEST.cmd again.
        echo ============================================================
        echo.
        pause
        exit /b !RRC!
    )
    echo.
    echo PREVIOUS_SESSION_RECOVERY=PASS
    echo.
)

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
