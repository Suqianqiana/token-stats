@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  推送到 GitHub —— 双击运行即可
rem  为什么需要这个脚本：
rem    WorkBuddy 的执行环境没有终端/GUI，Git Credential Manager
rem    弹不出登录窗口，所以第一次授权必须在本机双击运行完成。
rem    授权一次后凭据会存进 Windows 凭据管理器，以后直接用
rem    git push 即可，不再需要这个脚本。
rem ============================================================

rem [2026-11-04] 修正两处写死路径:
rem   ① PortableGit 版本已从 1.2.0 升到 1.3.0 —— 原来那条路径早已不存在,
rem      全靠下一行的 fallback 到 PATH 里的 git 才没暴露问题。
rem   ② 脚本自身已随项目迁到 D:\Deepseek-Harness-EAC\token-stats, 但用 %~dp0 相对定位,
rem      所以这里无需改动(项目根由第 3 行 cd /d "%~dp0" 决定)。
set "GIT_EXE=C:\Users\a3564\.workbuddy\binaries\PortableGit\versions\1.3.0\mingw64\bin\git.exe"
if not exist "%GIT_EXE%" set "GIT_EXE=git"

echo ============================================================
echo   token-stats  --^>  GitHub
echo ============================================================
echo.
echo [1/3] Remote:
"%GIT_EXE%" remote -v
echo.
echo [2/3] Local branch: main
"%GIT_EXE%" log --oneline -1
echo.
echo [3/3] Pushing... a browser window may open for GitHub login.
echo       Please finish the authorization (only needed ONCE),
echo       then come back to this window.
echo.
pause

echo.
"%GIT_EXE%" push -u origin main
set "RC=%ERRORLEVEL%"

echo.
echo ------------------------------------------------------------
if "%RC%"=="0" (
  echo [OK] Push succeeded.  https://github.com/Suqianqiana/token-stats
) else (
  echo [FAILED] exit code = %RC%
  echo.
  echo Most likely cause: the repository does not exist yet.
  echo Create it first (30 seconds):
  echo   1. open  https://github.com/new
  echo   2. Repository name:  token-stats
  echo   3. Select  Private
  echo   4. Do NOT tick "Add a README file" (must stay empty)
  echo   5. Click  Create repository
  echo   6. Double-click this script again
  echo.
  echo Other cause: you cancelled the authorization window.
  echo In that case just run this script again.
)
echo ------------------------------------------------------------
echo.
pause
endlocal
