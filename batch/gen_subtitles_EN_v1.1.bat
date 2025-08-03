@echo off
setlocal enabledelayedexpansion

:: === Header ===
title AutoGenSubTitles
color 60
cls
echo.
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
echo  -----------------------------------------------------------------
echo   Drag and drop a .mp4 video onto this script to start.
echo  -----------------------------------------------------------------
echo.

if "%~1"=="" (
    echo [!] No video provided. Drag and drop a .mp4 file onto this script.
    pause
    exit /b
)

set "video=%~1"
set "basename=%~n1"
set "ext=%~x1"

:: --- Prerequisites check ---
echo  -----------------------------------------------------------------
echo   [ CHECK ] Checking prerequisites...
echo  -----------------------------------------------------------------

:: ffmpeg
where ffmpeg >nul 2>&1
if errorlevel 1 (
    if not exist ffmpeg.exe (
        echo [!] FFmpeg not found. Put ffmpeg.exe here or add to PATH.
        pause
        exit /b
    )
)
echo   [ OK ] FFmpeg available.

:: whisper
where whisper >nul 2>&1
if errorlevel 1 (
    echo [!] Whisper CLI not found in PATH. Ensure it's installed.
    pause
    exit /b
)
echo   [ OK ] Whisper available.

echo.

:: --- Step 1: output folder ---
echo  -----------------------------------------------------------------
echo   [ STEP 1/6 ] Output folder
echo  -----------------------------------------------------------------
set "default_out=%basename%"
set /p outdir="   Output folder name (default '%basename%'): "
if "%outdir%"=="" set "outdir=%default_out%"
set "outdir=%CD%\%outdir%"
if not exist "%outdir%" mkdir "%outdir%"
echo   [ OK ] Using output folder: "%outdir%"
echo.

:: --- Step 2: source language ---
echo  -----------------------------------------------------------------
echo   [ STEP 2/6 ] Source audio language
echo  -----------------------------------------------------------------
set "lang_arg="
set "lang_selected=Auto-detect"
set /p inlang="   Enter source audio language (e.g., en, fr, es) [leave empty = auto]: "
if not "%inlang%"=="" (
    set "lang_arg=--language %inlang%"
    set "lang_selected=%inlang%"
    echo   [ OK ] Forced language: %inlang%
) else (
    echo   [ OK ] Auto-detect enabled.
)
echo.

:: --- Step 3: translate or transcribe ---
echo  -----------------------------------------------------------------
echo   [ STEP 3/6 ] Translation mode
echo  -----------------------------------------------------------------
choice /M "   Translate to English? (Yes = translate / No = transcribe only)"
if errorlevel 2 (
    set "task_arg=--task transcribe"
    set "task_selected=Transcription only"
) else (
    set "task_arg=--task translate"
    set "task_selected=Translation to English"
)
echo   [ OK ] Mode: %task_selected%
echo.

:: --- Step 4: Whisper model ---
echo  -----------------------------------------------------------------
echo   [ STEP 4/6 ] Whisper model size
echo  -----------------------------------------------------------------
echo   1) tiny    (fast, lower accuracy)
echo   2) base
echo   3) small   (balance)
echo   4) medium
echo   5) large   (slow, high accuracy)
set "model_selected_arg=small"
set "model_selected_name=Small"
set /p model_choice="   Choose model [3]: "
if "%model_choice%"=="1" (set "model_selected_arg=tiny" & set "model_selected_name=Tiny")
if "%model_choice%"=="2" (set "model_selected_arg=base" & set "model_selected_name=Base")
if "%model_choice%"=="3" (set "model_selected_arg=small" & set "model_selected_name=Small")
if "%model_choice%"=="4" (set "model_selected_arg=medium" & set "model_selected_name=Medium")
if "%model_choice%"=="5" (set "model_selected_arg=large" & set "model_selected_name=Large")
echo   [ OK ] Selected model: %model_selected_name%
echo.

:: --- Step 5: behaviour flags (clean / overwrite / skip) ---
echo  -----------------------------------------------------------------
echo   [ STEP 5/6 ] File handling preferences
echo  -----------------------------------------------------------------
:: Clean WAV?
choice /M "   Remove intermediate .wav after run? (Yes=clean / No=keep)"
if errorlevel 2 (
    set "clean_wav=no"
) else (
    set "clean_wav=yes"
)

:: Overwrite .srt?
choice /M "   Overwrite existing .srt if present? (Yes=overwrite / No=keep existing)"
if errorlevel 2 (
    set "overwrite=no"
) else (
    set "overwrite=yes"
)

:: Skip if .srt exists?
choice /M "   Skip processing if .srt already exists? (Yes=skip / No=force)"
if errorlevel 2 (
    set "skip_if_exists=no"
) else (
    set "skip_if_exists=yes"
)

echo   [ OK ] clean_wav=%clean_wav% overwrite=%overwrite% skip_if_exists=%skip_if_exists%
echo.

:: --- Step 6: summary & start ---
echo  -----------------------------------------------------------------
echo   [ SUMMARY ] Ready to process
echo  -----------------------------------------------------------------
echo   Video file         : "%video%"
echo   Output folder      : "%outdir%"
echo   Source language    : %lang_selected%
echo   Mode               : %task_selected%
echo   Whisper model      : %model_selected_name%
echo   Clean WAV          : %clean_wav%
echo   Overwrite .srt     : %overwrite%
echo   Skip if exists     : %skip_if_exists%
echo.
pause >nul

:: === Processing ===
echo.
echo  -----------------------------------------------------------------
echo   [1/4] Extract audio
echo  -----------------------------------------------------------------
set "wav=%outdir%\%basename%.wav"
ffmpeg -hide_banner -loglevel error -i "%video%" -ar 16000 -ac 1 -c:a pcm_s16le "%wav%"
if errorlevel 1 (
    echo [!] Audio extraction failed.
    pause
    exit /b
)
echo   [ OK ] Audio extracted to "%wav%"

:: decide if we should run Whisper:
set "srt_dest=%outdir%\%basename%.srt"
if exist "%srt_dest%" (
    if "%skip_if_exists%"=="yes" (
        echo   [!] .srt exists and skip_if_exists enabled → skipping Whisper.
        goto after_whisper
    )
    if "%overwrite%"=="no" (
        echo   [!] .srt exists and overwrite disabled → skipping Whisper.
        goto after_whisper
    )
)

echo.
echo  -----------------------------------------------------------------
echo   [2/4] Running Whisper
echo  -----------------------------------------------------------------
whisper "%wav%" --model %model_selected_arg% %lang_arg% %task_arg%
if errorlevel 1 (
    echo [!] Whisper failed. Output may be incomplete.
) else (
    echo   [ OK ] Whisper finished.
)

:after_whisper
echo.
echo  -----------------------------------------------------------------
echo   [3/4] Moving outputs
echo  -----------------------------------------------------------------
for %%e in (srt json tsv txt vtt) do (
    if exist "%basename%.%%e" (
        move /Y "%basename%.%%e" "%outdir%\" >nul 2>&1
        echo   moved: %basename%.%%e
    )
)

:: clean wav if requested
if "%clean_wav%"=="yes" (
    if exist "%wav%" del "%wav%" >nul 2>&1
    echo   [ OK ] Cleaned .wav
) else (
    echo   [ INFO ] Keeping .wav: "%wav%"
)

:: move video into output
echo.
echo  -----------------------------------------------------------------
echo   [4/4] Finalizing
echo  -----------------------------------------------------------------
set "target_video=%outdir%\%~nx1"
if exist "%target_video%" (
    set /a i=1
    :loopname
    if exist "%outdir%\%basename%_%i%%ext%" (
        set /a i+=1
        goto loopname
    )
    set "target_video=%outdir%\%basename%_%i%%ext%"
)
move "%video%" "%target_video%" >nul 2>&1
echo   [ OK ] Video moved to: "%target_video%"

:: final summary
echo.
echo  #################################################################
echo  #                   PROCESS COMPLETE ✅                       #
echo  #################################################################
echo.
echo   Subtitles (and related): "%outdir%\%basename%.srt"
echo   Video location         : "%target_video%"
echo.
pause
