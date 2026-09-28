# DroidDeck — Installation complète

**© 2026 HAMADI CORP** · Licence MIT · Logiciel Windows pour **ton propre** téléphone Android.

---

## 1. Prérequis

- Windows 10/11
- Python 3.10+ ([python.org](https://www.python.org/downloads/) — cocher *Add to PATH*)
- Un câble USB (Wi-Fi possible, voir §6)
- **Ton téléphone** : Paramètres → À propos du téléphone → tap **7 fois** sur
  « Numéro de build » → Paramètres → Système → **Options développeur** →
  **Débogage USB** (et « Débogage sans fil » si Android 11+, voir §6)

## 2. Installation automatique (recommandée)

```powershell
# PowerShell dans ce dossier INSTALL\
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Le script installe : **adb** (winget), **scrcpy** (winget), les dépendances
Python (`requirements.txt`), puis vérifie l'installation.

## 3. Installation manuelle

```powershell
winget install Google.PlatformTools   # adb
winget install Genymobile.scrcpy      # miroir d'écran
pip install -r requirements.txt
```

## 4. Premier lancement

- **Double-clic sur `INSTALL\LANCER.bat`**, ou :
```powershell
python droiddeck.py
```

## 5. Connexion du téléphone

1. Branche le câble USB → sur le tel : mode **« Transfert de fichiers »**
2. Sur l'écran du tel : pop-up **« Autoriser le débogage USB ? »** → **Autoriser**
   (+ cocher *toujours autoriser*)
3. DroidDeck détecte l'appareil **seul** en ~2 s (détection permanente, jamais
   de bouton « Actualiser » obligatoire)
4. Onglet **Connexion** → bouton **📱 Écran éveillé tant que branché : ON**
   → le tel ne se verrouille plus pendant les sessions

> Plusieurs téléphones ? Le menu déroulant de l'onglet Connexion liste tous les
> appareils connectés — sélectionne celui que tu veux piloter.

## 6. Sans câble — Wi-Fi (débogage sans fil) + Tailscale

1. Tel : Paramètres → Développeur → **Débogage sans fil** → **Activer** (Android 11+)
2. Dans le panneau « Pairage » : **Pair appareil avec code** (IP:port + code)
3. DroidDeck : onglet Connexion → entrer `IP:port`… (pairage adb `adb pair`)
   puis connexion — **ou** simplement utiliser le câble
4. **Accès depuis l'extérieur** : installe [Tailscale](https://tailscale.com)
   sur le PC **et** le tel (même compte) → les deux se voient comme sur le même
   réseau → débogage sans fil fonctionne de partout, chiffré, sans ouvrir de port

## 7. Dépannage

| Symptôme | Solution |
|---|---|
| `offline` dans la barre d'état | regarder l'écran du tel → accepter la pop-up RSA ; sinon révoquer les autorisations (Dev options) et rebrancher |
| État vide alors que le câble est branché | changer de câble (certains sont charge-only) ; mode « Transfert de fichiers » |
| 3× « realme Phone » en erreur dans Windows | driver MTP manquant — cosmétique, n'empêche pas DroidDeck (adb fonctionne) ; installer le driver constructeur si besoin le transfert Windows |
| `adb introuvable` | relancer `install.ps1` ou ouvrir un **nouveau** terminal (PATH mis à jour) |
| Écran cassé | déjà couvert : débogage activé AVANT + autorisation PC = tout passe par le câble (fichiers + miroir + souris sur le PC) |

## 8. Ce que DroidDeck ne fait PAS (volontairement)

- rien n'est installé sur le téléphone (tout passe par adb, réversible)
- pas de furtivité, pas de capture covite, pas de collecte d'identifiants
- pas d'accès aux bases d'apps privées (nécessite le root)
- usage réservé à **tes propres appareils**, avec ton consentement

---
**DroidDeck — © 2026 HAMADI CORP** · Licence MIT · [github (voir §9 du README racine)]
