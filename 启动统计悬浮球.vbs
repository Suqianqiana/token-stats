' Token Audit Card Launcher (VBS, hidden window)
' 路径全部基于 %USERPROFILE% 动态推导, 不再写死用户名, 跨机器可直接复用.
Set oWSH = CreateObject("WScript.Shell")
Set oFSO = CreateObject("Scripting.FileSystemObject")
home = oWSH.ExpandEnvironmentStrings("%USERPROFILE%")
dir  = oFSO.GetParentFolderName(WScript.ScriptFullName)
py   = home & "\.workbuddy\binaries\python\envs\pyside6\Scripts\pythonw.exe"
card = oFSO.BuildPath(dir, "card_app.py")
oWSH.Run """" & py & """ """ & card & """", 0, False
