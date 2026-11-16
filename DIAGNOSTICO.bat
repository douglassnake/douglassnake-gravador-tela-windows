@echo off
setlocal EnableExtensions
title Gravador de Tela Windows v1.3 - diagnostico
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR.ps1" -Acao Diagnostico
if errorlevel 1 (
  echo Diagnostico do PowerShell nao terminou corretamente.
)
echo.
echo Arquivo para enviar: "%LOCALAPPDATA%\GravadorTelaWin\diagnostico_completo.txt"
echo.
pause
