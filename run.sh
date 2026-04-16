#!/bin/bash

set -euo pipefail

source mask_env/bin/activate

spinner() {
  local pid=$1
  local label="$2"
  local spin='|/-\'
  local i=0

  while kill -0 $pid 2>/dev/null; do
    i=$(( (i+1) %4 ))
    printf "\r[%c] %s..." "${spin:$i:1}" "$label"
    sleep 0.1
  done
}

run() {
  local label="$1"
  shift

  "$@" > /tmp/anonymizer_last.log 2>&1 &
  local pid=$!
  spinner $pid "$label"

  if wait $pid; then
    printf "\r[✓] %s Done            \n" "$label"
  else
    printf "\r[✗] %s ERREUR           \n" "$label"
    echo ""
    echo "=== Erreur dans : $* ==="
    cat /tmp/anonymizer_last.log
    echo "========================="
    exit 1
  fi
}

run "Mask               " python3 face_mask.py
run "Glitch             " python3 glitch.py
run "Voice Encryption   " python3 audio.py
run "Transitions        " python3 introNoutro.py
run "Background & Pip   " python3 backNpip.py
run "Intro & Outro added" python3 introEndOutro.py

echo ""
echo "[✓] Video Anonymizer    Done"

rm -f /tmp/anonymizer_last.log
rm -f output/.output1/* output/.output2/* output/.output3/* output/.output4/* 2>/dev/null || true
#rm input/vid*.mp4 2>/dev/null || true
