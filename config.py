# -*- coding: utf-8 -*-
"""
config.py — Configuration centrale du pipeline Anonymizer
Modifier ce fichier pour changer les chemins ou parametres globaux.
"""

# ======================
# DOSSIERS PIPELINE
# ======================
INPUT_DIR   = "input"
OUTPUT_DIR  = "output"

DIRS = {
    "input":       "input",
    "output0":     "output/.output0",   # face_mask   → glitch
    "output1":     "output/.output1",   # glitch      → audio
    "output2":     "output/.output2",   # audio       → introNoutro
    "output3":     "output/.output3",   # introNoutro → backNpip
    "output4":     "output/.output4",   # backNpip    → introEndOutro
    "final":       "output",            # introEndOutro → sortie finale
    "metadata":    "output/.metadata",  # positions PIP (JSON)
}

# ======================
# RESSOURCES
# ======================
RESOURCES_DIR  = "resources"
MASK_PATH      = "resources/mask.png"
KEYPOINTS_PATH = "resources/mask_keypoints.json"
BACKGROUND     = "resources/background.mp4"
PIP_INTRO      = "resources/pipintro.mp4"
PIP_OUTRO      = "resources/pipoutro.mp4"
INTRO          = "resources/intro.mp4"
OUTRO          = "resources/outro.mp4"

# ======================
# VIDEO
# ======================
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")
MAX_WIDTH        = 1280

# ======================
# FACE MASK
# ======================
MAX_FACES      = 1
DETECT_SCALE   = 2.0
EMA_ALPHA      = 0.35   # Lissage temporel (0 = immobile, 1 = pas de lissage)
FEATHER_RADIUS = 11     # Pixels de bord mou sur le masque (0 = desactive)
MASK_SCALE     = 1.1    # Facteur d'agrandissement du masque (1.0 = original)

# ======================
# PIP EXTRACTION
# ======================
PIP_EXTRACT         = True   # Activer l'extraction PIP automatique
PIP_MAX_FACE_RATIO  = 0.10   # Si visage < 10% de la largeur du frame → c'est un PIP
PIP_PADDING         = 0.60   # Marge autour du PIP detecte (20%)

# ======================
# GLITCH / CRT
# ======================
GLITCH_INTENSITY  = 5
MAX_BAND_WIDTH    = 20
MAX_SHIFT         = 20
GREEN_NOISE_LEVEL = 30
RB_ATTENUATION    = 0.60
SCANLINE_STRENGTH = 20

# ======================
# AUDIO
# ======================
PITCH_UP       = 1.25
PITCH_DOWN     = 0.80
AUDIO_RATE     = 44100
AUDIO_CHANNELS = 2
AUDIO_BITRATE  = "192k"

# ======================
# BACKGROUND & PIP
# ======================
MARGIN    = 80
PIP_SCALE = 1.25
POP       = 0.3
FADE      = 0.3
AUDIO_FADE = 0.3
