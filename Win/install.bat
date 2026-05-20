@echo off

set PYTHONPATH=
set PYTHONHOME=

chcp 65001 >nul
echo === Installation environnement Anonymizer (Windows) ===
echo.

:: Verification Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python introuvable.
    echo Installez Python depuis https://www.python.org/downloads/
    echo Choisissez Windows installer 64-bit et cochez Add Python to PATH.
    pause
    exit /b 1
)
echo [OK] Python detecte :
python --version

:: Verification ffmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [ATTENTION] ffmpeg introuvable dans le PATH.
    echo Installez ffmpeg depuis https://ffmpeg.org/download.html
    pause
) else (
    echo [OK] ffmpeg detecte
)

:: Creation du virtualenv (si absent)
if not exist "..\mask_env\Scripts\python.exe" (
    echo.
    echo Creation du virtualenv...
    python -m venv "..\mask_env"
    if errorlevel 1 ( echo [ERREUR] Creation virtualenv echouee & pause & exit /b 1 )
    echo [OK] Virtualenv cree
) else (
    echo [OK] Virtualenv existant
)

:: Activation
call "..\mask_env\Scripts\activate.bat"

:: Mise a jour pip
echo.
echo Mise a jour pip...
python -m pip install --upgrade pip wheel setuptools

:: Installation dependances Python
echo.
echo Installation des dependances Python...
python -m pip install -r "..\requirements.txt"
if errorlevel 1 ( echo [ERREUR] Installation des dependances echouee & pause & exit /b 1 )

:: Telechargement du modele MediaPipe FaceLandmarker
echo.
echo Telechargement du modele MediaPipe...
python -c "import os,urllib.request; d=os.path.join('..','resources','face_landmarker.task'); os.makedirs(os.path.dirname(d),exist_ok=True); urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task',d) if not os.path.exists(d) else None; print('[OK] face_landmarker.task')"
if errorlevel 1 ( echo [ATTENTION] Telechargement echoue - sera retente au premier lancement )

:: Verification finale
echo.
echo Verification des imports...
python -c "import cv2; print('[OK] OpenCV', cv2.__version__)"
if errorlevel 1 ( echo [ERREUR] Un import a echoue & pause & exit /b 1 )

:: Extraction des ressources (les .7z sont conserves pour reinstall ulterieur)
if exist "..\resources\resources.7z.001" (
    echo.
    echo Extraction des ressources...
    "C:\Program Files\7-Zip\7z.exe" x "..\resources\resources.7z.001" -o"..\resources" -y
    if errorlevel 1 ( echo [ERREUR] Extraction echouee & pause & exit /b 1 )
    echo [OK] Ressources extraites (archives .7z conservees)
)

echo.
echo ================================
echo [OK] Installation terminee !
echo ================================
echo.
echo Pour utiliser :
echo   1. Ajoutez vos videos dans le dossier input\
echo   2. Double-cliquez sur run.bat
echo.
pause
