# DroidDeck

> **Console d'administration Android pour tes propres appareils** — une seule
> fenêtre Windows, thème sombre, zéro installation sur le téléphone.

**© 2026 HAMADI CORP** · Licence MIT · Python + CustomTkinter + adb + scrcpy

---

## Fonctionnalités

| Onglet | Ce qu'il fait |
|---|---|
| 🔗 **Connexion** | détection **automatique** (branche = connecté en ~2 s), USB + Wi-Fi, multi-appareils, écran éveillé branché, quitter le verrou |
| 🖥 **Écran** | miroir **scrcpy** (contrôle total), capture, enregistrement vidéo, verrouillage, volume, reboot (normal/recovery/bootloader) |
| 📦 **Apps** | liste des apps tierces, désinstallation, installation d'APK |
| 📁 **Fichiers** | **explorateur** (navigation + téléchargement au clic), envoi/réception, copie de `Download/` ou de tout `/sdcard` |
| 💬 **Messages** | notifications en direct (+ **auto-refresh 5 s**), SMS, **contacts** ( rappel 📞 / SMS 💬 ), **journal d'appels**, **import des exports Meta** (FB/Insta), comptes/emails |
| ⚙️ **Système** | modèle/Android/batterie/stockage/IP, **localisation** + carte, Find My Device |

**Exports CSV** : contacts, SMS, journal d'appels — en un clic.

## Installation rapide

```powershell
powershell -ExecutionPolicy Bypass -File INSTALL\install.ps1
```

Puis double-clic sur **`INSTALL\LANCER.bat`**. Guide complet :
[`INSTALL/README.md`](INSTALL/README.md).

## Préparer le téléphone (une fois)

1. Paramètres → À propos du téléphone → tap **7 fois** sur le n° de build
2. Paramètres → Système → Options développeur → **Débogage USB**
3. Brancher → accepter la pop-up RSA sur l'écran du tel

## Tests

```powershell
python test_ui.py
```
Smoke test : compilation des modules, instanciation des 6 onglets, API backend
(35 fonctions), parser d'export Meta, résolution adb/scrcpy.

## Architecture

```
droiddeck/
├── droiddeck.py      # interface graphique (CustomTkinter)
├── adb.py            # backend adb/scrcpy (toutes les commandes)
├── meta_export.py    # parseur des exports Facebook/Instagram (ZIP/JSON)
├── test_ui.py        # smoke test
├── requirements.txt
├── INSTALL/
│   ├── README.md     # guide d'installation complet
│   ├── install.ps1   # installation automatisée
│   └── LANCER.bat    # lancement en double-clic
├── LICENSE           # MIT — © HAMADI CORP
└── README.md
```

## Limites (volontaires et techniques)

- **Aucune donnée ne quitte le PC** : tout passe par le câble/adb local, zéro serveur
- Rien n'est installé sur le téléphone — réversible, visible, sans service caché
- Pas d'accès aux bases d'apps privées (root requis — jamais proposé)
- **Hors périmètre, définitivement** : furtivité, capture covite, collecte
  d'identifiants — ces capacités définissent un malware, pas un outil d'admin
- Localisation best-effort (`dumpsys location`) ; backup d'urgence : Find My Device

## Licence

MIT — voir [`LICENSE`](LICENSE). © 2026 **HAMADI CORP**.

*Utiliser DroidDeck uniquement sur des appareils dont tu es propriétaire, avec ton plein consentement.*
