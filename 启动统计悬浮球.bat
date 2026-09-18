@echo off
rem Token Audit Card Launcher (ASCII only)
rem Double-click: floating ball + independent card window (PySide6).
rem 路径全部基于 %USERPROFILE% 动态推导, 不再写死用户名, 跨机器可直接复用.
start "" "%USERPROFILE%\.workbuddy\binaries\python\envs\pyside6\Scripts\pythonw.exe" "%~dp0card_app.py"
exit /b 0
