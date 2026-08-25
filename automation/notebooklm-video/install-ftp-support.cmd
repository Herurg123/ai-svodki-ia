@echo off
setlocal
cd /d "%~dp0"
npm install --no-audit --no-fund
exit /b %errorlevel%
