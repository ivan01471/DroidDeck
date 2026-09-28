"""Parse les exports d'information Meta (Facebook / Instagram) — ZIP ou JSON.

Format officiel : Paramètres → Vos informations → Télécharger vos informations
→ catégorie Messages → format JSON. Le ZIP contient
messages/inbox/<conversation>/message_1.json
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path


def _parse_payload(data, fallback_title: str) -> dict | None:
    if not isinstance(data, dict) or "messages" not in data:
        return None
    names = [p.get("name", "?") for p in data.get("participants", [])]
    title = ", ".join(names[:6]) + ("…" if len(names) > 6 else "") if names else fallback_title
    msgs = []
    for m in data["messages"]:
        content = m.get("content")
        if content is None:
            content = f"⟨{m.get('type') or m.get('photos') or 'pièce jointe'}⟩"
        msgs.append({"sender": m.get("sender_name", "?"),
                     "when": int(m.get("timestamp_ms") or 0),
                     "text": str(content)})
    msgs.sort(key=lambda x: x["when"])
    return {"title": title, "messages": msgs}


def _folder_title(name: str) -> str:
    base = Path(name).parent.name or Path(name).stem
    base = re.sub(r"_\d{6,}$", "", base)
    return base.replace("_", " ") or "conversation"


def load(path) -> dict[str, list[dict]]:
    """→ {titre conversation: [{sender, when, text}, ...]} trié chronologiquement."""
    out: dict[str, list[dict]] = {}
    path = Path(path)
    entries = []
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if re.search(r"message.*\.json$", n, re.I):
                    try:
                        entries.append((n, json.loads(z.read(n))))
                    except Exception:
                        continue
    else:
        entries.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
    for name, data in entries:
        parsed = _parse_payload(data, _folder_title(name))
        if parsed and parsed["messages"]:
            key, i = parsed["title"], 2
            while key in out:
                key = f"{parsed['title']} ({i})"
                i += 1
            out[key] = parsed["messages"]
    return out
