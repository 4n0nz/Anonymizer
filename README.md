```
  ╔═╗ ╔╗╔ ╔═╗ ╔╗╔ ╦ ╦ ╔╦╗ ╦ ══╗ ╔══ ╔═╗
  ╠═╣ ║║║ ║ ║ ║║║ ╚╦╝ ║║║ ║  ╱  ╠═  ╠╦╝
  ╩ ╩ ╝╚╝ ╚═╝ ╝╚╝  ╩  ╩ ╩ ╩ ╚══ ╚══ ╩╚═
       Anonymous Video Pipeline
```

---

## What it does

Anonymizer is a 6-step automated pipeline that processes videos to protect the identity of the person on screen:

| Phase | Script | Description |
|-------|--------|-------------|
| 1 | `face_mask.py` | Detects face via MediaPipe and overlays a custom PNG mask |
| 2 | `glitch.py` | Applies glitch / CRT visual effect |
| 3 | `audio.py` | Encrypts / distorts the voice |
| 4 | `introNoutro.py` | Adds transitions between clips |
| 5 | `backNpip.py` | Replaces background and adds PIP overlay |
| 6 | `introEndOutro.py` | Adds intro and outro sequences |

---

## Requirements

- Python 3.8+
- ffmpeg (in PATH)
- 7-Zip (for resource extraction)

---

## Installation

### Linux / WSL
```bash
chmod +x install.sh
./install.sh
```

### Windows
```
Double-click Win\install.bat
```

---

## Usage

1. Add your videos into the `input/` folder (`.mp4`, `.mov`, `.avi`, `.mkv`)
2. Run the pipeline:

```bash
# Linux / WSL
python3 run.py

# Windows
Double-click Win\run.bat
```

3. Retrieve your anonymized videos from the `output/` folder

---

## Configuration

All settings are centralized in a single file : **`config.py`**

> No need to touch the individual scripts. Every path, parameter and tuning value lives here.

```python
# Folder routing between pipeline steps
DIRS = {
    "input":   "input",
    "output0": "output/.output0",  # face_mask  → glitch
    "output1": "output/.output1",  # glitch     → audio
    ...
}

# Resources
MASK_PATH  = "resources/mask.png"
BACKGROUND = "resources/background.mp4"
INTRO      = "resources/intro.mp4"
...

# Face detection
MAX_WIDTH    = 1280
DETECT_SCALE = 2.0   # upscale factor before MediaPipe detection

# Glitch / CRT effect
RB_ATTENUATION    = 0.60   # green tint intensity
GLITCH_INTENSITY  = 5      # number of glitch bands per frame
SCANLINE_STRENGTH = 20     # CRT scanline darkness

# Voice encryption
PITCH_UP   = 1.25
PITCH_DOWN = 0.80

# Background & PIP
PIP_SCALE = 0.7    # presenter window size (ratio)
MARGIN    = 80     # pixels from edge
```

---

## Project structure

```
Anonymizer/
├── input/               # Drop your source videos here
├── output/              # Final anonymized videos
├── logs/                # One log file per run (timestamped)
├── resources/           # Mask PNG, background, intro/outro videos
├── config.py            # ← Central config — edit this file only
├── face_mask.py         # Step 1 — Face masking
├── glitch.py            # Step 2 — Glitch / CRT effect
├── audio.py             # Step 3 — Voice encryption
├── introNoutro.py       # Step 4 — Transitions
├── backNpip.py          # Step 5 — Background & PIP
├── introEndOutro.py     # Step 6 — Intro & Outro
├── run.py               # Cross-platform pipeline runner
├── install.sh           # Linux installer
├── requirements.txt     # Python dependencies
└── Win/                 # Windows versions
    ├── install.bat
    ├── run.bat
    └── *.py
```
