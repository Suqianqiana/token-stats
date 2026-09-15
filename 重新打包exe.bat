@echo off
rem Token Audit Card - rebuild exe (ASCII only)
rem Double-click after changing sprites/code: rebuilds TokenStats.exe and copies it to Desktop.
setlocal
set PY=C:\Users\a3564\.workbuddy\binaries\python\envs\pyside6\Scripts\python.exe
if not exist "%PY%" (
  echo [ERROR] python not found: %PY%
  pause
  exit /b 1
)
echo Rebuilding exe ...
"%PY%" "%~dp0tools\build_exe.py" %*
echo.
echo Done. Press any key to close.
pause >nul
exit /b 0
