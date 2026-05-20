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
Real-time webcam masking via `mask-live/live.py`. Full details in the [Live mode](#live-mode-architecture) section below.

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
   *(or double-click `mask-live\run.bat` on Windows)*
2. The `live.py` window opens — resize it freely
3. In your streaming app (Zoom / TikTok web / Discord / OBS) :
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

All pipeline settings are centralized in **`config.py`** — no need to touch the individual scripts.

```python
# ── PRE-PROCESSING ──
PREPROCESS_MAX_WIDTH = 1920   # Auto-downscale source videos > this width

# ── FACE DETECTION ──
MAX_WIDTH      = 960          # Frame width used for MediaPipe detection
DETECT_SCALE   = 1.0          # Upscale before detection (1.0 = none, faster)
EMA_ALPHA      = 0.35         # Temporal smoothing of landmarks (0–1)
FEATHER_RADIUS = 6            # Mask edge softness (px)
MASK_SCALE     = 1.1          # Scale factor of the mask around the face

# ── PIP EXTRACTION ──
PIP_EXTRACT        = True
PIP_MAX_FACE_RATIO = 0.10
PIP_PADDING        = 0.60
PIP_ZOOM_FACTOR    = 0.9

# ── GLITCH / CRT ──
GLITCH_INTENSITY  = 5
GREEN_NOISE_LEVEL = 30
RB_ATTENUATION    = 0.60
SCANLINE_STRENGTH = 20

# ── VOICE ──
PITCH_UP   = 1.25
PITCH_DOWN = 0.80

# ── COMPOSITION ──
SCREEN_RATIO       = 0.854
PIP_DISPLAY_RATIO  = 0.416
SCREEN_DELAY       = 3.0
```

Live mode has its own constants at the top of `mask-live/live.py` — see the [Live mode config](#live-mode-config) section.

---

## Live mode architecture

`mask-live/live.py` runs a **3-thread pipeline** to minimize end-to-end latency while keeping the display loop fast :

```
┌─────────────────────────────────────────────────────────────────┐
│  Thread 1 — Capture                                             │
│  cap.read() in a tight loop → always overwrites _cap_frame      │
│  Eliminates OpenCV's 4-frame buffer lag (~130 ms by default)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ latest BGR frame
┌──────────────────────────▼──────────────────────────────────────┐
│  Thread 2 — ML Worker                                           │
│  • MediaPipe FaceLandmarker  (Tasks API, VIDEO mode) ~10–15 ms  │
│  • selfie_segmenter_landscape.tflite at ½ resolution  ~40 ms   │
│    runs every _SEG_EVERY frames (default: 2)                    │
│  Publishes: landmarks + segmentation mask + result_id           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ landmarks, mask, result_id
┌──────────────────────────▼──────────────────────────────────────┐
│  Thread 3 — Main (display)                                      │
│  • Reads latest frame from _cap_frame (no blocking)             │
│  • Reads ML results (non-blocking)                              │
│  • Velocity-based landmark prediction (+1 frame ahead)          │
│  • apply_mask() — affine warp of PNG mask onto face             │
│  • _composite_fast() — luma-blend background at ½ res           │
│  • cv2.imshow() + optional pyvirtualcam push                    │
└─────────────────────────────────────────────────────────────────┘
```

**Typical latency budget (1280×720, Qualcomm Snapdragon X) :**

| Step | Time |
|------|------|
| Webcam capture (thread 1) | ~33 ms / frame |
| Face landmarks (thread 2) | ~12 ms |
| Segmentation at 640×360 (thread 2) | ~40 ms |
| apply_mask + composite (thread 3) | ~15 ms |
| **End-to-end display lag** | **~35–50 ms** |

---

## Live mode — background compositing

The matrix `background.mp4` is composited under the person using a **luma-based transparency** :

- **Black pixels** (luma = 0) → 100% real room visible through
- **Bright green pixels** (luma = 1) → matrix fully opaque
- **In between** → natural gradient

This creates the effect of the real room being visible in filigree behind the matrix rain, without altering the brightness of any non-black pixels.

```
result = person × seg_mask + (matrix × luma + room × (1−luma)) × (1−seg_mask)
```

The compositing is done at **half resolution** (640×360) then upscaled — 4× fewer float32 operations — while the person layer stays at full resolution (1280×720) via `cv2.blendLinear`.

Background playback uses a **debt accumulator** to stay locked to wall-clock time regardless of the main loop speed :

```python
_bg_state["debt"] += elapsed / _bg_interval
frames_to_advance  = int(_bg_state["debt"])
_bg_state["debt"] -= frames_to_advance   # keep fractional remainder
```

This avoids the classic "floor division drift" where a 30 fps loop never advances a 29.97 fps video.

---

## Live mode config

Edit these constants at the top of `mask-live/live.py` :

```python
WEBCAM_INDEX   = 1      # 0 = rear cam, 1 = front cam (Surface Pro / Qualcomm)
WIDTH          = 1280   # Requested capture resolution
HEIGHT         = 720
FPS            = 30

EMA_ALPHA      = 0.7    # Landmark smoothing (0 = frozen, 1 = raw/jittery)
FEATHER_RADIUS = 8      # Mask edge softness in pixels
MASK_SCALE     = 1.1    # Scale of the PNG mask around the face
NO_FACE_GRACE  = 1      # Worker-result frames before switching to pipintro

BG_OPACITY     = 0.85   # Matrix transparency (0.0 = room only, 1.0 = matrix only)
BG_BRIGHTNESS  = 1.0    # Matrix brightness (0.5 = dark, 1.0 = original, 1.5 = bright)
```

---

## Live mode — security model

The raw webcam feed is **never sent to the output** :

1. As long as face tracking is active → anonymized composite is displayed
2. On tracking loss → `last_safe_frame` (last anonymized frame) is frozen on screen for `NO_FACE_GRACE` worker-result frames
3. After grace period → `pipintro.mp4` loops until the face is re-detected
4. On face return → switches back to anonymized feed within one worker cycle (~37 ms)

The `no_face` counter only increments/resets when the ML worker delivers a **new result** (`result_id` changes). This prevents the fast display loop (~100 fps) from racing ahead of the worker and getting stuck in pipintro.

---

## Live mode — mask edge quality

The segmentation mask goes through a 4-step refinement pipeline at ½ resolution :

1. **Guided filter** (radius 6, eps 1e-4) — edge-aware smoothing guided by the grayscale frame → mask edges follow real contours instead of blurring across them
2. **Sigmoid** (scale 12, center 0.5) — sharpens the soft probability map into a clean alpha channel
3. **Morphological close** (5×5 ellipse) — fills small holes in the person silhouette
4. **Gaussian blur** (3×3) — final light smoothing to remove pixel-level jaggies after upscale

---

## Live mode — velocity prediction

The ML worker runs on a separate thread and delivers landmarks with ~1 frame of latency. To compensate, `apply_mask` tracks the **velocity** of the landmark positions between consecutive worker results and extrapolates the mask position one frame ahead :

```python
velocity = raw_pts - prev_raw                         # delta between last two worker results
velocity = 0.4 * velocity + 0.6 * smoothed_velocity  # EMA-smoothed to avoid overshooting
raw_pts  = raw_pts + velocity                         # predict 1 frame ahead
```

The result is a mask that follows the face in real time even during fast movement, with no visible lag.

---

## Project structure

```
Anonymizer/
├── input/                       # Drop your source videos here
├── output/                      # Final anonymized videos
│   ├── .output0/ … .output4/    # Intermediate pipeline stages
│   └── .metadata/               # PIP positions + safe zones (JSON)
├── logs/                        # One log file per run (timestamped)
├── resources/                   # Mask PNG, models, background, intro/outro videos
│   ├── mask.png
│   ├── mask_keypoints.json      # Auto-generated on first calibration
│   ├── face_landmarker.task     # MediaPipe FaceLandmarker (auto-downloaded)
│   ├── selfie_segmenter_landscape.tflite  # Person segmentation (auto-downloaded)
│   ├── background.mp4           # Matrix rain background for live mode
│   ├── intro.mp4 / outro.mp4
│   └── pipintro.mp4 / pipoutro.mp4
│
├── run.py                       # 4-option main menu launcher
├── config.py                    # ← Central config for pipeline modes
├── Downloader.py                # OpenClassrooms + YouTube downloader
│
├── Pipeline/
│   ├── face_mask.py             # 1. Face masking + PIP + safe zone
│   ├── glitch.py                # 2. VHS / CRT glitch
│   ├── audio.py                 # 3. Voice encryption
│   ├── introNoutro.py           # 4. Transitions
│   ├── backNpip.py              # 5. Background + screen + PIP composition
│   ├── introEndOutro.py         # 6. Final intro & outro
│   ├── test_vcam.py             # Diagnostic: test pyvirtualcam pipeline
│   └── ocr_credentials.example.py
│
├── mask-live/
│   └── live.py                  # Real-time webcam masking → OBS Virtual Camera
│
├── requirements.txt
├── install.sh / install_osx.sh / Win/install.bat
├── reset.sh / Win/reset.bat
└── uninstall.sh / Win/uninstall.bat
```

---

## How "Safe Zone" works

For Mode 1 (with PIP), `face_mask.py` accumulates **every detected face bounding box** across the whole video, then computes a single rectangle that covers all of them plus margin. This guarantees the PIP overlay always covers 100% of the speaker. Saved to `output/.metadata/<video>_pip.json` :

```json
{
  "x":  320, "y":  180, "w":  640, "h":  360,
  "face_x":  480, "face_y":  240, "face_w": 200, "face_h": 240,
  "safe_x":  280, "safe_y":  150, "safe_w":  720, "safe_h":  405
}
```

---

## Streaming setup (Mode 3)

```
┌──────────────┐                      ┌────────────────────┐
│ Webcam       │ ──► live.py ──────►  │ OBS Virtual Camera │ ──┐
└──────────────┘                      └────────────────────┘   │
                                                               ├─► TikTok / Zoom / OBS
┌──────────────┐                      ┌────────────────────┐   │
│ Microphone   │ ──► Voicemod ─────►  │ Voicemod Virtual   │ ──┘
└──────────────┘                      │ Microphone         │
                                      └────────────────────┘
```

> 💡 In Voicemod's Voice Lab you can recreate the same audio effect as `audio.py` (pitch up/down + mix) for a consistent voice signature between recorded videos and live streams.

---

## Troubleshooting

**"AttributeError: module 'mediapipe' has no attribute 'solutions'"**  
MediaPipe ≥ 0.10.x removed the legacy API. The scripts auto-fall back to the Tasks API. The model `resources/face_landmarker.task` is auto-downloaded on first run.

**"OBS Virtual Camera shows static in browser"**  
(a) Make sure `live.py` is running before opening the consumer app. (b) OBS Studio's own Virtual Camera must **not** be active in parallel. (c) Only one app at a time can write to OBS Virtual Camera.

**Pipeline is very slow on a 1080p+ source**  
Set `PREPROCESS_MAX_WIDTH = 1280` in `config.py` to auto-downscale to 720p.

**Surface Pro / Qualcomm webcam not detected**  
Try `WEBCAM_INDEX = 1` (front camera) instead of `0` (rear) in `mask-live/live.py`. Media Foundation backend is more reliable than DirectShow on ARM devices.

**Live mode: mask lags behind face during fast movement**  
This is handled automatically by the velocity predictor. If lag is still visible, lower `EMA_ALPHA` (e.g. `0.5`) for more smoothing, or increase it (`0.9`) for faster response.

**Live mode: pipintro doesn't stop when face comes back**  
Fixed in current version via `result_id` sync. If it recurs, it usually means the segmentation model is taking too long — try increasing `_SEG_EVERY` from `2` to `3` in `live.py` to give the worker more headroom.

---

## Recent additions

| Feature | File | Notes |
|---------|------|-------|
| **3-thread pipeline** | `live.py` | Capture / ML worker / display run in parallel — eliminates webcam buffer lag |
| **Dedicated capture thread** | `live.py` | Always holds the latest webcam frame; main loop never blocks on `cap.read()` |
| **Person segmentation** | `live.py` | `selfie_segmenter_landscape.tflite` at ½ res, guided-filter + sigmoid refinement |
| **Matrix background** | `live.py` | `background.mp4` composited with luma-based transparency |
| **Luma-based alpha** | `live.py` | Black = transparent, bright green = opaque — real room visible in filigree |
| **BG_BRIGHTNESS / BG_OPACITY** | `live.py` | Independent control of matrix brightness and transparency level |
| **Half-res composite** | `live.py` | Float32 ops at 640×360, person stays at 1280×720 → 4× faster |
| **Debt-accumulator bg sync** | `live.py` | Background plays at exact native FPS regardless of main loop speed |
| **Velocity prediction** | `live.py` | Extrapolates landmark position 1 frame ahead to cancel worker-thread delay |
| **result_id sync** | `live.py` | `no_face` counter only moves on new worker results — fixes pipintro lock-on |
| **Resizable window** | `live.py` | `cv2.WINDOW_NORMAL` — drag to any size |
| **Security cache** | `live.py` | Raw webcam feed never displayed; grace period shows last safe anonymized frame |
| **MediaPipe Tasks API** | `live.py`, `face_mask.py` | Migrated from removed `mp.solutions` (MediaPipe ≥ 0.10.x) |
| **UTF-8 on Windows** | All scripts | Auto-reconfigures stdout/stderr (no more cp1252 errors) |
| **Reset / Uninstall scripts** | `reset.*`, `uninstall.*` | Keeps `.7z*` archives for fast re-install |

---

## License & credits

Personal anonymization toolkit. Uses :
- [MediaPipe](https://google.github.io/mediapipe/) (Apache 2.0) — face detection & segmentation
- [OpenCV](https://opencv.org/) (Apache 2.0) — video I/O, guided filter, blending
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense) — downloads
- [pyvirtualcam](https://github.com/letmaik/pyvirtualcam) (GPL-2) — OBS Virtual Camera bridge
- [FFmpeg](https://ffmpeg.org/) (LGPL/GPL) — audio/video processing
