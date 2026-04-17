@echo off
chcp 65001 >nul
echo === Installation environnement Anonymizer (Windows) ===
echo.

:: Verification Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python introuvable.
    echo Installez Python depuis https://www.python.org/downloads/
    echo Cochez bien "Add Python to PATH" lors de l'installation.
    pause & exit /b 1
)
echo [OK] Python detecte :
python --version

:: Verification pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] pip introuvable.
    pause & exit /b 1
)
echo [OK] pip detecte

:: Verification ffmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [ATTENTION] ffmpeg introuvable dans le PATH.
    echo Installez ffmpeg depuis https://ffmpeg.org/download.html
    echo et ajoutez le dossier bin\ a votre variable d'environnement PATH.
    echo.
    echo Continuez quand meme ? (Les scripts auront besoin de ffmpeg pour fonctionner)
    pause
) else (
    echo [OK] ffmpeg detecte
)

:: Creation du virtualenv
if not exist mask_env (
    echo.
    echo Creation du virtualenv...
    python -m venv mask_env
    if errorlevel 1 ( echo [ERREUR] Creation virtualenv echouee & pause & exit /b 1 )
)
echo [OK] Virtualenv pret

:: Activation
call mask_env\Scripts\activate.bat

:: Mise a jour pip
echo.
echo Mise a jour pip...
pip install --upgrade pip wheel setuptools

:: Installation dependances Python
echo.
echo Installation des dependances Python...
pip install numpy opencv-python mediapipe tqdm moviepy
if errorlevel 1 ( echo [ERREUR] Installation des dependances echouee & pause & exit /b 1 )

:: Verification finale
echo.
echo Verification des imports...
python -c "import cv2, numpy, mediapipe, tqdm; print('[OK] OpenCV :', cv2.__version__); print('[OK] NumPy :', numpy.__version__); print('[OK] MediaPipe OK'); print('[OK] tqdm OK')"
if errorlevel 1 ( echo [ERREUR] Un import a echoue & pause & exit /b 1 )

:: Extraction des ressources (7-Zip) — dossier parent
if exist "..\resources\resources.7z.001" (
    echo.
    echo Extraction des ressources...
    where 7z >nul 2>&1
    if errorlevel 1 (
        echo [ATTENTION] 7-Zip introuvable. Installez-le depuis https://www.7-zip.org/
        echo et ajoutez-le au PATH, puis relancez ce script.
    ) else (
        7z x "..\resources\resources.7z.001" -o"..\resources" -y
        del "..\resources\resources.7z.*" 2>nul
        echo [OK] Ressources extraites dans le dossier parent
    )
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
