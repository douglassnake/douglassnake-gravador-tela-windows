@echo off
setlocal EnableExtensions
title Gravador de Tela Windows v1.3 - inicializacao
REM Usa caminho absoluto: funciona mesmo aberto de pasta de rede (UNC).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR.ps1" -Acao Iniciar
if not errorlevel 1 exit /b 0
echo.
echo Falha na inicializacao. Execute DIAGNOSTICO.bat e envie diagnostico_completo.txt.
echo Pasta de trabalho: "%LOCALAPPDATA%\GravadorTelaWin"
pause
exit /b 1
