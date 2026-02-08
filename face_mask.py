#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import mediapipe as mp
import numpy as np
import json
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
    input_dir: str = "input"
    output_dir: str = "output/.output0"

    mask_path: str = "resources/mask.png"
    keypoints_path: str = "resources/mask_keypoints.json"

    max_width: int = 1280
    max_faces: int = 1


CFG = Config()

LEFT_EYE = 33
RIGHT_EYE = 263
CHIN = 152

os.makedirs(CFG.output_dir, exist_ok=True)

# ======================
# MASK KEYPOINTS UI
# ======================

def create_mask_keypoints_interactive(mask_path, keypoints_path):
    if os.path.exists(keypoints_path):
        return

    mask = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
    if mask is None:
        raise RuntimeError("Masque PNG introuvable")

    points = []
    labels = ["CLIQUE : ŒIL GAUCHE", "CLIQUE : ŒIL DROIT", "CLIQUE : MENTON"]
    display = mask.copy()

    def mouse_cb(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 3:
            points.append((x, y))
            cv2.circle(display, (x, y), 6, (0, 255, 0, 255), -1)

    cv2.namedWindow("Calibration masque", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("Calibration masque", mouse_cb)

    while True:
        temp = display.copy()
        if len(points) < 3:
            cv2.putText(
                temp, labels[len(points)], (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2
            )
        else:
            cv2.putText(
                temp, "ENTRÉE pour valider", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )

        cv2.imshow("Calibration masque", temp)
        key = cv2.waitKey(1) & 0xFF

        if key == 13 and len(points) == 3:
            break
        if key == 27:
            raise RuntimeError("Calibration annulée")

    cv2.destroyAllWindows()

    data = {
        "left_eye": list(points[0]),
        "right_eye": list(points[1]),
        "chin": list(points[2])
    }

    os.makedirs(os.path.dirname(keypoints_path), exist_ok=True)
    with open(keypoints_path, "w") as f:
        json.dump(data, f, indent=2)

    print("[OK] mask_keypoints.json créé")

# ======================
# LOAD STATIC
# ======================

create_mask_keypoints_interactive(CFG.mask_path, CFG.keypoints_path)

with open(CFG.keypoints_path) as f:
    MASK_KP = json.load(f)

MASK = cv2.imread(CFG.mask_path, cv2.IMREAD_UNCHANGED)
if MASK is None or MASK.shape[2] != 4:
    raise RuntimeError("Masque RGBA requis")

# ======================
# UTILS
# ======================

def resize_frame(frame):
    h, w = frame.shape[:2]
    if w <= CFG.max_width:
        return frame
    scale = CFG.max_width / w
    return cv2.resize(frame, (int(w * scale), int(h * scale)))

def landmark_xy(lm, idx, w, h):
    return int(lm[idx].x * w), int(lm[idx].y * h)

def sanitize_rgba(img):
    alpha = img[:, :, 3]
    img[alpha == 0, :3] = 0
    return img

def blend_rgba(frame, overlay):
    alpha = overlay[:, :, 3:4] / 255.0
    frame[:] = alpha * overlay[:, :, :3] + (1 - alpha) * frame
    return frame.astype(np.uint8)

# ======================
# VIDEO PROCESSING
# ======================

def process_video(video_path, temp_out):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Vidéo illisible")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    ret, frame = cap.read()
    frame = resize_frame(frame)
    h, w = frame.shape[:2]

    out = cv2.VideoWriter(
        temp_out,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h)
    )

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=CFG.max_faces
    )

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    last_landmarks = None
    no_face_counter = 0

    for _ in tqdm(range(total), desc=os.path.basename(video_path)):
        ret, frame = cap.read()
        if not ret:
            break

        frame = resize_frame(frame)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = face_mesh.process(rgb)

        if result.multi_face_landmarks:
            last_landmarks = result.multi_face_landmarks[0].landmark
            no_face_counter = 0
        else:
            no_face_counter += 1
            if no_face_counter > 2:
                last_landmarks = None

        if last_landmarks:
            left = landmark_xy(last_landmarks, LEFT_EYE, w, h)
            right = landmark_xy(last_landmarks, RIGHT_EYE, w, h)
            chin = landmark_xy(last_landmarks, CHIN, w, h)

            src = np.float32([
                MASK_KP["left_eye"],
                MASK_KP["right_eye"],
                MASK_KP["chin"]
            ])
            dst = np.float32([left, right, chin])

            M = cv2.getAffineTransform(src, dst)
            warped = cv2.warpAffine(
                MASK, M, (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0)
            )

            warped = sanitize_rgba(warped)
            frame = blend_rgba(frame, warped)

        out.write(frame)

    cap.release()
    out.release()
    face_mesh.close()

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
        raise RuntimeError("Aucune vidéo")

    for v in videos:
        src = os.path.join(CFG.input_dir, v)
        tmp = os.path.join(CFG.output_dir, v + ".tmp.mp4")
        out = os.path.join(CFG.output_dir, v)

        process_video(src, tmp)
        merge_audio(src, tmp, out)

        print(f"[OK] {out}")

if __name__ == "__main__":
    main()
