@echo off
setlocal
chcp 65001 >nul
set "ORIGEM=%~dp0JanelaNoTopo.ps1"
set "DESTINO=%LOCALAPPDATA%\JanelaNoTopo"
if not exist "%ORIGEM%" (
    echo ERRO: nao encontrei JanelaNoTopo.ps1 na mesma pasta do INICIAR.bat
    pause
    exit /b 1
)
if not exist "%DESTINO%" mkdir "%DESTINO%" >nul 2>&1
if not exist "%DESTINO%" (
    echo ERRO: nao consegui criar a pasta %DESTINO%
    pause
    exit /b 1
)
if /I not "%ORIGEM%"=="%DESTINO%\JanelaNoTopo.ps1" (
    copy /Y "%ORIGEM%" "%DESTINO%\JanelaNoTopo.ps1" >nul
    if errorlevel 1 (
        echo ERRO: nao foi possivel copiar o aplicativo para o disco local.
        pause
        exit /b 1
    )
)
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL%" (
    echo ERRO: Windows PowerShell nao encontrado.
    pause
    exit /b 1
)
start "" "%POWERSHELL%" -NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File "%DESTINO%\JanelaNoTopo.ps1"
endlocal
