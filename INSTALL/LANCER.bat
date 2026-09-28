@echo off
chcp 65001 >nul
title DroidDeck - HAMADI CORP
cd /d "%~dp0.."
echo ============================================
echo    DroidDeck - (c) 2026 HAMADI CORP
echo ============================================
python droiddeck.py
if errorlevel 1 (
    echo.
    echo [ERREUR] Demarrage impossible.
    echo  - Python absent ? installer python.org (cocher Add to PATH)
    echo  - Dependances ? lancer INSTALL\install.ps1
    echo.
    pause
)
