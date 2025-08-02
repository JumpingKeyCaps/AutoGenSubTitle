@echo off
setlocal

if "%~1"=="" (
  echo Glisse ta video dessus pour generer les sous-titres.
  pause
  exit /b
)

set "video=%~1"
set "basename=%~n1"

REM --- choix de la langue source ---
set /p inlang=Langue source de l'audio (ex: en, fr, es) [auto]: 
if "%inlang%"=="" (
  set "lang_arg="
  echo Auto-detection de la langue activée.
) else (
  set "lang_arg=--language %inlang%"
  echo Langue forcee : %inlang%
)

REM --- choix transcription vs traduction vers EN ---
set /p do_translate=Tu veux traduire vers l'anglais (y/N) ? 
if /I "%do_translate%"=="y" (
  set "task_arg=--task translate"
  echo Mode : traduction vers l'anglais (translate).
) else (
  set "task_arg="
  echo Mode : transcription seule.
)

echo.
echo -------------------------------
echo Extraction audio de "%video%"...
ffmpeg -i "%video%" -ar 16000 -ac 1 -c:a pcm_s16le "%basename%.wav"

echo.
echo -------------------------------
echo Lancement de Whisper...
whisper "%basename%.wav" --model tiny %lang_arg% %task_arg%

echo.
echo -------------------------------
echo Nettoyage du fichier audio temporaire...
del "%basename%.wav"

echo.
echo -------------------------------
echo Sous-titres generes : %basename%.srt
echo -------------------------------
pause
