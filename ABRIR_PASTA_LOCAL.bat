@echo off
setlocal EnableExtensions
if exist "%LOCALAPPDATA%\GravadorTelaWin" (
  explorer.exe "%LOCALAPPDATA%\GravadorTelaWin"
) else (
  echo A instalacao local ainda nao foi iniciada.
  pause
)
