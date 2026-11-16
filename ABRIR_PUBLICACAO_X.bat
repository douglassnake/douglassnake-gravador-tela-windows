@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ABRIR_PUBLICACAO_X.ps1"
set "RET=%ERRORLEVEL%"
echo.
if not "%RET%"=="0" echo Publicacao no X nao iniciada. Veja a mensagem acima.
pause
exit /b %RET%
