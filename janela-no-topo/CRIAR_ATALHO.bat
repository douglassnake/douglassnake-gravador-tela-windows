@echo off
setlocal
set "ORIGEM=%~dp0"
set "DESTINO=%LOCALAPPDATA%\JanelaNoTopo"
if not exist "%DESTINO%" mkdir "%DESTINO%" >nul 2>&1
copy /Y "%ORIGEM%JanelaNoTopo.ps1" "%DESTINO%\JanelaNoTopo.ps1" >nul
copy /Y "%ORIGEM%INICIAR.bat" "%DESTINO%\INICIAR.bat" >nul
if not exist "%DESTINO%\JanelaNoTopo.ps1" (
  echo Nao foi possivel copiar os arquivos.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Janela no Topo.lnk')); $s.TargetPath=(Join-Path $env:LOCALAPPDATA 'JanelaNoTopo\INICIAR.bat'); $s.WorkingDirectory=(Join-Path $env:LOCALAPPDATA 'JanelaNoTopo'); $s.IconLocation=($env:SystemRoot+'\System32\shell32.dll,44'); $s.Description='Fixar janelas do Windows acima das outras'; $s.Save()"
if errorlevel 1 (
  echo Falha ao criar atalho. Voce ainda pode usar INICIAR.bat.
) else (
  echo Atalho criado na Area de Trabalho: Janela no Topo.
)
pause
