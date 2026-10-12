@echo off
rem ArgusGrid setup. Options are passed through: -CheckOnly  -DryRun  -AssumeYes  -WithDemo  -DatabaseUrl <url>
rem After a fully successful setup this file deletes itself (the package must be downloaded again to repeat).
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set RC=%ERRORLEVEL%
if not "%RC%"=="0" exit /b %RC%
if exist "%~dp0.setup-done" (
    del "%~dp0.setup-done" >nul 2>&1
    (goto) 2>nul & del "%~f0"
)
exit /b 0
