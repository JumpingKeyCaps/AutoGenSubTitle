@echo off
setlocal enabledelayedexpansion

:: --- Color configuration for console look ---
title AutoGenSubTitles
color 60
cls

:: --- Welcome header (simple ASCII style) ---
echo.
echo.
echo        db    88   88 888888  dP"Yb   dP""b8 888888 88b 88       
echo       dPYb   88   88   88   dP   Yb dP   `" 88__   88Yb88       
echo      dP__Yb  Y8   8P   88   Yb   dP Yb  "88 88""   88 Y88       
echo     dP""""Yb `YbodP'   88    YbodP   YboodP 888888 88  Y8    
echo.   
echo   .dP"Y8 88   88 88""Yb 888888 88 888888 88     888888 .dP"Y8 
echo   `Ybo." 88   88 88__dP   88   88   88   88     88__   `Ybo." 
echo   o.`Y8b Y8   8P 88""Yb   88   88   88   88  .o 88""   o.`Y8b 
echo   8bodP' `YbodP' 88oodP   88   88   88   88ood8 888888 8bodP'       
echo.  
echo.
echo  -----------------------------------------------------------------                                            
echo.
echo   [ INFO ] Drag and drop a video (.mp4) onto this script to start.
echo.
echo.

if "%~1"=="" (
   echo [!] No video detected. Please drag and drop a video onto the script.
   pause
   exit /b
)

set "video=%~1"
set "basename=%~n1"

echo  -----------------------------------------------------------------
echo   [ CHECK ] Checking prerequisites...
echo  -----------------------------------------------------------------

:: --- Check FFmpeg ---
if not exist ffmpeg.exe (
   where ffmpeg >nul 2>&1 || (
     echo [!] FFmpeg not found. Place "ffmpeg.exe" in this folder or add it to the PATH.
     pause
     exit /b
   )
)
echo   [ OK ] FFmpeg is properly configured.

:: --- Check Whisper ---
where whisper >nul 2>&1
if errorlevel 1 (
   echo [!] Whisper not found. Make sure Whisper is installed and the command is in the PATH.
   pause
   exit /b
)
echo   [ OK ] Whisper is installed.
echo.
echo.
echo  -----------------------------------------------------------------
echo   [ VIDEO ] Video information:
echo  -----------------------------------------------------------------
echo   Target video : "%video%"
echo   Base name    : "%basename%"
echo.
echo.
:: --- Select source language ---
echo  -----------------------------------------------------------------
echo   [ STEP 1/4 ] Select the source audio language
echo  -----------------------------------------------------------------
set "lang_arg="
set /p inlang="   Enter source audio language (e.g., en, fr, es) [default: auto-detect]: "
if not "%inlang%"=="" (
   set "lang_selected=%inlang%"
   set "lang_arg=--language %inlang%"
   echo   [ OK ] Forced language: %inlang%
) else (
   set "lang_selected=Auto-detect"
   echo   [ OK ] Auto-detect enabled.
)
echo.

:: --- Select transcription vs translation to English ---
echo  -----------------------------------------------------------------
echo   [ STEP 2/4 ] Select processing mode
echo  -----------------------------------------------------------------
echo   Do you want to translate the transcript to English?
choice /M "   (Y)es to translate / (N)o to transcribe only"
if errorlevel 2 (
   set "task_selected=Transcription only"
   set "task_arg=--task transcribe"
   echo   [ OK ] Selected mode: Transcription only.
) else (
   set "task_selected=Translation to English"
   set "task_arg=--task translate"
   echo   [ OK ] Selected mode: Translation to English.
)
echo.

:: --- Select Whisper model ---
echo  -----------------------------------------------------------------
echo   [ STEP 3/4 ] Select Whisper model
echo  -----------------------------------------------------------------
echo   Choose Whisper model size (affects speed and accuracy):
echo     1) Tiny   (Fast, less accurate)
echo     2) Base
echo     3) Small  (Good balance)
echo     4) Medium
echo     5) Large  (Slow, very accurate)
set "model_selected_name=Small" :: Default display name
set "model_selected_arg=small"  :: Default Whisper model argument
set /p model_choice="   Enter the number of your choice [3]: "
if "%model_choice%"=="1" (set "model_selected_name=Tiny" & set "model_selected_arg=tiny")
if "%model_choice%"=="2" (set "model_selected_name=Base" & set "model_selected_arg=base")
if "%model_choice%"=="3" (set "model_selected_name=Small" & set "model_selected_arg=small")
if "%model_choice%"=="4" (set "model_selected_name=Medium" & set "model_selected_arg=medium")
if "%model_choice%"=="5" (set "model_selected_name=Large" & set "model_selected_arg=large")
echo   [ OK ] Selected model: %model_selected_name%
echo.

:: --- Summary ---
echo  #################################################################
echo  #                          R E A D Y ?                          #
echo  #################################################################
echo.
echo   Video file         : "%video%"
echo   Source language    : %lang_selected%
echo   Processing mode    : %task_selected%
echo   Whisper model      : %model_selected_name%
echo.
echo  -----------------------------------------------------------------
echo   Press any key to START the process...
echo  -----------------------------------------------------------------
pause >nul

echo.
echo  #################################################################
echo  #                      P R O C E S S I N G...                   #
echo  #################################################################
echo.

echo   [1/3] Extracting audio to WAV...
ffmpeg -hide_banner -loglevel error -i "%video%" -ar 16000 -ac 1 -c:a pcm_s16le "%basename%.wav"
if errorlevel 1 (
   echo [!] Audio extraction failed.
   pause
   exit /b
)
echo   [ OK ] Audio extracted.

echo.
echo   [2/3] Running Whisper...
whisper "%basename%.wav" --model %model_selected_arg% %lang_arg% %task_arg%
if errorlevel 1 (
   echo [!] Whisper failed. The .srt may be incomplete or missing.
   pause
) else (
   echo   [ OK ] Whisper completed.
)
echo.

echo   [3/3] Cleaning up...
if exist "%basename%.wav" del "%basename%.wav" >nul 2>&1
echo   [ OK ] Temporary audio file deleted.
echo.

echo  #################################################################
echo  #                   P R O C E S S   C O M P L E T E !           #
echo  #################################################################
echo.
echo   Generated subtitles: "%basename%.srt" (and other formats)
echo.
echo   Press any key to CLOSE...
pause
