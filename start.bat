@echo off
cd /d "%~dp0"
pythonw.exe shield.pyw 2>nul || python.exe shield.pyw 2>nul || py -3.14 shield.pyw 2>nul || py shield.pyw 2>nul || start "" pythonw.exe "%~dp0shield.pyw"
