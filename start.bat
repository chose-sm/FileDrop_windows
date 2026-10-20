@echo off
title FileDrop pre Windows
cd /d "%~dp0"
if exist "python\python.exe" (
    "python\python.exe" filedrop.py
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python nebol najdeny / Python not found.
        echo Stiahni prenosnu verziu / Download the portable version:
        echo https://github.com/chose-sm/FileDrop_windows/releases
    ) else (
        python filedrop.py
    )
)
pause
