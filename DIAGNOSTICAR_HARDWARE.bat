@echo off
setlocal
cd /d "%~dp0"
set "REPORT=Video360_HCE_%COMPUTERNAME%_%RANDOM%.json"
if exist "video360_hce.exe" (
  "video360_hce.exe" --output "%REPORT%"
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "video360_hce.py" --output "%REPORT%"
) else (
  py -3.12 "video360_hce.py" --output "%REPORT%"
)
echo.
echo Relatorio sera salvo na pasta do diagnostico.
echo Se houve erro, copie o texto mostrado na tela.
pause