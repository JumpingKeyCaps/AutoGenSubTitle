@echo off
if "%~1"=="" (
  echo Glisse ta video dessus pour generer les sous-titres.
  pause
  exit /b
)
set "video=%~1"
set "basename=%~n1"

echo Extraction audio...
ffmpeg -i "%video%" -ar 16000 -ac 1 -c:a pcm_s16le "%basename%.wav"

echo Transcription + traduction en anglais...
whisper "%basename%.wav" --model tiny --task translate --language en

echo Nettoyage du fichier audio temporaire...
del "%basename%.wav"

echo -------------------------------
echo Sous-titres generes : %basename%.srt
echo -------------------------------
pause
