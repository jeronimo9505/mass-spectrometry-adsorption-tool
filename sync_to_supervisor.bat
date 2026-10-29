@echo off
title Syncing AI Antigravity Software to Supervisor Folder
echo ======================================================================
echo Syncing to: C:\Users\Lenovo\OneDrive - unizar.es\Shayan Ph.D. Student\AI Antigravity software
echo ======================================================================
echo.

robocopy "c:\Users\Lenovo\OneDrive - unizar.es\AI Antigravity software" "C:\Users\Lenovo\OneDrive - unizar.es\Shayan Ph.D. Student\AI Antigravity software" /MIR /XD .git __pycache__ /XF *.tmp

echo.
if %ERRORLEVEL% LSS 8 (
    echo [SUCCESS] Synchronization complete! All updates are now shared on OneDrive.
) else (
    echo [ERROR] Synchronization encountered an issue. Exit code: %ERRORLEVEL%
)

echo.
timeout /t 5
