#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import cv2
import mediapipe as mp
import numpy as np
import urllib.request

# ======================
# COMPATIBILITÉ MEDIAPIPE
# ======================
# MediaPipe < 0.10.x  → solutions API  (mp.solutions.face_mesh.FaceMesh)
# MediaPipe >= 0.10.x → Tasks API      (FaceLandmarker)
# On essaie les deux ; si aucune ne marche on arrête proprement.

def _download_model(dest):
    """Télécharge face_landmarker.task si absent."""
    if os.path.exists(dest):
        return
    url = (
        "https://storage.googleapis.com/mediapipe-models/"
        "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
    )
    print(f"[INFO] Téléchargement du modèle MediaPipe Tasks → {dest}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print("[INFO] Modèle téléchargé.")


class _LandmarkWrap:
    __slots__ = ("x", "y", "z")
    def __init__(self, lm):
        self.x = lm.x; self.y = lm.y; self.z = getattr(lm, "z", 0.0)

class _FaceLandmarksWrap:
    """Imite res.multi_face_landmarks[i].landmark[j] de l'ancienne API."""
    def __init__(self, lm_list):
        self.landmark = [_LandmarkWrap(lm) for lm in lm_list]

class _ResultWrap:
    """Imite le résultat de face_mesh.process()."""
    def __init__(self, tasks_result):
        self.multi_face_landmarks = (
            [_FaceLandmarksWrap(l) for l in tasks_result.face_landmarks]
            if tasks_result.face_landmarks else None
        )

class _FaceMeshTasksAdapter:
    """Wrapper Tasks API avec la même interface que l'ancien FaceMesh."""
    def __init__(self, max_num_faces=1, min_detection_confidence=0.5, **_):
        from mediapipe.tasks import python as _mp_py
        from mediapipe.tasks.python import vision as _vis

        # Le script est dans Pipeline/ → on remonte d'un niveau vers BASE_DIR
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "resources", "face_landmarker.task"
        )
        _download_model(model_path)

        opts = _vis.FaceLandmarkerOptions(
            base_options=_mp_py.BaseOptions(model_asset_path=model_path),
            num_faces=max_num_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
            running_mode=_vis.RunningMode.IMAGE,
        )
        self._det = _vis.FaceLandmarker.create_from_options(opts)

    def process(self, rgb):
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        return _ResultWrap(self._det.detect(img))

    def close(self):
        self._det.close()


# Choisit l'implémentation disponible
def _build_face_mesh_class():
    # Essai 1 : ancienne solutions API (mediapipe < 0.10.x)
    for path in ("mediapipe.solutions.face_mesh",
                 "mediapipe.python.solutions.face_mesh"):
        try:
            mod = __import__(path, fromlist=["FaceMesh"])
            return mod.FaceMesh
        except Exception:
            pass
    try:
        return mp.solutions.face_mesh.FaceMesh
    except Exception:
        pass
    # Essai 2 : Tasks API (mediapipe >= 0.10.x)
    try:
        import mediapipe.tasks  # noqa
        return _FaceMeshTasksAdapter
    except Exception:
        pass
    return None

_FaceMesh = _build_face_mesh_class()
if _FaceMesh is None:
    print("[ERREUR] Impossible d'initialiser MediaPipe FaceMesh.")
    print("         Essayez : pip install mediapipe==0.10.9")
    import sys; sys.exit(1)
import json
import os
import sys
import subprocess
import shutil
from dataclasses import dataclass
from tqdm import tqdm
# config.py est à la racine du projet (un niveau au-dessus de Pipeline/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C

# ======================
# CONFIG
# ======================

@dataclass
class Config:
    input_dir: str       = C.DIRS["input"]
    output_dir: str      = C.DIRS["output0"]
    mask_path: str       = C.MASK_PATH
    keypoints_path: str  = C.KEYPOINTS_PATH
    max_width: int       = C.MAX_WIDTH
    max_faces: int       = C.MAX_FACES
    detect_scale: float  = C.DETECT_SCALE
    ema_alpha: float     = C.EMA_ALPHA
    feather_radius: int  = C.FEATHER_RADIUS
    mask_scale: float    = C.MASK_SCALE
    pip_extract: bool    = C.PIP_EXTRACT
    pip_max_ratio: float = C.PIP_MAX_FACE_RATIO
    pip_padding: float   = C.PIP_PADDING


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

def compute_face_bbox(landmarks, w, h):
    """Bounding box serre autour du visage via tous les landmarks."""
    xs = [lm.x * w for lm in landmarks]
    ys = [lm.y * h for lm in landmarks]
    x1 = max(0, int(min(xs)))
    y1 = max(0, int(min(ys)))
    x2 = min(w, int(max(xs)))
    y2 = min(h, int(max(ys)))
    return np.float32([x1, y1, x2 - x1, y2 - y1])  # x, y, w, h


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
    face_mesh = _FaceMesh(
        static_image_mode=True,
        max_num_faces=CFG.max_faces,
        min_detection_confidence=0.3
    )

    last_landmarks = None
    best_region    = None   # derniere region ou le visage a ete detecte
    ema_pts        = None   # points lisses par EMA (float32)
    ema_bbox       = None   # bounding box lissee par EMA
    bbox_history   = []     # historique des bbox (pour detecter PIP)
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

            # Lissage EMA sur la bounding box (pour detection PIP)
            if CFG.pip_extract:
                raw_bbox = compute_face_bbox(found_lm, w, h)
                if ema_bbox is None:
                    ema_bbox = raw_bbox.copy()
                else:
                    ema_bbox = CFG.ema_alpha * raw_bbox + (1 - CFG.ema_alpha) * ema_bbox
                bbox_history.append(ema_bbox.copy())
        else:
            no_face += 1
            if no_face > 2:
                last_landmarks = None
                best_region = None   # reset : le visage a disparu, on rescanne tout
                ema_pts     = None
                ema_bbox    = None

        if last_landmarks and ema_pts is not None:
            # Scale du masque autour du centroide des 3 points
            centroid   = ema_pts.mean(axis=0)
            scaled_pts = centroid + (ema_pts - centroid) * CFG.mask_scale

            M = cv2.getAffineTransform(
                np.float32([MASK_KP["left_eye"], MASK_KP["right_eye"], MASK_KP["chin"]]),
                scaled_pts
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

    # --- Detection PIP ---
    pip_bbox  = None
    safe_zone = None
    if CFG.pip_extract and bbox_history:
        all_bboxes  = np.array(bbox_history)                          # (N, 4)
        median_bbox = np.median(all_bboxes, axis=0).astype(int)       # x, y, w, h
        bx, by, bw, bh = median_bbox
        ratio = bw / out_w
        if ratio < CFG.pip_max_ratio:
            pip_bbox = (int(bx), int(by), int(bw), int(bh))
            print(f"  [PIP] Visage detecte comme PIP — {bw}x{bh}px (ratio={ratio:.2f} < {CFG.pip_max_ratio})")

            # --- SAFE ZONE : union de toutes les bboxes + extension corps + marge ---
            xs    = all_bboxes[:, 0]
            ys    = all_bboxes[:, 1]
            x2s   = all_bboxes[:, 0] + all_bboxes[:, 2]
            y2s   = all_bboxes[:, 1] + all_bboxes[:, 3]

            min_x = float(xs.min())
            min_y = float(ys.min())
            max_x = float(x2s.max())
            max_y = float(y2s.max())

            # Hauteur de visage max → base pour les extensions
            face_h_max = float(all_bboxes[:, 3].max())

            # Élargir minimum — on couvre juste tête + épaules
            min_x -= face_h_max * 0.15  # gauche
            max_x += face_h_max * 0.15  # droite
            min_y -= face_h_max * 0.15  # haut
            max_y += face_h_max * 0.6   # bas (épaules seulement)

            # Marge de sécurité 5%
            cx = (min_x + max_x) / 2
            cy = (min_y + max_y) / 2
            half_w = (max_x - min_x) / 2 * 1.05
            half_h = (max_y - min_y) / 2 * 1.05

            # Forcer ratio 16:9 (étendre la dimension trop courte)
            target_ratio = 16 / 9
            cur_w = half_w * 2
            cur_h = half_h * 2
            if cur_w / cur_h < target_ratio:
                # Pas assez large → étendre largeur
                half_w = (cur_h * target_ratio) / 2
            else:
                # Pas assez haut → étendre hauteur
                half_h = (cur_w / target_ratio) / 2

            min_x = cx - half_w
            max_x = cx + half_w
            min_y = cy - half_h
            max_y = cy + half_h

            # Clamp aux limites du frame
            min_x = max(0, min_x)
            min_y = max(0, min_y)
            max_x = min(out_w, max_x)
            max_y = min(out_h, max_y)

            safe_zone = (
                int(min_x), int(min_y),
                int(max_x - min_x), int(max_y - min_y)
            )
            print(f"  [SAFE] Zone sûre : x={safe_zone[0]} y={safe_zone[1]} "
                  f"w={safe_zone[2]} h={safe_zone[3]} (couvre toutes les positions)")
        else:
            print(f"  [PIP] Visage plein ecran (ratio={ratio:.2f}) — pas de PIP")

    return pip_bbox, safe_zone

# ======================
# PIP EXTRACTION
# ======================

def extract_pip(masked_video, original_src, bbox, frame_w, frame_h, safe_zone=None):
    """
    Routing :
      - _pip.mp4    → output0  (crop du masqué, passera par glitch)
      - _screen.mp4 → output1  (vidéo originale, skip glitch)
    """
    if shutil.which("ffmpeg") is None:
        print("  [PIP] ffmpeg introuvable — extraction ignoree")
        return None, None

    bx, by, bw, bh = bbox

    # Centre du visage
    cx = bx + bw // 2
    cy = by + bh // 2

    # Padding autour de la zone webcam
    pad_x = int(bw * CFG.pip_padding)
    pad_y = int(bh * CFG.pip_padding)
    pw = bw + pad_x * 2
    ph = bh + pad_y * 2

    # Force ratio 16:9
    target_ratio = 16 / 9
    if pw / ph < target_ratio:
        pw = int(ph * target_ratio)
    else:
        ph = int(pw / target_ratio)

    # Centrer le crop sur le visage
    px = cx - pw // 2
    py = cy - ph // 2

    # Clamp dans les limites du frame
    px = max(0, min(px, frame_w - pw))
    py = max(0, min(py, frame_h - ph))
    pw = min(pw, frame_w - px)
    ph = min(ph, frame_h - py)

    # libx264 exige des dimensions paires
    pw = pw - (pw % 2)
    ph = ph - (ph % 2)

    basename = os.path.splitext(os.path.basename(original_src))[0]
    dir_out0 = C.DIRS["output0"]
    dir_out1 = C.DIRS["output1"]
    dir_meta = C.DIRS["metadata"]
    os.makedirs(dir_out0, exist_ok=True)
    os.makedirs(dir_out1, exist_ok=True)
    os.makedirs(dir_meta, exist_ok=True)

    pip_out    = os.path.join(dir_out0, basename + "_pip.mp4")
    screen_out = os.path.join(dir_out1, basename + "_screen.mp4")

    # Sauvegarde position pour backNpip.py
    # x, y, w, h     = crop PIP centré sur le visage (extraction)
    # face_*         = bounding box du visage uniquement
    # safe_*         = ZONE SÛRE qui couvre TOUTES les positions du personnage
    #                  → backNpip utilise ça pour garantir 100% de couverture
    import json
    meta_data = {
        "x": int(px), "y": int(py), "w": int(pw), "h": int(ph),
        "face_x": int(bx), "face_y": int(by), "face_w": int(bw), "face_h": int(bh),
    }
    if safe_zone is not None:
        sx, sy, sw, sh = safe_zone
        meta_data["safe_x"] = int(sx)
        meta_data["safe_y"] = int(sy)
        meta_data["safe_w"] = int(sw)
        meta_data["safe_h"] = int(sh)

    with open(os.path.join(dir_meta, basename + "_pip.json"), "w") as f:
        json.dump(meta_data, f)
    print(f"  [PIP] Crop : ({px}, {py}) {pw}x{ph} | Visage : ({bx}, {by})")
    if safe_zone is not None:
        print(f"  [SAFE] Sauvegarde zone sûre : ({sx}, {sy}) {sw}x{sh}")

    # PIP : crop depuis la video maskée → output0 → sera glitchée
    subprocess.run([
        "ffmpeg", "-y", "-i", masked_video,
        "-vf", f"crop={pw}:{ph}:{px}:{py}",
        "-c:v", "libx264", "-crf", "18",
        "-c:a", "copy", pip_out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  [PIP] pip    → {pip_out}")

    # SCREEN : video originale → output1 → skip glitch
    subprocess.run([
        "ffmpeg", "-y", "-i", original_src,
        "-c:v", "libx264", "-crf", "18",
        "-c:a", "copy", screen_out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  [PIP] screen → {screen_out}")

    return pip_out, screen_out


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
        pip_bbox, safe_zone = process_video(src, tmp)
        merge_audio(src, tmp, out)
        print(f"[OK] {out}")

        # Extraction PIP depuis la vidéo maskée (out) — le masque est déjà appliqué
        if pip_bbox is not None:
            cap_out = cv2.VideoCapture(out)
            frame_w = int(cap_out.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_h = int(cap_out.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap_out.release()
            extract_pip(out, src, pip_bbox, frame_w, frame_h, safe_zone)
            os.remove(out)  # glitch ne voit que _pip.mp4, pas la vidéo maskée complète
            print(f"[OK] pip → output0 | screen → output1")

if __name__ == "__main__":
    main()
