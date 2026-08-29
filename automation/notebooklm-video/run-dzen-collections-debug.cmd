@echo off
setlocal
cd /d "%~dp0"
node "%~dp0dzen-collections.js" %*
exit /b %errorlevel%
