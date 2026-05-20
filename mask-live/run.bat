@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Active le virtualenv
if exist "..\mask_env\Scripts\activate.bat" (
    call "..\mask_env\Scripts\activate.bat"
) else (
    echo [ERREUR] mask_env introuvable. Lance d'abord Win\install.bat
    pause
    exit /b 1
)

:: Lance le live
python live.py
pause
