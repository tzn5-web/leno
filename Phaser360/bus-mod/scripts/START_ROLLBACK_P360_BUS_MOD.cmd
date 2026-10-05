@echo off
setlocal
title PHASER360 BUS MOD - ROLLBACK

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$id=[Security.Principal.WindowsIdentity]::GetCurrent();$p=New-Object Security.Principal.WindowsPrincipal($id);if($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){exit 0}else{exit 1}"
if %errorlevel%==0 goto :admin

echo Requesting Administrator privileges...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b

:admin
echo ============================================================
echo PHASER360 BUS MOD - ROLLBACK
echo ============================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ROLLBACK_P360_BUS_MOD.ps1"
set RC=%errorlevel%
echo.
echo Exit code: %RC%
echo.
pause
exit /b %RC%
