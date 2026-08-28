@echo off
setlocal
cd /d "%~dp0"
node "%~dp0scheduled-worker.js"
exit /b %errorlevel%