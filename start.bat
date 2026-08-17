@echo off
title Minecraft IP Shield
cd /d "%~dp0"
python shield.py %*
if errorlevel 1 (
    echo.
    echo  Si Python n'est pas reconnu, essayez :
    echo  py shield.py
    echo.
    pause
)
