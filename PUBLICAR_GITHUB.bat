@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PUBLICAR_GITHUB.ps1"
set "RET=%ERRORLEVEL%"
echo.
if not "%RET%"=="0" echo Publicacao nao concluida. Veja a mensagem acima.
pause
exit /b %RET%
