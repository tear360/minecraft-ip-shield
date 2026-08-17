; ──────────────────────────────────────────────
; Minecraft IP Shield - Installeur NSIS
; Nécessite : NSIS (https://nsis.sourceforge.io/)
; ──────────────────────────────────────────────

!include "MUI2.nsh"

Name "Minecraft IP Shield"
OutFile "MinecraftIPShield_Setup.exe"
InstallDir "$LOCALAPPDATA\MinecraftIPShield"
InstallDirRegKey HKCU "Software\MinecraftIPShield" "InstallDir"
RequestExecutionLevel user
BrandingText "Minecraft IP Shield v2.0"

!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "French"

Section "Installation"
    SetOutPath "$INSTDIR"

    File "dist\MinecraftIPShield.exe"
    File /r "tor\*.*"
    File "config.json"

    ; Raccourcis
    CreateDirectory "$SMPROGRAMS\Minecraft IP Shield"
    CreateShortCut "$SMPROGRAMS\Minecraft IP Shield\Minecraft IP Shield.lnk" "$INSTDIR\MinecraftIPShield.exe"
    CreateShortCut "$DESKTOP\Minecraft IP Shield.lnk" "$INSTDIR\MinecraftIPShield.exe"

    ; Registry
    WriteRegStr HKCU "Software\MinecraftIPShield" "InstallDir" "$INSTDIR"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateShortCut "$SMPROGRAMS\Minecraft IP Shield\Désinstaller.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Désinstallation"
    Delete "$INSTDIR\MinecraftIPShield.exe"
    Delete "$INSTDIR\config.json"
    RMDir /r "$INSTDIR\tor_data"
    RMDir /r "$INSTDIR"

    Delete "$DESKTOP\Minecraft IP Shield.lnk"
    Delete "$SMPROGRAMS\Minecraft IP Shield\Minecraft IP Shield.lnk"
    Delete "$SMPROGRAMS\Minecraft IP Shield\Désinstaller.lnk"
    RMDir "$SMPROGRAMS\Minecraft IP Shield"

    DeleteRegKey HKCU "Software\MinecraftIPShield"
SectionEnd
