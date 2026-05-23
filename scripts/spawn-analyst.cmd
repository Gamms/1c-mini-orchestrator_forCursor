@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0spawn-analyst.ps1" %*
exit /b %ERRORLEVEL%
