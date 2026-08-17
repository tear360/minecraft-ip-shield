@echo off
cd /d "%~dp0"

set "APPDIR=%LOCALAPPDATA%\MinecraftIPShield"
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Minecraft IP Shield"

echo ==========================================
echo   Installation Minecraft IP Shield
echo ==========================================
echo.

mkdir "%APPDIR%" 2>nul
mkdir "%STARTMENU%" 2>nul

copy /Y "dist\MinecraftIPShield.exe" "%APPDIR%\MinecraftIPShield.exe"
copy /Y "LICENSE.txt" "%APPDIR%\LICENSE.txt"

powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%STARTMENU%\Minecraft IP Shield.lnk'); $s.TargetPath='%APPDIR%\MinecraftIPShield.exe'; $s.Save()"
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\Minecraft IP Shield.lnk'); $s.TargetPath='%APPDIR%\MinecraftIPShield.exe'; $s.Save()"

powershell -Command "New-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MinecraftIPShield' -Force | Out-Null; Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MinecraftIPShield' -Name 'DisplayName' -Value 'Minecraft IP Shield'; Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MinecraftIPShield' -Name 'UninstallString' -Value '\"%APPDIR%\uninstall.bat\"'; Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MinecraftIPShield' -Name 'InstallLocation' -Value '%APPDIR%'"

echo.
echo Installation terminee !
echo   - Raccourci Bureau : cree
echo   - Menu Demarrer   : cree
echo   - App             : %APPDIR%\MinecraftIPShield.exe
echo.
pause
