@echo off
setlocal enabledelayedexpansion

:: --- Configuration des couleurs pour un look console ---
color 0E
cls

:: --- En-tête de bienvenue  ---
echo.
echo  #################################################################
echo  #        G E N E R A T E U R   D E   S O U S - T I T R E S      #
echo  #             A V E C   W H I S P E R / F F M P E G             #
echo  #################################################################
echo.
echo   [ INFO ] Glissez-deposez une video (.mp4) sur ce script pour demarrer.
echo.
echo  -----------------------------------------------------------------
echo.

if "%~1"=="" (
   echo [!] Aucune video detectee. Veuillez glisser une video sur le script.
   pause
   exit /b
)

set "video=%~1"
set "basename=%~n1"

echo  -----------------------------------------------------------------
echo   [ VERIF ] Verification des prerequis...
echo  -----------------------------------------------------------------

:: --- Verification FFmpeg ---
if not exist ffmpeg.exe (
   where ffmpeg >nul 2>&1 || (
     echo [!] FFmpeg introuvable. Mettez "ffmpeg.exe" dans ce dossier ou ajoutez-le au PATH.
     pause
     exit /b
   )
)
echo   [ OK ] FFmpeg est bien configure.

:: --- Verification Whisper ---
where whisper >nul 2>&1
if errorlevel 1 (
   echo [!] Whisper introuvable. Assurez-vous que Whisper est installe et que la commande est sur le PATH.
   pause
   exit /b
)
echo   [ OK ] Whisper est bien installe.
echo.

echo  -----------------------------------------------------------------
echo   [ VIDEO ] Informations sur la video :
echo  -----------------------------------------------------------------
echo   Video cible : "%video%"
echo   Nom de base : "%basename%"
echo.

:: --- Choix de la langue source ---
echo  -----------------------------------------------------------------
echo   [ ETAPE 1/4 ] Selection de la langue de l'audio source
echo  -----------------------------------------------------------------
set "lang_arg="
set /p inlang="   Entrez la langue source de l'audio (ex: en, fr, es) [auto-detection par dflt]: "
if not "%inlang%"=="" (
   set "lang_selected=%inlang%"
   set "lang_arg=--language %inlang%"
   echo   [ OK ] Langue forcee : %inlang%
) else (
   set "lang_selected=Auto-detection"
   echo   [ OK ] Auto-detection de la langue activee.
)
echo.

:: --- Choix transcription vs traduction vers l'anglais ---
echo  -----------------------------------------------------------------
echo   [ ETAPE 2/4 ] Selection du mode de traitement
echo  -----------------------------------------------------------------
echo   Voulez-vous traduire le texte transcrit vers l'anglais ?
choice /M "   (O)ui pour traduire / (N)on pour transcrire uniquement"
if errorlevel 2 (
   set "task_selected=Transcription seule"
   set "task_arg=--task transcribe"
   echo   [ OK ] Mode selectionne : Transcription seule.
) else (
   set "task_selected=Traduction vers l'anglais"
   set "task_arg=--task translate"
   echo   [ OK ] Mode selectionne : Traduction vers l'anglais.
)
echo.

:: --- Choix du modèle Whisper ---
echo  -----------------------------------------------------------------
echo   [ ETAPE 3/4 ] Selection du modele Whisper
echo  -----------------------------------------------------------------
echo   Choisissez la taille du modele Whisper (affecte vitesse et precision):
echo     1) Tiny   (Rapide, Moins precis)
echo     2) Base
echo     3) Small  (Bon equilibre)
echo     4) Medium
echo     5) Large  (Lent, Tres precis)
set "model_selected_name=Small" :: Nom d'affichage par defaut
set "model_selected_arg=small"  :: Argument du modele par defaut pour Whisper
set /p model_choice="   Entrez le numero de votre choix [3]: "
if "%model_choice%"=="1" (set "model_selected_name=Tiny" & set "model_selected_arg=tiny")
if "%model_choice%"=="2" (set "model_selected_name=Base" & set "model_selected_arg=base")
if "%model_choice%"=="3" (set "model_selected_name=Small" & set "model_selected_arg=small")
if "%model_choice%"=="4" (set "model_selected_name=Medium" & set "model_selected_arg=medium")
if "%model_choice%"=="5" (set "model_selected_name=Large" & set "model_selected_arg=large")
echo   [ OK ] Modele selectionne : %model_selected_name%
echo.

:: --- Résumé des choix ---
echo  #################################################################
echo  #                          R E A D Y ?                          #
echo  #################################################################
echo.
echo   Fichier Video       : "%video%"
echo   Langue Source       : %lang_selected%
echo   Mode de Traitement  : %task_selected%
echo   Modele Whisper      : %model_selected_name%
echo.
echo  -----------------------------------------------------------------
echo   Appuyez sur n'importe quelle touche pour DEMARRER le processus...
echo  -----------------------------------------------------------------
pause >nul

echo.
echo  #################################################################
echo  #                      P R O C E S S I N G...                   #
echo  #################################################################
echo.

echo   [1/3] Extraction audio en WAV...
ffmpeg -hide_banner -loglevel error -i "%video%" -ar 16000 -ac 1 -c:a pcm_s16le "%basename%.wav"
if errorlevel 1 (
   echo [!] Echec de l'extraction audio.
   pause
   exit /b
)
echo   [ OK ] Audio extrait.

echo.
echo   [2/3] Lancement de Whisper...
whisper "%basename%.wav" --model %model_selected_arg% %lang_arg% %task_arg%
if errorlevel 1 (
   echo [!] Whisper a echoue. Le .srt peut etre incomplet ou absent.
   pause
) else (
   echo [ OK ] Whisper a termine.
)
echo.

echo   [3/3] Nettoyage...
if exist "%basename%.wav" del "%basename%.wav" >nul 2>&1
echo   [ OK ] Fichier audio temporaire supprime.
echo.

echo  #################################################################
echo  #               P R O C E S S U S   T E R M I N E !             #
echo  #################################################################
echo.
echo   Sous-titres generes : "%basename%.srt" (et autres formats)
echo.
echo   Appuyez sur n'importe quelle touche pour FERMER...
pause
