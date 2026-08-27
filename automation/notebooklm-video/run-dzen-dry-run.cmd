@echo off
setlocal
cd /d "%~dp0"
node "%~dp0dzen-browser-runner.js" --dry-run %*
exit /b %errorlevel%
