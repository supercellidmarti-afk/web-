@echo off
setlocal
cd /d "%~dp0"
if not exist ".runtime\python\python.exe" (
  echo No se encontro la instalacion local de Frameforge.
  pause
  exit /b 1
)
taskkill /IM python.exe /F >nul 2>&1
echo Frameforge se ha detenido.
