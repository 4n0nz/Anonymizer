#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

"""
run.py — Pipeline Video Anonymizer
Remplace run.bat (Windows) — cross-platform
Usage : python run.py   ou   python3 run.py
"""

import subprocess
import sys
import os
import re
import glob
import time
from datetime import datetime

# ======================
# CONFIGURATION
# ======================

# Tous les scripts du pipeline sont dans Pipeline/
PIPELINE_SUBDIR = "Pipeline"

STEPS = [
    ("Mask face",        f"{PIPELINE_SUBDIR}/face_mask.py"),
    ("Glitch / CRT",     f"{PIPELINE_SUBDIR}/glitch.py"),
    ("Voice Encryption", f"{PIPELINE_SUBDIR}/audio.py"),
    ("Transitions",      f"{PIPELINE_SUBDIR}/introNoutro.py"),
    ("Background & PIP", f"{PIPELINE_SUBDIR}/backNpip.py"),
    ("Intro & Outro",    f"{PIPELINE_SUBDIR}/introEndOutro.py"),
]

TEMP_DIRS = [
    "output/.output0",
    "output/.output1",
    "output/.output2",
    "output/.output3",
    "output/.output4",
    "output/.metadata",
]

# Caracteres spinner : version Unicode (Linux) ou ASCII (Windows CMD)
if sys.platform == "win32":
    SPINNER = ["|", "/", "-", "\\"]
    OK  = "[OK]"
    ERR = "[ERREUR]"
    SKP = "[SKIP]"
    BAR_FULL  = "#"
    BAR_EMPTY = "-"
else:
    SPINNER = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    OK  = "✓"
    ERR = "✗"
    SKP = "⊘"
    BAR_FULL  = "█"
    BAR_EMPTY = "░"

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.py")
LOGS_DIR    = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
RUN_LOG = os.path.join(LOGS_DIR, datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log")

# ======================
# PYTHON EXECUTABLE
# ======================

def find_python():
    candidates = [
        os.path.join(BASE_DIR, "mask_env", "bin", "python"),
        os.path.join(BASE_DIR, "mask_env", "Scripts", "python.exe"),
        os.path.join(BASE_DIR, "Win", "mask_env", "Scripts", "python.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return sys.executable

PYTHON      = find_python()
LABEL_WIDTH = max(len(label) for label, _ in STEPS)

# ======================
# CONFIG READ / WRITE
# ======================

MENU_PARAMS = [
    ("Pipeline",      []),   # special section — handled separately
    ("Detection",     [
        ("PIP_MAX_FACE_RATIO", float, "PIP threshold (face/frame ratio)"),
        ("MASK_SCALE",         float, "Mask size (1.0 = original)"),
    ]),
    ("Glitch / CRT",  [
        ("GLITCH_INTENSITY",   int,   "Glitch intensity"),
    ]),
    ("Audio",         [
        ("PITCH_UP",           float, "Pitch up"),
        ("PITCH_DOWN",         float, "Pitch down"),
    ]),
    ("Composition",   [
        ("SCREEN_RATIO",       float, "Screen width / background"),
        ("PIP_DISPLAY_RATIO",  float, "PIP width / background"),
    ]),
]


def cfg_read(key):
    with open(CONFIG_PATH) as f:
        m = re.search(rf'^{key}\s*=\s*([^\s#]+)', f.read(), re.MULTILINE)
    return m.group(1) if m else "?"


def cfg_write(key, value):
    with open(CONFIG_PATH) as f:
        content = f.read()
    content = re.sub(
        rf'^({key}\s*=\s*)([^\s#]+)',
        rf'\g<1>{value}',
        content, flags=re.MULTILINE
    )
    with open(CONFIG_PATH, "w") as f:
        f.write(content)


# ======================
# CONFIGURE
# ======================

SEP = "  " + "─" * 52


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def print_ascii():
    print()
    print("  ╔═╗ ╔╗╔ ╔═╗ ╔╗╔ ╦ ╦ ╔╦╗ ╦ ══╗ ╔══ ╔═╗")
    print("  ╠═╣ ║║║ ║ ║ ║║║ ╚╦╝ ║║║ ║  ╱  ╠═  ╠╦╝")
    print("  ╩ ╩ ╝╚╝ ╚═╝ ╝╚╝  ╩  ╩ ╩ ╩ ╚══ ╚══ ╩╚═")
    print("       Anonymous Video Pipeline")
    print()


def main_menu():
    """Menu principal — retourne 'pipeline', 'pipeline_nopip', 'live' ou 'swapface'."""
    clear()
    print_ascii()
    print(SEP)
    print("  WHAT YOU WANNA DO ?")
    print(SEP)
    print()
    print("    1. Edit Video With Pip")
    print("    2. Edit Video With No Pip")
    print("    3. Start Virtual Streaming Cam")
    print("    4. Swapface")
    print()
    while True:
        raw = input("  Choice [1/2/3/4] : ").strip()
        if raw == "1":
            return "pipeline"
        if raw == "2":
            return "pipeline_nopip"
        if raw == "3":
            return "live"
        if raw == "4":
            return "swapface"
        print(f"  {ERR} Invalid choice — type 1, 2, 3 or 4")


def launch_live():
    """Lance mask-live/live.py et attend qu'il se termine."""
    clear()
    print_ascii()
    print(SEP)
    print("  VIRTUAL STREAMING CAM")
    print(SEP)
    print()
    live_script = os.path.join(BASE_DIR, "mask-live", "live.py")
    if not os.path.isfile(live_script):
        print(f"  {ERR} Script introuvable : {live_script}")
        return
    print(f"  Lancement de live.py — Échap pour quitter")
    print()
    try:
        subprocess.call([PYTHON, live_script], cwd=BASE_DIR)
    except KeyboardInterrupt:
        pass


def launch_swapface():
    """Placeholder — sera implémenté plus tard (Roop / DeepFaceLive)."""
    clear()
    print_ascii()
    print(SEP)
    print("  SWAPFACE")
    print(SEP)
    print()
    print(f"  {SKP} Pas encore implémenté.")
    print()
    input("  Press ↵ to return ...")


def configure():
    """Linear one-by-one questionnaire. Returns active_steps set."""
    clear()
    print_ascii()
    print(SEP)
    print("  CONFIGURATION — press ↵ to keep the current value")
    print(SEP)
    print()

    # --- Parameters ---
    for _section, params in MENU_PARAMS[1:]:   # skip Pipeline section
        for key, typ, label in params:
            current = cfg_read(key)
            raw = input(f"  {label} [{current}] : ").strip()
            if raw:
                try:
                    val = typ(raw)
                    cfg_write(key, val)
                    print(f"  {OK} saved → {key} = {val}")
                except ValueError:
                    print(f"  {ERR} Invalid value — keeping {current}")

    # --- Pipeline steps ---
    print()
    print(SEP)
    print("  PIPELINE STEPS")
    print(SEP)
    for i, (label, _) in enumerate(STEPS):
        print(f"    {i+1}. {label}")
    print()
    raw = input("  Steps to run (e.g. 1 2 3 4 5 6) [↵ = all] : ").strip()
    if raw:
        try:
            active = set(int(x) - 1 for x in raw.split() if 1 <= int(x) <= len(STEPS))
        except ValueError:
            active = set(range(len(STEPS)))
    else:
        active = set(range(len(STEPS)))

    print()
    return active


# ======================
# UTILS
# ======================

def progress_bar(current, total, width=30):
    filled = int(width * current / total)
    bar = BAR_FULL * filled + BAR_EMPTY * (width - filled)
    return f"[{bar}] {current}/{total}"


def format_time(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def print_header(active_steps):
    print()
    print("  ╔═╗ ╔╗╔ ╔═╗ ╔╗╔ ╦ ╦ ╔╦╗ ╦ ══╗ ╔══ ╔═╗")
    print("  ╠═╣ ║║║ ║ ║ ║║║ ╚╦╝ ║║║ ║  ╱  ╠═  ╠╦╝")
    print("  ╩ ╩ ╝╚╝ ╚═╝ ╝╚╝  ╩  ╩ ╩ ╩ ╚══ ╚══ ╩╚═")
    print("       Anonymous Video Pipeline")
    print()
    print("=" * 54)
    print(f"  Scripts : {BASE_DIR}")
    print(f"  Python  : {PYTHON}")
    print(f"  Phases  : {len(active_steps)}/{len(STEPS)} actives")
    print(f"  Log     : {RUN_LOG}")
    print("=" * 54)
    print()


def print_footer(total_time):
    print()
    print("=" * 54)
    print(f"  {OK} Pipeline termine en {format_time(total_time)}")
    print("=" * 54)
    print()


# ======================
# RUNNER
# ======================

def run_step(label, script, step_num, total_steps):
    script_path = os.path.join(BASE_DIR, script)

    if not os.path.isfile(script_path):
        print(f"  {ERR} Script introuvable : {script}")
        return False

    start = time.time()

    with open(RUN_LOG, "a") as log_file:
        log_file.write(f"\n{'='*60}\n")
        log_file.write(f"[{datetime.now().strftime('%H:%M:%S')}] STEP {step_num}/{total_steps} — {label}\n")
        log_file.write(f"{'='*60}\n")
        log_file.flush()

    proc = subprocess.Popen(
        [PYTHON, script_path],
        cwd=BASE_DIR,
        stdout=open(RUN_LOG, "a"),
        stderr=subprocess.STDOUT,
        text=True
    )

    spin_i = 0
    while proc.poll() is None:
        elapsed = time.time() - start
        bar     = progress_bar(step_num - 1, total_steps)
        char    = SPINNER[spin_i % len(SPINNER)]
        print(f"\r\033[K  {bar}  [{step_num}/{total_steps}] {label:<{LABEL_WIDTH}}  {char}  {format_time(elapsed)}", end="", flush=True)
        spin_i += 1
        time.sleep(0.15)

    elapsed    = time.time() - start
    returncode = proc.returncode

    with open(RUN_LOG, "a") as log_file:
        status = "OK" if returncode == 0 else "ECHEC"
        log_file.write(f"[{datetime.now().strftime('%H:%M:%S')}] {status} — {label} ({format_time(elapsed)})\n")

    if returncode == 0:
        bar = progress_bar(step_num, total_steps)
        print(f"\r\033[K  {bar}  [{step_num}/{total_steps}] {label:<{LABEL_WIDTH}}  {OK}  ({format_time(elapsed)})")
        return True
    else:
        print(f"\r\033[K      {ERR}  ECHEC après {format_time(elapsed)}")
        print()
        print(f"  {'='*50}")
        print(f"  Erreur dans : {script}")
        print(f"  {'='*50}")
        try:
            with open(RUN_LOG) as f:
                lines = f.readlines()
            for line in lines[-30:]:
                print("  " + line, end="")
        except Exception:
            pass
        print(f"\n  {'='*50}")
        print(f"  Log complet : {RUN_LOG}")
        return False


# ======================
# NETTOYAGE
# ======================

def cleanup():
    print()
    print("  Nettoyage des dossiers temporaires...")
    removed = 0
    for d in TEMP_DIRS:
        pattern = os.path.join(BASE_DIR, d, "*")
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                removed += 1
            except Exception:
                pass
    print(f"  {removed} fichier(s) supprime(s).")


# ======================
# PRÉ-TRAITEMENT — downscale les vidéos source trop grandes
# ======================

def _ffprobe_size(video_path):
    """Retourne (width, height) ou (0, 0) si échec."""
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0", video_path],
            stderr=subprocess.DEVNULL, timeout=10
        ).decode().strip()
        w, h = map(int, out.split(","))
        return w, h
    except Exception:
        return 0, 0


def preprocess_inputs():
    """Downscale les vidéos de input/ qui dépassent PREPROCESS_MAX_WIDTH.
    Modifie les fichiers en place (avec backup .orig si pas déjà fait)."""
    try:
        import config as C
    except Exception:
        return

    max_w = getattr(C, "PREPROCESS_MAX_WIDTH", 0)
    if not max_w or max_w <= 0:
        return  # désactivé

    input_dir = os.path.join(BASE_DIR, "input")
    if not os.path.isdir(input_dir):
        return

    videos = [
        os.path.join(input_dir, f) for f in os.listdir(input_dir)
        if f.lower().endswith(C.VIDEO_EXTENSIONS) and not f.endswith(".orig.mp4")
    ]
    if not videos:
        return

    to_process = []
    for v in videos:
        w, h = _ffprobe_size(v)
        if w > max_w:
            to_process.append((v, w, h))

    if not to_process:
        print(f"  {OK} Toutes les vidéos sont ≤ {max_w}px de large, pas de pré-traitement")
        return

    print()
    print(SEP)
    print(f"  PRÉ-TRAITEMENT — downscale à {max_w}px max")
    print(SEP)

    for v, w, h in to_process:
        new_h = int(h * max_w / w)
        new_h = new_h - (new_h % 2)  # libx264 exige paire
        backup = v + ".orig"
        tmp = v + ".tmp.mp4"

        print(f"  {os.path.basename(v)} : {w}x{h} → {max_w}x{new_h}")

        cmd = [
            "ffmpeg", "-y", "-i", v,
            "-vf", f"scale={max_w}:{new_h}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "copy",
            tmp
        ]
        try:
            subprocess.run(cmd, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Backup de l'original (uniquement si pas déjà fait)
            if not os.path.exists(backup):
                os.rename(v, backup)
            else:
                os.remove(v)
            os.rename(tmp, v)
            print(f"    {OK} downscaled (original sauvé : .orig)")
        except subprocess.CalledProcessError:
            print(f"    {ERR} échec — vidéo intacte")
            if os.path.exists(tmp):
                os.remove(tmp)


# ======================
# KEEP AWAKE — empêche la mise en veille pendant le pipeline
# ======================

def keep_awake_start():
    """Empêche écran + machine de tomber en veille. Renvoie un handle à passer à stop()."""
    if sys.platform == "win32":
        import ctypes
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        ES_CONTINUOUS       = 0x80000000
        ES_SYSTEM_REQUIRED  = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        return "win32"
    elif sys.platform == "darwin":
        # macOS : caffeinate en arrière-plan
        return subprocess.Popen(["caffeinate", "-dimsu", "-w", str(os.getpid())])
    else:
        # Linux : systemd-inhibit si disponible
        try:
            return subprocess.Popen([
                "systemd-inhibit", "--what=idle:sleep:handle-lid-switch",
                "--why=Anonymizer pipeline running",
                "--mode=block", "sleep", "infinity"
            ])
        except FileNotFoundError:
            return None


def keep_awake_stop(handle):
    if handle == "win32":
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    elif hasattr(handle, "terminate"):
        try:
            handle.terminate()
        except Exception:
            pass


# ======================
# MAIN
# ======================

def main():
    # Menu principal
    choice = main_menu()

    if choice == "live":
        launch_live()
        return

    if choice == "swapface":
        launch_swapface()
        return

    # Mode "Edit Video With No Pip" → désactive l'extraction PIP temporairement
    pip_was = None
    if choice == "pipeline_nopip":
        pip_was = cfg_read("PIP_EXTRACT")
        cfg_write("PIP_EXTRACT", "False")
        print(f"  {OK} PIP_EXTRACT temporairement désactivé pour ce run")

    # Pré-traitement : downscale les vidéos source trop grandes
    preprocess_inputs()

    # choice == "pipeline" ou "pipeline_nopip"
    active_steps = configure()

    clear()
    print_header(active_steps)

    pipeline_start = time.time()
    total_active   = len(active_steps)
    step_counter   = 0

    for i, (label, script) in enumerate(STEPS):
        if i not in active_steps:
            print(f"  {'░'*30}  [{i+1}/{len(STEPS)}] {label:<{LABEL_WIDTH}}  {SKP}")
            continue

        step_counter += 1
        success = run_step(label, script, step_counter, total_active)

        if not success:
            print()
            print(f"  Pipeline arrete a l'etape {i+1}/{len(STEPS)} — {label}")
            print(f"  Les etapes suivantes n'ont pas ete executees.")
            sys.exit(1)

    cleanup()
    print_footer(time.time() - pipeline_start)
    print(f"  Log sauvegarde : {RUN_LOG}")

    # Restaure PIP_EXTRACT si on l'avait désactivé
    if pip_was is not None:
        cfg_write("PIP_EXTRACT", pip_was)
        print(f"  {OK} PIP_EXTRACT restauré → {pip_was}")


def restore_terminal():
    if sys.platform != "win32":
        subprocess.call(["stty", "sane"], stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    awake_handle = keep_awake_start()
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Pipeline interrompu par l'utilisateur (Ctrl+C)")
    finally:
        keep_awake_stop(awake_handle)
        restore_terminal()
