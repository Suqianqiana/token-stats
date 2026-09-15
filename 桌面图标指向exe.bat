@echo off
rem 把桌面快捷方式指向带图标的启动器 exe（双击本文件一次即可）
setlocal
set "EXE=%~dp0TokenStats.exe"
set "LNK=%USERPROFILE%\Desktop\Token统计.lnk"
if not exist "%EXE%" (
  echo [X] 找不到启动器: %EXE%
  pause
  exit /b 1
)
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell;$s=$w.CreateShortcut('%LNK%');$s.TargetPath='%EXE%';$s.WorkingDirectory='%~dp0';$s.IconLocation='%EXE%,0';$s.Description='Token 统计';$s.Save()"
if exist "%LNK%" (
  echo [OK] 桌面快捷方式已指向: %EXE%
  echo      图标也会变成我们自己的图标(可能需要在桌面按 F5 刷新)
) else (
  echo [X] 创建失败
)
pause
