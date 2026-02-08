#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import os
import subprocess
import shutil
from dataclasses import dataclass
from tqdm import tqdm

# ======================
# CONFIG
# ======================

@dataclass
class Config:
    input_dir: str = "output/.output0"
    output_dir: str = "output/.output1"

    max_width: int = 1280

    glitch_intensity: int = 3
    noise_level: int = 60
    max_band_width: int = 25
    max_shift: int = 25


CFG = Config()
rng = np.random.default_rng(42)

os.makedirs(CFG.output_dir, exist_ok=True)

# ======================
# UTILS
# ======================

def resize_frame(frame):
    h, w = frame.shape[:2]
    if w <= CFG.max_width:
        return frame
    scale = CFG.max_width / w
    return cv2.resize(frame, (int(w * scale), int(h * scale)))

def apply_glitch(frame):
    h, w, _ = frame.shape
    out = frame.copy()

    # Décalages horizontaux par bandes
    for _ in range(CFG.glitch_intensity):
        y = rng.integers(0, h)
        bh = rng.integers(5, CFG.max_band_width)
        shift = rng.integers(-CFG.max_shift, CFG.max_shift)
        out[y:y + bh] = np.roll(out[y:y + bh], shift, axis=1)

    # Bruit sur le canal vert (look glitch numérique)
    noise = rng.integers(0, CFG.noise_level, (h, w), dtype=np.uint8)
    out[:, :, 1] = np.clip(out[:, :, 1] + noise, 0, 255)

    return out

# ======================
# VIDEO PROCESSING
# ======================

def process_video(video_path, temp_out):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Vidéo illisible : {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("Impossible de lire la première frame")

    frame = resize_frame(frame)
    h, w = frame.shape[:2]

    out = cv2.VideoWriter(
        temp_out,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h)
    )

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    for _ in tqdm(range(total), desc=os.path.basename(video_path)):
        ret, frame = cap.read()
        if not ret:
            break

        frame = resize_frame(frame)
        frame = apply_glitch(frame)
        out.write(frame)

    cap.release()
    out.release()

# ======================
# AUDIO MERGE
# ======================

def merge_audio(src, video, out):
    if shutil.which("ffmpeg") is None:
        os.rename(video, out)
        return

    subprocess.run([
        "ffmpeg", "-y",
        "-i", video,
        "-i", src,
        "-map", "0:v:0",
        "-map", "1:a?",
        "-c:v", "libx264",
        "-c:a", "copy",
        "-shortest",
        out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    os.remove(video)

# ======================
# MAIN
# ======================

def main():
    videos = [
        v for v in os.listdir(CFG.input_dir)
        if v.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))
    ]

    if not videos:
        raise RuntimeError("Aucune vidéo à traiter")

    for v in videos:
        src = os.path.join(CFG.input_dir, v)
        tmp = os.path.join(CFG.output_dir, v + ".tmp.mp4")
        out = os.path.join(CFG.output_dir, v)

        process_video(src, tmp)
        merge_audio(src, tmp, out)

        print(f"[OK] {out}")

if __name__ == "__main__":
    main()
