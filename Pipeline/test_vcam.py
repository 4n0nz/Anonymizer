import pyvirtualcam
import numpy as np

with pyvirtualcam.Camera(width=1280, height=720, fps=30, backend="obs") as cam:
    print(f"Active : {cam.device}")
    print("Envoi de frames rouges... Ctrl+C pour arreter")
    while True:
        frame = np.zeros((720, 1280, 3), np.uint8)
        frame[:, :, 0] = 255  # rouge
        cam.send(frame)
        cam.sleep_until_next_frame()