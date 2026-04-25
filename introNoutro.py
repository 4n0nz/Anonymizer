#!/usr/bin/env python3
import os
import subprocess
import sys
import config as C

INPUT_DIR        = C.DIRS["output2"]
OUTPUT_DIR       = C.DIRS["output3"]
INTRO            = C.PIP_INTRO
OUTRO            = C.PIP_OUTRO
VIDEO_EXTENSIONS = C.VIDEO_EXTENSIONS
SCREEN_DELAY     = C.SCREEN_DELAY  # secondes supprimées au début du screen

def get_resolution(video):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0", video
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    width, height = map(int, result.stdout.strip().split(","))
    return width, height

def has_audio(video):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "csv=p=0", video
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return bool(result.stdout.strip())

def main():
    if not os.path.isfile(INTRO) or not os.path.isfile(OUTRO):
        print("Fichiers intro ou outro introuvables")
        sys.exit(1)
    if not os.path.isdir(INPUT_DIR):
        print("Dossier input introuvable")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    videos = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(VIDEO_EXTENSIONS)]
    if not videos:
        print("Aucune vidéo trouvée")
        sys.exit(0)

    for video in videos:
        input_video  = os.path.join(INPUT_DIR, video)
        output_video = os.path.join(OUTPUT_DIR, video)
        is_screen    = video.endswith("_screen.mp4")
        print(f"Traitement : {video}" + (" [screen -3s]" if is_screen else ""))

        width, height = get_resolution(input_video)

        audio = has_audio(input_video)

        if is_screen and SCREEN_DELAY > 0:
            # 1) Trim les N premières secondes du screen
            # 2) Ensuite seulement, pipintro est ajouté devant
            if audio:
                filter_complex = (
                    f"[0:v]scale={width}:{height},setsar=1[intro];"
                    f"[1:v]trim=start={SCREEN_DELAY},setpts=PTS-STARTPTS,"
                    f"scale={width}:{height},setsar=1[main];"
                    f"[1:a]atrim=start={SCREEN_DELAY},asetpts=PTS-STARTPTS[maina];"
                    f"[2:v]scale={width}:{height},setsar=1[outro];"
                    "[intro][0:a][main][maina][outro][2:a]concat=n=3:v=1:a=1[outv][outa]"
                )
            else:
                # Screen sans audio (retiré dans audio.py)
                filter_complex = (
                    f"[0:v]scale={width}:{height},setsar=1[intro];"
                    f"[1:v]trim=start={SCREEN_DELAY},setpts=PTS-STARTPTS,"
                    f"scale={width}:{height},setsar=1[main];"
                    f"[2:v]scale={width}:{height},setsar=1[outro];"
                    "[intro][main][outro]concat=n=3:v=1:a=0[outv]"
                )
        else:
            if audio:
                filter_complex = (
                    f"[0:v]scale={width}:{height},setsar=1[intro];"
                    f"[1:v]scale={width}:{height},setsar=1[main];"
                    f"[2:v]scale={width}:{height},setsar=1[outro];"
                    "[intro][0:a][main][1:a][outro][2:a]concat=n=3:v=1:a=1[outv][outa]"
                )
            else:
                filter_complex = (
                    f"[0:v]scale={width}:{height},setsar=1[intro];"
                    f"[1:v]scale={width}:{height},setsar=1[main];"
                    f"[2:v]scale={width}:{height},setsar=1[outro];"
                    "[intro][main][outro]concat=n=3:v=1:a=0[outv]"
                )

        maps = ["-map", "[outv]"]
        if audio:
            maps += ["-map", "[outa]", "-c:a", "aac"]
        else:
            maps += ["-an"]

        cmd = [
            "ffmpeg", "-y",
            "-i", INTRO,
            "-i", input_video,
            "-i", OUTRO,
            "-filter_complex", filter_complex,
            *maps,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-movflags", "+faststart",
            output_video
        ]
        subprocess.run(cmd, check=True)

    print("Terminé.")

if __name__ == "__main__":
    main()
