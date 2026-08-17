@echo off
title Minecraft IP Shield - Setup
color 0B
echo.
echo  ============================================
echo   Minecraft IP Shield - Installation
echo  ============================================
echo.
echo  [1/2] Installation des dependances Python...
echo.
python -m pip install requests[socks] stem
if errorlevel 1 (
    echo.
    echo  Tentative avec pip3...
    pip3 install requests[socks] stem
)
echo.
echo  [2/2] Verification de Tor...
echo.
where tor >nul 2>&1
if %errorlevel% == 0 (
    echo  [OK] Tor trouve dans le PATH
    goto :done
)

if exist "%PROGRAMFILES%\Tor Browser\Browser\TorBrowser\Tor\tor.exe" (
    echo  [OK] Tor Browser detecte
    goto :done
)

if exist "%LOCALAPPDATA%\Tor Browser\Browser\TorBrowser\Tor\tor.exe" (
    echo  [OK] Tor Browser detecte (LocalAppData)
    goto :done
)

if exist "tor\tor.exe" (
    echo  [OK] Tor Expert Bundle detecte (dossier tor\)
    goto :done
)

echo.
echo  [!] Tor n'a pas ete trouve.
echo.
echo  Options :
echo    A) Installez Tor Browser depuis :
echo       https://www.torproject.org/download/
echo.
echo    B) Telechargez le Tor Expert Bundle depuis :
echo       https://www.torproject.org/download/tor/
echo       Exctraire le dossier "tor" dans : %~dp0
echo.
echo    C) Utilisez winget :
echo       winget install TorProject.Tor
echo.
echo  Apres installation, relancez ce script.
echo.

:done
echo.
echo  ============================================
echo   Installation terminee !
echo   Lancez start.bat pour demarrer le shield.
echo  ============================================
echo.
pause
