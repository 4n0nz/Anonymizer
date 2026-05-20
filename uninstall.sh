#!/usr/bin/env bash
# uninstall.sh — Vide complètement le dossier Anonymizer
# Compatible Linux / macOS / WSL

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==============================================="
echo "  Anonymizer Uninstaller"
echo "==============================================="
echo
echo "  Ce script va EFFACER TOUT LE CONTENU de :"
echo "    $DIR"
echo
echo "  Sera supprimé :"
echo "    - mask_env/                 (virtualenv Python)"
echo "    - input/, output/, logs/    (toutes les vidéos)"
echo "    - resources/                (masque, backgrounds, modèles)"
echo "    - Tous les fichiers source (.py, .md, .txt, etc.)"
echo "    - .git/                     (historique Git si présent)"
echo "    - Ce script lui-même"
echo
echo "  Le dossier '$(basename "$DIR")' lui-même sera conservé (vide)."
echo
read -p "  Tape 'YES' (en majuscules) pour confirmer : " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    echo
    echo "  Annulé. Aucun fichier supprimé."
    exit 0
fi

echo
echo "[*] Suppression du virtualenv Python..."
[ -d "$DIR/mask_env" ] && rm -rf "$DIR/mask_env"

echo "[*] Suppression de tous les fichiers et sous-dossiers..."
# -mindepth 1 = inclut tout sauf le dossier racine
# -delete = suppression effective
find "$DIR" -mindepth 1 -delete 2>/dev/null || true

echo
echo "[OK] Désinstallation terminée."
echo "     Le dossier est maintenant vide :"
echo "     $DIR"
