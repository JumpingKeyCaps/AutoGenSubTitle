# Générateur de sous-titres avec Whisper et FFmpeg (Windows)

Ce repo contient un guide complet et un script `.bat` pour générer automatiquement un fichier de sous-titres en anglais à partir de vidéos `.mp4`, grâce à FFmpeg et OpenAI Whisper.  
⚠️ La traduction vers le français ou une autre langue doit être faite séparément.

---

## 📋 Prérequis

- Windows 10 ou supérieur
- Python 3.9+ (avec pip)
- FFmpeg (build essentials)
- Connexion internet (pour l’installation des dépendances Whisper)
- Whisper installé via `pip`

---


## 1. Installation

### 1.1 Installer Python

- Télécharger Python : [https://www.python.org/downloads/](https://www.python.org/downloads/)
- Lors de l'installation, **cochez "Add Python to PATH"**

### 1.2 Installer FFmpeg

- Télécharger FFmpeg (build essentials) : [https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip)
- Décompressez dans un dossier simple (ex : `C:\Outils\ffmpeg\`)
- Vérifiez l’exécutable avec `ffmpeg.exe -version` dans un terminal ouvert dans ce dossier

### 1.3 Installer Whisper et dépendances Python

Ouvrez un terminal (cmd ou PowerShell) et lancez :

```bash
python -m pip install --upgrade pip
pip install git+https://github.com/openai/whisper.git
pip install ffmpeg-python
```

## 2. Utilisation

### 2.1 Commandes séparées

```bash
# 1. Extraire l’audio en WAV optimisé pour Whisper
ffmpeg -i mavideo.mp4 -ar 16000 -ac 1 -c:a pcm_s16le audio.wav

# 2. Transcrire en anglais
whisper audio.wav --model small --language en

# 3. Transcrire + traduire en anglais (video en francais)
whisper audio.wav --model small --language fr --task translate

```

### 2.2 Script `.bat` automatique (glisser-déposer)

Placez ce fichier `gen_subs.bat` dans le même dossier que `ffmpeg.exe` et vos vidéos `.mp4`.  
Glissez-déposez une vidéo dessus : le script va extraire l’audio, lancer Whisper pour transcrire et traduire, puis supprimer l’audio temporaire.

```bat
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

```
### 2.3 Résultat

- Un fichier `.srt` est généré dans le même dossier que la vidéo.
- Si le fichier `.srt` porte exactement le même nom que la vidéo (`ma_video.mp4` et `ma_video.srt`), VLC l’affichera automatiquement.
- Sinon, vous pouvez charger manuellement le fichier depuis VLC :  
  **Menu** → *Sous-titres* → *Ajouter un fichier de sous-titres…*

---

## 3. Notes

- **Vitesse vs précision** :
  - `--model tiny` → très rapide, moins précis
  - `--model small` → rapide et précis pour la plupart des cas
  - `--model medium` ou `large` → très précis, mais plus lent
- **Langue source** :
  - Ici `--language en` indique que l’audio est en anglais.
  - Changez-le si la vidéo est dans une autre langue (ex: `--language fr`).
- **Traduction** :
  - `--task translate` traduit automatiquement **vers l'anglais**.
  - Pour traduire vers une autre langue, transcrivez d’abord (`--task transcribe`), puis utilisez un traducteur externe.
- Le script supprime le `.wav` temporaire après génération du `.srt` pour garder le dossier propre.

---

## 4. Exemple d’usage rapide

1. Glissez `ma_video.mp4` sur `gen_subs.bat`.
2. Attendez que le script ait terminé l’extraction audio, la transcription et la traduction.
3. Ouvrez `ma_video.mp4` dans VLC.  
   - Si le `.srt` a le même nom que la vidéo, il se chargera automatiquement.
   - Sinon, ajoutez-le via le menu des sous-titres.
