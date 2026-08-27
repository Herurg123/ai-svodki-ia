@echo off
setlocal
cd /d "%~dp0"
node "%~dp0dzen-publish-live.js" %*
exit /b %errorlevel%
