@echo off
chcp 65001 >nul

:: Se placer dans le dossier parent (Anonymizer)
cd /d "%~dp0.."

:: Activer le virtualenv dans Win\mask_env
call "%~dp0mask_env\Scripts\activate.bat"

:: Lancer le pipeline depuis la racine
python run.py

pause
