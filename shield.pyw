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
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path


def ensure_deps():
    deps = {"requests[socks]": "requests", "stem": "stem", "PySocks": "socks"}
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

import socks
import requests
from stem import Signal
from stem.control import Controller

VERSION = "2.0"
GITHUB_REPO = "tear360/minecraft-ip-shield"
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
TOR_DATA_DIR = BASE_DIR / "tor_data"
TOR_BINARY_DIR = BASE_DIR / "tor"
SOCKS_PORT = 9250
CONTROL_PORT = 9251
CONTROL_PASS = "minecraftshield2026"
IS_WIN = sys.platform == "win32"

BG = "#1a1b2e"
BG2 = "#24283b"
BG3 = "#2f3347"
FG = "#c0caf5"
FG2 = "#a9b1d6"
ACCENT = "#7aa2f7"
GREEN = "#9ece6a"
RED = "#f7768e"
YELLOW = "#e0af68"


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
            assets = data.get("assets", [])
            exe_url = None
            for a in assets:
                if a["name"].endswith(".exe"):
                    exe_url = a["browser_download_url"]
                    break
            return {"version": tag, "url": exe_url, "notes": data.get("body", "")}
        except Exception:
            return None

    def update(self, url, callback=None):
        try:
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            exe_path = sys.executable if getattr(sys, "frozen", False) else __file__
            if exe_path.endswith(".pyw") or exe_path.endswith(".py"):
                exe_path = Path(BASE_DIR) / "MinecraftIPShield.exe"
            tmp = str(exe_path) + ".update"
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            if callback:
                callback(tmp, str(exe_path))
            return True
        except Exception:
            return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Minecraft IP Shield v{VERSION}")
        self.geometry("520x560")
        self.resizable(False, False)
        self.configure(bg=BG)

        try:
            self.update_idletasks()
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

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
        f_title = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        f_sub = tkfont.Font(family="Segoe UI", size=10)
        f_status = ("Consolas", 11)
        f_btn = ("Segoe UI", 10, "bold")
        f_entry = ("Consolas", 11)
        f_log = ("Consolas", 9)
        f_note = ("Segoe UI", 8)

        tk.Label(self, text="Minecraft IP Shield", font=f_title, bg=BG, fg=ACCENT).pack(pady=(18, 2))
        tk.Label(self, text="Prot\u00e9gez votre IP via Tor", font=f_sub, bg=BG, fg=FG2).pack(pady=(0, 12))

        tk.Frame(self, bg=BG3, height=1).pack(fill="x", padx=20, pady=2)

        sf = tk.Frame(self, bg=BG)
        sf.pack(fill="x", padx=20, pady=6)
        self.lbl_tor = tk.Label(sf, text="\u25cb Tor: ...", font=f_status, bg=BG, fg=YELLOW)
        self.lbl_tor.pack(side="left")
        self.lbl_ip = tk.Label(sf, text="IP: ...", font=f_status, bg=BG, fg=FG)
        self.lbl_ip.pack(side="right")

        self.lbl_proxy = tk.Label(self, text="\u25cb Proxy: OFF", font=f_status, bg=BG, fg=RED)
        self.lbl_proxy.pack(anchor="w", padx=20, pady=2)

        tk.Frame(self, bg=BG3, height=1).pack(fill="x", padx=20, pady=2)

        lf = tk.Frame(self, bg=BG)
        lf.pack(fill="x", padx=20, pady=8)
        tk.Label(lf, text="Serveur", font=("Segoe UI", 10), bg=BG, fg=FG2).pack(anchor="w")

        ef = tk.Frame(lf, bg=BG)
        ef.pack(fill="x", pady=(4, 0))

        self.ent_host = tk.Entry(ef, font=f_entry, bg=BG2, fg=FG,
                                 insertbackground=FG, relief="flat", bd=5)
        self.ent_host.pack(side="left", fill="x", expand=True)
        self.ent_host.insert(0, "")
        self.ent_host.configure(fg=FG2)
        self.ent_host.bind("<FocusIn>", self._on_host_focus)
        self.ent_host.bind("<FocusOut>", self._on_host_blur)
        self.ent_host.bind("<Return>", lambda e: self._connect())

        self.ent_port = tk.Entry(ef, font=f_entry, bg=BG2, fg=FG,
                                 insertbackground=FG, relief="flat", bd=5, width=6)
        self.ent_port.pack(side="left", padx=(5, 0))
        self.ent_port.insert(0, "25565")

        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", padx=20, pady=4)

        self.btn_connect = tk.Button(
            bf, text="\u25b6 Connecter", font=f_btn, bg=ACCENT, fg=BG,
            activebackground="#6a9ae8", activeforeground=BG,
            relief="flat", bd=0, padx=15, pady=8,
            command=self._connect, state="disabled",
        )
        self.btn_connect.pack(side="left", expand=True, fill="x")

        self.btn_disconnect = tk.Button(
            bf, text="\u23f9 Stop", font=f_btn, bg=RED, fg=BG,
            activebackground="#e06070", activeforeground=BG,
            relief="flat", bd=0, padx=15, pady=8,
            command=self._disconnect, state="disabled",
        )
        self.btn_disconnect.pack(side="left", expand=True, fill="x", padx=(5, 0))

        self.btn_rotate = tk.Button(
            self, text="\U0001f504 Changer d'IP", font=f_btn, bg=YELLOW, fg=BG,
            activebackground="#d0a050", activeforeground=BG,
            relief="flat", bd=0, padx=15, pady=8,
            command=self._rotate, state="disabled",
        )
        self.btn_rotate.pack(fill="x", padx=20, pady=10)

        tk.Label(self, text="D\u00e9connectez-vous du serveur avant de changer d'IP",
                 font=f_note, bg=BG, fg=FG2).pack()

        tk.Frame(self, bg=BG3, height=1).pack(fill="x", padx=20, pady=6)

        lf2 = tk.Frame(self, bg=BG)
        lf2.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.log_text = tk.Text(lf2, font=f_log, bg=BG2, fg=FG2,
                                relief="flat", bd=5, state="disabled", wrap="word")
        sb = tk.Scrollbar(lf2, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_text.tag_configure("green", foreground=GREEN)
        self.log_text.tag_configure("red", foreground=RED)
        self.log_text.tag_configure("yellow", foreground=YELLOW)
        self.log_text.tag_configure("blue", foreground=ACCENT)

    def _on_host_focus(self, e):
        if self.ent_host.get() == "" or self.ent_host.cget("fg") == FG2:
            self.ent_host.delete(0, "end")
            self.ent_host.configure(fg=FG)

    def _on_host_blur(self, e):
        if not self.ent_host.get().strip():
            self.ent_host.configure(fg=FG2)

    def _log(self, msg, color=None):
        def _do():
            self.log_text.config(state="normal")
            if color:
                self.log_text.insert("end", f"  {msg}\n", color)
            else:
                self.log_text.insert("end", f"  {msg}\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(0, _do)

    def _set_tor(self, text, color):
        self.after(0, lambda: self.lbl_tor.config(text=text, fg=color))

    def _set_proxy(self, text, color):
        self.after(0, lambda: self.lbl_proxy.config(text=text, fg=color))

    def _set_ip(self, text):
        self.after(0, lambda: self.lbl_ip.config(text=text))

    def _start_tor(self):
        self._set_tor("\u25cb Tor: D\u00e9marrage...", YELLOW)
        threading.Thread(target=self._tor_worker, daemon=True).start()

    def _tor_worker(self):
        try:
            if not self.tor.tor_path:
                self._set_tor("\u25cb Tor: Non trouv\u00e9", RED)
                self._log("Tor non trouv\u00e9! Installez Tor Browser.", "red")
                return
            self._log("D\u00e9marrage de Tor...")
            self.tor.start()
            self._set_tor("\u25cf Tor: ON", GREEN)
            self.after(0, lambda: self.btn_connect.config(state="normal"))
            self.after(0, lambda: self.btn_rotate.config(state="normal"))
            self._log("Tor actif!", "green")
            ip = self.checker.get_ip()
            self._set_ip(f"IP: {ip}")
        except Exception as e:
            self._set_tor("\u25cb Tor: Erreur", RED)
            self._log(f"Erreur Tor: {e}", "red")

    def _connect(self):
        host = self.ent_host.get().strip()
        if not host or self.ent_host.cget("fg") == FG2:
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
            self._log(f"Connexion \u00e0 {host}:{port} via Tor...")
            lp = self.proxy.start(host, port)
            self._set_proxy(f"\u25cf Proxy: ON  \u2192  127.0.0.1:{lp}", GREEN)
            self.after(0, lambda: self.btn_connect.config(state="disabled"))
            self.after(0, lambda: self.btn_disconnect.config(state="normal"))
            self._log(f"Proxy actif!", "green")
            self._log(f"Ajoutez ce serveur dans Minecraft: 127.0.0.1:{lp}", "blue")
        except Exception as e:
            self._log(f"Erreur: {e}", "red")

    def _disconnect(self):
        self.proxy.stop()
        self._set_proxy("\u25cb Proxy: OFF", RED)
        self.after(0, lambda: self.btn_connect.config(state="normal"))
        self.after(0, lambda: self.btn_disconnect.config(state="disabled"))
        self._log("Proxy arr\u00eat\u00e9.", "yellow")

    def _rotate(self):
        was_running = self.proxy.running
        if was_running:
            self.proxy.stop()
            self._set_proxy("\u25cb Proxy: OFF", RED)
            self.after(0, lambda: self.btn_disconnect.config(state="disabled"))

        threading.Thread(target=self._rotate_worker, daemon=True).start()

    def _rotate_worker(self):
        try:
            self._log("Nouvelle identit\u00e9 Tor...")
            self.tor.new_identity()
            ip = self.checker.get_ip()
            self._set_ip(f"IP: {ip}")
            self._log(f"Nouvelle IP: {ip}", "green")
            self.after(0, lambda: self.btn_connect.config(state="normal"))
            if self._last_host:
                self._log("Reconnectez-vous au serveur pour utiliser la nouvelle IP.", "blue")
        except Exception as e:
            self._log(f"Erreur rotation: {e}", "red")

    def _check_update(self):
        def _worker():
            info = self.updater.check()
            if info and info["version"] != self.updater.current_version:
                self._log(f"Nouvelle version disponible: v{info['version']}", "blue")
                if info.get("url"):
                    self._log("T\u00e9l\u00e9chargement de la mise \u00e0 jour...")
                    def _on_done(tmp, dest):
                        import shutil
                        shutil.move(tmp, dest)
                        self._log("Mise \u00e0 jour install\u00e9e ! Red\u00e9marrez l'application.", "green")
                    self.updater.update(info["url"], callback=_on_done)
        threading.Thread(target=_worker, daemon=True).start()

    def _on_close(self):
        self.proxy.stop()
        self.tor.stop()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
