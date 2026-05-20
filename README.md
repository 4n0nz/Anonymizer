```
  ╔═╗ ╔╗╔ ╔═╗ ╔╗╔ ╦ ╦ ╔╦╗ ╦ ══╗ ╔══ ╔═╗
  ╠═╣ ║║║ ║ ║ ║║║ ╚╦╝ ║║║ ║  ╱  ╠═  ╠╦╝
  ╩ ╩ ╝╚╝ ╚═╝ ╝╚╝  ╩  ╩ ╩ ╩ ╚══ ╚══ ╩╚═
       Anonymous Video Pipeline
```

---

## What it does

Anonymizer is a complete anonymization toolkit with **3 working modes** + extra tools :

### Mode 1 — Edit Video With PIP
6-step pipeline that masks the speaker's face, extracts a small picture-in-picture of the person, then composes everything on a custom background :

| Phase | Script | Description |
|-------|--------|-------------|
| 1 | `face_mask.py` | Detects face via MediaPipe, overlays a custom PNG mask, extracts PIP + computes safe zone |
| 2 | `glitch.py` | Applies VHS / CRT glitch effect on the PIP |
| 3 | `audio.py` | Encrypts the voice (pitch shift up + down + mix) |
| 4 | `introNoutro.py` | Adds pipintro / pipoutro transitions |
| 5 | `backNpip.py` | Composes background + screen + PIP overlay (uses safe zone for 100% coverage) |
| 6 | `introEndOutro.py` | Adds final intro and outro sequences |

### Mode 2 — Edit Video With No PIP
Same pipeline but no PIP extraction. The mask is applied directly on the source video, and the **glitch effect is selective** : only applied to frames where the mask is actually present. Useful when the person is fullscreen.

### Mode 3 — Start Virtual Streaming Cam
Real-time webcam masking via `mask-live/live.py` :
- MediaPipe face tracking with EMA smoothing
- Outputs to **OBS Virtual Camera** (selectable in Zoom, Teams, TikTok web, Discord, etc.)
- Falls back to looped `pipintro.mp4` when the face tracking is lost (anti-leak protection)

### Mode 4 — Swapface *(placeholder)*
Reserved slot for future integration with DeepFaceLive / Roop / InsightFace.

### Extra tool — `Downloader.py`
Downloads videos from **OpenClassrooms** (with login) or **YouTube** (videos / playlists / channels) directly into `input/`. Auto-renames files (max 4 words, no special characters).

---

## Requirements

- **Python 3.8+**
- **ffmpeg** (in PATH)
- **7-Zip** (for resource extraction, Windows only)
- **OBS Studio** (optional — only needed for Mode 3 to provide the Virtual Camera driver)
- **Voicemod** (optional — for live voice anonymization in Mode 3)

---

## Installation

### Linux / WSL
```bash
chmod +x install.sh
./install.sh
```

### macOS
```bash
chmod +x install_osx.sh
./install_osx.sh
```

### Windows
```
Double-click Win\install.bat
```

The installer creates a `mask_env/` virtualenv, installs all Python deps from `requirements.txt`, auto-downloads the MediaPipe FaceLandmarker model (~1.2 MB), and extracts the resource archives (`resources.7z.*`) which are **kept after extraction** so you can re-install without re-downloading.

### Reset (clean working data, keep code)

Use this when you want to start fresh : clears `input/`, `output/`, `logs/`, removes the virtualenv, and wipes extracted resources (but **keeps** the `.7z*` archives).

```bash
# Linux / macOS / WSL
chmod +x reset.sh
./reset.sh

# Windows
Double-click Win\reset.bat
```

After a reset, just run `install.sh` / `Win\install.bat` again to restore the virtualenv + re-extract resources from the kept `.7z*` archives.

### Uninstall (wipe everything)

Removes the virtualenv **and** every file/folder inside `Anonymizer/` (source code, resources, configs, logs, the script itself...). Only the empty `Anonymizer/` directory remains.

```bash
# Linux / macOS / WSL
chmod +x uninstall.sh
./uninstall.sh

# Windows
Double-click Win\uninstall.bat
```

Both scripts ask for an explicit `YES` confirmation before destroying anything.

| Action | `reset` | `uninstall` |
|--------|---------|-------------|
| Source code (.py) | ✅ Kept | ❌ Deleted |
| `resources/*` (extracted) | ❌ Wiped | ❌ Deleted |
| `resources/resources.7z.*` (archives) | ✅ **Kept** | ❌ Deleted |
| `config.py`, credentials | ✅ Kept | ❌ Deleted |
| `input/`, `output/`, `logs/` | ❌ Wiped | ❌ Deleted |
| `mask_env/` (virtualenv) | ❌ Removed | ❌ Removed |
| The `Anonymizer/` folder itself | ✅ Kept | ✅ Kept (empty) |

---

## Usage

### Pipeline (Modes 1 & 2)

1. Add source videos into `input/` (or use `Downloader.py` — see below)
2. Launch the menu :
   ```bash
   # Linux / macOS / WSL
   python3 run.py

   # Windows
   Double-click Win\run.bat
   ```
3. Pick **1** (with PIP) or **2** (no PIP)
4. Tweak parameters in the linear questionnaire (or just press Enter to keep defaults)
5. Retrieve `output/output.mp4`

### Live virtual cam (Mode 3)

1. Launch `python3 run.py` and pick **3**
2. The `live.py` window opens, OBS Virtual Camera becomes active
3. In your streaming app (Zoom / TikTok web / Discord / OBS / browser) :
   - **Camera** → select **OBS Virtual Camera**
   - **Microphone** → select your Voicemod virtual mic (if using one)
4. Press `Échap` in the live window to stop

### Download videos

```bash
# YouTube — single video, playlist or channel
python3 Downloader.py https://www.youtube.com/watch?v=...
python3 Downloader.py https://www.youtube.com/playlist?list=...
python3 Downloader.py https://www.youtube.com/@channel

# OpenClassrooms — full course
python3 Downloader.py https://openclassrooms.com/fr/courses/1234567

# Quality / output options
python3 Downloader.py <url> --quality 720
python3 Downloader.py <url> -o my_videos
```

For OpenClassrooms, copy `ocr_credentials.example.py` to `ocr_credentials.py` and add your login. This file is gitignored.

---

## Configuration

All settings are centralized in **`config.py`** — no need to touch the individual scripts.

```python
# ── PRE-PROCESSING ──
PREPROCESS_MAX_WIDTH = 1920   # Auto-downscale source videos > this width
                              # (1920 = 1080p max, 1280 = 720p max, 0 = disabled)

# ── FACE DETECTION ──
MAX_WIDTH      = 960          # Frame width used for MediaPipe detection
DETECT_SCALE   = 1.0          # Upscale before detection (1.0 = none, faster)
EMA_ALPHA      = 0.35         # Temporal smoothing of landmarks (0–1)
FEATHER_RADIUS = 6            # Mask edge softness (px)
MASK_SCALE     = 1.1          # Scale factor of the mask around the face

# ── PIP EXTRACTION ──
PIP_EXTRACT        = True     # Extract a small PIP from the masked video
PIP_MAX_FACE_RATIO = 0.10     # If face < 10% of frame width → it's a PIP
PIP_PADDING        = 0.60     # Crop margin around the face
PIP_ZOOM_FACTOR    = 0.9      # Final PIP size multiplier (1.0 = exact safe zone)

# ── GLITCH / CRT ──
GLITCH_INTENSITY  = 5
GREEN_NOISE_LEVEL = 30
RB_ATTENUATION    = 0.60      # Strength of the green tint (lower = greener)
SCANLINE_STRENGTH = 20

# ── VOICE ──
PITCH_UP   = 1.25             # Pitch up factor (mixed with pitch-down)
PITCH_DOWN = 0.80

# ── COMPOSITION ──
SCREEN_RATIO       = 0.854    # Screen width / background width
PIP_DISPLAY_RATIO  = 0.416    # Fallback PIP width when no safe zone available
SCREEN_DELAY       = 3.0      # Seconds trimmed from screen start (offset vs PIP)
```

The interactive questionnaire in `run.py` lets you change the most useful values per run without editing the file.

---

## Project structure

```
Anonymizer/
├── input/                       # Drop your source videos here (or auto-filled by Downloader.py)
├── output/                      # Final anonymized videos
│   ├── .output0/                # face_mask  → glitch
│   ├── .output1/                # glitch     → audio
│   ├── .output2/                # audio      → introNoutro
│   ├── .output3/                # introNoutro → backNpip
│   ├── .output4/                # backNpip   → introEndOutro
│   └── .metadata/               # PIP positions + safe zones (JSON per video)
├── logs/                        # One log file per run (timestamped)
├── resources/                   # Mask PNG, background, intro/outro videos
│   ├── mask.png
│   ├── mask_keypoints.json      # Auto-generated on first run
│   ├── face_landmarker.task     # MediaPipe Tasks model (auto-downloaded)
│   ├── background.mp4
│   ├── intro.mp4 / outro.mp4
│   └── pipintro.mp4 / pipoutro.mp4
│
├── run.py                       # 4-option main menu launcher
├── config.py                    # ← Central config — edit this file only
├── Downloader.py                # OpenClassrooms + YouTube downloader → input/
│
│ ── PIPELINE STEPS (Pipeline/) ──
├── Pipeline/
│   ├── face_mask.py             # 1. Face masking + PIP extraction + safe zone calc
│   ├── glitch.py                # 2. VHS / CRT glitch (selective in no-PIP mode)
│   ├── audio.py                 # 3. Voice encryption (pitch up/down + mix)
│   ├── introNoutro.py           # 4. Transitions (pipintro/pipoutro on PIP & screen)
│   ├── backNpip.py              # 5. Composition: background + screen + PIP overlay
│   ├── introEndOutro.py         # 6. Final intro & outro added
│   ├── test_vcam.py             # Diagnostic: test pyvirtualcam → OBS pipeline
│   └── ocr_credentials.example.py   # Template (copy to ocr_credentials.py, gitignored)
│
│ ── LIVE MODE ──
├── mask-live/
│   └── live.py                  # Real-time webcam masking → OBS Virtual Camera
│
├── requirements.txt             # Python deps (incl. pyvirtualcam, mediapipe-tasks)
│
│ ── INSTALL / RESET / UNINSTALL ──
├── install.sh                   # Linux installer
├── install_osx.sh               # macOS installer
├── reset.sh                     # Wipes input/output/logs/mask_env/resources (keeps .7z)
├── uninstall.sh                 # Wipes EVERYTHING inside the folder
└── Win/
    ├── install.bat              # Windows installer (auto-downloads MediaPipe model)
    ├── run.bat                  # Windows pipeline launcher
    ├── reset.bat                # Same as reset.sh
    └── uninstall.bat            # Same as uninstall.sh
```

### Main menu (run.py)

```
WHAT YOU WANNA DO ?
  1. Edit Video With Pip          → Full pipeline (PIP overlay on background)
  2. Edit Video With No Pip       → Full pipeline, no PIP extraction
                                    (glitch only on frames where mask is present)
  3. Start Virtual Streaming Cam  → Live webcam masking → OBS Virtual Camera
  4. Swapface                     → Placeholder (DeepFaceLive / Roop integration)
```

---

## How "Safe Zone" works

For Mode 1 (with PIP), `face_mask.py` doesn't just track one position — it accumulates **every detected face bounding box** across the whole video, then computes a single rectangle that covers all of them, plus margin for shoulders / hair.

This guarantees that in `backNpip.py`, the PIP overlay **always covers 100% of the speaker**, even if they move around. The result is saved into `output/.metadata/<video>_pip.json` :

```json
{
  "x":  320, "y":  180, "w":  640, "h":  360,   // PIP crop (centered on face)
  "face_x":  480, "face_y":  240, "face_w": 200, "face_h": 240,  // Face bbox
  "safe_x":  280, "safe_y":  150, "safe_w":  720, "safe_h":  405 // Safe zone (16:9)
}
```

The PIP is anchored at `(x, y)` and sized to `safe_w × PIP_ZOOM_FACTOR` (16:9 enforced).

---

## Recent additions

| Feature | File | Description |
|---------|------|-------------|
| **Safe Zone algorithm** | `face_mask.py` | Tracks all face positions to compute a "safe zone" that always covers the speaker |
| **Selective glitch** | `glitch.py` | In no-PIP mode, glitch is applied only to frames containing the mask flag |
| **Auto-preprocess** | `run.py` | Source videos > `PREPROCESS_MAX_WIDTH` auto-downscaled with `.orig` backup |
| **Keep awake** | `run.py` | Prevents Windows/macOS/Linux from sleeping during pipeline |
| **YouTube support** | `Downloader.py` | Single video / playlist / channel — saves to `input/` directly |
| **Auto-rename** | `Downloader.py` | Filenames simplified: max 4 words, no special characters |
| **Live mask** | `mask-live/live.py` | Real-time webcam masking with EMA smoothing + pipintro fallback |
| **Configurable PIP zoom** | `config.py` | `PIP_ZOOM_FACTOR` controls final PIP size around safe zone |
| **MediaPipe Tasks API** | `face_mask.py`, `live.py` | Migrated from removed `mp.solutions.face_mesh` |
| **UTF-8 on Windows** | All scripts | Auto-reconfigures stdout/stderr to UTF-8 (no more cp1252 errors) |
| **Reset script** | `reset.sh`, `Win\reset.bat` | Clears working data + virtualenv, **keeps `.7z*` archives** for fast re-install |
| **Uninstall script** | `uninstall.sh`, `Win\uninstall.bat` | Wipes everything in the folder (with `YES` confirmation) |
| **Persistent archives** | `install.sh/.bat` | `.7z*` archives kept after extraction → re-install without re-downloading |

---

## Streaming setup (Mode 3)

For full anonymization (face + voice) in TikTok / Zoom / Discord / OBS :

```
┌──────────────┐                      ┌────────────────────┐
│ Webcam       │ ──► live.py ──────►  │ OBS Virtual Camera │ ──┐
└──────────────┘                      └────────────────────┘   │
                                                               ├─► TikTok / Zoom / OBS
┌──────────────┐                      ┌────────────────────┐   │   (selectable in app)
│ Microphone   │ ──► Voicemod ─────►  │ Voicemod Virtual   │ ──┘
└──────────────┘                      │ Microphone         │
                                      └────────────────────┘
```

In your app, just select **OBS Virtual Camera** for video and **Voicemod Virtual Microphone** for audio. Configure once, never touch again.

> 💡 In Voicemod's Voice Lab you can recreate the same audio effect as `audio.py` (pitch up/down + mix) for a consistent voice signature between recorded videos and live streams.

---

## Troubleshooting

**"AttributeError: module 'mediapipe' has no attribute 'solutions'"**
MediaPipe ≥ 0.10.x removed the legacy API. The scripts auto-fall back to the Tasks API. If it still fails, the model `resources/face_landmarker.task` will be auto-downloaded on first run.

**"OBS Virtual Camera shows static in browser"**
Make sure (a) `live.py` is running before opening the consumer app, (b) OBS Studio's own Virtual Camera button is **not** active in parallel, (c) only one app at a time can write to OBS Virtual Camera.

**Pipeline is very slow on a 1080p+ source**
Set `PREPROCESS_MAX_WIDTH = 1280` in `config.py` to auto-downscale to 720p. Or check that `DETECT_SCALE = 1.0` (not 2.0) and `MAX_WIDTH = 960` (not 1280).

**Surface Pro / Qualcomm webcam not detected by `live.py`**
Try `WEBCAM_INDEX = 1` (front camera) instead of `0` (rear) in `mask-live/live.py`. The default backend (Media Foundation) is more reliable than DirectShow on these devices.

---

## License & credits

Personal anonymization toolkit. Uses :
- [MediaPipe](https://google.github.io/mediapipe/) (Apache 2.0) — face detection
- [OpenCV](https://opencv.org/) (Apache 2.0) — video I/O & filters
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense) — downloads
- [pyvirtualcam](https://github.com/letmaik/pyvirtualcam) (GPL-2) — OBS Virtual Camera bridge
- [FFmpeg](https://ffmpeg.org/) (LGPL/GPL) — audio/video processing
