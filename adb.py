"""DroidDeck — backend adb/scrcpy (aucune dépendance externe hors adb+scrcpy)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import webbrowser
from datetime import datetime
from pathlib import Path

HOME = Path.home()
CAPTURE_DIR = HOME / "Pictures" / "DroidDeck"
RECORD_DIR = HOME / "Videos" / "DroidDeck"
_REMOTE_REC = "/sdcard/droiddeck_rec.mp4"


class DroidError(Exception):
    """Erreur destinée à être affichée telle quelle dans l'interface."""


def _resolve(tool: str, candidates: list[str]) -> str:
    found = shutil.which(tool)
    if found:
        return found
    import glob
    for c in candidates:
        if "*" in c:
            for hit in sorted(glob.glob(c), reverse=True):
                if os.path.isfile(hit):
                    return hit
        elif c and os.path.isfile(c):
            return c
    hint = {"adb": "winget install Google.PlatformTools",
            "scrcpy": "winget install Genymobile.scrcpy"}[tool]
    raise DroidError(f"{tool} introuvable — installe-le avec : {hint}")


def adb_exe() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    return _resolve("adb", [
        os.path.join(local, "Microsoft", "WinGet", "Links", "adb.exe"),
        os.path.join(local, "Microsoft", "WinGet", "Packages",
                     "Google.PlatformTools_*", "platform-tools", "adb.exe"),
        os.path.join(local, "Android", "Sdk", "platform-tools", "adb.exe"),
        r"C:\Program Files\platform-tools\adb.exe",
        r"C:\platform-tools\adb.exe",
    ])


def scrcpy_exe() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    return _resolve("scrcpy", [
        os.path.join(local, "Microsoft", "WinGet", "Links", "scrcpy.exe"),
        os.path.join(local, "Microsoft", "WinGet", "Packages",
                     "Genymobile.scrcpy_*", "scrcpy-win*", "scrcpy.exe"),
        r"C:\Program Files\scrcpy\scrcpy.exe",
        r"C:\scrcpy\scrcpy.exe",
    ])


def _run(cmd: list[str], timeout: int = 20, binary: bool = False):
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    except FileNotFoundError:
        raise DroidError(f"exécutable introuvable : {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise DroidError(f"commande expirée ({timeout}s) : {' '.join(cmd[:3])} …")
    if binary:
        if proc.returncode != 0:
            raise DroidError(proc.stderr.decode("utf-8", "replace").strip() or "échec (binaire)")
        return proc.stdout
    out = (proc.stdout or b"").decode("utf-8", "replace")
    err = (proc.stderr or b"").decode("utf-8", "replace")
    if proc.returncode != 0 or out.lstrip().startswith("error:") or "failed to" in out.lower():
        raise DroidError((err or out).strip() or f"code {proc.returncode}")
    return out.strip()


def adb(args: list[str], serial: str | None = None, timeout: int = 20, binary: bool = False):
    cmd = [adb_exe()]
    if serial:
        cmd += ["-s", serial]
    return _run(cmd + args, timeout=timeout, binary=binary)


def shell(command: str, serial: str | None = None, timeout: int = 20) -> str:
    return adb(["shell", command], serial=serial, timeout=timeout)


# ------------------------------------------------------------- appareils
def list_devices() -> list[dict]:
    out = adb(["devices", "-l"])
    devs = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devs.append({"serial": parts[0], "state": parts[1]})
    return devs


def connect_wifi(address: str) -> str:
    address = address.strip()
    if not address:
        raise DroidError("entre une adresse IP (ex : 192.168.1.42:5555)")
    if ":" not in address:
        address += ":5555"
    return adb(["connect", address])


def disconnect_wifi() -> str:
    return adb(["disconnect"])


def launch_scrcpy(serial: str | None) -> None:
    subprocess.Popen(
        [scrcpy_exe(), "--window-title", "DroidDeck — miroir"]
        + (["-s", serial] if serial else []),
        creationflags=subprocess.CREATE_NO_WINDOW)


def props(serial):
    return {
        "model": shell("getprop ro.product.model", serial),
        "brand": shell("getprop ro.product.brand", serial),
        "android": shell("getprop ro.build.version.release", serial),
        "sdk": shell("getprop ro.build.version.sdk", serial),
    }


def battery(serial) -> dict:
    out = shell("dumpsys battery", serial)
    lvl = re.search(r"level:\s*(\d+)", out)
    tmp = re.search(r"temperature:\s*(\d+)", out)
    sta = re.search(r"status:\s*(\d+)", out)
    st_map = {1: "inconnu", 2: "en charge", 3: "en décharge",
              4: "ne se charge pas", 5: "plein"}
    return {
        "level": int(lvl.group(1)) if lvl else None,
        "temp_c": round(int(tmp.group(1)) / 10, 1) if tmp else None,
        "status": st_map.get(int(sta.group(1)), "?") if sta else "?",
    }


def storage(serial) -> str:
    out = shell("df /data", serial)
    for line in out.splitlines()[1:]:
        f = line.split()
        if len(f) >= 6 and f[-1].startswith("/"):

            def go(s):
                return (s.upper().replace("K", " Ko").replace("M", " Mo")
                        .replace("G", " Go"))
            return f"{go(f[2])} utilisés / {go(f[1])} ({go(f[4])} libres)"
    return "—"


def device_ip(serial) -> str:
    out = shell("ip addr show wlan0 2>/dev/null || true", serial)
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else "—"


def screenshot(serial) -> Path:
    data = adb(["exec-out", "screencap", "-p"], serial=serial, timeout=30, binary=True)
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_DIR / f"capture_{datetime.now():%Y%m%d_%H%M%S}.png"
    path.write_bytes(data)
    return path


def record_start(serial):
    p = subprocess.Popen(
        [adb_exe(), "-s", serial, "shell", "screenrecord", _REMOTE_REC],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(1.0)
    if p.poll() is not None:
        raise DroidError("screenrecord refusé par l'appareil")
    return p


def record_stop(serial, popen) -> Path:
    try:
        shell("pkill -INT screenrecord || killall -INT screenrecord",
              serial, timeout=10)
    except DroidError:
        pass
    try:
        popen.wait(timeout=10)
    except Exception:
        popen.kill()
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    local = RECORD_DIR / f"video_{datetime.now():%Y%m%d_%H%M%S}.mp4"
    adb(["pull", _REMOTE_REC, str(local)], serial=serial, timeout=180)
    adb(["shell", "rm", "-f", _REMOTE_REC], serial=serial, timeout=10)
    return local


# ----------------------------------------------------------- commandes UI
def key(serial, keycode: int):
    shell(f"input keyevent {keycode}", serial, timeout=10)


def screen_on(serial) -> bool:
    out = shell("dumpsys power 2>/dev/null | grep -E 'mWakefulness=|"
                "mHoldingDisplay' | head -3", serial, timeout=10)
    return "Awake" in out or "=true" in out


def lock_screen(serial):
    """Éteint l'écran (verrouillage si schéma/PIN défini sur le tel)."""
    if screen_on(serial):
        key(serial, 26)


def wake_screen(serial):
    if not screen_on(serial):
        key(serial, 26)


def volume(serial, up: bool):
    key(serial, 24 if up else 25)


def reboot(serial, mode: str = ""):
    shell(f"reboot {mode}".strip(), serial, timeout=10)


def list_apps(serial, include_system: bool = False) -> list[str]:
    flag = "" if include_system else " -3"
    out = shell(f"pm list packages{flag}", serial, timeout=30)
    return sorted(line.split(":", 1)[1] for line in out.splitlines()
                  if line.startswith("package:"))


def uninstall(serial, pkg: str) -> str:
    return adb(["uninstall", pkg], serial=serial, timeout=90)


def install_apk(serial, path) -> str:
    return adb(["install", "-r", str(path)], serial=serial, timeout=240)


def push(serial, local, remote: str = "/sdcard/Download/") -> str:
    return adb(["push", str(local), remote], serial=serial, timeout=180)


def pull(serial, remote: str, local) -> str:
    return adb(["pull", remote, str(local)], serial=serial, timeout=300)


def location(serial) -> tuple[float, float]:
    """Best-effort : dumpsys location (dernière position connue par le système)."""
    out = shell("dumpsys location", serial, timeout=15)
    m = re.search(r"(?:lat/lng[:\s]+|ocation[^\n]*?)(-?\d{1,3}\.\d{3,})[,\s]+"
                  r"(-?\d{1,3}\.\d{3,})", out)
    if not m:
        m = re.search(r"(-?\d{1,3}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})", out)
    if not m:
        raise DroidError("position introuvable — ouvre une app de cartes sur le "
                         "tel (GPS actif) puis réessaie")
    return float(m.group(1)), float(m.group(2))


def open_find_my_device():
    webbrowser.open("https://www.google.com/android/find")


# ----------------------------------------------------- messages / notifications
def open_app(serial, pkg: str):
    shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", serial, timeout=15)


def notifications(serial, limit: int = 40) -> list[dict]:
    """Aperçu des notifications récentes (title/text des apps), via dumpsys."""
    try:
        out = shell("dumpsys notification --noredact 2>/dev/null "
                    "|| dumpsys notification", serial, timeout=25)
    except DroidError:
        out = shell("dumpsys notification", serial, timeout=25)
    recs, cur = [], None
    for line in out.splitlines():
        s = line.strip()
        m = re.search(r"\bpkg=([\w.]+\.[\w.]+)", s)
        if m:
            if cur:
                recs.append(cur)
            cur = {"pkg": m.group(1), "title": "", "text": "", "when": ""}
        elif cur is not None:
            if s.startswith("android.title="):
                cur["title"] = s.split("=", 1)[1].strip()
            elif s.startswith("android.text=") and not cur["text"]:
                cur["text"] = s.split("=", 1)[1].strip()
            elif s.startswith("tickerText=") and not cur["text"]:
                cur["text"] = s.split("=", 1)[1].strip()
            elif "created=" in s or "posttime=" in s or "when=" in s:
                m2 = re.search(r"(\d{13})", s)
                if m2:
                    cur["when"] = m2.group(1)
    if cur:
        recs.append(cur)
    recs = [r for r in recs if r["title"] or r["text"]]
    wrap = re.compile(r"^(?:String|SpannableString|java\.lang\.String)\s*\((.*)\)\s*$",
                      re.S)
    for r in recs:
        for k in ("title", "text"):
            if r[k] == "null":
                r[k] = ""
            m = wrap.match(r[k])
            if m:
                r[k] = m.group(1)
        r["title"] = r["title"].replace("\n", " ")[:80]
        r["text"] = r["text"].replace("\n", " ")[:120]
    recs.sort(key=lambda r: r["when"], reverse=True)
    return recs[:limit]


def sms(serial, limit: int = 50) -> list[dict]:
    """SMS via le content provider (fonctionne sans root sur la plupart des tels)."""
    out = shell("content query --uri content://sms", serial, timeout=25)
    rows = [r for r in _rows(out) if "body" in r]
    rows.sort(key=lambda r: int(r.get("date") or 0), reverse=True)
    return [{"address": r.get("address", "?"), "body": r.get("body", ""),
             "date": int(r.get("date") or 0)} for r in rows[:limit]]


# --------------------------------------------------- confort câble / verrou
def stay_awake(serial, enable: bool):
    """1=AC, 2=USB, 4=Wi-Fi → 7 = écran toujours éveillé pendant la charge."""
    shell(f"settings put global stay_on_while_plugged_in {7 if enable else 0}",
          serial, timeout=10)


def stay_awake_state(serial) -> bool:
    out = shell("settings get global stay_on_while_plugged_in", serial, timeout=10)
    return out.strip() not in ("0", "null", "")


def dismiss_keyguard(serial):
    """Quitte l'écran de verrouillage SANS code (fonctionne si aucun PIN/schema)."""
    shell("wm dismiss-keyguard", serial, timeout=10)


# ------------------------------------------- contacts / appels / comptes
def _rows(text: str) -> list[dict]:
    """Parse le format 'Row: N k=v, k=v, …' de `content query`."""
    rows = []
    for line in text.splitlines():
        if "Row:" not in line or "=" not in line:
            continue
        chunks = re.split(r",\s*([A-Za-z_][\w]*)=", line.split("Row:", 1)[1])
        d = {}
        if "=" in chunks[0]:
            k, v = chunks[0].split("=", 1)
            k = k.strip()
            if " " in k:          # « 0 date » → « date » (numéro de Row en tête)
                k = k.split()[-1]
            d[k] = v.strip()
        for i in range(1, len(chunks) - 1, 2):
            d[chunks[i]] = chunks[i + 1].strip()
        rows.append(d)
    return rows


def contacts(serial, limit: int = 600) -> list[dict]:
    out = shell("content query --uri content://com.android.contacts/data/phones",
                serial, timeout=30)
    res = []
    for r in _rows(out):
        name = r.get("display_name") or r.get("display_name_alt") or "?"
        num = r.get("data1") or r.get("number") or ""
        if num:
            res.append({"name": name, "number": num.strip(),
                        "starred": r.get("starred", "0") == "1"})
    res.sort(key=lambda c: c["name"].lower())
    return res[:limit]


def call_log(serial, limit: int = 150) -> list[dict]:
    out = shell("content query --uri content://call_log/calls", serial, timeout=30)
    res = []
    for r in _rows(out):
        try:
            when = int(r.get("date") or 0)
        except ValueError:
            when = 0
        try:
            dur = int(r.get("duration") or 0)
        except ValueError:
            dur = 0
        try:
            kind = int(r.get("type") or 0)
        except ValueError:
            kind = 0
        res.append({"number": r.get("number") or r.get("formatted_number") or "?",
                    "when": when, "duration": dur, "type": kind})
    res.sort(key=lambda c: c["when"], reverse=True)
    return res[:limit]


def accounts(serial) -> list[str]:
    """Comptes du tél (emails notamment) via dumpsys account."""
    out = shell("dumpsys account", serial, timeout=20)
    seen, res = set(), []
    for name in re.findall(r"name=([^,}]+), type=", out):
        name = name.strip()
        if name and name not in seen:
            seen.add(name)
            res.append(name)
    return res


def dial(serial, number: str):
    num = re.sub(r"[^\d+*#]", "", number)
    if not num:
        raise DroidError("numéro invalide")
    shell(f"am start -a android.intent.action.CALL -d tel:{num}",
          serial, timeout=15)


def compose_sms(serial, number: str):
    num = re.sub(r"[^\d+*#]", "", number)
    if not num:
        raise DroidError("numéro invalide")
    shell(f"am start -a android.intent.action.SENDTO -d smsto:{num}",
          serial, timeout=15)


def ls(serial, path: str) -> tuple[list[str], list[str]]:
    """Liste un dossier → (répertoires, fichiers) en chemins absolus."""
    q = path.replace('"', '\\"')
    dirs = shell(f'find "{q}" -maxdepth 1 -mindepth 1 -type d 2>/dev/null',
                 serial, timeout=25)
    files = shell(f'find "{q}" -maxdepth 1 -mindepth 1 -type f 2>/dev/null',
                  serial, timeout=40)
    d = sorted(x.strip() for x in dirs.splitlines() if x.strip())
    f = sorted(x.strip() for x in files.splitlines() if x.strip())
    return d, f


def base_name(p: str) -> str:
    return p.rstrip("/").rsplit("/", 1)[-1] or "/"

