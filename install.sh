#!/usr/bin/env bash
set -e

echo "=== Installation environnement Glitch ==="

# ------------------------------------------------------------
# Vérification OS
# ------------------------------------------------------------
if ! command -v apt >/dev/null 2>&1; then
    echo "❌ Ce script est prévu pour Debian / Ubuntu"
    exit 1
fi

# ------------------------------------------------------------
# Vérification Python
# ------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python3 non installé"
    exit 1
fi

PYVER=$(python3 - <<EOF
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
EOF
)

echo "Python détecté : $PYVER"

# ------------------------------------------------------------
# Dépendances système
# ------------------------------------------------------------
echo "📦 Installation dépendances système..."
apt update
apt install -y \
    ffmpeg \
    python3-venv \
    python3-pip \
    build-essential \
    7zip

# ------------------------------------------------------------
# Virtualenv
# ------------------------------------------------------------
if [ ! -d "mask_env" ]; then
    echo "🐍 Création du virtualenv..."
    python3 -m venv mask_env
fi

source mask_env/bin/activate

# ------------------------------------------------------------
# Pip
# ------------------------------------------------------------
echo "📦 Mise à jour pip..."
pip install --upgrade pip wheel setuptools

# ------------------------------------------------------------
# Dépendances Python
# ------------------------------------------------------------
echo "📦 Installation dépendances Python..."

pip install -r requirements.txt

# ------------------------------------------------------------
# Vérifications finales
# ------------------------------------------------------------
echo "🔍 Vérifications..."

python - <<EOF
import cv2, numpy, moviepy, tqdm
print("✔ OpenCV:", cv2.__version__)
print("✔ NumPy:", numpy.__version__)
print("✔ MoviePy:", moviepy.__version__)
print("✔ MediaPipe OK")
print("✔ tqdm OK")
EOF

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "❌ ffmpeg non disponible"
    exit 1
fi

echo "✔ ffmpeg OK"
echo
echo "✅ Installation terminée"
echo
echo "Pour utiliser :"
echo "  add video into input folder"
echo "  execute : python3 run.py"

chmod +x run.py
7z x resources/resources.7z.001 -o./resources
rm resources/resources.7z.*
#source mask_env/bin/activate
