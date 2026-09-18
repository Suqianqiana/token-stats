@echo off
rem Enable auto-start with Windows startup folder (ASCII only)
rem 自启入口统一走 launcher.py, 由它动态定位 pythonw + card_app.py (PySide6),
rem 路径基于 %USERPROFILE% 动态推导, 不再写死用户名.
set "PY=%USERPROFILE%\.workbuddy\binaries\python\envs\pyside6\Scripts\pythonw.exe"
set "SCRIPT=%~dp0launcher.py"
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TokenAuditCard.lnk"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');$s.TargetPath='%PY%';$s.Arguments='%SCRIPT%';$s.WindowStyle=7;$s.Save()"
if exist "%LNK%" (
  echo Auto-start enabled: %LNK%
) else (
  echo Failed to create shortcut.
)
pause
