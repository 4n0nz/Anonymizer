#!/usr/bin/env bash
# reset.sh — Vide input/, output/, logs/ et supprime le virtualenv
# Compatible Linux / macOS / WSL

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==============================================="
echo "  Anonymizer Reset"
echo "==============================================="
echo
echo "  Dossier ciblé : $DIR"
echo
echo "  Sera vidé / supprimé :"
echo "    - input/      (vidéos source)"
echo "    - output/     (vidéos finales + intermédiaires + metadata)"
echo "    - logs/       (logs des runs)"
echo "    - mask_env/   (virtualenv Python complet)"
echo "    - resources/  (fichiers extraits — les archives .7z* sont gardées)"
echo
echo "  Le code source et la config sont CONSERVÉS."
echo
read -p "  Tape 'YES' pour confirmer : " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    echo
    echo "  Annulé. Aucun fichier supprimé."
    exit 0
fi

echo

# Vide le contenu d'un dossier (le garde lui-même)
clear_dir() {
    local target="$1"
    if [ -d "$target" ]; then
        echo "[*] Vidage de $target/"
        find "$target" -mindepth 1 -delete 2>/dev/null || true
    else
        echo "[-] $target/ inexistant, ignoré"
    fi
}

clear_dir "$DIR/input"
clear_dir "$DIR/output"
clear_dir "$DIR/logs"

# Vide resources/ EXCEPT les archives .7z*
if [ -d "$DIR/resources" ]; then
    echo "[*] Vidage de resources/ (sauf les archives .7z*)"
    find "$DIR/resources" -mindepth 1 \
        ! -name 'resources.7z.*' \
        -delete 2>/dev/null || true
fi

if [ -d "$DIR/mask_env" ]; then
    echo "[*] Suppression du virtualenv mask_env/"
    rm -rf "$DIR/mask_env"
fi

echo
echo "[OK] Reset terminé."
echo "     Pour réinstaller le virtualenv : ./install.sh"
