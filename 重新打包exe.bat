@echo off
rem Token Audit Card - rebuild exe (ASCII only)
rem Double-click after changing sprites/code: rebuilds TokenStats.exe and copies it to Desktop.
setlocal
rem 2026-09-18 update-log: PY 改为按当前用户目录动态解析, 不再写死用户名, 跨机器可复用
set PY=%USERPROFILE%\.workbuddy\binaries\python\envs\pyside6\Scripts\python.exe
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
