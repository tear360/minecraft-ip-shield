@echo off
echo.
echo  ═══════════════════════════════════════════
echo   Minecraft IP Shield - Build
echo  ═══════════════════════════════════════════
echo.

echo  [1/4] Installation de PyInstaller...
pip install pyinstaller --quiet
echo.

echo  [2/4] Installation des dépendances...
pip install "requests[socks]" stem PySocks --quiet
echo.

echo  [3/4] Compilation de l'executable...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --noconsole ^
    --name "MinecraftIPShield" ^
    --clean ^
    shield.pyw

if errorlevel 1 (
    echo.
    echo  ✗ Erreur lors de la compilation
    pause
    exit /b 1
)

echo.
echo  [4/4] Copie des fichiers nécessaires...
mkdir "dist\tor_data" 2>nul
copy /Y "config.json" "dist\" 2>nul

echo.
echo  ═══════════════════════════════════════════
echo   Build terminé !
echo   Exécutable : dist\MinecraftIPShield.exe
echo  ═══════════════════════════════════════════
echo.
pause
