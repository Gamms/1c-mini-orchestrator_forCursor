@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0spawn-implementer.ps1" %*
exit /b %ERRORLEVEL%
