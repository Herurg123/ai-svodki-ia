@echo off
setlocal
cd /d "%~dp0"
node "%~dp0dzen-browser-runner.js" %*
exit /b %errorlevel%
