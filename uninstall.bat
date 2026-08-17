@echo off
echo ==========================================
echo   Desinstallation Minecraft IP Shield
echo ==========================================
echo.

set "APPDIR=%LOCALAPPDATA%\MinecraftIPShield"
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Minecraft IP Shield"

del "%USERPROFILE%\Desktop\Minecraft IP Shield.lnk" 2>nul
rmdir "%STARTMENU%" 2>nul
rmdir "%APPDIR%" 2>nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MinecraftIPShield" /f 2>nul

echo Desinstalle !
pause
