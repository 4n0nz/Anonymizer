#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py — Pipeline Video Anonymizer
Remplace run.bat (Windows) — cross-platform
Usage : python run.py   ou   python3 run.py
"""

import subprocess
import sys
import os
import glob
import time
import threading
from datetime import datetime

# ======================
# CONFIGURATION
# ======================

STEPS = [
    ("Mask face",        "face_mask.py"),
    ("Glitch / CRT",     "glitch.py"),
    ("Voice Encryption", "audio.py"),
    ("Transitions",      "introNoutro.py"),
    ("Background & PIP", "backNpip.py"),
    ("Intro & Outro",    "introEndOutro.py"),
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
    BAR_FULL  = "#"
    BAR_EMPTY = "-"
else:
    SPINNER = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    OK  = "✓"
    ERR = "✗"
    BAR_FULL  = "█"
    BAR_EMPTY = "░"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
RUN_LOG  = os.path.join(LOGS_DIR, datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log")

# ======================
# PYTHON EXECUTABLE
# ======================

def find_python():
    """Utilise le Python du virtualenv mask_env si disponible,
    sinon le Python courant (sys.executable)."""
    candidates = [
        os.path.join(BASE_DIR, "mask_env", "bin", "python"),         # Linux / Mac
        os.path.join(BASE_DIR, "mask_env", "Scripts", "python.exe"), # Windows
        os.path.join(BASE_DIR, "Win",      "mask_env", "Scripts", "python.exe"), # Win/mask_env
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return sys.executable  # fallback : Python courant

PYTHON      = find_python()
LABEL_WIDTH = max(len(label) for label, _ in STEPS)

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


def print_header():
    print()
    print("  ╔═╗ ╔╗╔ ╔═╗ ╔╗╔ ╦ ╦ ╔╦╗ ╦ ══╗ ╔══ ╔═╗")
    print("  ╠═╣ ║║║ ║ ║ ║║║ ╚╦╝ ║║║ ║  ╱  ╠═  ╠╦╝")
    print("  ╩ ╩ ╝╚╝ ╚═╝ ╝╚╝  ╩  ╩ ╩ ╩ ╚══ ╚══ ╩╚═")
    print("       Anonymous Video Pipeline")
    print()
    print("=" * 54)
    print(f"  Scripts : {BASE_DIR}")
    print(f"  Python  : {PYTHON}")
    print(f"  Phases  : {len(STEPS)}")
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
    """Lance un script Python, affiche un spinner + chrono.
    Retourne True si succes, False si erreur."""

    script_path = os.path.join(BASE_DIR, script)

    if not os.path.isfile(script_path):
        print(f"  {ERR} Script introuvable : {script}")
        return False

    # Lancement du process
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

    # Spinner — meme ligne que le resultat final (pas de print initial)
    spin_i = 0
    while proc.poll() is None:
        elapsed = time.time() - start
        bar     = progress_bar(step_num - 1, total_steps)
        char    = SPINNER[spin_i % len(SPINNER)]
        print(f"\r\033[K  {bar}  [{step_num}/{total_steps}] {label:<{LABEL_WIDTH}}  {char}  {format_time(elapsed)}", end="", flush=True)
        spin_i += 1
        time.sleep(0.15)

    elapsed   = time.time() - start
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
        # Affiche les dernieres lignes du log
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
# MAIN
# ======================

def main():
    print_header()

    pipeline_start = time.time()
    total = len(STEPS)

    for i, (label, script) in enumerate(STEPS, 1):
        success = run_step(label, script, i, total)

        if not success:
            print()
            print(f"  Pipeline arrete a l'etape {i}/{total} — {label}")
            print(f"  Les etapes suivantes n'ont pas ete executees.")
            sys.exit(1)

    cleanup()
    print_footer(time.time() - pipeline_start)
    print(f"  Log sauvegarde : {RUN_LOG}")


def restore_terminal():
    """Restaure les parametres du terminal sur Linux/Mac (apres tqdm/cv2)."""
    if sys.platform != "win32":
        subprocess.call(["stty", "sane"], stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Pipeline interrompu par l'utilisateur (Ctrl+C)")
    finally:
        restore_terminal()
