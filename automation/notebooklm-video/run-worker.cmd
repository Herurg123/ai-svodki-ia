@echo off
setlocal
cd /d "%~dp0"
node "%~dp0worker.js"
exit /b %errorlevel%
