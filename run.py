#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py — Pipeline Video Anonymizer
Remplace run.sh (Linux/WSL) et run.bat (Windows)
Usage : python run.py   ou   python3 run.py
"""

import subprocess
import sys
import os
import glob
import time
import threading

# ======================
# CONFIGURATION
# ======================

STEPS = [
    ("Masque visage",    "face_mask.py"),
    ("Glitch / CRT",     "glitch.py"),
    ("Chiffrement voix", "audio.py"),
    ("Transitions",      "introNoutro.py"),
    ("Background & PIP", "backNpip.py"),
    ("Intro & Outro",    "introEndOutro.py"),
]

TEMP_DIRS = [
    "output/.output1",
    "output/.output2",
    "output/.output3",
    "output/.output4",
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

PYTHON = find_python()

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
    print("=" * 54)
    print("         Video Anonymizer — Pipeline")
    print("=" * 54)
    print(f"  Scripts : {BASE_DIR}")
    print(f"  Python  : {PYTHON}")
    print(f"  Etapes  : {len(STEPS)}")
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

    # Ligne de debut
    bar = progress_bar(step_num - 1, total_steps)
    print(f"  {bar}  [{step_num}/{total_steps}] {label}")

    # Lancement du process
    log_path = os.path.join(BASE_DIR, ".pipeline.log")
    start    = time.time()

    proc = subprocess.Popen(
        [PYTHON, script_path],
        cwd=BASE_DIR,
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        text=True
    )

    # Spinner dans le thread principal pendant que le script tourne
    spin_i = 0
    while proc.poll() is None:
        elapsed = time.time() - start
        char    = SPINNER[spin_i % len(SPINNER)]
        print(f"\r      {char}  En cours...  {format_time(elapsed)}", end="", flush=True)
        spin_i += 1
        time.sleep(0.15)

    elapsed   = time.time() - start
    returncode = proc.returncode

    if returncode == 0:
        bar = progress_bar(step_num, total_steps)
        print(f"\r  {bar}  [{step_num}/{total_steps}] {label}  {OK}  ({format_time(elapsed)})")
        return True
    else:
        print(f"\r      {ERR}  ECHEC après {format_time(elapsed)}                    ")
        print()
        print(f"  {'='*50}")
        print(f"  Erreur dans : {script}")
        print(f"  {'='*50}")
        # Affiche les dernieres lignes du log
        try:
            with open(log_path) as f:
                lines = f.readlines()
            for line in lines[-30:]:
                print("  " + line, end="")
        except Exception:
            pass
        print(f"\n  {'='*50}")
        print(f"  Log complet : {log_path}")
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

    # Supprime le log temporaire si tout s'est bien passe
    log_path = os.path.join(BASE_DIR, ".pipeline.log")
    if os.path.exists(log_path):
        os.remove(log_path)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Pipeline interrompu par l'utilisateur (Ctrl+C)")
        sys.exit(0)
