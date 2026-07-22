@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\start-local-qa.ps1"
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" goto :error
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\start-local-qa-server.ps1"
set EXIT_CODE=%ERRORLEVEL%
:error
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
