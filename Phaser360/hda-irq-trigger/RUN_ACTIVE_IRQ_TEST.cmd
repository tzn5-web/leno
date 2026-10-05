@echo off
setlocal
title PHASER360 ACTIVE READ-ONLY IRQ TEST
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent());if($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){exit 0}else{exit 1}"
if %errorlevel% neq 0 (
 powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
 exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ACTIVE_IRQ_TEST.ps1"
set RC=%errorlevel%
echo Return Code: %RC%
pause
exit /b %RC%
