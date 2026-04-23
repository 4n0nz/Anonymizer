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
import re
import glob
import time
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
# MENU
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


def show_main_menu(active_steps):
    while True:
        clear()
        print_ascii()
        print(SEP)
        print("  CONFIGURATION — Anonymous Video Pipeline")
        print(SEP)
        print()

        # [P] Pipeline — étapes actives
        steps_display = "  ".join(
            f"{i+1}:{label[:3]}" for i, (label, _) in enumerate(STEPS)
            if i in active_steps
        )
        skipped = [str(i+1) for i in range(len(STEPS)) if i not in active_steps]
        skip_str = f"  (skip: {', '.join(skipped)})" if skipped else ""
        print(f"  [P] Pipeline        {steps_display}{skip_str}")
        print()

        # Sections paramètres
        for idx, (section, params) in enumerate(MENU_PARAMS[1:], 1):
            print(f"  [{idx}] {section}")
            for key, _, label in params:
                val = cfg_read(key)
                print(f"      {label:<35} = {val}")
            print()

        print(SEP)
        print(f"  [↵]  Run pipeline")
        print(f"  [q]  Quit")
        print(SEP)
        print()

        choice = input("  Choice : ").strip().lower()

        if choice == "":
            return active_steps
        elif choice == "q":
            sys.exit(0)
        elif choice == "p":
            active_steps = menu_pipeline(active_steps)
        else:
            try:
                idx = int(choice)
                if 1 <= idx <= len(MENU_PARAMS) - 1:
                    menu_section(MENU_PARAMS[idx])
            except ValueError:
                pass


def menu_pipeline(active_steps):
    clear()
    print_ascii()
    print(SEP)
    print("  PIPELINE — Active steps")
    print(SEP)
    print()
    for i, (label, _) in enumerate(STEPS):
        status = OK if i in active_steps else SKP
        print(f"  [{status}] {i+1}. {label}")
    print()
    raw = input("  Steps to enable (e.g. 1 2 3 4 5 6) [↵ = all] : ").strip()
    if raw:
        try:
            return set(int(x) - 1 for x in raw.split() if 1 <= int(x) <= len(STEPS))
        except ValueError:
            pass
    return set(range(len(STEPS)))


def menu_section(section_data):
    section_name, params = section_data
    clear()
    print_ascii()
    print(SEP)
    print(f"  {section_name.upper()}")
    print(SEP)
    print()
    print("  Press ↵ to keep current value.")
    print()
    for key, typ, label in params:
        current = cfg_read(key)
        raw = input(f"  {label} [{current}] : ").strip()
        if raw:
            try:
                val = typ(raw)
                cfg_write(key, val)
                print(f"  {OK} {key} = {val}")
            except ValueError:
                print(f"  {ERR} Invalid value — ignored")
    print()
    input(f"  [↵] Back to menu...")


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
# MAIN
# ======================

def main():
    # Menu de configuration
    active_steps = show_main_menu(set(range(len(STEPS))))

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


def restore_terminal():
    if sys.platform != "win32":
        subprocess.call(["stty", "sane"], stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Pipeline interrompu par l'utilisateur (Ctrl+C)")
    finally:
        restore_terminal()
