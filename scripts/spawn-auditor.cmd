@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0spawn-auditor.ps1" %*
exit /b %ERRORLEVEL%
