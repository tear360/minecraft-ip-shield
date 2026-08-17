#!/usr/bin/env python3
"""
Minecraft IP Shield v2.0
Interface graphique pour protéger votre IP des serveurs Minecraft via Tor.
"""

import sys
import os
import time
import json
import socket
import select
import subprocess
import shutil
import threading
from pathlib import Path


def ensure_deps():
    deps = {"requests[socks]": "requests", "stem": "stem", "PySocks": "socks", "customtkinter": "customtkinter"}
    missing = []
    for pkg, mod in deps.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


ensure_deps()

import customtkinter as ctk
import socks
import requests
from stem import Signal
from stem.control import Controller

VERSION = "3.0"
GITHUB_REPO = "tear360/minecraft-ip-shield"
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
TOR_DATA_DIR = BASE_DIR / "tor_data"
TOR_BINARY_DIR = BASE_DIR / "tor"
SOCKS_PORT = 9250
CONTROL_PORT = 9251
CONTROL_PASS = "minecraftshield2026"
IS_WIN = sys.platform == "win32"


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


class TorManager:
    def __init__(self):
        self.process = None
        self.config = load_config()
        self.tor_path = self._find_tor()

    def _find_tor(self):
        home = Path.home()
        tor_sub = "Browser/TorBrowser/Tor/tor.exe"
        candidates = [
            TOR_BINARY_DIR / "tor.exe",
            TOR_BINARY_DIR / "tor",
            Path(os.environ.get("PROGRAMFILES", "")) / f"Tor Browser/{tor_sub}",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / f"Tor Browser/{tor_sub}",
            Path(os.environ.get("LOCALAPPDATA", "")) / f"Tor Browser/{tor_sub}",
            home / f"AppData/Local/Tor Browser/{tor_sub}",
            home / f"Desktop/Tor Browser/{tor_sub}",
            home / f"Downloads/Tor Browser/{tor_sub}",
            home / f"Documents/Tor Browser/{tor_sub}",
        ]
        if self.config.get("tor_binary"):
            candidates.insert(0, Path(self.config["tor_binary"]))
        for p in candidates:
            if p.exists():
                return str(p)
        return shutil.which("tor")

    def _hash_pw(self, pw):
        if not self.tor_path:
            raise RuntimeError("Tor non trouv\u00e9")
        r = subprocess.run(
            [self.tor_path, "--hash-password", pw],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip().split("\n")[-1].strip()

    def _find_geoip(self):
        tor_exe = Path(self.tor_path)
        torbrowser_data = tor_exe.parent.parent / "Data" / "Tor"
        candidates = [torbrowser_data / "geoip", torbrowser_data / "geoip6"]
        if all(c.exists() for c in candidates):
            return candidates[0].parent
        return None

    def setup(self):
        if not self.tor_path:
            self.tor_path = self._find_tor()
        if not self.tor_path:
            return False
        data = TOR_DATA_DIR / "data"
        data.mkdir(parents=True, exist_ok=True)
        hashed = self._hash_pw(CONTROL_PASS)
        lines = [
            f"SocksPort {SOCKS_PORT}",
            f"ControlPort {CONTROL_PORT}",
            f"HashedControlPassword {hashed}",
            f"DataDirectory {data}",
            f"Log notice file {TOR_DATA_DIR / 'tor.log'}",
        ]
        geoip_dir = self._find_geoip()
        if geoip_dir:
            lines.append(f"GeoIPFile {geoip_dir / 'geoip'}")
            lines.append(f"GeoIPv6File {geoip_dir / 'geoip6'}")
        (TOR_DATA_DIR / "torrc").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.config["tor_binary"] = self.tor_path
        save_config(self.config)
        return True

    def start(self):
        if not self.tor_path:
            raise RuntimeError("Tor non trouv\u00e9")
        torrc = TOR_DATA_DIR / "torrc"
        if not torrc.exists():
            if not self.setup():
                raise RuntimeError("\u00c9chec configuration Tor")
        flags = 0x08000000 if IS_WIN else 0
        self.process = subprocess.Popen(
            [self.tor_path, "-f", str(torrc)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        self._wait_bootstrap()

    def _wait_bootstrap(self, timeout=120):
        start = time.time()
        last_pct = -1
        while time.time() - start < timeout:
            try:
                with Controller.from_port(port=CONTROL_PORT) as ctrl:
                    ctrl.authenticate(password=CONTROL_PASS)
                    st = ctrl.get_info("status/bootstrap-phase")
                    pct = -1
                    for part in st.split():
                        if part.startswith("PROGRESS="):
                            try:
                                pct = int(part.split("=")[1])
                            except ValueError:
                                pass
                    if pct >= 0 and pct != last_pct:
                        last_pct = pct
                    if pct >= 100:
                        return True
            except Exception:
                pass
            time.sleep(1)
        raise TimeoutError("Tor n'a pas pu se connecter")

    def new_identity(self):
        with Controller.from_port(port=CONTROL_PORT) as ctrl:
            ctrl.authenticate(password=CONTROL_PASS)
            ctrl.signal(Signal.NEWNYM)
        time.sleep(3)

    def proxy_dict(self):
        p = f"socks5h://127.0.0.1:{SOCKS_PORT}"
        return {"http": p, "https": p}

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None


class TorProxy:
    def __init__(self, tor: TorManager):
        self.tor = tor
        self.server = None
        self.proxy_port = None
        self.running = False
        self._target_host = None
        self._target_port = None

    def start(self, target_host, target_port, local_port=25565):
        self.stop()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.settimeout(1.0)
        try:
            self.server.bind(("127.0.0.1", local_port))
        except OSError:
            local_port = 12565
            self.server.bind(("127.0.0.1", local_port))
        self.server.listen(5)
        self.proxy_port = local_port
        self.running = True
        self._target_host = target_host
        self._target_port = target_port
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return local_port

    def _accept_loop(self):
        while self.running:
            try:
                client, _ = self.server.accept()
                threading.Thread(
                    target=self._handle_client, args=(client,), daemon=True
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, client_sock):
        remote_sock = None
        try:
            remote_sock = socks.socksocket()
            remote_sock.set_proxy(socks.SOCKS5, "127.0.0.1", SOCKS_PORT)
            remote_sock.settimeout(15)
            remote_sock.connect((self._target_host, self._target_port))
            remote_sock.settimeout(None)
            self._bridge(client_sock, remote_sock)
        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            if remote_sock:
                try:
                    remote_sock.close()
                except Exception:
                    pass

    def _bridge(self, s1, s2):
        socks_list = [s1, s2]
        while True:
            readable, _, ex = select.select(socks_list, [], socks_list, 60)
            if ex or not readable:
                break
            for s in readable:
                try:
                    data = s.recv(8192)
                except Exception:
                    return
                if not data:
                    return
                try:
                    (sock2 if s is s1 else s1).sendall(data)
                except Exception:
                    return

    def stop(self):
        self.running = False
        if self.server:
            try:
                self.server.close()
            except Exception:
                pass
            self.server = None


class IPChecker:
    def __init__(self, tor: TorManager):
        self.tor = tor

    def get_ip(self):
        try:
            r = requests.get(
                "https://api.ipify.org?format=json",
                proxies=self.tor.proxy_dict(), timeout=15,
            )
            return r.json().get("ip", "?")
        except Exception:
            return "?"

    def get_info(self):
        try:
            r = requests.get(
                "https://ipinfo.io/json",
                proxies=self.tor.proxy_dict(), timeout=15,
            )
            return r.json()
        except Exception:
            return {}


class Updater:
    def __init__(self):
        self.current_version = VERSION

    @staticmethod
    def _parse_ver(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except (ValueError, AttributeError):
            return (0,)

    def check(self):
        try:
            r = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                timeout=10,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            tag = data.get("tag_name", "").lstrip("v")
            if not tag:
                return None
            if self._parse_ver(tag) <= self._parse_ver(self.current_version):
                return None
            assets = data.get("assets", [])
            exe_url = None
            for a in assets:
                if a["name"].endswith(".exe") and "Setup" not in a["name"]:
                    exe_url = a["browser_download_url"]
                    break
            return {"version": tag, "url": exe_url, "notes": data.get("body", "")}
        except Exception:
            return None

    def download(self, url, on_progress=None, on_done=None, on_error=None):
        def _worker():
            try:
                r = requests.get(url, stream=True, timeout=120)
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                exe_path = sys.executable if getattr(sys, "frozen", False) else __file__
                if exe_path.endswith(".pyw") or exe_path.endswith(".py"):
                    exe_path = str(Path(BASE_DIR) / "MinecraftIPShield.exe")
                tmp = exe_path + ".update"
                downloaded = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total:
                            on_progress(downloaded, total)
                if on_done:
                    on_done(tmp, exe_path)
            except Exception as e:
                if on_error:
                    on_error(e)
        threading.Thread(target=_worker, daemon=True).start()


class StatusCard(ctk.CTkFrame):
    def __init__(self, master, label_text, **kwargs):
        super().__init__(master, fg_color="#1e2030", corner_radius=12, **kwargs)
        self.label = ctk.CTkLabel(self, text=label_text, font=("Segoe UI", 12), text_color="#9494a8", anchor="w")
        self.label.pack(fill="x", padx=16, pady=(12, 2))
        self.value = ctk.CTkLabel(self, text="...", font=("Segoe UI", 15, "bold"), text_color="#c0caf5", anchor="w")
        self.value.pack(fill="x", padx=16, pady=(0, 12))

    def set_value(self, text, color="#c0caf5"):
        self.value.configure(text=text, text_color=color)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(f"Minecraft IP Shield v{VERSION}")
        self.geometry("540x680")
        self.minsize(540, 680)
        self.maxsize(540, 680)
        self.configure(fg_color="#161824")

        self.tor = TorManager()
        self.proxy = TorProxy(self.tor)
        self.checker = IPChecker(self.tor)
        self.updater = Updater()
        self._last_host = None
        self._last_port = 25565

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(600, self._start_tor)
        self.after(3000, self._check_update)

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=(16, 12))

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))

        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(title_row, text="Minecraft IP Shield", font=("Segoe UI", 24, "bold"), text_color="#7aa2f7").pack(side="left")

        self.btn_update = ctk.CTkButton(
            title_row, text="v" + VERSION, font=("Segoe UI", 11),
            fg_color="#2a2d3e", hover_color="#3b3f57", text_color="#9494a8",
            corner_radius=6, height=28, width=60,
            command=lambda: threading.Thread(target=self._manual_check_update, daemon=True).start(),
        )
        self.btn_update.pack(side="right")

        ctk.CTkLabel(header, text="Protégez votre IP via Tor", font=("Segoe UI", 12), text_color="#6a6a8a").pack(anchor="w", pady=(2, 0))

        divider1 = ctk.CTkFrame(container, fg_color="#2a2d3e", height=1)
        divider1.pack(fill="x", pady=(0, 14))

        cards = ctk.CTkFrame(container, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 12))
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        self.card_tor = StatusCard(cards, text="Tor")
        self.card_tor.grid(row=0, column=0, padx=(0, 5), sticky="nsew")

        self.card_ip = StatusCard(cards, text="IP sortante")
        self.card_ip.grid(row=0, column=1, padx=(5, 0), sticky="nsew")

        self.card_proxy = StatusCard(container, text="Proxy local")
        self.card_proxy.pack(fill="x", pady=(0, 12))

        divider2 = ctk.CTkFrame(container, fg_color="#2a2d3e", height=1)
        divider2.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(container, text="Serveur Minecraft", font=("Segoe UI", 13, "bold"), text_color="#c0caf5", anchor="w").pack(fill="x", pady=(0, 6))

        input_frame = ctk.CTkFrame(container, fg_color="transparent")
        input_frame.pack(fill="x", pady=(0, 14))
        input_frame.columnconfigure(0, weight=1)
        input_frame.columnconfigure(1, weight=0)

        self.ent_host = ctk.CTkEntry(
            input_frame,
            placeholder_text="ex: mc.hypixel.net",
            font=("Consolas", 13),
            fg_color="#1e2030",
            border_color="#3b3f57",
            text_color="#c0caf5",
            placeholder_text_color="#4a4a6a",
            corner_radius=8,
            height=40,
        )
        self.ent_host.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.ent_host.bind("<Return>", lambda e: self._connect())

        self.ent_port = ctk.CTkEntry(
            input_frame,
            placeholder_text="25565",
            font=("Consolas", 13),
            fg_color="#1e2030",
            border_color="#3b3f57",
            text_color="#c0caf5",
            placeholder_text_color="#4a4a6a",
            corner_radius=8,
            width=80,
            height=40,
        )
        self.ent_port.grid(row=0, column=1)
        self.ent_port.insert(0, "25565")

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 6))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.btn_connect = ctk.CTkButton(
            btn_frame,
            text="Connecter",
            font=("Segoe UI", 13, "bold"),
            fg_color="#7aa2f7",
            hover_color="#5a8ae0",
            text_color="#1a1b2e",
            corner_radius=8,
            height=40,
            command=self._connect,
            state="disabled",
        )
        self.btn_connect.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.btn_disconnect = ctk.CTkButton(
            btn_frame,
            text="Stop",
            font=("Segoe UI", 13, "bold"),
            fg_color="#f7768e",
            hover_color="#d9556e",
            text_color="#1a1b2e",
            corner_radius=8,
            height=40,
            command=self._disconnect,
            state="disabled",
        )
        self.btn_disconnect.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.btn_rotate = ctk.CTkButton(
            container,
            text="Changer d'IP",
            font=("Segoe UI", 13, "bold"),
            fg_color="#e0af68",
            hover_color="#c89850",
            text_color="#1a1b2e",
            corner_radius=8,
            height=40,
            command=self._rotate,
            state="disabled",
        )
        self.btn_rotate.pack(fill="x", pady=(6, 4))

        ctk.CTkLabel(container, text="Déconnectez-vous du serveur avant de changer d'IP", font=("Segoe UI", 10), text_color="#5a5a7a").pack(pady=(0, 10))

        divider3 = ctk.CTkFrame(container, fg_color="#2a2d3e", height=1)
        divider3.pack(fill="x", pady=(0, 10))

        self.log_text = ctk.CTkTextbox(
            container,
            font=("Consolas", 11),
            fg_color="#1e2030",
            text_color="#9494a8",
            corner_radius=10,
            border_width=1,
            border_color="#2a2d3e",
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

    def _log(self, msg, color=None):
        colors = {
            "green": "#9ece6a",
            "red": "#f7768e",
            "yellow": "#e0af68",
            "blue": "#7aa2f7",
        }
        c = colors.get(color, "#9494a8")

        def _do():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"  {msg}\n")
            self.log_text.configure(state="disabled")
            self.log_text.see("end")
            # Apply color to last line
            start = self.log_text.index("end-2l")
            end = self.log_text.index("end-1l")
            self.log_text.tag_add(c, start, end)
            self.log_text.tag_config(c, text_color=c)
        self.after(0, _do)

    def _set_tor(self, text, color):
        self.after(0, lambda: self.card_tor.set_value(text, color))

    def _set_ip(self, text):
        self.after(0, lambda: self.card_ip.set_value(text, "#7aa2f7"))

    def _set_proxy(self, text, color):
        self.after(0, lambda: self.card_proxy.set_value(text, color))

    def _start_tor(self):
        self._set_tor("Démarrage...", "#e0af68")
        threading.Thread(target=self._tor_worker, daemon=True).start()

    def _tor_worker(self):
        try:
            if not self.tor.tor_path:
                self._set_tor("Non trouvé", "#f7768e")
                self._log("Tor non trouvé! Installez Tor Browser.", "red")
                return
            self._log("Démarrage de Tor...")
            self.tor.start()
            self._set_tor("Actif", "#9ece6a")
            self.after(0, lambda: self.btn_connect.configure(state="normal"))
            self.after(0, lambda: self.btn_rotate.configure(state="normal"))
            self._log("Tor actif!", "green")
            ip = self.checker.get_ip()
            self._set_ip(ip)
        except Exception as e:
            self._set_tor("Erreur", "#f7768e")
            self._log(f"Erreur Tor: {e}", "red")

    def _connect(self):
        host = self.ent_host.get().strip()
        if not host:
            self._log("Entrez une adresse de serveur.", "yellow")
            return
        port_str = self.ent_port.get().strip()
        try:
            port = int(port_str) if port_str else 25565
        except ValueError:
            port = 25565

        self._last_host = host
        self._last_port = port

        if self.proxy.running:
            self.proxy.stop()

        threading.Thread(target=self._connect_worker, args=(host, port), daemon=True).start()

    def _connect_worker(self, host, port):
        try:
            self._log(f"Connexion à {host}:{port} via Tor...")
            lp = self.proxy.start(host, port)
            self._set_proxy(f"127.0.0.1:{lp}", "#9ece6a")
            self.after(0, lambda: self.btn_connect.configure(state="disabled"))
            self.after(0, lambda: self.btn_disconnect.configure(state="normal"))
            self._log("Proxy actif!", "green")
            self._log(f"Ajoutez ce serveur dans Minecraft: 127.0.0.1:{lp}", "blue")
        except Exception as e:
            self._log(f"Erreur: {e}", "red")

    def _disconnect(self):
        self.proxy.stop()
        self._set_proxy("OFF", "#f7768e")
        self.after(0, lambda: self.btn_connect.configure(state="normal"))
        self.after(0, lambda: self.btn_disconnect.configure(state="disabled"))
        self._log("Proxy arrêté.", "yellow")

    def _rotate(self):
        was_running = self.proxy.running
        if was_running:
            self.proxy.stop()
            self._set_proxy("OFF", "#f7768e")
            self.after(0, lambda: self.btn_disconnect.configure(state="disabled"))

        threading.Thread(target=self._rotate_worker, daemon=True).start()

    def _rotate_worker(self):
        try:
            self._log("Nouvelle identité Tor...")
            self.tor.new_identity()
            ip = self.checker.get_ip()
            self._set_ip(ip)
            self._log(f"Nouvelle IP: {ip}", "green")
            self.after(0, lambda: self.btn_connect.configure(state="normal"))
            if self._last_host:
                self._log("Reconnectez-vous au serveur pour utiliser la nouvelle IP.", "blue")
        except Exception as e:
            self._log(f"Erreur rotation: {e}", "red")

    def _check_update(self):
        def _worker():
            info = self.updater.check()
            if info:
                self.after(0, lambda: self._show_update_dialog(info))
        threading.Thread(target=_worker, daemon=True).start()

    def _manual_check_update(self):
        self.after(0, lambda: self.btn_update.configure(text="...", state="disabled"))
        info = self.updater.check()
        if info:
            self.after(0, lambda: self._show_update_dialog(info))
        else:
            self.after(0, lambda: self._show_no_update())
        self.after(0, lambda: self.btn_update.configure(text="v" + VERSION, state="normal"))

    def _show_no_update(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Vérification")
        dlg.geometry("300x120")
        dlg.configure(fg_color="#161824")
        dlg.resizable(False, False)
        dlg.grab_set()
        frame = ctk.CTkFrame(dlg, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(frame, text="Vous êtes à jour !", font=("Segoe UI", 16, "bold"), text_color="#9ece6a").pack(pady=(0, 8))
        ctk.CTkLabel(frame, text=f"Version actuelle : v{VERSION}", font=("Segoe UI", 12), text_color="#9494a8").pack()
        ctk.CTkButton(frame, text="OK", fg_color="#3b3f57", hover_color="#2a2d3e", text_color="#c0caf5", corner_radius=8, height=32, width=80, command=dlg.destroy).pack(pady=(12, 0))

    def _show_update_dialog(self, info):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Mise à jour disponible")
        dlg.geometry("420x380")
        dlg.configure(fg_color="#161824")
        dlg.resizable(False, False)
        dlg.grab_set()

        try:
            dlg.update_idletasks()
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(dlg.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

        frame = ctk.CTkFrame(dlg, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(frame, text="Mise à jour disponible", font=("Segoe UI", 20, "bold"), text_color="#7aa2f7").pack(anchor="w")
        ctk.CTkLabel(frame, text=f"v{self.updater.current_version} → v{info['version']}", font=("Segoe UI", 13), text_color="#c0caf5").pack(anchor="w", pady=(4, 10))

        if info.get("notes"):
            ctk.CTkLabel(frame, text="Nouveautés :", font=("Segoe UI", 11, "bold"), text_color="#9494a8", anchor="w").pack(anchor="w", pady=(0, 4))
            notes_box = ctk.CTkTextbox(frame, font=("Consolas", 11), fg_color="#1e2030", text_color="#9494a8", corner_radius=8, height=120, border_width=1, border_color="#2a2d3e")
            notes_box.pack(fill="x", pady=(0, 12))
            notes_box.configure(state="normal")
            notes_box.insert("1.0", info["notes"])
            notes_box.configure(state="disabled")

        self._dl_progress = ctk.CTkProgressBar(frame, fg_color="#1e2030", progress_color="#7aa2f7", height=6)
        self._dl_progress.pack(fill="x", pady=(0, 4))
        self._dl_progress.set(0)

        self._dl_label = ctk.CTkLabel(frame, text="", font=("Segoe UI", 10), text_color="#9494a8")
        self._dl_label.pack(anchor="w", pady=(0, 8))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        self._btn_install = ctk.CTkButton(
            btn_frame, text="Installer et redémarrer", font=("Segoe UI", 13, "bold"),
            fg_color="#9ece6a", hover_color="#7ab854", text_color="#1a1b2e",
            corner_radius=8, height=38, state="normal",
            command=lambda: self._start_update(info["url"], dlg),
        )
        self._btn_install.pack(side="left", expand=True, fill="x", padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="Plus tard", font=("Segoe UI", 12),
            fg_color="#3b3f57", hover_color="#2a2d3e", text_color="#9494a8",
            corner_radius=8, height=38,
            command=dlg.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _start_update(self, url, dlg):
        self._btn_install.configure(state="disabled", text="Téléchargement...")
        self._dl_label.configure(text="Téléchargement en cours...")

        def on_progress(downloaded, total):
            pct = downloaded / total if total else 0
            self.after(0, lambda: self._dl_progress.set(pct))
            mb_done = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024) if total else 0
            self.after(0, lambda: self._dl_label.configure(text=f"{mb_done:.1f} Mo / {mb_total:.1f} Mo"))

        def on_done(tmp, dest):
            shutil.move(tmp, dest)
            self.after(0, lambda: self._dl_label.configure(text="Installation terminée !"))
            self.after(0, lambda: self._btn_install.configure(state="normal", text="Redémarrer"))
            self.after(0, lambda: self._btn_install.configure(command=lambda: self._restart_app()))

        def on_error(e):
            self.after(0, lambda: self._dl_label.configure(text=f"Erreur : {e}"))
            self.after(0, lambda: self._btn_install.configure(state="normal", text="Réessayer"))

        self.updater.download(url, on_progress=on_progress, on_done=on_done, on_error=on_error)

    def _restart_app(self):
        self.proxy.stop()
        self.tor.stop()
        exe = sys.executable if getattr(sys, "frozen", False) else sys.executable
        if getattr(sys, "frozen", False):
            subprocess.Popen([exe])
        else:
            subprocess.Popen([sys.executable, __file__])
        self.destroy()

    def _on_close(self):
        self.proxy.stop()
        self.tor.stop()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
