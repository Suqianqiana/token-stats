@echo off
rem Enable auto-start with Windows startup folder (ASCII only)
set "TARGET=%~dp0start_card.bat"
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TokenAuditCard.lnk"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');$s.TargetPath='%TARGET%';$s.WindowStyle=7;$s.Save()"
if exist "%LNK%" (
  echo Auto-start enabled: %LNK%
) else (
  echo Failed to create shortcut.
)
pause
