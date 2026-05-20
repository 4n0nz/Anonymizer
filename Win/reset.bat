@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: Le script est dans Win\, on remonte d'un niveau pour cibler le dossier Anonymizer
set "ROOT=%~dp0.."
pushd "%ROOT%" >nul
set "ROOT=%CD%"

echo ===============================================
echo   Anonymizer Reset
echo ===============================================
echo.
echo   Dossier cible : %ROOT%
echo.
echo   Sera vide / supprime :
echo     - input\      (videos source)
echo     - output\     (videos finales + intermediaires + metadata)
echo     - logs\       (logs des runs)
echo     - mask_env\   (virtualenv Python complet)
echo     - resources\  (fichiers extraits - les archives .7z* sont gardees)
echo.
echo   Le code source et la config sont CONSERVES.
echo.

set /p CONFIRM="  Tape 'YES' pour confirmer : "

if /i not "%CONFIRM%"=="YES" (
    echo.
    echo   Annule. Aucun fichier supprime.
    popd >nul
    exit /b 0
)

echo.

call :clear_dir "input"
call :clear_dir "output"
call :clear_dir "logs"

:: Vide resources\ EXCEPT les archives resources.7z.*
if exist "resources\" (
    echo [*] Vidage de resources\ ^(sauf les archives .7z*^)
    :: Sous-dossiers (s'il y en a)
    for /D %%D in ("resources\*") do rmdir /s /q "%%D" 2>nul
    :: Fichiers : on parcourt et on skip ceux qui matchent resources.7z.*
    for %%F in ("resources\*") do (
        echo %%~nxF | findstr /r /c:"^resources\.7z\." >nul
        if errorlevel 1 del /f /q "%%F" 2>nul
    )
) else (
    echo [-] resources\ inexistant, ignore
)

if exist "mask_env" (
    echo [*] Suppression du virtualenv mask_env\
    rmdir /s /q "mask_env"
) else (
    echo [-] mask_env\ inexistant, ignore
)

echo.
echo [OK] Reset termine.
echo      Pour reinstaller le virtualenv : Win\install.bat

popd >nul
exit /b 0


:: -----------------------------------------------
:: Fonction : vide le contenu d'un dossier (le garde lui-meme)
:: -----------------------------------------------
:clear_dir
set "TARGET=%~1"
if exist "%TARGET%\" (
    echo [*] Vidage de %TARGET%\
    :: Supprime tous les fichiers
    del /f /q /a "%TARGET%\*" 2>nul
    :: Supprime tous les sous-dossiers (visibles + cachés)
    for /D %%D in ("%TARGET%\*") do rmdir /s /q "%%D" 2>nul
    for /F "delims=" %%D in ('dir /b /a:dh "%TARGET%" 2^>nul') do rmdir /s /q "%TARGET%\%%D" 2>nul
) else (
    echo [-] %TARGET%\ inexistant, ignore
)
exit /b 0
