@echo off
setlocal
cd /d "%~dp0"
npm ci --no-audit --no-fund
exit /b %errorlevel%
