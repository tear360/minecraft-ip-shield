# Minecraft IP Shield

Protégez votre IP des serveurs Minecraft en routant votre trafic via Tor.

## Fonctionnement

L'application lance un proxy TCP local (`127.0.0.1:25565`) qui redirige tout le trafic Minecraft vers le serveur distant via Tor. Votre vraie IP est masquée.

```
Minecraft → 127.0.0.1:25565 → Tor → Serveur Minecraft
```

## Installation

### Via l'installeur
1. Téléchargez `MinecraftIPShield_Setup.exe` depuis les [Releases](https://github.com/tear360/minecraft-ip-shield/releases)
2. Lancez l'installeur
3. L'app apparaît dans votre Bureau et Menu Démarrer

### Via install.bat
1. Clonez le repo ou téléchargez le `.zip`
2. Lancez `build.bat` pour compiler le `.exe`
3. Lancez `install.bat`

### Prérequis
- [Tor Browser](https://www.torproject.org/download/) installé

## Utilisation

1. Lancez l'application
2. Tor démarre automatiquement
3. Entrez l'adresse du serveur Minecraft (ex: `mc.hypixel.net`)
4. Cliquez sur **Connecter**
5. Dans Minecraft, ajoutez le serveur `127.0.0.1:25565`
6. Connectez-vous — votre IP est masquée

### Changer d'IP
- Déconnectez-vous du serveur Minecraft
- Cliquez sur **Changer d'IP**
- Reconnectez-vous avec `127.0.0.1:25565`

## Structure

```
minecraft-ip-shield/
├── shield.pyw        # Application principale (tkinter)
├── shield.py         # Même chose (dev)
├── install.bat       # Installe l'app + raccourcis
├── uninstall.bat     # Désinstalle l'app
├── build.bat         # Compile en .exe (PyInstaller)
├── setup.bat         # Installe les dépendances Python
├── start.bat         # Lance l'app
├── requirements.txt  # Dépendances Python
└── installer.nsi     # Script installeur NSIS
```

## Développement

```bash
pip install -r requirements.txt
python shield.pyw
```

## Build

```bash
# Compile en .exe
build.bat

# Crée l'installeur (nécessite NSIS)
makensis installer.nsi
```

## Technos

- Python 3.14
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — interface moderne
- [PySocks](https://github.com/Anorov/PySocks) — proxy SOCKS5
- [stem](https://github.com/torproject/stem) — contrôle Tor
- [PyInstaller](https://pyinstaller.org/) — compilation .exe

## Licence

[MIT](LICENSE.txt)
