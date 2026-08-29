@echo off
setlocal
cd /d "%~dp0"
node "%~dp0dzen-collections.js" --apply %*
exit /b %errorlevel%
