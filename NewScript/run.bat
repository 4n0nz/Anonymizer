@echo off
chcp 65001 >nul

:: Memoriser le chemin absolu du dossier NewScript (avec \ final)
set "SCRIPTS=%~dp0"

:: Se placer dans le dossier parent (Anonymizer) :
:: les scripts cherchent input\, output\, resources\ en relatif
cd /d "%~dp0.."

:: Activer le virtualenv (chemin absolu vers NewScript\mask_env)
call "%SCRIPTS%mask_env\Scripts\activate.bat"

echo [*] Mask...
python "%SCRIPTS%face_mask.py"
if errorlevel 1 ( echo [ERREUR] face_mask.py & pause & exit /b 1 )
echo [OK] Mask Done

echo [*] Glitch...
python "%SCRIPTS%glitch.py"
if errorlevel 1 ( echo [ERREUR] glitch.py & pause & exit /b 1 )
echo [OK] Glitch Done

echo [*] Voice Encryption...
python "%SCRIPTS%audio.py"
if errorlevel 1 ( echo [ERREUR] audio.py & pause & exit /b 1 )
echo [OK] Voice Encryption Done

echo [*] Transitions...
python "%SCRIPTS%introNoutro.py"
if errorlevel 1 ( echo [ERREUR] introNoutro.py & pause & exit /b 1 )
echo [OK] Transitions Done

echo [*] Background ^& Pip...
python "%SCRIPTS%backNpip.py"
if errorlevel 1 ( echo [ERREUR] backNpip.py & pause & exit /b 1 )
echo [OK] Background ^& Pip Done

echo [*] Intro ^& Outro...
python "%SCRIPTS%introEndOutro.py"
if errorlevel 1 ( echo [ERREUR] introEndOutro.py & pause & exit /b 1 )
echo [OK] Intro ^& Outro Done

echo.
echo [OK] Video Anonymizer - Termine !

:: Nettoyage dossiers temporaires (dans le dossier parent)
for %%i in (1 2 3 4) do (
    if exist "output\.output%%i\" (
        del /q "output\.output%%i\*" 2>nul
    )
)

pause
