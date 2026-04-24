@echo off
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
if not exist mask_env\Scripts\python.exe (
    echo.
    echo Creation du virtualenv...
    python -m venv mask_env
    if errorlevel 1 ( echo [ERREUR] Creation virtualenv echouee & pause & exit /b 1 )
    echo [OK] Virtualenv cree
) else (
    echo [OK] Virtualenv existant
)

:: Activation
call mask_env\Scripts\activate.bat

:: Mise a jour pip
echo.
echo Mise a jour pip...
python -m pip install --upgrade pip wheel setuptools

:: Installation dependances Python
echo.
echo Installation des dependances Python...
python -m pip install -r "..\requirements.txt"
if errorlevel 1 ( echo [ERREUR] Installation des dependances echouee & pause & exit /b 1 )

:: Verification finale
echo.
echo Verification des imports...
python -c "import cv2, numpy, mediapipe, tqdm; print(chr(91)+chr(79)+chr(75)+chr(93)+chr(32)+chr(79)+chr(112)+chr(101)+chr(110)+chr(67)+chr(86)+chr(32)+cv2.__version__)"
if errorlevel 1 ( echo [ERREUR] Un import a echoue & pause & exit /b 1 )

:: Extraction des ressources (7-Zip)
if exist "..\resources\resources.7z.001" (
    echo.
    echo Extraction des ressources...
    set "SEVENZIP="
    where 7z >nul 2>&1 && set "SEVENZIP=7z"
    if exist "C:\Program Files\7-Zip\7z.exe" set "SEVENZIP=C:\Program Files\7-Zip\7z.exe"
    if "%SEVENZIP%"=="" (
        echo [ATTENTION] 7-Zip introuvable. Installez-le depuis https://www.7-zip.org/
        echo et relancez install.bat
    ) else (
        "%SEVENZIP%" x "..\resources\resources.7z.001" -o"..\resources" -y
        if errorlevel 1 ( echo [ERREUR] Extraction echouee & pause & exit /b 1 )
        del "..\resources\resources.7z.*" 2>nul
        echo [OK] Ressources extraites
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