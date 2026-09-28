#==============================================================
# DroidDeck - Installation automatisee  (c) 2026 HAMADI CORP
# Usage : powershell -ExecutionPolicy Bypass -File .\install.ps1
#==============================================================
$ErrorActionPreference = "Continue"
Write-Host "== DroidDeck - Installation (HAMADI CORP) ==" -ForegroundColor Cyan

# [1/4] adb (Google platform-tools)
if (Get-Command winget -ErrorAction SilentlyContinue) {
    if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
        Write-Host "[1/4] Installation de adb (platform-tools)..."
        winget install --id Google.PlatformTools --accept-source-agreements --accept-package-agreements --silent --disable-interactivity
    } else { Write-Host "[1/4] adb deja present" -ForegroundColor Green }
} else { Write-Host "[1/4] winget absent - installer adb manuellement (voir README)" -ForegroundColor Yellow }

# [2/4] scrcpy (miroir d'ecran)
if (Get-Command winget -ErrorAction SilentlyContinue) {
    if (-not (Get-Command scrcpy -ErrorAction SilentlyContinue)) {
        Write-Host "[2/4] Installation de scrcpy..."
        winget install --id Genymobile.scrcpy --accept-source-agreements --accept-package-agreements --silent --disable-interactivity
    } else { Write-Host "[2/4] scrcpy deja present" -ForegroundColor Green }
} else { Write-Host "[2/4] winget absent - installer scrcpy manuellement" -ForegroundColor Yellow }

# [3/4] dependances Python
Write-Host "[3/4] Installation des dependances Python..."
$req = Join-Path $PSScriptRoot "..\requirements.txt"
python -m pip install -r $req

# [4/4] verification
Write-Host "[4/4] Verification..."
python -c "import customtkinter, sys; print('OK customtkinter', customtkinter.__version__)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERREUR : customtkinter absent -> pip install customtkinter" -ForegroundColor Red
} else {
    Write-Host "Installation terminee !" -ForegroundColor Green
}
Write-Host ""
Write-Host "Telephone : Parametres > A propos > Version (tap 7 fois) >" -ForegroundColor Cyan
Write-Host "Systeme > Options developpeur > Debogage USB (et Debogage sans fil)." -ForegroundColor Cyan
Write-Host "Puis double-clic sur LANCER.bat pour demarrer DroidDeck." -ForegroundColor Cyan
Read-Host "`nEntree pour fermer"
