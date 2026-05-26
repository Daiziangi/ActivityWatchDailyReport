@echo off
setlocal
set "ROOT=%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell was not found.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%start_web_ui.ps1"
endlocal
