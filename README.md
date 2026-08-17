# Minecraft IP Shield

Protégez votre IP des serveurs Minecraft en routant votre trafic via Tor.

## Fonctionnement

L'application lance un proxy TCP local (`127.0.0.1:25565`) qui redirige tout le trafic Minecraft vers le serveur distant via Tor. Votre vraie IP est masquée.

```
Minecraft → 127.0.0.1:25565 → Tor → Serveur Minecraft
```

## Installation

### Via le .exe (recommandé)
1. Téléchargez `MinecraftIPShield.exe` depuis les [Releases](https://github.com/tear360/minecraft-ip-shield/releases)
2. Lancez-le — l'app s'installe automatiquement
3. Un raccourci Bureau et Menu Démarrer sont créés
4. Pour désinstaller : clic droit sur l'app → `--uninstall`

### En développement
```bash
git clone https://github.com/tear360/minecraft-ip-shield.git
pip install -r requirements.txt
python shield.pyw
```

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
├── shield.pyw        # Application principale (avec installateur intégré)
├── shield.py         # Même chose (dev)
├── build.bat         # Compile en .exe (PyInstaller)
├── start.bat         # Lance l'app (dev)
├── requirements.txt  # Dépendances Python
├── LICENSE.txt       # Licence MIT
└── README.md
```

## Build

```bash
build.bat
```

## Technos

- Python 3.14
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — interface moderne
- [PySocks](https://github.com/Anorov/PySocks) — proxy SOCKS5
- [stem](https://github.com/torproject/stem) — contrôle Tor
- [PyInstaller](https://pyinstaller.org/) — compilation .exe

## Licence

[MIT](LICENSE.txt)
