@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0spawn-sdd-writer.ps1" %*
exit /b %ERRORLEVEL%
