@echo off
setlocal
cd /d "%~dp0"
node "%~dp0dzen-manual-draft-recovery.js" %*
exit /b %errorlevel%
