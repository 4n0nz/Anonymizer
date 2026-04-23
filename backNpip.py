#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backNpip.py — Etape 5 : Composition background + screen + pip → 1 seul fichier final

  Paire _screen / _pip  → background + screen (gauche) + pip (sur le carré noir)
  Vidéo standalone       → background + vidéo centrée
  Toutes les sources sont concaténées en UN seul fichier de sortie.
"""

import os
import json
import subprocess
import sys
import config as C

# ======================
# CONFIG
# ======================
INPUT_DIR    = C.DIRS["output3"]
OUTPUT_DIR   = C.DIRS["output4"]
META_DIR     = C.DIRS["metadata"]
BACKGROUND   = C.BACKGROUND
MARGIN       = C.MARGIN
AUDIO_FADE   = C.AUDIO_FADE
PIP_START    = 2   # secondes avant que le pip apparaisse
SCREEN_START = 5   # secondes avant que le screen apparaisse

SCREEN_RATIO     = 0.854  # largeur screen / largeur background
PIP_DISPLAY_RATIO = 0.416  # largeur PIP / largeur background (indépendant de la bbox)
PIP_BORDER        = 4     # bordure blanche autour du PIP (px)
OUTPUT_NAME       = "output.mp4"


# ======================
# UTILS FFPROBE
# ======================

def ffprobe_json(path):
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams", path
    ]
    return json.loads(subprocess.check_output(cmd).decode())


def get_duration(path):
    return float(ffprobe_json(path)["format"]["duration"])


def get_resolution(path):
    for s in ffprobe_json(path)["streams"]:
        if s.get("codec_type") == "video":
            return int(s["width"]), int(s["height"])
    raise RuntimeError(f"Résolution introuvable : {path}")


def has_audio(path):
    for s in ffprobe_json(path)["streams"]:
        if s.get("codec_type") == "audio":
            return True
    return False


def even(n):
    return n - (n % 2)


def load_meta(base, script_dir):
    """Charge le JSON de position PIP pour une source donnée."""
    meta_path = os.path.join(script_dir, META_DIR, base + "_pip.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            return json.load(f)
    return None


# ======================
# COMPOSITION SCREEN + PIP
# ======================

def compose_screen_pip(bg, screen, pip_vid, meta, out_tmp):
    """
    3 couches :
      [0] background  — plein frame, boucle sur la durée
      [1] _screen     — 65% gauche, centré verticalement
      [2] _pip        — positionné exactement sur le carré noir, bordure blanche
    """
    bg_w,  bg_h  = get_resolution(bg)
    scr_w, scr_h = get_resolution(screen)
    dur          = max(get_duration(screen), get_duration(pip_vid))

    # --- Screen ---
    s_w = even(int(bg_w * SCREEN_RATIO))
    s_h = even(int(s_w * scr_h / scr_w))
    s_x = 25
    s_y = 25

    # --- PIP aligné sur la zone cropée pour couvrir 100% le personnage ---
    scale_x = s_w / scr_w
    scale_y = s_h / scr_h

    b = PIP_BORDER

    # Coordonnées metadata en espace 1280px → espace display
    masked_w = min(scr_w, C.MAX_WIDTH)
    masked_h = int(scr_h * masked_w / scr_w)

    # Coin haut-gauche du crop dans l'espace display
    crop_x = s_x + int(meta["x"] * s_w / masked_w)
    crop_y = s_y + int(meta["y"] * s_h / masked_h)

    # Taille du crop dans l'espace display
    crop_display_w = int(meta["w"] * s_w / masked_w)
    crop_display_h = int(meta["h"] * s_h / masked_h)

    # PIP au moins aussi grand que le crop, avec marge de 20%
    p_w = even(max(int(bg_w * PIP_DISPLAY_RATIO), int(crop_display_w * 1.2)))
    p_h = even(int(p_w * 9 / 16))  # toujours 16:9

    # Aligner le coin haut-gauche du PIP sur le coin haut-gauche du crop
    p_x = crop_x - b
    p_y = crop_y - b

    filter_complex = (
        f"[0:v]loop=-1:size=32767,trim=0:{dur},setpts=PTS-STARTPTS[bg];"
        f"[1:v]scale={s_w}:{s_h},setsar=1[scr];"
        f"[2:v]scale={p_w}:{p_h},setsar=1,"
        f"pad={p_w + b*2}:{p_h + b*2}:{b}:{b}:0x00ff00[pip];"
        f"[bg][scr]overlay={s_x}:{s_y}:enable='gte(t,{SCREEN_START})'[tmp];"
        f"[tmp][pip]overlay={p_x - b}:{p_y - b}:enable='gte(t,{PIP_START})'[outv]"
    )

    audio_scr = has_audio(screen)
    audio_pip = has_audio(pip_vid)

    if audio_scr and audio_pip:
        filter_complex += f";[1:a][2:a]amix=inputs=2:normalize=1[aout]"
        audio_args = ["-map", "[aout]", "-c:a", "aac"]
    elif audio_scr:
        audio_args = ["-map", "1:a", "-c:a", "aac"]
    elif audio_pip:
        audio_args = ["-map", "2:a", "-c:a", "aac"]
    else:
        audio_args = ["-an"]

    cmd = [
        "ffmpeg", "-y",
        "-i", bg, "-i", screen, "-i", pip_vid,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        *audio_args,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        out_tmp
    ]

    print(f"  [COMPOSE] screen+pip → {os.path.basename(out_tmp)}")
    subprocess.run(cmd, check=True)


# ======================
# COMPOSITION STANDALONE
# ======================

def compose_standalone(bg, src, out_tmp):
    """
    2 couches :
      [0] background  — plein frame, boucle
      [1] vidéo       — centrée sur le fond
    """
    bg_w, bg_h = get_resolution(bg)
    src_w, src_h = get_resolution(src)
    dur = get_duration(src)

    s_w = even(int(bg_w * SCREEN_RATIO))
    s_h = even(int(s_w * src_h / src_w))
    s_x = 25
    s_y = 25

    filter_complex = (
        f"[0:v]loop=-1:size=32767,trim=0:{dur},setpts=PTS-STARTPTS[bg];"
        f"[1:v]scale={s_w}:{s_h},setsar=1[src];"
        f"[bg][src]overlay={s_x}:{s_y}[outv]"
    )

    audio_args = (["-map", "1:a", "-c:a", "aac"] if has_audio(src) else ["-an"])

    cmd = [
        "ffmpeg", "-y",
        "-i", bg, "-i", src,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        *audio_args,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        out_tmp
    ]

    print(f"  [STANDALONE] → {os.path.basename(out_tmp)}")
    subprocess.run(cmd, check=True)


# ======================
# CONCATENATION FINALE
# ======================

def concatenate(segments, out_final):
    """Concatène tous les segments en un seul fichier."""
    filelist = out_final + ".txt"
    with open(filelist, "w") as f:
        for s in segments:
            f.write(f"file '{s}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", filelist,
        "-c", "copy",
        out_final
    ], check=True)

    os.remove(filelist)
    print(f"  [FINAL] → {out_final}")


# ======================
# MAIN
# ======================

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bg         = os.path.join(script_dir, BACKGROUND)
    input_dir  = os.path.join(script_dir, INPUT_DIR)
    output_dir = os.path.join(script_dir, OUTPUT_DIR)
    tmp_dir    = os.path.join(output_dir, ".tmp")

    if not os.path.isfile(bg):
        print(f"ERREUR : background introuvable → {bg}")
        sys.exit(1)
    if not os.path.isdir(input_dir):
        print(f"ERREUR : dossier input introuvable → {input_dir}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(tmp_dir,    exist_ok=True)

    files = sorted(f for f in os.listdir(input_dir) if f.lower().endswith(".mp4"))
    if not files:
        print("ERREUR : aucune vidéo dans", INPUT_DIR)
        sys.exit(1)

    screen_files = {f for f in files if f.endswith("_screen.mp4")}
    pip_files    = {f for f in files if f.endswith("_pip.mp4")}
    standalone   = [f for f in files if f not in screen_files and f not in pip_files]

    segments = []

    # --- Paires screen + pip ---
    for screen_f in sorted(screen_files):
        base  = screen_f[: -len("_screen.mp4")]
        pip_f = base + "_pip.mp4"

        screen_path = os.path.join(input_dir, screen_f)
        pip_path    = os.path.join(input_dir, pip_f)
        tmp_path    = os.path.join(tmp_dir, base + ".mp4")

        meta = load_meta(base, script_dir)

        if pip_f not in pip_files or meta is None:
            print(f"  [WARN] PIP ou metadata manquant pour {base} → standalone")
            compose_standalone(bg, screen_path, tmp_path)
        else:
            compose_screen_pip(bg, screen_path, pip_path, meta, tmp_path)

        segments.append(tmp_path)

    # --- Vidéos standalone ---
    for f in standalone:
        tmp_path = os.path.join(tmp_dir, f)
        compose_standalone(bg, os.path.join(input_dir, f), tmp_path)
        segments.append(tmp_path)

    if not segments:
        print("ERREUR : aucun segment produit")
        sys.exit(1)

    # --- Concaténation finale ---
    out_final = os.path.join(output_dir, OUTPUT_NAME)

    if len(segments) == 1:
        # Un seul segment : copie directe sans re-encode
        import shutil
        shutil.move(segments[0], out_final)
    else:
        concatenate(segments, out_final)
        # Nettoyage des fichiers temporaires
        for s in segments:
            if os.path.exists(s):
                os.remove(s)

    # Supprime le dossier tmp s'il est vide
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    print(f"\nTerminé → {out_final}")


if __name__ == "__main__":
    main()
