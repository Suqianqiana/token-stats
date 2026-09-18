@echo off
chcp 65001 >nul
rem 2026-09-18 update-log: python 路径改为按当前用户目录动态解析, 不再写死用户名
"%USERPROFILE%\.workbuddy\binaries\python\envs\pyside6\Scripts\python.exe" "%~dp0sn_login.py"
echo.
echo 登录完成后可关闭此窗口
pause
