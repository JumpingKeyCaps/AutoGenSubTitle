@echo off
setlocal enabledelayedexpansion

if "%~1"=="" (
  echo [!] Glisse une video dessus pour generer les sous-titres.
  pause
  exit /b
)

set "video=%~1"
set "basename=%~n1"

REM --- vérif outils ---
if not exist ffmpeg.exe (
  where ffmpeg >nul 2>&1 || (
    echo [!] ffmpeg introuvable. Mets ffmpeg.exe dans ce dossier ou ajoute-le au PATH.
    pause
    exit /b
  )
)
where whisper >nul 2>&1
if errorlevel 1 (
  echo [!] whisper introuvable. Assure-toi que Whisper est installe et que la commande "whisper" est sur le PATH.
  pause
  exit /b
)

echo -------------------------------------------------------
echo Video cible : "%video%"
echo Nom base   : "%basename%"
echo -------------------------------------------------------

REM --- langue source ---
set "lang_arg="
set /p inlang=Langue source de l'audio (ex: en, fr, es) [auto] : 
if not "%inlang%"=="" (
  set "lang_arg=--language %inlang%"
  echo [*] Langue forcee : %inlang%
) else (
  echo [*] Auto-detection de la langue activée.
)

REM --- choix transcription vs traduction vers l'anglais ---
echo.
echo Veux-tu traduire vers l'anglais (quelle que soit la langue source) ?
choice /M "Traduire vers l'anglais ?"
if errorlevel 2 (
  set "task_arg="
  echo [*] Mode : transcription seule.
) else (
  set "task_arg=--task translate"
  echo [*] Mode : traduction vers l'anglais.
)

echo.
echo [1/3] Extraction audio...
ffmpeg -hide_banner -loglevel error -i "%video%" -ar 16000 -ac 1 -c:a pcm_s16le "%basename%.wav"
if errorlevel 1 (
  echo [!] echec de l'extraction audio.
  pause
  exit /b
)

echo.
echo [2/3] Lancement de Whisper...
whisper "%basename%.wav" --model tiny %lang_arg% %task_arg%
if errorlevel 1 (
  echo [!] Whisper a echoue. Le .srt peut etre incomplet ou absent.
) else (
  echo [*] Whisper a termine.
)

echo.
echo [3/3] Nettoyage...
if exist "%basename%.wav" del "%basename%.wav" >nul 2>&1

echo.
echo -------------------------------------------------------
echo Sous-titres generes : "%basename%.srt"
echo -------------------------------------------------------
pause
