@echo off
setlocal EnableExtensions
title Gravador de Tela Windows v2.3 RC2 - gerar executavel
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR.ps1" -Acao GerarEXE
if errorlevel 1 (
  echo Falha na compilacao. Execute DIAGNOSTICO.bat.
) else (
  echo.
  echo Executavel gerado em: "%LOCALAPPDATA%\GravadorTelaWin\dist\GravadorTelaWin_v2_3_RC2_DESENHO.exe"
  echo Este executavel nao e assinado digitalmente.
)
pause
