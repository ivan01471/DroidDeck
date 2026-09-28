"""Smoke test DroidDeck : compile, instancie chaque onglet, ferme sans erreur."""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import py_compile
for f in ("adb.py", "droiddeck.py"):
    py_compile.compile(str(HERE / f), doraise=True)
    print(f"[ok] compilation {f}")

import droiddeck

app = droiddeck.DroidDeck()
app.update_idletasks()
app.update()

for key in droiddeck.FRAME_MAP:
    app.show(key)
    app.update_idletasks()
    app.update()
    print(f"[ok] onglet {key}")

# vérifie que les sous-modules adb expose bien tout ce que l'UI appelle
import adb
for fn in ("list_devices", "connect_wifi", "disconnect_wifi", "launch_scrcpy",
           "screenshot", "record_start", "record_stop", "lock_screen",
           "wake_screen", "volume", "reboot", "list_apps", "uninstall",
           "install_apk", "push", "pull", "location", "open_find_my_device",
           "props", "battery", "storage", "device_ip",
           "notifications", "sms", "open_app",
           "stay_awake", "stay_awake_state", "dismiss_keyguard",
           "contacts", "call_log", "accounts", "dial", "compose_sms",
           "ls", "base_name"):
    assert callable(getattr(adb, fn)), f"manquant : {fn}"
print("[ok] API backend complète")

# parser export Meta (fixture synthétique)
import json as _json
import tempfile
import meta_export
_sample = {"participants": [{"name": "Moi"}, {"name": "Ami"}],
           "messages": [{"sender_name": "Ami", "timestamp_ms": 1700000000000,
                         "content": "salut !"},
                        {"sender_name": "Moi", "timestamp_ms": 1699999990000,
                         "content": "yo"}]}
_p = Path(tempfile.gettempdir()) / "dd_export_test.json"
_p.write_text(_json.dumps(_sample), encoding="utf-8")
_convs = meta_export.load(_p)
assert _convs, "aucune conversation parsée"
assert "Moi, Ami" in _convs, list(_convs)
assert _convs["Moi, Ami"][0]["sender"] == "Moi", "tri chronologique cassé"
_p.unlink()
print("[ok] parser export Meta")

# binaires requis
try:
    print("[ok] adb ->", adb.adb_exe())
except adb.DroidError as e:
    print("[!!] ", e)
try:
    print("[ok] scrcpy ->", adb.scrcpy_exe())
except adb.DroidError as e:
    print("[!!] ", e)

app.destroy()
print("SMOKE TEST OK")
