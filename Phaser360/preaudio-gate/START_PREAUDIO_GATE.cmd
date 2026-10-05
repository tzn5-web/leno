@echo off
setlocal
title PHASER360 PRE-AUDIO GATE
echo ============================================================
echo PHASER360 PRE-AUDIO GATE
echo Active IRQ proof via READ-ONLY HDA verb. NO AUDIO.
echo ============================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent());if($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){exit 0}else{exit 1}"
if %errorlevel% neq 0 (
 powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
 exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_P360_PREAUDIO_GATE.ps1"
set RC=%errorlevel%
echo.
echo Return Code: %RC%
pause
exit /b %RC%
