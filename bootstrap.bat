@echo off
title LIEM OS Bootstrapper
echo Starting LIEM OS automated environment bootstrapper...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Bootstrapper failed with error code %errorlevel%.
    echo Please review the errors above.
) else (
    echo.
    echo [SUCCESS] Environment successfully provisioned.
)
pause
