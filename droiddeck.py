"""DroidDeck — console d'administration pour TON propre téléphone Android.

Logiciel Windows (CustomTkinter) : connexion USB/Wi-Fi, miroir scrcpy,
captures, apps, fichiers, infos système — le tout dans une seule fenêtre.
Prérequis : adb (Google.PlatformTools) + scrcpy installés via winget.
"""
from __future__ import annotations

import posixpath
import threading
import time
import webbrowser
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog

import adb
from adb import DroidError

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACCENT = "#4f8cff"
BG = "#0e1013"
PANEL = "#171a21"
CARD = "#12141a"
TEXT = "#e8eaed"
MUTED = "#8b93a1"
OK = "#34d399"
ERR = "#f87171"

NAV = [("connexion", "🔗  Connexion"), ("ecran", "🖥  Écran"),
       ("apps", "📦  Apps"), ("fichiers", "📁  Fichiers"),
       ("messages", "💬  Messages"), ("systeme", "⚙️  Système")]
TITRES = {"connexion": "Connexion", "ecran": "Écran", "apps": "Apps",
          "fichiers": "Fichiers", "messages": "Messages", "systeme": "Système"}


def card(master, title: str | None = None) -> ctk.CTkFrame:
    """Carte panellisée réutilisable ; renvoie le conteneur à remplir."""
    c = ctk.CTkFrame(master, fg_color=PANEL, corner_radius=16)
    if title:
        ctk.CTkLabel(c, text=title, font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TEXT, anchor="w").pack(fill="x", padx=20, pady=(18, 6))
    return c


def button(master, text, cmd, *, accent=False, danger=False, width=170, height=38):
    fg = ACCENT if accent else ("#3a1f24" if danger else "#232733")
    hover = "#3f7ae0" if accent else ("#4a272e" if danger else "#2c313d")
    return ctk.CTkButton(master, text=text, command=cmd, width=width, height=height,
                         corner_radius=10, fg_color=fg, hover_color=hover,
                         font=ctk.CTkFont(size=13), text_color=TEXT)


def _save_csv_path(titre: str):
    from datetime import datetime
    return filedialog.asksaveasfilename(
        defaultextension=".csv", filetypes=[("CSV", "*.csv")],
        initialfile=f"{titre}_{datetime.now():%Y%m%d_%H%M}.csv",
        title="Exporter en CSV")


def _write_csv(path, fields, rows):
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


class DroidDeck(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DroidDeck — HAMADI CORP")
        self.geometry("1100x700")
        self.minsize(940, 620)
        self.configure(fg_color=BG)

        self.serial: str | None = None
        self.rec_popen = None
        self.frames: dict[str, ctk.CTkFrame] = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()
        self.show("connexion")
        self.refresh_devices()
        self._start_auto_poll()

    # ------------------------------------------------------------- chrome
    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=230, fg_color=PANEL, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="DROIDDECK", anchor="w",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=ACCENT).pack(fill="x", padx=22, pady=(28, 0))
        ctk.CTkLabel(side, text="console android • ton appareil", anchor="w",
                     font=ctk.CTkFont(size=12),
                     text_color=MUTED).pack(fill="x", padx=22, pady=(2, 26))
        self.nav_buttons = {}
        for key_, label in NAV:
            b = ctk.CTkButton(side, text=label, anchor="w", height=42, corner_radius=10,
                              fg_color="transparent", hover_color="#232733",
                              font=ctk.CTkFont(size=14),
                              command=lambda k=key_: self.show(k))
            b.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[key_] = b
        foot = ctk.CTkFrame(side, fg_color=CARD, corner_radius=12)
        foot.pack(side="bottom", fill="x", padx=14, pady=16)
        self.dot = ctk.CTkLabel(foot, text="●  hors ligne", text_color=ERR,
                                anchor="w", font=ctk.CTkFont(size=12))
        self.dot.pack(fill="x", padx=12, pady=(10, 2))
        self.dev_label = ctk.CTkLabel(foot, text="aucun appareil", text_color=MUTED,
                                      anchor="w", font=ctk.CTkFont(size=11))
        self.dev_label.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(foot, text="© 2026 HAMADI CORP", text_color="#5a6172",
                     anchor="center", font=ctk.CTkFont(size=10)
                     ).pack(fill="x", padx=12, pady=(0, 10))

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(main, fg_color=BG, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 8))
        self.title_lbl = ctk.CTkLabel(top, text="Connexion",
                                      font=ctk.CTkFont(size=24, weight="bold"))
        self.title_lbl.pack(side="left")
        button(top, "⟳  Actualiser", self.refresh_devices, width=130).pack(side="right")
        self.body = ctk.CTkFrame(main, fg_color=BG, corner_radius=0)
        self.body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 10))
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(main, text="prêt.", anchor="w", text_color=MUTED,
                                   font=ctk.CTkFont(size=12))
        self.status.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 14))

    # ------------------------------------------------------------ actions
    def show(self, name: str):
        if name not in self.frames:
            self.frames[name] = FRAME_MAP[name](self.body, self)
        for f in self.frames.values():
            f.grid_forget()
        self.frames[name].grid(row=0, column=0, sticky="nsew")
        self.title_lbl.configure(text=TITRES.get(name, name))
        for k, b in self.nav_buttons.items():
            b.configure(fg_color="#232733" if k == name else "transparent")

    def set_status(self, text: str, color: str = MUTED):
        self.status.configure(text=text, text_color=color)

    def task(self, fn, on_ok=None, label: str = "exécution…"):
        """Exécute fn hors du fil UI, renvoie le résultat à on_ok (fil UI)."""
        self.set_status(label)

        def run():
            try:
                result = fn()
            except DroidError as e:
                self.after(0, lambda: self.set_status(f"✗ {e}", ERR))
                return
            except Exception as e:  # jamais de fenêtre qui meurt en silence
                self.after(0, lambda: self.set_status(f"✗ erreur inattendue : {e}", ERR))
                return
            if on_ok:
                self.after(0, lambda: on_ok(result))
            else:
                self.after(0, lambda: self.set_status("✓ fait", OK))
        threading.Thread(target=run, daemon=True).start()

    def require_device(self) -> str:
        if not self.serial:
            raise DroidError("aucun appareil sélectionné — onglet Connexion")
        return self.serial

    @staticmethod
    def _sig(devs):
        return tuple((d["serial"], d["state"]) for d in devs)

    def refresh_devices(self):
        def done(devs):
            self._last_sig = self._sig(devs)
            self._apply_devices(devs)
        self.task(adb.list_devices, done, label="détection des appareils…")

    def _apply_devices(self, devs):
        """Met à jour l'UI (fil principal) ; no-op si la fenêtre est fermée."""
        if not self.winfo_exists():
            return
        frame = self.frames.get("connexion")
        if frame and hasattr(frame, "update_devices"):
            frame.update_devices(devs)
        online = [d["serial"] for d in devs if d["state"] == "device"]
        if online:
            if self.serial not in online:
                self.select_device(online[0])
        elif self.serial is not None:
            self.select_device(None)

    def _start_auto_poll(self):
        """Détection permanente : tu branches le câble → le tel apparaît seul (~2 s)."""
        self._last_sig = None

        def loop():
            while True:
                time.sleep(2.0)
                try:
                    devs = adb.list_devices()
                except Exception:
                    devs = []
                if self._sig(devs) == self._last_sig:
                    continue
                self._last_sig = self._sig(devs)
                try:
                    self.after(0, lambda d=devs: self._apply_devices(d))
                except Exception:
                    return  # fenêtre fermée
        threading.Thread(target=loop, daemon=True).start()

    def select_device(self, serial: str | None):
        self.serial = serial
        if serial:
            self.dot.configure(text="●  en ligne", text_color=OK)
            self.dev_label.configure(text=serial)
            f = self.frames.get("systeme")
            if f and hasattr(f, "load"):
                f.load()
        else:
            self.dot.configure(text="●  hors ligne", text_color=ERR)
            self.dev_label.configure(text="aucun appareil")


class ConnexionFrame(ctk.CTkFrame):
    def __init__(self, master, app: "DroidDeck"):
        super().__init__(master, fg_color=BG)
        self.app = app
        self.dev_values: list[str] = []

        c1 = card(self, "Appareils détectés (USB ou Wi-Fi)")
        c1.pack(fill="x", pady=(0, 16))
        row = ctk.CTkFrame(c1, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(4, 6))
        self.dev_menu = ctk.CTkOptionMenu(row, values=["— aucun —"], width=420,
                                          command=self._pick)
        self.dev_menu.pack(side="left")
        button(row, "⟳  Rescanner", self.app.refresh_devices,
               width=130).pack(side="left", padx=10)
        ctk.CTkLabel(c1, text="branche le tel en USB avec « débogage USB » activé",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 16))

        c2 = card(self, "Connexion Wi-Fi (débogage sans fil)")
        c2.pack(fill="x", pady=(0, 16))
        row2 = ctk.CTkFrame(c2, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(4, 6))
        self.ip_entry = ctk.CTkEntry(row2, placeholder_text="192.168.1.42:5555", width=280)
        self.ip_entry.pack(side="left")
        button(row2, "Connexion", self._wifi_connect,
               accent=True, width=130).pack(side="left", padx=10)
        button(row2, "Déconnexion", self._wifi_disconnect,
               danger=True, width=130).pack(side="left")
        ctk.CTkLabel(c2, text="option : « débogage sans fil » dans Paramètres → Développeur, "
                              "l'IP s'affiche sur le tel",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 16))

        c2b = card(self, "Confort câble — accès immédiat")
        c2b.pack(fill="x", pady=(0, 16))
        row2b = ctk.CTkFrame(c2b, fg_color="transparent")
        row2b.pack(fill="x", padx=20, pady=(4, 6))
        self.stay_btn = button(row2b, "📱  Écran éveillé tant que branché : ?",
                               self._stay, width=290)
        self.stay_btn.pack(side="left")
        button(row2b, "🔓  Quitter le verrou (aucun code)", self._dismiss,
               width=250).pack(side="left", padx=10)
        ctk.CTkLabel(c2b, text="avec l'écran éveillé, branche le câble = tel prêt à être "
                               "utilisé sans se verrouiller pendant la session",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 16))

        c3 = card(self, "État de la session")
        c3.pack(fill="x")
        self.state_lbl = ctk.CTkLabel(c3, text="aucun appareil sélectionné",
                                      text_color=MUTED, anchor="w",
                                      font=ctk.CTkFont(size=13))
        self.state_lbl.pack(fill="x", padx=20, pady=(4, 16))

    def update_devices(self, devs: list[dict]):
        self.dev_values = [d["serial"] for d in devs] or []
        if devs:
            labels = [f"{d['serial']}  ({d['state']})" for d in devs]
            self.dev_menu.configure(values=labels)
            self.dev_menu.set(labels[0])
        else:
            self.dev_menu.configure(values=["— aucun —"])
            self.dev_menu.set("— aucun —")
        self._sync_state()

    def _pick(self, choice: str):
        serial = choice.split("  (")[0]
        if serial and serial != "— aucun —":
            self.app.select_device(serial)
        self._sync_state()

    def _sync_state(self):
        s = self.app.serial
        self.state_lbl.configure(
            text=f"session active : {s}" if s else "aucun appareil sélectionné",
            text_color=OK if s else MUTED)

    def _wifi_connect(self):
        addr = self.ip_entry.get()

        def ok(res):
            self.app.set_status(f"✓ {res}", OK)
            self.app.refresh_devices()
        self.app.task(lambda: adb.connect_wifi(addr), ok, label="connexion Wi-Fi…")

    def _wifi_disconnect(self):
        self.app.task(adb.disconnect_wifi, lambda r: self.app.refresh_devices(),
                      label="déconnexion…")

    def _stay(self):
        s = self.app.require_device

        def toggle():
            serial = s()
            on = adb.stay_awake_state(serial)
            adb.stay_awake(serial, not on)
            return not on

        def done(now_on):
            txt = "📱  Écran éveillé : ON" if now_on else "📱  Écran éveillé : OFF"
            self.stay_btn.configure(text=txt)
            self.app.set_status("✓ réglage enregistré", OK)
        self.app.task(toggle, done, label="réglage écran…")

    def _dismiss(self):
        s = self.app.require_device
        self.app.task(lambda: adb.dismiss_keyguard(s()),
                      lambda _: self.app.set_status(
                          "✓ fait (si aucun PIN/schema actif)", OK),
                      label="…")


class EcranFrame(ctk.CTkFrame):
    def __init__(self, master, app: "DroidDeck"):
        super().__init__(master, fg_color=BG)
        self.app = app

        c1 = card(self, "Miroir d'écran (scrcpy)")
        c1.pack(fill="x", pady=(0, 16))
        row = ctk.CTkFrame(c1, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(4, 16))
        button(row, "🖥  Ouvrir le miroir", self._mirror,
               accent=True, width=200, height=44).pack(side="left")
        ctk.CTkLabel(c1, text="contrôle complet de l'écran du tel dans une fenêtre native",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 14))

        c2 = card(self, "Captures & enregistrement")
        c2.pack(fill="x", pady=(0, 16))
        row2 = ctk.CTkFrame(c2, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(4, 6))
        button(row2, "📸  Capture", self._shot, width=150).pack(side="left", padx=(0, 8))
        self.rec_btn = button(row2, "⏺  Démarrer l'enregistrement",
                              self._rec_toggle, danger=True, width=230)
        self.rec_btn.pack(side="left", padx=(0, 8))
        button(row2, "📂  Ouvrir le dossier",
               lambda: self.app.task(self._open_dir, label="ouverture…"),
               width=170).pack(side="left")
        ctk.CTkLabel(c2, text="captures → Pictures\\DroidDeck   •   vidéos → Videos\\DroidDeck",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(6, 16))

        c3 = card(self, "Commandes rapides")
        c3.pack(fill="x")
        row3 = ctk.CTkFrame(c3, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=(4, 6))
        button(row3, "🔒  Verrouiller écran", self._lock,
               width=170).pack(side="left", padx=(0, 8))
        button(row3, "☀️  Allumer l'écran", self._wake,
               width=170).pack(side="left", padx=(0, 8))
        button(row3, "🔉  Volume −", lambda: self._vol(False),
               width=110).pack(side="left", padx=(0, 8))
        button(row3, "🔊  Volume +", lambda: self._vol(True),
               width=110).pack(side="left")
        row4 = ctk.CTkFrame(c3, fg_color="transparent")
        row4.pack(fill="x", padx=20, pady=(8, 16))
        button(row4, "↻  Redémarrer", lambda: self._reboot(""),
               width=150).pack(side="left", padx=(0, 8))
        button(row4, "↻  Recovery", lambda: self._reboot("recovery"),
               width=150).pack(side="left", padx=(0, 8))
        button(row4, "↻  Bootloader", lambda: self._reboot("bootloader"),
               width=150).pack(side="left")

    # ---------------------------------------------------------- handlers
    def _mirror(self):
        try:
            adb.launch_scrcpy(self.app.serial)
            self.app.set_status("✓ miroir scrcpy lancé", OK)
        except DroidError as e:
            self.app.set_status(f"✗ {e}", ERR)

    def _open_dir(self):
        adb.CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        import os
        os.startfile(adb.CAPTURE_DIR)

    def _shot(self):
        s = self.app.require_device
        self.app.task(lambda: adb.screenshot(s()),
                      lambda p: self.app.set_status(f"✓ capture : {p}", OK),
                      label="capture en cours…")

    def _rec_toggle(self):
        if self.app.rec_popen is None:
            s = self.app.require_device

            def start():
                self.app.rec_popen = adb.record_start(s())
            self.app.task(start, lambda _: (
                self.rec_btn.configure(text="⏹  Arrêter l'enregistrement"),
                self.app.set_status("● enregistrement en cours…", ERR)),
                label="démarrage…")
        else:
            s, p = self.app.serial, self.app.rec_popen

            def stop():
                self.app.rec_popen = None
                return adb.record_stop(s, p)
            self.app.task(stop, lambda path: (
                self.rec_btn.configure(text="⏺  Démarrer l'enregistrement"),
                self.app.set_status(f"✓ vidéo : {path}", OK)),
                label="arrêt + transfert…")

    def _lock(self):
        s = self.app.require_device
        self.app.task(lambda: adb.lock_screen(s()), label="verrouillage…")

    def _wake(self):
        s = self.app.require_device
        self.app.task(lambda: adb.wake_screen(s()), label="allumage…")

    def _vol(self, up: bool):
        s = self.app.require_device
        self.app.task(lambda: adb.volume(s(), up), label="volume…")

    def _reboot(self, mode: str):
        s = self.app.require_device
        self.app.task(lambda: adb.reboot(s(), mode),
                      lambda _: self.app.set_status(
                          f"✓ reboot {mode or 'normal'} envoyé", OK),
                      label="redémarrage…")


class AppsFrame(ctk.CTkFrame):
    def __init__(self, master, app: "DroidDeck"):
        super().__init__(master, fg_color=BG)
        self.app = app
        c1 = card(self, "Applications tierces installées")
        c1.pack(fill="both", expand=True, pady=(0, 16))
        top = ctk.CTkFrame(c1, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(4, 8))
        button(top, "⟳  Charger la liste", self._load,
               accent=True, width=170).pack(side="left")
        button(top, "📦  Installer un APK…", self._install,
               width=180).pack(side="left", padx=10)
        self.count_lbl = ctk.CTkLabel(top, text="", text_color=MUTED,
                                      font=ctk.CTkFont(size=12))
        self.count_lbl.pack(side="left", padx=10)
        self.list_frame = ctk.CTkScrollableFrame(c1, fg_color=CARD, corner_radius=12)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        ctk.CTkLabel(self.list_frame, text="« Charger la liste » pour afficher les apps",
                     text_color=MUTED).pack(pady=20)

    def _load(self):
        s = self.app.require_device
        self.app.task(lambda: adb.list_apps(s()), self._render,
                      label="lecture de l'inventaire…")

    def _render(self, pkgs: list[str]):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.count_lbl.configure(text=f"{len(pkgs)} apps")
        if not pkgs:
            ctk.CTkLabel(self.list_frame, text="aucune app tierce",
                         text_color=MUTED).pack(pady=20)
            return
        for pkg in pkgs:
            row = ctk.CTkFrame(self.list_frame, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", padx=6, pady=3)
            ctk.CTkLabel(row, text=pkg, anchor="w",
                         font=ctk.CTkFont(family="Consolas", size=12)
                         ).pack(side="left", padx=14, pady=6)
            button(row, "✖  Désinstaller", lambda p=pkg: self._remove(p),
                   danger=True, width=140, height=28).pack(side="right", padx=8, pady=4)

    def _remove(self, pkg: str):
        s = self.app.require_device

        def ok(res):
            self.app.set_status(f"✓ {pkg} : {res.strip()}", OK)
            self._load()
        self.app.task(lambda: adb.uninstall(s(), pkg), ok, label=f"suppression {pkg}…")

    def _install(self):
        s = self.app.require_device
        path = filedialog.askopenfilename(filetypes=[("APK", "*.apk")])
        if not path:
            return
        self.app.task(lambda: adb.install_apk(s(), path),
                      lambda r: self.app.set_status(f"✓ {r.strip()}", OK),
                      label="installation…")


class FichiersFrame(ctk.CTkFrame):
    def __init__(self, master, app: "DroidDeck"):
        super().__init__(master, fg_color=BG)
        self.app = app
        # ---- explorateur de fichiers
        c0 = card(self, "Explorateur de fichiers du téléphone")
        c0.pack(fill="x", pady=(0, 16))
        row0 = ctk.CTkFrame(c0, fg_color="transparent")
        row0.pack(fill="x", padx=20, pady=(4, 6))
        button(row0, "⬆  Dossier parent", self._fs_up,
               width=150).pack(side="left", padx=(0, 8))
        button(row0, "⟳  Actualiser", self._fs_refresh,
               width=130).pack(side="left", padx=(0, 8))
        self.fs_path = ctk.CTkEntry(row0, width=330, placeholder_text="/sdcard")
        self.fs_path.insert(0, "/sdcard")
        self.fs_path.pack(side="left", padx=8)
        button(row0, "📁  Aller", self._fs_refresh,
               accent=True, width=100).pack(side="left")
        self.fs_list = ctk.CTkScrollableFrame(c0, fg_color=CARD, corner_radius=12,
                                              height=340)
        self.fs_list.pack(fill="x", padx=20, pady=(6, 6))
        ctk.CTkLabel(c0, text="📁 dossier = cliquer pour naviguer   •   ⬇ fichier = "
                              "cliquer pour le récupérer sur le PC",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 14))
        self.cur_path = "/sdcard"

        c1 = card(self, "Envoyer un fichier vers le téléphone")
        c1.pack(fill="x", pady=(0, 16))
        row = ctk.CTkFrame(c1, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(4, 6))
        button(row, "⬆  Choisir un fichier…", self._push,
               accent=True, width=190).pack(side="left")
        ctk.CTkLabel(row, text="destination : /sdcard/Download/",
                     text_color=MUTED, font=ctk.CTkFont(size=12)).pack(side="left", padx=14)
        ctk.CTkLabel(c1, text="le fichier arrive dans Téléchargements du tel",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 16))

        c2 = card(self, "Récupérer un fichier depuis le téléphone")
        c2.pack(fill="x", pady=(0, 16))
        row2 = ctk.CTkFrame(c2, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(4, 6))
        self.path_entry = ctk.CTkEntry(row2, width=430,
                                       placeholder_text="/sdcard/Download/photo.jpg")
        self.path_entry.pack(side="left")
        button(row2, "⬇  Récupérer…", self._pull,
               accent=True, width=160).pack(side="left", padx=10)
        ctk.CTkLabel(c2, text="chemin absolu du fichier sur le tel",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 16))

        c3 = card(self, "Transfert en lot")
        c3.pack(fill="x")
        row3 = ctk.CTkFrame(c3, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=(4, 6))
        button(row3, "⬇  Récupérer tout Download/", self._pull_dir,
               width=240).pack(side="left")
        button(row3, "⬇  Tout récupérer (/sdcard)", self._pull_all,
               accent=True, width=220).pack(side="left", padx=10)
        ctk.CTkLabel(c3, text="copie /sdcard/Download/ entier vers un dossier local",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 16))

    def _fs_refresh(self):
        s = self.app.require_device
        path = self.fs_path.get().strip() or "/sdcard"
        self.app.task(lambda: adb.ls(s(), path),
                      lambda res: self._fs_render(path, res),
                      label=f"lecture de {path}…")

    def _fs_render(self, path, res):
        dirs, files = res
        self.cur_path = path
        self.fs_path.delete(0, "end")
        self.fs_path.insert(0, path)
        for w in self.fs_list.winfo_children():
            w.destroy()
        if not dirs and not files:
            ctk.CTkLabel(self.fs_list, text="dossier vide ou inaccessible",
                         text_color=MUTED).pack(pady=16)
            return
        for d in dirs:
            name = adb.base_name(d)
            b = ctk.CTkButton(self.fs_list, text=f"📁  {name}", anchor="w",
                              fg_color="transparent", hover_color="#232733",
                              corner_radius=8, height=30,
                              font=ctk.CTkFont(size=13),
                              command=lambda n=name: self._fs_open(n))
            b.pack(fill="x", padx=6, pady=2)
        for f in files:
            name = adb.base_name(f)
            row = ctk.CTkFrame(self.fs_list, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", padx=6, pady=2)
            ctk.CTkLabel(row, text=name, anchor="w",
                         font=ctk.CTkFont(size=13)
                         ).pack(side="left", padx=14, pady=5)
            button(row, "⬇", lambda n=name: self._fs_pull(n),
                   accent=True, width=54, height=26).pack(side="right",
                                                           padx=8, pady=4)
        self.app.set_status(
            f"✓ {len(dirs)} dossiers, {len(files)} fichiers dans {path}", OK)

    def _fs_open(self, name: str):
        self.fs_path.delete(0, "end")
        self.fs_path.insert(0, posixpath.join(self.cur_path, name))
        self._fs_refresh()

    def _fs_up(self):
        parent = posixpath.dirname(self.cur_path.rstrip("/")) or "/"
        self.fs_path.delete(0, "end")
        self.fs_path.insert(0, parent)
        self._fs_refresh()

    def _fs_pull(self, name: str):
        remote = posixpath.join(self.cur_path, name)
        dest = filedialog.asksaveasfilename(initialfile=name)
        if not dest:
            return
        s = self.app.require_device
        self.app.task(lambda: adb.pull(s(), remote, dest),
                      lambda _: self.app.set_status(f"✓ récupéré : {dest}", OK),
                      label=f"transfert de {name}…")

    def _push(self):
        s = self.app.require_device
        path = filedialog.askopenfilename()
        if not path:
            return
        self.app.task(lambda: adb.push(s(), path),
                      lambda r: self.app.set_status(f"✓ {r.splitlines()[-1]}", OK),
                      label="envoi en cours…")

    def _pull(self):
        s = self.app.require_device
        remote = self.path_entry.get().strip()
        if not remote:
            self.app.set_status("✗ entre un chemin distant", ERR)
            return
        dest = filedialog.asksaveasfilename(initialname=remote.rsplit("/", 1)[-1])
        if not dest:
            return
        self.app.task(lambda: adb.pull(s(), remote, dest),
                      lambda r: self.app.set_status(f"✓ récupéré : {dest}", OK),
                      label="récupération…")

    def _pull_dir(self):
        s = self.app.require_device
        dest = filedialog.askdirectory()
        if not dest:
            return
        self.app.task(lambda: adb.pull(s(), "/sdcard/Download", dest),
                      lambda r: self.app.set_status(f"✓ copié vers {dest}", OK),
                      label="copie du dossier…")

    def _pull_all(self):
        """Récupération complète — solution écran cassé (Android/data exclu par OS)."""
        s = self.app.require_device
        dest = filedialog.askdirectory()
        if not dest:
            return
        self.app.task(lambda: adb.pull(s(), "/sdcard", dest),
                      lambda r: self.app.set_status(
                          f"✓ tout le stockage copié vers {dest}", OK),
                      label="copie complète du stockage (peut être très long)…")


class MessagesFrame(ctk.CTkFrame):
    def __init__(self, master, app: "DroidDeck"):
        super().__init__(master, fg_color=BG)
        self.app = app
        tabs = ctk.CTkTabview(self, fg_color=PANEL, corner_radius=16)
        tabs.pack(fill="both", expand=True)
        tabs.add("Notifications")
        tabs.add("SMS")
        tabs.add("Contacts")
        tabs.add("Appels")
        tabs.add("Import Meta")
        tabs.add("Réseaux & mots de passe")
        tabs.set("Notifications")

        # ---- onglet Notifications
        t1 = tabs.tab("Notifications")
        top = ctk.CTkFrame(t1, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 6))
        button(top, "⟳  Rafraîchir", self._notif,
               accent=True, width=150).pack(side="left")
        self.auto_btn = button(top, "⏱  Auto : OFF", self._toggle_auto, width=130)
        self.auto_btn.pack(side="left", padx=8)
        self.filtre = ctk.CTkEntry(
            top, placeholder_text="filtre : messenger, instagram, x…", width=280)
        self.filtre.pack(side="left", padx=10)
        ctk.CTkLabel(top, text="aperçu des messages reçus (FB, Insta, X, WhatsApp…)",
                     text_color=MUTED, font=ctk.CTkFont(size=12)).pack(side="left")
        self.notif_list = ctk.CTkScrollableFrame(t1, fg_color=CARD, corner_radius=12)
        self.notif_list.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        ctk.CTkLabel(self.notif_list, text="« Rafraîchir » pour lire les notifications du tel",
                     text_color=MUTED).pack(pady=20)

        # ---- onglet SMS
        t2 = tabs.tab("SMS")
        top2 = ctk.CTkFrame(t2, fg_color="transparent")
        top2.pack(fill="x", padx=14, pady=(12, 6))
        button(top2, "📱  Charger les SMS", self._sms,
               accent=True, width=180).pack(side="left")
        button(top2, "⬇  Export CSV", self._export_sms,
               width=130).pack(side="left", padx=8)
        ctk.CTkLabel(top2, text="50 derniers (certains tels bloquent ce canal)",
                     text_color=MUTED, font=ctk.CTkFont(size=12)).pack(side="left", padx=10)
        self.sms_list = ctk.CTkScrollableFrame(t2, fg_color=CARD, corner_radius=12)
        self.sms_list.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        # ---- onglet Contacts
        tC = tabs.tab("Contacts")
        topC = ctk.CTkFrame(tC, fg_color="transparent")
        topC.pack(fill="x", padx=14, pady=(12, 4))
        button(topC, "⟳  Charger les contacts", self._contacts,
               accent=True, width=210).pack(side="left")
        button(topC, "⬇  Export CSV", self._export_contacts,
               width=130).pack(side="left", padx=8)
        self.c_filtre = ctk.CTkEntry(topC, placeholder_text="rechercher nom / numéro…",
                                     width=250)
        self.c_filtre.pack(side="left", padx=10)
        self.c_filtre.bind("<KeyRelease>", lambda e: self._render_contacts())
        self.acc_lbl = ctk.CTkLabel(topC, text="", text_color=MUTED,
                                    font=ctk.CTkFont(size=11))
        self.acc_lbl.pack(side="left", padx=8)
        self.c_list = ctk.CTkScrollableFrame(tC, fg_color=CARD, corner_radius=12)
        self.c_list.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        ctk.CTkLabel(self.c_list,
                     text="« Charger » → liste complète, 📞 rappelle et 💬 SMS en 1 clic",
                     text_color=MUTED).pack(pady=20)
        self._contacts_data = []

        # ---- onglet Appels
        tA = tabs.tab("Appels")
        topA = ctk.CTkFrame(tA, fg_color="transparent")
        topA.pack(fill="x", padx=14, pady=(12, 6))
        button(topA, "⟳  Journal d'appels", self._calls,
               accent=True, width=190).pack(side="left")
        button(topA, "⬇  Export CSV", self._export_calls,
               width=130).pack(side="left", padx=8)
        ctk.CTkLabel(topA, text="150 derniers : entrant / sortant / manqué",
                     text_color=MUTED, font=ctk.CTkFont(size=12)).pack(side="left", padx=10)
        self.a_list = ctk.CTkScrollableFrame(tA, fg_color=CARD, corner_radius=12)
        self.a_list.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        ctk.CTkLabel(self.a_list, text="« Charger » pour afficher l'historique des appels",
                     text_color=MUTED).pack(pady=20)

        # ---- onglet Import Meta
        tI = tabs.tab("Import Meta")
        topI = ctk.CTkFrame(tI, fg_color="transparent")
        topI.pack(fill="x", padx=14, pady=(12, 6))
        button(topI, "📥  Choisir l'export ZIP/JSON…", self._import,
               accent=True, width=240).pack(side="left")
        self.conv_menu = ctk.CTkOptionMenu(topI, values=["—"], width=320,
                                           command=self._render_conv)
        self.conv_menu.pack(side="left", padx=10)
        ctk.CTkLabel(topI, text="FB/Insta : Paramètres → Vos informations → "
                                "Télécharger → Messages (JSON)",
                     text_color=MUTED, font=ctk.CTkFont(size=11)).pack(side="left")
        self.conv_list = ctk.CTkScrollableFrame(tI, fg_color=CARD, corner_radius=12)
        self.conv_list.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        ctk.CTkLabel(self.conv_list,
                     text="importe ton export officiel pour lire TES messages ici — "
                          "aucune donnée ne passe par le tél",
                     text_color=MUTED).pack(pady=20)
        self._convs = {}
        self.auto_on = False
        self._sms_data = []
        self._calls_data = []
        self.cur_path = "/sdcard"

        # ---- onglet Réseaux & mots de passe
        t3 = tabs.tab("Réseaux & mots de passe")
        ctk.CTkLabel(t3, text="Ouvre l'app sur le tel, puis lis les DM dans le miroir (onglet Écran)",
                     text_color=MUTED, font=ctk.CTkFont(size=13),
                     anchor="w").pack(fill="x", padx=18, pady=(14, 6))
        row = ctk.CTkFrame(t3, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=4)
        for label, pkg in (("💬 Messenger", "com.facebook.orca"),
                           ("📷 Instagram", "com.instagram.android"),
                           ("𝕏 X", "com.twitter.android"),
                           ("👤 Facebook", "com.facebook.katana")):
            button(row, label, lambda p=pkg: self._open(p),
                   width=150).pack(side="left", padx=(0, 8))
        pw = ctk.CTkFrame(t3, fg_color=CARD, corner_radius=12)
        pw.pack(fill="x", padx=14, pady=(14, 12))
        ctk.CTkLabel(pw, text="🔑  Mots de passe — inaccessibles par câble (Keystore Android :\n"
                              "les clés ne sortent jamais du tél). Voies légitimes :",
                     text_color=TEXT, anchor="w", justify="left",
                     font=ctk.CTkFont(size=13)).pack(fill="x", padx=16, pady=(14, 6))
        row2 = ctk.CTkFrame(pw, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 6))
        button(row2, "🔑  Google Password Manager",
               lambda: webbrowser.open("https://passwords.google.com"),
               accent=True, width=250).pack(side="left")
        ctk.CTkLabel(pw, text="ou in-app : Profil → Paramètres → Sécurité → Mot de passe (Meta) ;\n"
                              "X → Paramètres → Confidentialité → Mots de passe (à lire via miroir)",
                     text_color=MUTED, anchor="w", justify="left",
                     font=ctk.CTkFont(size=12)).pack(fill="x", padx=16, pady=(0, 14))

    # ------------------------------------------------------------ handlers
    def _toggle_auto(self):
        """Auto-refresh des notifications toutes les 5 s (toggle)."""
        self.auto_on = not self.auto_on
        self.auto_btn.configure(
            text="⏱  Auto : ON" if self.auto_on else "⏱  Auto : OFF")
        if self.auto_on:
            self._auto_tick()

    def _auto_tick(self):
        if not (self.auto_on and self.winfo_exists()):
            return
        self._notif()
        self.after(5000, self._auto_tick)

    def _notif(self):
        s = self.app.require_device
        self.app.task(lambda: adb.notifications(s()), self._render_notifs,
                      label="lecture des notifications…")

    def _render_notifs(self, recs):
        from datetime import datetime
        f = self.notif_list
        for w in f.winfo_children():
            w.destroy()
        filtre = self.filtre.get().strip().lower()
        if filtre:
            recs = [r for r in recs
                    if filtre in (r["pkg"] + r["title"] + r["text"]).lower()]
        if not recs:
            ctk.CTkLabel(f, text="aucune notification lisible",
                         text_color=MUTED).pack(pady=16)
            return
        for r in recs:
            row = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", padx=6, pady=3)
            when = ""
            if r["when"]:
                try:
                    when = datetime.fromtimestamp(
                        int(r["when"]) / 1000).strftime("%H:%M %d/%m")
                except Exception:
                    pass
            ctk.CTkLabel(row, text=f"{r['pkg']}  •  {when}", anchor="w",
                         text_color=MUTED, font=ctk.CTkFont(size=11)
                         ).pack(fill="x", padx=12, pady=(6, 0))
            body = r["title"] + (f" — {r['text']}" if r["text"] else "")
            ctk.CTkLabel(row, text=body, anchor="w", justify="left",
                         font=ctk.CTkFont(size=13)
                         ).pack(fill="x", padx=12, pady=(0, 6))


    def _sms(self):
        s = self.app.require_device
        self.app.task(lambda: adb.sms(s()), self._render_sms,
                      label="lecture des SMS…")

    def _render_sms(self, rows):
        from datetime import datetime
        self._sms_data = rows
        f = self.sms_list
        for w in f.winfo_children():
            w.destroy()
        if not rows:
            ctk.CTkLabel(f, text="aucun SMS lu — ce canal est bloqué sur ce tél",
                         text_color=MUTED).pack(pady=16)
            return
        for r in rows:
            row = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", padx=6, pady=3)
            try:
                when = datetime.fromtimestamp(
                    r["date"] / 1000).strftime("%d/%m %H:%M")
            except Exception:
                when = ""
            ctk.CTkLabel(row, text=f"{r['address']}  •  {when}", anchor="w",
                         text_color=MUTED, font=ctk.CTkFont(size=11)
                         ).pack(fill="x", padx=12, pady=(6, 0))
            ctk.CTkLabel(row, text=r["body"], anchor="w", justify="left",
                         font=ctk.CTkFont(size=13)
                         ).pack(fill="x", padx=12, pady=(0, 6))

    def _contacts(self):
        s = self.app.require_device

        def gather():
            return adb.contacts(s()), adb.accounts(s())

        def ok(res):
            self._contacts_data, accs = res
            self.acc_lbl.configure(
                text=("comptes : " + ", ".join(accs[:5]) + ("…" if len(accs) > 5 else ""))
                if accs else "")
            self._render_contacts()
            self.app.set_status(f"✓ {len(self._contacts_data)} contacts", OK)
        self.app.task(gather, ok, label="lecture des contacts…")

    def _render_contacts(self, *_):
        f = self.c_list
        for w in f.winfo_children():
            w.destroy()
        filtre = self.c_filtre.get().strip().lower()
        rows = self._contacts_data
        if filtre:
            rows = [c for c in rows
                    if filtre in c["name"].lower() or filtre in c["number"]]
        if not rows:
            ctk.CTkLabel(f, text="aucun contact" + (" pour ce filtre" if filtre else ""),
                         text_color=MUTED).pack(pady=16)
            return
        for c in rows[:300]:
            row = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", padx=6, pady=3)
            star = "★ " if c["starred"] else ""
            ctk.CTkLabel(row, text=f"{star}{c['name']}", anchor="w",
                         font=ctk.CTkFont(size=13)
                         ).pack(side="left", padx=14, pady=6)
            ctk.CTkLabel(row, text=c["number"], anchor="w", text_color=MUTED,
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=14)
            button(row, "📞", lambda n=c["number"]: self._dial(n),
                   width=52, height=28).pack(side="right", padx=(6, 8), pady=4)
            button(row, "💬", lambda n=c["number"]: self._sms_to(n),
                   width=52, height=28).pack(side="right", padx=0, pady=4)

    def _dial(self, number: str):
        s = self.app.require_device
        self.app.task(lambda: adb.dial(s(), number),
                      lambda _: self.app.set_status(f"✓ appel de {number}", OK),
                      label="appel…")

    def _sms_to(self, number: str):
        s = self.app.require_device
        self.app.task(lambda: adb.compose_sms(s(), number),
                      lambda _: self.app.set_status(
                          f"✓ SMS à {number} — compose sur le tel (miroir)", OK),
                      label="ouverture du composeur…")

    def _calls(self):
        s = self.app.require_device

        def ok(rows):
            self._calls_data = rows
            self._render_calls(rows)
        self.app.task(lambda: adb.call_log(s()), ok, label="journal d'appels…")

    def _render_calls(self, rows):
        from datetime import datetime
        f = self.a_list
        for w in f.winfo_children():
            w.destroy()
        if not rows:
            ctk.CTkLabel(f, text="aucun appel trouvé", text_color=MUTED).pack(pady=16)
            return
        kinds = {1: ("↓ entrant", TEXT), 2: ("↑ sortant", TEXT),
                 3: ("✖ manqué", ERR), 4: ("✉ messagerie", MUTED),
                 5: ("✖ refusé", ERR), 6: ("✖ bloqué", ERR)}
        for r in rows:
            label, color = kinds.get(r["type"], ("•", MUTED))
            row = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", padx=6, pady=3)
            try:
                when = datetime.fromtimestamp(r["when"] / 1000).strftime("%d/%m %H:%M")
            except Exception:
                when = ""
            dur = ""
            if r["duration"]:
                dur = (f"{r['duration'] // 60}m{r['duration'] % 60}s"
                       if r["duration"] >= 60 else f"{r['duration']}s")
            ctk.CTkLabel(row, text=when, anchor="w", width=110, text_color=MUTED,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=(12, 8), pady=6)
            ctk.CTkLabel(row, text=label, anchor="w", width=100, text_color=color,
                         font=ctk.CTkFont(size=12)).pack(side="left", pady=6)
            ctk.CTkLabel(row, text=r["number"], anchor="w",
                         font=ctk.CTkFont(size=13)).pack(side="left", padx=8, pady=6)
            if dur:
                ctk.CTkLabel(row, text=dur, anchor="w", text_color=MUTED,
                             font=ctk.CTkFont(size=11)).pack(side="right",
                                                              padx=14, pady=6)

    def _export_contacts(self):
        if not self._contacts_data:
            self.app.set_status("✗ charge d'abord les contacts", ERR)
            return
        path = _save_csv_path("contacts")
        if not path:
            return
        rows = [dict(c, starred="oui" if c["starred"] else "non")
                for c in self._contacts_data]
        self.app.task(lambda: _write_csv(path, ["name", "number", "starred"], rows),
                      lambda p: self.app.set_status(f"✓ exporté : {p}", OK),
                      label="export CSV…")

    def _export_sms(self):
        if not self._sms_data:
            self.app.set_status("✗ charge d'abord les SMS", ERR)
            return
        path = _save_csv_path("sms")
        if not path:
            return
        from datetime import datetime
        rows = []
        for r in self._sms_data:
            try:
                iso = datetime.fromtimestamp(r["date"] / 1000).isoformat()
            except Exception:
                iso = ""
            rows.append({"expediteur": r["address"], "date": iso,
                         "message": r["body"]})
        self.app.task(lambda: _write_csv(
            path, ["expediteur", "date", "message"], rows),
            lambda p: self.app.set_status(f"✓ exporté : {p}", OK),
            label="export CSV…")

    def _export_calls(self):
        if not self._calls_data:
            self.app.set_status("✗ charge d'abord le journal", ERR)
            return
        path = _save_csv_path("appels")
        if not path:
            return
        from datetime import datetime
        kinds = {1: "entrant", 2: "sortant", 3: "manque", 4: "messagerie",
                 5: "refuse", 6: "bloque"}
        rows = []
        for r in self._calls_data:
            try:
                iso = datetime.fromtimestamp(r["when"] / 1000).isoformat()
            except Exception:
                iso = ""
            rows.append({"number": r["number"], "date": iso,
                         "type": kinds.get(r["type"], r["type"]),
                         "duree_s": r["duration"]})
        self.app.task(lambda: _write_csv(
            path, ["number", "date", "type", "duree_s"], rows),
            lambda p: self.app.set_status(f"✓ exporté : {p}", OK),
            label="export CSV…")

    def _import(self):
        path = filedialog.askopenfilename(filetypes=[
            ("Export Meta (ZIP/JSON)", "*.zip *.json"), ("Tous", "*.*")])
        if not path:
            return

        def go():
            import meta_export
            return meta_export.load(path)

        def ok(convs):
            self._convs = convs or {}
            names = sorted(self._convs, key=lambda n: -len(self._convs[n]))
            if not names:
                self.app.set_status(
                    "✗ rien trouvé — réexporte au format JSON, catégorie Messages", ERR)
                return
            self.conv_menu.configure(values=names)
            self.conv_menu.set(names[0])
            self._render_conv(names[0])
            self.app.set_status(f"✓ {len(names)} conversations importées", OK)
        self.app.task(go, ok, label="import de l'export…")

    def _render_conv(self, name):
        from datetime import datetime
        f = self.conv_list
        for w in f.winfo_children():
            w.destroy()
        for m in self._convs.get(name, []):
            row = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8)
            row.pack(fill="x", padx=6, pady=3)
            when = ""
            if m["when"]:
                try:
                    when = datetime.fromtimestamp(
                        m["when"] / 1000).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    pass
            ctk.CTkLabel(row, text=f"{m['sender']}  •  {when}", anchor="w",
                         text_color=MUTED, font=ctk.CTkFont(size=11)
                         ).pack(fill="x", padx=12, pady=(6, 0))
            ctk.CTkLabel(row, text=m["text"], anchor="w", justify="left",
                         font=ctk.CTkFont(size=13)
                         ).pack(fill="x", padx=12, pady=(0, 6))

    def _open(self, pkg: str):
        s = self.app.require_device

        def go(serial):
            adb.open_app(serial, pkg)
            return serial

        def ok(serial):
            try:
                adb.launch_scrcpy(serial)
                self.app.set_status(
                    f"✓ {pkg} ouvert sur le tel + miroir affiché ici", OK)
            except DroidError as e:
                self.app.set_status(f"✓ {pkg} ouvert (miroir : {e})", OK)
        self.app.task(lambda: go(s()), ok, label=f"ouverture {pkg}…")
class SystemeFrame(ctk.CTkFrame):
    def __init__(self, master, app: "DroidDeck"):
        super().__init__(master, fg_color=BG)
        self.app = app

        c1 = card(self, "Informations appareil")
        c1.pack(fill="x", pady=(0, 16))
        self.info = ctk.CTkLabel(c1, text="aucune donnée — sélectionne un appareil",
                                 text_color=MUTED, anchor="w", justify="left",
                                 font=ctk.CTkFont(size=13), compound="left")
        self.info.pack(fill="x", padx=20, pady=(4, 6))
        button(c1, "⟳  Actualiser les infos", self.load,
               width=190).pack(anchor="w", padx=20, pady=(4, 16))

        c2 = card(self, "Localisation")
        c2.pack(fill="x", pady=(0, 16))
        row = ctk.CTkFrame(c2, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(4, 6))
        button(row, "📍  Localiser le tel", self._locate,
               accent=True, width=180).pack(side="left")
        self.loc_lbl = ctk.CTkLabel(row, text="position inconnue", text_color=MUTED,
                                    font=ctk.CTkFont(size=13))
        self.loc_lbl.pack(side="left", padx=14)
        self._coords: tuple[float, float] | None = None
        button(row, "🗺  Ouvrir la carte", self._map,
               width=160).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(c2, text="best-effort via la dernière position connue par Android "
                              "(ouvre une app de cartes sur le tel si vide)",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 16))

        c3 = card(self, "Sécurité à distance")
        c3.pack(fill="x")
        row3 = ctk.CTkFrame(c3, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=(4, 6))
        button(row3, "🔍  Find My Device (Google)", self._fmd,
               width=230).pack(side="left")
        ctk.CTkLabel(c3, text="localiser / sonner / verrouiller / effacer via le site Google — "
                              "backup si le tel est hors portée d'adb",
                     text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="w").pack(fill="x", padx=20, pady=(0, 16))

        self._loaded = False

    def load(self):
        if not self.app.serial:
            return
        s = self.app.require_device

        def gather():
            p = adb.props(s())
            b = adb.battery(s())
            return p, b, adb.storage(s()), adb.device_ip(s())

        def done(res):
            p, b, st, ip = res
            lvl = f"{b['level']}%" if b["level"] is not None else "?"
            temp = f" • {b['temp_c']} °C" if b["temp_c"] is not None else ""
            self.info.configure(
                text=(f"{p['brand']} {p['model']}   •   Android {p['android']} (API {p['sdk']})\n"
                      f"Batterie : {lvl} ({b['status']}){temp}   •   IP Wi-Fi : {ip}\n"
                      f"Stockage /data : {st}"),
                text_color=TEXT)
            self._loaded = True
        self.app.task(gather, done, label="lecture des infos système…")

    def _locate(self):
        s = self.app.require_device

        def ok(coords):
            self._coords = coords
            self.loc_lbl.configure(text=f"{coords[0]:.5f}, {coords[1]:.5f}",
                                   text_color=OK)
            self.app.set_status("✓ position trouvée", OK)
        self.app.task(lambda: adb.location(s()), ok, label="localisation…")

    def _map(self):
        if not self._coords:
            self.app.set_status("✗ lance d'abord « Localiser le tel »", ERR)
            return
        lat, lng = self._coords
        webbrowser.open(f"https://www.google.com/maps?q={lat},{lng}")

    def _fmd(self):
        adb.open_find_my_device()
        self.app.set_status("✓ Find My Device ouvert dans le navigateur", OK)


FRAME_MAP = {
    "connexion": ConnexionFrame,
    "ecran": EcranFrame,
    "apps": AppsFrame,
    "fichiers": FichiersFrame,
    "messages": MessagesFrame,
    "systeme": SystemeFrame,
}

if __name__ == "__main__":
    app = DroidDeck()
    app.mainloop()







