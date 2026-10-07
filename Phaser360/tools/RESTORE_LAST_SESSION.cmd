@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title PHASER360 RESTORE

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Requesting Administrator rights...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo PHASER360 RESTORE LAST HARDWARE SESSION
echo ============================================================
echo.

set "RECOVERY_SESSION="
if exist "%USERPROFILE%\Desktop\P360_AUDIO_SAFE" (
    for /f "delims=" %%D in ('dir /b /ad /o-d "%USERPROFILE%\Desktop\P360_AUDIO_SAFE\P360_AUDIO_*" 2^>nul') do (
        if not defined RECOVERY_SESSION if exist "%USERPROFILE%\Desktop\P360_AUDIO_SAFE\%%D\STATE.json" set "RECOVERY_SESSION=%USERPROFILE%\Desktop\P360_AUDIO_SAFE\%%D"
    )
    if not defined RECOVERY_SESSION (
        for /f "delims=" %%D in ('dir /b /ad /o-d "%USERPROFILE%\Desktop\P360_AUDIO_SAFE\P360_PREAUDIO_*" 2^>nul') do (
            if not defined RECOVERY_SESSION if exist "%USERPROFILE%\Desktop\P360_AUDIO_SAFE\%%D\STATE.json" set "RECOVERY_SESSION=%USERPROFILE%\Desktop\P360_AUDIO_SAFE\%%D"
        )
    )
    if not defined RECOVERY_SESSION (
        for /f "delims=" %%D in ('dir /b /ad /o-d "%USERPROFILE%\Desktop\P360_AUDIO_SAFE\P360_BOUNDEDSPEAKER_*" 2^>nul') do (
            if not defined RECOVERY_SESSION if exist "%USERPROFILE%\Desktop\P360_AUDIO_SAFE\%%D\STATE.json" set "RECOVERY_SESSION=%USERPROFILE%\Desktop\P360_AUDIO_SAFE\%%D"
        )
    )
)

if not defined RECOVERY_SESSION (
    echo No prior hardware-changing P360 session was found.
    echo Nothing to restore.
    echo.
    pause
    exit /b 0
)

echo Recovering:
echo !RECOVERY_SESSION!
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0P360_AUDIO_GATE.ps1" -Mode Restore -SessionPath "!RECOVERY_SESSION!"
set "RC=!errorlevel!"

echo.
echo ============================================================
if "!RC!"=="0" (
    echo RESTORE: PASS
) else (
    echo RESTORE: FAILED - inspect Desktop\P360_AUDIO_SAFE
    echo If the log says a Windows restart is required, restart once and
    echo double-click RESTORE_LAST_SESSION.cmd again.
)
echo Return code: !RC!
echo ============================================================
echo.
pause
exit /b !RC!
