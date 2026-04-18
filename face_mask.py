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
import config as C

# ======================
# CONFIG
# ======================

@dataclass
class Config:
    input_dir: str      = C.DIRS["input"]
    output_dir: str     = C.DIRS["output0"]
    mask_path: str      = C.MASK_PATH
    keypoints_path: str = C.KEYPOINTS_PATH
    max_width: int      = C.MAX_WIDTH
    max_faces: int      = C.MAX_FACES
    detect_scale: float = C.DETECT_SCALE
    ema_alpha: float    = C.EMA_ALPHA
    feather_radius: int = C.FEATHER_RADIUS


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
            cv2.putText(temp, labels[len(points)], (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        else:
            cv2.putText(temp, "ENTRÉE pour valider", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        cv2.imshow("Calibration masque", temp)
        key = cv2.waitKey(1) & 0xFF

        if key == 13 and len(points) == 3:
            break
        if key == 27:
            raise RuntimeError("Calibration annulée")

    cv2.destroyAllWindows()

    with open(keypoints_path, "w") as f:
        json.dump({
            "left_eye": list(points[0]),
            "right_eye": list(points[1]),
            "chin": list(points[2])
        }, f, indent=2)

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
    img[img[:, :, 3] == 0, :3] = 0
    return img

def feather_mask(warped, radius):
    """Applique un flou gaussien sur le canal alpha pour adoucir les bords du masque."""
    if radius <= 0:
        return warped
    k = radius * 2 + 1  # taille du kernel (doit etre impair)
    alpha = warped[:, :, 3].astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (k, k), 0)
    result = warped.copy()
    result[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    return result

def blend_rgba(frame, overlay):
    alpha = overlay[:, :, 3:4] / 255.0
    frame[:] = alpha * overlay[:, :, :3] + (1 - alpha) * frame
    return frame.astype(np.uint8)


# ======================
# MULTI-REGION DETECTION
# ======================

def get_scan_regions(w, h):
    """Retourne des regions (x, y, rw, rh) couvrant le frame.
    Zones : frame entier, 4 coins (50%), 4 bords (50%), centre.
    Overlap garanti pour ne rater aucun visage."""
    hw, hh = w // 2, h // 2
    regions = [
        (0, 0, w, h),          # frame entier
        (0, 0, hw, hh),        # top-left
        (hw, 0, hw, hh),       # top-right
        (0, hh, hw, hh),       # bottom-left
        (hw, hh, hw, hh),      # bottom-right
        (w // 4, h // 4, hw, hh),  # centre
        (0, 0, w, hh),         # top half
        (0, hh, w, hh),        # bottom half
        (0, 0, hw, h),         # left half
        (hw, 0, hw, h),        # right half
    ]
    return regions


class AdjustedLandmark:
    """Landmark avec coordonnees normalisees [0-1] ramenees au frame complet."""
    __slots__ = ("x", "y", "z")
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


def _try_full_frame(rgb, face_mesh, w, h):
    """Teste la detection sur le frame entier upscale. Retourne landmarks ou None."""
    if CFG.detect_scale > 1.0:
        det = cv2.resize(rgb, (int(w * CFG.detect_scale), int(h * CFG.detect_scale)))
    else:
        det = rgb
    res = face_mesh.process(det)
    if res.multi_face_landmarks:
        return res.multi_face_landmarks[0].landmark
    return None


def _try_region(rgb, face_mesh, w, h, rx, ry, rw, rh):
    """Teste la detection sur une sous-region upscalee.
    Retourne les landmarks convertis en coords du frame complet, ou None."""
    if rw < 50 or rh < 50:
        return None
    crop    = rgb[ry:ry + rh, rx:rx + rw]
    target_w = max(rw * 4, 640)
    target_h = int(rh * target_w / rw)
    crop_up  = cv2.resize(crop, (target_w, target_h))
    res = face_mesh.process(crop_up)
    if not res.multi_face_landmarks:
        return None
    return [
        AdjustedLandmark((rx + p.x * rw) / w, (ry + p.y * rh) / h, p.z)
        for p in res.multi_face_landmarks[0].landmark
    ]


def detect_in_regions(rgb, face_mesh, w, h, best_region=None):
    """Detecte un visage en testant en priorite la derniere region qui a fonctionne,
    puis le frame entier, puis toutes les sous-regions.

    Retourne (landmarks, region) :
      - region = 'full'         si detecte sur le frame entier
      - region = (rx,ry,rw,rh) si detecte dans une sous-region
      - (None, None)            si aucun visage trouve
    """

    # 1) Derniere region connue en priorite — evite de scanner si le visage n'a pas bouge
    if best_region is not None:
        if best_region == "full":
            lm = _try_full_frame(rgb, face_mesh, w, h)
            if lm is not None:
                return lm, "full"
        else:
            lm = _try_region(rgb, face_mesh, w, h, *best_region)
            if lm is not None:
                return lm, best_region

    # 2) Frame entier (si pas deja teste)
    if best_region != "full":
        lm = _try_full_frame(rgb, face_mesh, w, h)
        if lm is not None:
            return lm, "full"

    # 3) Scan de toutes les sous-regions
    for region in get_scan_regions(w, h)[1:]:
        lm = _try_region(rgb, face_mesh, w, h, *region)
        if lm is not None:
            return lm, region

    return None, None

# ======================
# VIDEO PROCESSING
# ======================

def process_video(video_path, temp_out):
    print(f"  [DEBUG] Ouverture : {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Impossible d'ouvrir : {video_path}")

    fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  [DEBUG] {orig_w}x{orig_h} @ {fps:.1f}fps, {total} frames")

    if orig_w <= 0 or orig_h <= 0:
        raise RuntimeError(f"Dimensions invalides pour : {video_path}")

    if orig_w > CFG.max_width:
        scale = CFG.max_width / orig_w
        out_w = int(orig_w * scale)
        out_h = int(orig_h * scale)
    else:
        out_w, out_h = orig_w, orig_h

    out = cv2.VideoWriter(
        temp_out,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (out_w, out_h)
    )

    # FaceMesh NEUF pour chaque video — evite toute corruption d'etat
    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=CFG.max_faces,
        min_detection_confidence=0.3
    )

    last_landmarks = None
    best_region    = None   # derniere region ou le visage a ete detecte
    ema_pts        = None   # points lisses par EMA (float32)
    no_face = 0
    detected = 0
    written = 0

    for i in tqdm(range(total), desc=os.path.basename(video_path)):
        ret, frame = cap.read()
        if not ret:
            break

        frame = resize_frame(frame)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detection : teste best_region en premier, puis fallback sur les autres zones
        found_lm, best_region = detect_in_regions(rgb, face_mesh, w, h, best_region)

        if found_lm is not None:
            last_landmarks = found_lm
            no_face = 0
            detected += 1

            # Lissage EMA sur les 3 points cles
            raw_pts = np.float32([
                landmark_xy(found_lm, LEFT_EYE, w, h),
                landmark_xy(found_lm, RIGHT_EYE, w, h),
                landmark_xy(found_lm, CHIN, w, h),
            ])
            if ema_pts is None:
                ema_pts = raw_pts.copy()
            else:
                ema_pts = CFG.ema_alpha * raw_pts + (1 - CFG.ema_alpha) * ema_pts
        else:
            no_face += 1
            if no_face > 2:
                last_landmarks = None
                best_region = None   # reset : le visage a disparu, on rescanne tout
                ema_pts     = None

        if last_landmarks and ema_pts is not None:
            M = cv2.getAffineTransform(
                np.float32([MASK_KP["left_eye"], MASK_KP["right_eye"], MASK_KP["chin"]]),
                ema_pts
            )

            warped = cv2.warpAffine(
                MASK, M, (w, h),
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0)
            )

            warped = sanitize_rgba(warped)
            warped = feather_mask(warped, CFG.feather_radius)
            frame = blend_rgba(frame, warped)

            # FLAG : masque present (pixel vert invisible)
            if np.any(warped[:, :, 3] > 0):
                frame[0:2, 0:2, 1] = 255

        out.write(frame)
        written += 1

    cap.release()
    out.release()
    face_mesh.close()

    print(f"  [RESULT] Visage detecte : {detected}/{total} frames | Ecrites : {written}/{total}")

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
    videos = sorted([
        v for v in os.listdir(CFG.input_dir)
        if v.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))
    ])

    if not videos:
        print("[ERREUR] Aucune video trouvee dans", CFG.input_dir)
        sys.exit(1)

    print(f"[INFO] {len(videos)} video(s) : {videos}")
    print(f"[INFO] detect_scale = {CFG.detect_scale}")

    for i, v in enumerate(videos, 1):
        src = os.path.join(CFG.input_dir, v)
        tmp = os.path.join(CFG.output_dir, v + ".tmp.mp4")
        out = os.path.join(CFG.output_dir, v)

        print(f"\n[{i}/{len(videos)}] {v}")
        process_video(src, tmp)
        merge_audio(src, tmp, out)
        print(f"[OK] {out}")

if __name__ == "__main__":
    main()
