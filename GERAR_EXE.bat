@echo off
setlocal EnableExtensions
title Gravador de Tela Windows v2.7 RC4 - gerar executavel
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR.ps1" -Acao GerarEXE
if errorlevel 1 (
  echo Falha na compilacao. Execute DIAGNOSTICO.bat.
) else (
  echo.
  echo Executavel gerado em: "%LOCALAPPDATA%\GravadorTelaWin\dist\GravadorTelaWin_v2_7_SCRCPY_RC4.exe"
  echo Este executavel nao e assinado digitalmente.
)
pause
