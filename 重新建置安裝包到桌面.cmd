@echo off
chcp 65001 >nul
setlocal
title 四維八德：重新建置安裝包到桌面
cd /d "%~dp0"
set "PS1=%~dp0_build\重新建置安裝包到桌面.ps1"
set "PSEXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS1%" goto nops1
if not exist "%PSEXE%" set "PSEXE=powershell.exe"
"%PSEXE%" -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
if errorlevel 1 goto failed
goto end

:nops1
echo 找不到建置腳本：
echo   %PS1%
echo 請確認這個 .cmd 放在四維八德資料夾的最上層（和 _build 資料夾同一層）。
pause
goto end

:failed
echo.
echo 建置腳本沒有正常結束，請把上面的訊息留下來。
pause

:end
endlocal
