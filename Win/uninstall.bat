@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
:: ÉTAPE 1 : si on n'est PAS déjà dans %TEMP%, on s'y copie et
:: on relance. Comme ça l'original peut être supprimé.
:: ============================================================
if /i not "%~dp0"=="%TEMP%\" (
    if /i not "%~dp0"=="%TEMP%" (
        :: Sauve le chemin Anonymizer (parent du dossier Win)
        for %%I in ("%~dp0..") do set "ANON_ROOT=%%~fI"

        :: Copie vers TEMP avec un nom unique
        copy /y "%~f0" "%TEMP%\anon_uninstall_self.bat" >nul

        :: Relance depuis TEMP en passant ANON_ROOT en argument
        call "%TEMP%\anon_uninstall_self.bat" "!ANON_ROOT!"

        :: Quand la version TEMP a fini, on nettoie son fichier
        del /f /q "%TEMP%\anon_uninstall_self.bat" 2>nul
        exit /b 0
    )
)

:: ============================================================
:: ÉTAPE 2 : on tourne depuis %TEMP%, plus rien ne nous lock.
:: ============================================================

set "ROOT=%~1"
if "%ROOT%"=="" (
    echo [ERREUR] ANON_ROOT non passe en argument
    exit /b 1
)

echo ===============================================
echo   Anonymizer Uninstaller
echo ===============================================
echo.
echo   Ce script va EFFACER TOUT LE CONTENU de :
echo     %ROOT%
echo.
echo   Sera supprime :
echo     - mask_env\                 (virtualenv Python)
echo     - input\, output\, logs\    (toutes les videos)
echo     - resources\                (masque, backgrounds, modeles)
echo     - Pipeline\                 (scripts du pipeline)
echo     - Tous les fichiers source (.py, .md, .txt, etc.)
echo     - .git\                     (historique Git si present)
echo     - Win\                      (et ce script lui-meme)
echo.
echo   Le dossier 'Anonymizer' lui-meme sera conserve (vide).
echo.

set /p CONFIRM="  Tape 'YES' (en majuscules) pour confirmer : "

if /i not "%CONFIRM%"=="YES" (
    echo.
    echo   Annule. Aucun fichier supprime.
    exit /b 0
)

echo.
echo [*] Suppression en cours via PowerShell (plus robuste)...

:: PowerShell est beaucoup plus fiable que cmd pour supprimer recursivement
:: Get-ChildItem -Force inclut hidden + system | Remove-Item supprime tout
powershell -NoProfile -Command ^
    "Get-ChildItem -LiteralPath '%ROOT%' -Force | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }"

:: Vérification
powershell -NoProfile -Command ^
    "$items = Get-ChildItem -LiteralPath '%ROOT%' -Force; if ($items.Count -eq 0) { Write-Host '[OK] Dossier vide.' -ForegroundColor Green } else { Write-Host '[WARN] Il reste:' -ForegroundColor Yellow; $items | ForEach-Object { Write-Host ('  - ' + $_.Name) -ForegroundColor Yellow } }"

echo.
echo [OK] Desinstallation terminee.
echo      Le dossier reste a : %ROOT%
echo.
pause
exit /b 0
