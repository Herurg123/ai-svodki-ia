@echo off
setlocal
cd /d "%~dp0"
node "%~dp0dzen-publish.js" --dry-run %*
exit /b %errorlevel%
