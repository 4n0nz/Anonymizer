@echo off
chcp 65001 >nul
call mask_env\Scripts\activate.bat

echo [*] Mask...
python face_mask.py
if errorlevel 1 ( echo [ERREUR] face_mask.py & exit /b 1 )
echo [OK] Mask Done

echo [*] Glitch...
python glitch.py
if errorlevel 1 ( echo [ERREUR] glitch.py & exit /b 1 )
echo [OK] Glitch Done

echo [*] Voice Encryption...
python audio.py
if errorlevel 1 ( echo [ERREUR] audio.py & exit /b 1 )
echo [OK] Voice Encryption Done

echo [*] Transitions...
python introNoutro.py
if errorlevel 1 ( echo [ERREUR] introNoutro.py & exit /b 1 )
echo [OK] Transitions Done

echo [*] Background ^& Pip...
python backNpip.py
if errorlevel 1 ( echo [ERREUR] backNpip.py & exit /b 1 )
echo [OK] Background ^& Pip Done

echo [*] Intro ^& Outro...
python introEndOutro.py
if errorlevel 1 ( echo [ERREUR] introEndOutro.py & exit /b 1 )
echo [OK] Intro ^& Outro Done

echo.
echo [OK] Video Anonymizer - Termine !

:: Nettoyage dossiers temporaires
for %%i in (1 2 3 4) do (
    if exist "output\.output%%i\" (
        del /q "output\.output%%i\*" 2>nul
    )
)

pause
