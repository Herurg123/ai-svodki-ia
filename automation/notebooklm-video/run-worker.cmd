@echo off
setlocal
cd /d "%~dp0"
node "%~dp0full-worker.js"
exit /b %errorlevel%
