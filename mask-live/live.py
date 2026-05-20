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
import json
import os
import time
import urllib.request
import subprocess
import ctypes
import threading

# ======================
# CAMERA OS-LEVEL LOCK (Windows admin)
# ======================

def _is_admin():
    if sys.platform != "win32":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_as_admin():
    """Relance ce script avec UAC. Retourne True si relance déclenchée."""
    if sys.platform != "win32" or _is_admin():
        return False
    params = " ".join(f'"{a}"' for a in sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    return rc > 32  # >32 = succès


def _list_cameras_pnp():
    """Retourne la liste de (InstanceId, FriendlyName) des caméras actives."""
    if sys.platform != "win32":
        return []
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-PnpDevice -Class Camera -Status OK | "
             "ForEach-Object { $_.InstanceId + '|' + $_.FriendlyName }"],
            capture_output=True, text=True, timeout=15
        )
        result = []
        for line in r.stdout.splitlines():
            line = line.strip()
            if "|" in line:
                iid, name = line.split("|", 1)
                result.append((iid.strip(), name.strip()))
        return result
    except Exception:
        return []


def _disable_camera(instance_id):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Disable-PnpDevice -InstanceId '{instance_id}' "
             "-Confirm:$false -ErrorAction Stop"],
            capture_output=True, text=True, timeout=15
        )
        return r.returncode == 0
    except Exception:
        return False


def _enable_camera(instance_id):
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Enable-PnpDevice -InstanceId '{instance_id}' "
             "-Confirm:$false -ErrorAction SilentlyContinue"],
            capture_output=True, text=True, timeout=15
        )
        return True
    except Exception:
        return False


# ======================
# CAMERA PRIVACY REGISTRY (per-user, sans admin)
# ======================
# Bloque l'accès caméra pour TOUTES les apps desktop (sauf celles qui
# ont déjà un handle ouvert avant le blocage = live.py).
# Path : HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam

_REG_PATH = r"HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"
_REG_PATH_NONPKG = _REG_PATH + r"\NonPackaged"


def _reg_read(path, name="Value"):
    if sys.platform != "win32":
        return None
    try:
        r = subprocess.run(
            ["reg", "query", path, "/v", name],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith(name):
                # Format: "Value    REG_SZ    Allow"
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    return parts[2].strip()
    except Exception:
        pass
    return None


def _reg_write(path, value, name="Value"):
    if sys.platform != "win32":
        return False
    try:
        r = subprocess.run(
            ["reg", "add", path, "/v", name, "/t", "REG_SZ",
             "/d", value, "/f"],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def _privacy_lock():
    """Bloque l'accès caméra pour toutes les apps desktop. Retourne les valeurs précédentes pour restauration."""
    prev = {
        "main": _reg_read(_REG_PATH) or "Allow",
        "nonpkg": _reg_read(_REG_PATH_NONPKG) or "Allow",
    }
    ok1 = _reg_write(_REG_PATH, "Deny")
    ok2 = _reg_write(_REG_PATH_NONPKG, "Deny")
    if ok1 or ok2:
        return prev
    return None


def _privacy_restore(prev):
    if prev is None:
        return
    _reg_write(_REG_PATH, prev["main"])
    _reg_write(_REG_PATH_NONPKG, prev["nonpkg"])


def _camera_alive(cap, n=4):
    """Vérifie que la caméra capture vraiment du contenu vivant.
    Retourne False si les frames sont figées (buffer mort)."""
    frames = []
    for _ in range(n):
        ret, frame = cap.read()
        if not ret or frame is None:
            return False
        frames.append(frame)
        time.sleep(0.07)
    # Variance entre frames consécutives → si c'est figé, diff ≈ 0
    for i in range(1, len(frames)):
        diff = float(np.mean(np.abs(
            frames[i].astype(np.int16) - frames[0].astype(np.int16)
        )))
        if diff > 1.0:
            return True
    return False

# ======================
# COMPATIBILITE MEDIAPIPE
# ======================
# MediaPipe < 0.10.x  -> solutions API  (mp.solutions.face_mesh.FaceMesh)
# MediaPipe >= 0.10.x -> Tasks API      (FaceLandmarker)

def _download_model(dest):
    """Telecharge face_landmarker.task si absent."""
    if os.path.exists(dest):
        return
    url = (
        "https://storage.googleapis.com/mediapipe-models/"
        "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
    )
    print(f"[INFO] Telechargement du modele MediaPipe Tasks -> {dest}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print("[INFO] Modele telecharge.")


class _LandmarkWrap:
    __slots__ = ("x", "y", "z")
    def __init__(self, lm):
        self.x = lm.x; self.y = lm.y; self.z = getattr(lm, "z", 0.0)

class _FaceLandmarksWrap:
    def __init__(self, lm_list):
        self.landmark = [_LandmarkWrap(lm) for lm in lm_list]

class _ResultWrap:
    def __init__(self, tasks_result):
        self.multi_face_landmarks = (
            [_FaceLandmarksWrap(l) for l in tasks_result.face_landmarks]
            if tasks_result.face_landmarks else None
        )

class _FaceMeshTasksAdapter:
    """Wrapper Tasks API (RunningMode.VIDEO) avec interface FaceMesh."""
    def __init__(self, max_num_faces=1, min_detection_confidence=0.5, **_):
        from mediapipe.tasks import python as _mp_py
        from mediapipe.tasks.python import vision as _vis

        # Le modele est dans ../resources/ (un niveau au-dessus de mask-live/)
        model_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "resources", "face_landmarker.task"
        )
        model_path = os.path.normpath(model_path)
        _download_model(model_path)

        opts = _vis.FaceLandmarkerOptions(
            base_options=_mp_py.BaseOptions(model_asset_path=model_path),
            num_faces=max_num_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
            running_mode=_vis.RunningMode.VIDEO,
        )
        self._det = _vis.FaceLandmarker.create_from_options(opts)
        self._t0 = time.monotonic()

    def process(self, rgb):
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms = int((time.monotonic() - self._t0) * 1000)
        return _ResultWrap(self._det.detect_for_video(img, ts_ms))

    def close(self):
        self._det.close()


def _build_face_mesh_class():
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
    sys.exit(1)

try:
    import pyvirtualcam
    VIRTUAL_CAM = True
except ImportError:
    VIRTUAL_CAM = False
    print("[INFO] pyvirtualcam non installé — affichage fenêtre uniquement")
    print("[INFO] Dans OBS, utilise 'Window Capture' pour capturer cette fenêtre")

# ======================
# CONFIG
# ======================

RESOURCES_DIR  = os.path.join(os.path.dirname(__file__), "..", "resources")
MASK_PATH      = os.path.join(RESOURCES_DIR, "mask.png")
KEYPOINTS_PATH = os.path.join(RESOURCES_DIR, "mask_keypoints.json")

WEBCAM_INDEX   = 1
WIDTH          = 1280
HEIGHT         = 720
FPS            = 30
EMA_ALPHA      = 0.7   # plus réactif qu'en post-processing
FEATHER_RADIUS = 8
MASK_SCALE     = 1.1
NO_FACE_GRACE  = 1     # frames de grâce avant de basculer sur pipintro

PIPINTRO_PATH  = os.path.join(RESOURCES_DIR, "pipintro.mp4")
BACKGROUND_PATH = os.path.join(RESOURCES_DIR, "background.mp4")

LEFT_EYE  = 33
RIGHT_EYE = 263
CHIN      = 152

# ======================
# CHARGEMENT MASQUE
# ======================

def load_mask():
    mask = cv2.imread(MASK_PATH, cv2.IMREAD_UNCHANGED)
    if mask is None:
        print(f"[ERREUR] Masque introuvable : {MASK_PATH}")
        sys.exit(1)
    if mask.shape[2] != 4:
        print("[ERREUR] Le masque doit être en RGBA (PNG avec transparence)")
        sys.exit(1)
    return mask


def load_or_create_keypoints(mask):
    if os.path.exists(KEYPOINTS_PATH):
        with open(KEYPOINTS_PATH) as f:
            return json.load(f)

    print("[CALIBRATION] Clique sur : œil gauche, œil droit, menton — puis Entrée")
    points = []
    display = mask.copy()

    def mouse_cb(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 3:
            points.append((x, y))
            cv2.circle(display, (x, y), 6, (0, 255, 0, 255), -1)

    labels = ["ŒIL GAUCHE", "ŒIL DROIT", "MENTON"]
    cv2.namedWindow("Calibration masque", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("Calibration masque", mouse_cb)

    while True:
        temp = display.copy()
        label = labels[len(points)] if len(points) < 3 else "ENTRÉE pour valider"
        cv2.putText(temp, label, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (255, 255, 255), 2)
        cv2.imshow("Calibration masque", temp)
        key = cv2.waitKey(1) & 0xFF
        if key == 13 and len(points) == 3:
            break
        if key == 27:
            sys.exit(0)

    cv2.destroyAllWindows()
    kp = {"left_eye": list(points[0]), "right_eye": list(points[1]), "chin": list(points[2])}
    with open(KEYPOINTS_PATH, "w") as f:
        json.dump(kp, f, indent=2)
    return kp

# ======================
# UTILS
# ======================

def landmark_xy(lm, idx, w, h):
    return int(lm[idx].x * w), int(lm[idx].y * h)


def feather_mask(warped, radius):
    if radius <= 0:
        return warped
    k = radius * 2 + 1
    alpha = warped[:, :, 3].astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (k, k), 0)
    result = warped.copy()
    result[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    return result


def blend_rgba(frame, overlay):
    alpha = overlay[:, :, 3:4] / 255.0
    frame[:] = (alpha * overlay[:, :, :3] + (1 - alpha) * frame).astype(np.uint8)
    return frame


def apply_mask(frame, mask, mask_kp, ema_pts):
    h, w = frame.shape[:2]

    raw_pts = np.float32([
        landmark_xy(ema_pts["lm"], LEFT_EYE, w, h),
        landmark_xy(ema_pts["lm"], RIGHT_EYE, w, h),
        landmark_xy(ema_pts["lm"], CHIN, w, h),
    ])

    # Compensation par vélocité : prédit la position actuelle du visage
    # pour compenser le délai d'un frame du thread ML.
    # velocity = déplacement mesuré entre les deux derniers résultats worker.
    # On extrapole raw_pts d'un frame en avant → masque en phase avec le visage.
    prev_raw = ema_pts.get("prev_raw")
    if prev_raw is not None:
        vel = raw_pts - prev_raw                          # déplacement brut
        vel_smooth = ema_pts.get("velocity")
        if vel_smooth is None:
            ema_pts["velocity"] = vel
        else:
            ema_pts["velocity"] = 0.4 * vel + 0.6 * vel_smooth   # lissage vélocité
        raw_pts = raw_pts + ema_pts["velocity"]           # extrapolation +1 frame
    ema_pts["prev_raw"] = raw_pts.copy()

    if ema_pts["smooth"] is None:
        ema_pts["smooth"] = raw_pts.copy()
    else:
        ema_pts["smooth"] = EMA_ALPHA * raw_pts + (1 - EMA_ALPHA) * ema_pts["smooth"]

    centroid   = ema_pts["smooth"].mean(axis=0)
    scaled_pts = centroid + (ema_pts["smooth"] - centroid) * MASK_SCALE

    M = cv2.getAffineTransform(
        np.float32([mask_kp["left_eye"], mask_kp["right_eye"], mask_kp["chin"]]),
        scaled_pts
    )
    warped = cv2.warpAffine(mask, M, (w, h),
                            borderMode=cv2.BORDER_CONSTANT,
                            borderValue=(0, 0, 0, 0))
    warped[warped[:, :, 3] == 0, :3] = 0
    warped = feather_mask(warped, FEATHER_RADIUS)
    frame  = blend_rgba(frame, warped)
    return frame

# ======================
# MAIN
# ======================

def main():
    mask    = load_mask()
    mask_kp = load_or_create_keypoints(mask)

    # Backend par défaut (Media Foundation sur Surface Pro / Qualcomm)
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # buffer minimal côté driver

    if not cap.isOpened():
        print(f"[ERREUR] Webcam {WEBCAM_INDEX} inaccessible")
        sys.exit(1)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Webcam : {actual_w}x{actual_h} @ {FPS}fps")

    # --- PipIntro (video de secours si tracking perdu) ---
    pip_cap = None
    if os.path.isfile(PIPINTRO_PATH):
        pip_cap = cv2.VideoCapture(PIPINTRO_PATH)
        print(f"[INFO] PipIntro charge : {PIPINTRO_PATH}")
    else:
        print(f"[WARN] PipIntro introuvable : {PIPINTRO_PATH}")
        print( "       → ecran noir si le tracking est perdu")

    face_mesh = _FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # --- Background video ---
    bg_cap = None
    if os.path.isfile(BACKGROUND_PATH):
        bg_cap = cv2.VideoCapture(BACKGROUND_PATH)
        print(f"[INFO] Background chargé : {BACKGROUND_PATH}")
    else:
        print(f"[WARN] Background introuvable : {BACKGROUND_PATH}")

    # --- Segmentation personne / fond (Tasks API) ---
    selfie_seg = None
    _seg_t0 = time.monotonic()
    try:
        from mediapipe.tasks import python as _mp_py
        from mediapipe.tasks.python import vision as _vis

        _seg_model = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "resources", "selfie_segmenter_landscape.tflite"
        ))
        if not os.path.exists(_seg_model):
            print("[INFO] Téléchargement du modèle de segmentation landscape...")
            urllib.request.urlretrieve(
                "https://storage.googleapis.com/mediapipe-models/"
                "image_segmenter/selfie_segmenter_landscape/float16/latest/"
                "selfie_segmenter_landscape.tflite",
                _seg_model
            )
            print("[INFO] Modèle segmentation téléchargé.")

        _seg_opts = _vis.ImageSegmenterOptions(
            base_options=_mp_py.BaseOptions(model_asset_path=_seg_model),
            running_mode=_vis.RunningMode.VIDEO,
            output_confidence_masks=True,
        )
        selfie_seg = _vis.ImageSegmenter.create_from_options(_seg_opts)
        print("[INFO] Segmentation activée — remplacement de background actif")
    except Exception as e:
        print(f"[WARN] Segmentation indisponible ({e}) — background non remplacé")

    ema_pts = {"lm": None, "smooth": None}

    cv2.namedWindow("Mask Live — Échap pour quitter", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Mask Live — Échap pour quitter", actual_w, actual_h)

    # Lecture du background calée sur le temps réel
    _bg_fps      = float(bg_cap.get(cv2.CAP_PROP_FPS) or 30.0) if bg_cap else 30.0
    _bg_interval = 1.0 / _bg_fps
    # "debt" : fraction de frame accumulée entre deux appels (évite la perte de précision)
    _bg_state    = {"last_t": -1.0, "cached": None, "debt": 0.0}
    BG_OPACITY     = 0.85  # transparence luma    (0.0 = pièce pure, 1.0 = matrix plein)
    BG_BRIGHTNESS  = 1.0   # luminosité du matrix (0.5 = sombre, 1.0 = normal, 1.5 = lumineux)

    def _get_bg_frame():
        """Retourne la frame background synchro sur le temps réel.
        Utilise un accumulateur de dette pour préserver la fraction de frame
        entre deux appels — garantit la bonne vitesse même quand la boucle
        principale tourne exactement à la même cadence que la vidéo."""
        if bg_cap is None:
            return np.zeros((actual_h, actual_w, 3), dtype=np.uint8)

        now = time.monotonic()

        # Initialisation : forcer la lecture de la 1ère frame
        if _bg_state["last_t"] < 0:
            _bg_state["last_t"] = now
            _bg_state["debt"]   = 1.0

        elapsed = now - _bg_state["last_t"]
        _bg_state["last_t"] = now   # réinitialiser sur le temps courant (pas sur un multiple d'intervalle)

        # Accumuler le temps en unités de frames
        _bg_state["debt"] += elapsed / _bg_interval
        frames_to_advance  = int(_bg_state["debt"])
        _bg_state["debt"] -= frames_to_advance   # conserver la fraction pour le prochain appel

        if frames_to_advance <= 0:
            # Pas encore le moment d'avancer — retourner la frame en cache
            return _bg_state["cached"] if _bg_state["cached"] is not None \
                   else np.zeros((actual_h, actual_w, 3), dtype=np.uint8)

        # Limiter le saut max (protection contre les gels ponctuels)
        frames_to_advance = min(frames_to_advance, 10)

        # Sauter les frames intermédiaires avec grab() (sans décodage)
        for _ in range(frames_to_advance - 1):
            if not bg_cap.grab():
                bg_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Lire et décoder uniquement la frame cible
        ret, frm = bg_cap.read()
        if not ret:
            bg_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frm = bg_cap.read()
        if ret and frm is not None:
            _bg_state["cached"] = cv2.resize(frm, (actual_w, actual_h))

        return _bg_state["cached"] if _bg_state["cached"] is not None \
               else np.zeros((actual_h, actual_w, 3), dtype=np.uint8)

    # Résolution réduite pour segmentation + guided filter (4x moins de pixels)
    _SEG_W     = actual_w // 2
    _SEG_H     = actual_h // 2
    _SEG_EVERY = 2   # segmentation tous les N frames dans le worker

    # Résolution réduite pour le composite fond (4x moins d'ops float32)
    # La personne reste en pleine résolution via blendLinear final
    _COMP_W = actual_w // 2
    _COMP_H = actual_h // 2

    # Kernels morpho précalculés
    _k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    _k_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def _refine_mask(person_mask, small_frame):
        """Pipeline de raffinage à demi-résolution."""
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        person_mask = cv2.ximgproc.guidedFilter(
            guide=gray, src=person_mask, radius=6, eps=1e-4
        )
        person_mask = np.clip(person_mask, 0.0, 1.0)
        person_mask = 1.0 / (1.0 + np.exp(-12.0 * (person_mask - 0.5)))
        m_u8 = (person_mask * 255).astype(np.uint8)
        # MORPH_CLOSE bouche les trous + laisse un bord légèrement plus généreux
        # que l'érosion → petite marge naturelle contre le lag du thread ML
        m_u8 = cv2.morphologyEx(m_u8, cv2.MORPH_CLOSE, _k_close)
        return m_u8.astype(np.float32) / 255.0

    def _composite_fast(frame, seg_mask):
        """Composite : personne (pleine résolution) sur fond matrix transparent.
        Le fond est calculé à demi-résolution (4× moins d'ops float32) puis
        upscalé — la qualité de la personne n'est pas affectée.
        Transparence luma : noir → pièce réelle, vert vif → matrix opaque."""
        if seg_mask is None:
            return frame
        try:
            bg_raw = _get_bg_frame()   # déjà en cache à full-res

            # --- Composite fond à demi-résolution ---
            bg_half   = cv2.resize(bg_raw, (_COMP_W, _COMP_H), interpolation=cv2.INTER_AREA)
            room_half = cv2.resize(frame,  (_COMP_W, _COMP_H), interpolation=cv2.INTER_AREA)

            matrix = bg_half.astype(np.float32)  * (BG_BRIGHTNESS / 255.0)
            room   = room_half.astype(np.float32) * (1.0 / 255.0)

            luma = np.max(matrix, axis=2, keepdims=True) * BG_OPACITY
            bg   = np.clip(matrix * luma + room * (1.0 - luma), 0.0, 1.0)
            bg   = (bg * 255.0).astype(np.uint8)

            # Upscale fond composite → pleine résolution
            bg_full = cv2.resize(bg, (actual_w, actual_h), interpolation=cv2.INTER_LINEAR)

            # --- Blend final pleine résolution : personne (frame) + fond (bg_full) ---
            return cv2.blendLinear(frame, bg_full, seg_mask, 1.0 - seg_mask)
        except Exception as e:
            print(f"[WARN] composite : {e}")
            return frame

    # --- Thread de capture : lit la webcam en continu, garde la frame la plus récente ---
    # Élimine l'accumulation de buffer (OpenCV bufférise jusqu'à 4 frames par défaut)
    _cap_lock  = threading.Lock()
    _cap_frame = [None]
    _cap_alive = [True]

    def _cap_reader():
        """Thread dédié : vide le buffer webcam en permanence."""
        while _cap_alive[0]:
            ret, f = cap.read()
            if ret and f is not None:
                with _cap_lock:
                    _cap_frame[0] = f

    # --- État partagé thread ML ↔ boucle principale ---
    _ml       = {"frame": None, "mask": None, "landmarks": None, "result_id": 0}
    _ml_lock  = threading.Lock()
    _ml_event = threading.Event()
    _ml_alive = [True]

    def _ml_worker():
        """Thread de fond : détection landmarks + segmentation.
        Les landmarks sont compensés par vélocité dans le thread principal
        pour supprimer le délai perceptible lors des mouvements rapides."""
        seg_count = 0

        while _ml_alive[0]:
            if not _ml_event.wait(timeout=0.05):
                continue
            _ml_event.clear()
            with _ml_lock:
                frame = _ml["frame"]
            if frame is None:
                continue
            try:
                rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ts_ms = int((time.monotonic() - _seg_t0) * 1000)

                # Face landmarks (rapide, ~10-15 ms)
                result = face_mesh.process(rgb)

                # Segmentation tous les _SEG_EVERY frames (lente, ~40 ms)
                seg_count += 1
                new_mask = None
                if selfie_seg is not None and seg_count % _SEG_EVERY == 0:
                    small_rgb   = cv2.resize(rgb,   (_SEG_W, _SEG_H), interpolation=cv2.INTER_AREA)
                    small_frame = cv2.resize(frame, (_SEG_W, _SEG_H), interpolation=cv2.INTER_AREA)

                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=small_rgb)
                    seg    = selfie_seg.segment_for_video(mp_img, ts_ms)
                    mask   = np.squeeze(seg.confidence_masks[0].numpy_view()).astype(np.float32)
                    if mask.shape != (_SEG_H, _SEG_W):
                        mask = cv2.resize(mask, (_SEG_W, _SEG_H), interpolation=cv2.INTER_LINEAR)

                    mask     = _refine_mask(mask, small_frame)
                    mask     = cv2.resize(mask, (actual_w, actual_h), interpolation=cv2.INTER_LINEAR)
                    new_mask = cv2.GaussianBlur(mask, (3, 3), 0)

                with _ml_lock:
                    _ml["landmarks"] = result
                    _ml["result_id"] += 1   # signal : nouveau résultat disponible
                    if new_mask is not None:
                        _ml["mask"] = new_mask
                    _ml["frame"] = None  # frame consommée
            except Exception as e:
                print(f"[WARN] ml_worker : {e}")
                with _ml_lock:
                    _ml["frame"] = None  # libérer même en cas d'erreur (évite le gel)

    def run_loop(vcam=None):
        no_face         = 0
        last_safe_frame = None
        last_result_id  = -1   # dernier result_id traité

        # Démarrer le thread de capture (élimine le lag du buffer webcam)
        cap_reader = threading.Thread(target=_cap_reader, daemon=True)
        cap_reader.start()

        # Attendre la première frame webcam
        t0_wait = time.monotonic()
        while _cap_frame[0] is None:
            if time.monotonic() - t0_wait > 5.0:
                print("[ERREUR] Timeout — aucune frame webcam reçue")
                return
            time.sleep(0.01)

        # Démarrer le worker ML en arrière-plan
        worker = threading.Thread(target=_ml_worker, daemon=True)
        worker.start()
        print("[INFO] Live démarré — Échap pour quitter")

        while True:
            # Toujours la frame la plus récente, sans blocage
            with _cap_lock:
                frame = _cap_frame[0]

            # Envoyer la frame au worker ML si il est libre (non-bloquant)
            with _ml_lock:
                if _ml["frame"] is None:
                    _ml["frame"] = frame.copy()
                    _ml_event.set()

            # Lire les derniers résultats ML (landmarks + masque) sans attendre
            with _ml_lock:
                result    = _ml["landmarks"]
                seg_mask  = _ml["mask"]
                result_id = _ml["result_id"]

            # no_face ne change que quand le worker livre un NOUVEAU résultat
            # → évite que la boucle rapide accumule no_face avant que le worker
            #   ait eu le temps de détecter le retour du visage (~37 ms)
            new_result = (result_id != last_result_id)
            if new_result:
                last_result_id = result_id
                if result is not None and result.multi_face_landmarks:
                    no_face = 0
                else:
                    no_face += 1

            if result is not None and result.multi_face_landmarks:
                ema_pts["lm"] = result.multi_face_landmarks[0].landmark
                try:
                    frame = apply_mask(frame, mask, mask_kp, ema_pts)
                except Exception as e:
                    print(f"[WARN] apply_mask : {e}")
                frame = _composite_fast(frame, seg_mask)
                last_safe_frame = frame.copy()
            else:
                if no_face <= NO_FACE_GRACE and last_safe_frame is not None:
                    frame = last_safe_frame
                else:
                    ema_pts["lm"]      = None
                    ema_pts["smooth"]  = None
                    ema_pts["prev_raw"] = None   # réinitialiser la vélocité
                    ema_pts["velocity"] = None
                    last_safe_frame    = None
                    try:
                        if pip_cap is not None:
                            ret_pip, pip_frame = pip_cap.read()
                            if not ret_pip:
                                pip_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                ret_pip, pip_frame = pip_cap.read()
                            if ret_pip and pip_frame is not None:
                                frame = cv2.resize(pip_frame, (actual_w, actual_h))
                            else:
                                frame = np.zeros((actual_h, actual_w, 3), dtype=np.uint8)
                        else:
                            frame = np.zeros((actual_h, actual_w, 3), dtype=np.uint8)
                    except Exception as e:
                        print(f"[WARN] pipintro read : {e}")
                        frame = np.zeros((actual_h, actual_w, 3), dtype=np.uint8)

            cv2.imshow("Mask Live — Échap pour quitter", frame)

            if vcam is not None:
                rgb_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                vcam.send(rgb_out)
                vcam.sleep_until_next_frame()

            if cv2.waitKey(1) & 0xFF == 27:
                break

        # Arrêt propre des threads
        _ml_alive[0] = False
        _ml_event.set()
        worker.join(timeout=2.0)

        _cap_alive[0] = False
        cap_reader.join(timeout=1.0)

    try:
        if VIRTUAL_CAM:
            print("[INFO] Caméra virtuelle active — sélectionne 'OBS Virtual Camera' dans OBS")
            with pyvirtualcam.Camera(
                width=actual_w, height=actual_h, fps=FPS, backend="obs"
            ) as vcam:
                print(f"[INFO] Backend pyvirtualcam : {vcam.device}")
                run_loop(vcam)
        else:
            run_loop()
    finally:
        cap.release()
        if pip_cap is not None:
            pip_cap.release()
        if bg_cap is not None:
            bg_cap.release()
        if selfie_seg is not None:
            try:
                selfie_seg.close()
            except Exception:
                pass
        face_mesh.close()
        cv2.destroyAllWindows()



if __name__ == "__main__":
    main()
