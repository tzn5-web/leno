@echo off
setlocal
cd /d "%~dp0"

echo PHASER360 WASAPI SHARED FINAL ACCEPTANCE
echo This runs exactly one physical speaker test:
echo 997 Hz, 2000 ms, less than 0.5 percent amplitude.
echo No automatic retry is performed.
echo.

"P360_WASAPI_TEST.exe"
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
  echo FINAL_ACCEPTANCE=WASAPI_SHARED_ENDPOINT_FUNCTIONAL
) else (
  echo FINAL_ACCEPTANCE=FAIL RC=%RC%
)
echo No second physical test was started automatically.
pause
exit /b %RC%
