#!/usr/bin/env python3
"""
AutoGenSubTitles – Générateur de sous-titres avec Whisper + FFmpeg (CLI Python)

Résumé :
  Ce script prend une vidéo (.mp4) en entrée, extrait l'audio optimisé pour Whisper,
  lance Whisper pour transcription ou traduction vers l'anglais, nettoie le WAV temporaire,
  et affiche un récapitulatif avec progression, bannière stylée et détection de langue.

Fonctionnalités :
  * Choix du modèle Whisper (tiny, base, small, medium, large)
  * Auto-détection de la langue source ou spécification manuelle
  * Transcription seule ou traduction vers l'anglais via Whisper
  * Affichage rétro avec bannière ASCII (pyfiglet) et interface colorée / progression (rich)
  * Vérification des outils requis dans le PATH (ffmpeg, whisper)
  * Nettoyage automatique du .wav intermédiaire (désactivable)
  * Détection de la langue réelle à partir du JSON Whisper généré
  * Logging optionnel dans un fichier
  * Fallback minimal quand rich / pyfiglet ne sont pas installés

Pré-requis pip (installer avant usage) :
  pip install rich pyfiglet
  pip install git+https://github.com/openai/whisper.git

Outils externes requis :
  * ffmpeg : doit être dans le PATH
  * whisper : la commande CLI (installée via pip ci-dessus)

Exemples :
  python gen_subs.py ma_video.mp4
  python gen_subs.py ma_video.mp4 --model small --language fr --translate-to-en --log run.log
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
import datetime
from typing import Optional

# ASCII banner
try:
    import pyfiglet
    FIGLET_AVAILABLE = True
except ImportError:
    FIGLET_AVAILABLE = False

# rich pour l'UX
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, Progress
    from rich.style import Style
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None  # fallback usage


MODELS = ["tiny", "base", "small", "medium", "large"]


def run_cmd(cmd, capture=False):
    if RICH_AVAILABLE:
        disp = " ".join(cmd) if isinstance(cmd, (list, tuple)) else cmd
        console.log(f"[bold blue]>>[/] {disp}")
    try:
        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd)
    except Exception as e:
        raise RuntimeError(f"Échec exécution commande `{cmd}` : {e}")
    if result.returncode != 0:
        if capture:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            raise RuntimeError(f"Commande a échoué ({cmd})\nstdout: {stdout}\nstderr: {stderr}")
        else:
            raise RuntimeError(f"Commande a échoué ({cmd})")
    return result.stdout if capture else None


def tool_status(name: str) -> bool:
    return shutil.which(name) is not None


def check_tools():
    ffmpeg_ok = tool_status("ffmpeg")
    whisper_ok = tool_status("whisper")
    return ffmpeg_ok, whisper_ok


def extract_audio(video_path: Path, wav_path: Path):
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(wav_path),
    ]
    run_cmd(cmd)


def run_whisper(wav_path: Path, model: str, language: Optional[str], translate: bool):
    task = "translate" if translate else "transcribe"
    cmd = ["whisper", str(wav_path), "--model", model, "--task", task]
    if language:
        cmd += ["--language", language]
    run_cmd(cmd)


def find_detected_language(srt_base: Path):
    json_path = srt_base.with_suffix(".json")
    if not json_path.exists():
        return None
    try:
        import json
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("language") or data.get("language_detected") or None
    except Exception:
        return None


def human_readable_time(dt: datetime.datetime):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def print_banner(title: str, subtitle: Optional[str] = None):
    if RICH_AVAILABLE:
        if FIGLET_AVAILABLE:
            fig = pyfiglet.figlet_format(title, font="slant")
            console.print(Panel(Text(fig, justify="center"), style="bold magenta", subtitle=subtitle or ""))
        else:
            console.print(Panel(f"[bold magenta]{title}[/]", title=subtitle or "", style="magenta"))
    else:
        if FIGLET_AVAILABLE:
            print(pyfiglet.figlet_format(title))
        else:
            print(f"=== {title} ===")


def ask_choice(prompt: str, options: list[str], default: str) -> str:
    if RICH_AVAILABLE:
        opt_lines = "\n".join(f"  [bold]{i+1})[/] {opt}" for i, opt in enumerate(options))
        console.print(Panel(f"{prompt}\n{opt_lines}\n(default: {default})", title="Choix", expand=False))
        while True:
            resp = input(f"Ton choix (1-{len(options)}) [default {default}]: ").strip()
            if resp == "":
                return default
            if resp.isdigit():
                idx = int(resp) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            elif resp in options:
                return resp
            console.print("[red]Choix invalide[/]")
    else:
        prompt_full = f"{prompt} {', '.join(f'{i+1}) {opt}' for i,opt in enumerate(options))} [default {default}]: "
        while True:
            resp = input(prompt_full).strip()
            if resp == "":
                return default
            if resp.isdigit():
                idx = int(resp) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            elif resp in options:
                return resp
            print(f"[!] choix invalide.")


def yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        resp = input(f"{prompt} [{suffix}]: ").strip().lower()
        if resp == "":
            return default
        if resp in ("y", "yes", "o", "oui"):
            return True
        if resp in ("n", "no"):
            return False
        print("Réponds par oui ou non.")


def main():
    parser = argparse.ArgumentParser(description="AutoGenSubTitles – Whisper + FFmpeg transcription / traduction vers l'anglais")
    parser.add_argument("video", type=Path, help="Fichier .mp4 source")
    parser.add_argument("--model", choices=MODELS, default=None, help="Taille du modèle Whisper")
    parser.add_argument("--language", "-l", default=None, help="Langue source (ex: fr, en); laisser vide pour autodétection")
    parser.add_argument("--translate-to-en", action="store_true", help="Traduire vers l'anglais (via Whisper)")
    parser.add_argument("--no-clean", action="store_true", help="Conserver le .wav intermédiaire")
    parser.add_argument("--log", type=Path, default=None, help="Fichier log")
    args = parser.parse_args()

    if RICH_AVAILABLE:
        console.clear()
    print_banner("AutoGenSubTitles", "v1")
    start_time = datetime.datetime.now()

    try:
        video = args.video
        if not video.exists():
            raise FileNotFoundError(f"Vidéo introuvable : {video}")
        basename = video.with_suffix("")
        wav = basename.with_suffix(".wav")
        srt_file = basename.with_suffix(".srt")

        # vérif outils
        ffmpeg_ok, whisper_ok = check_tools()
        if RICH_AVAILABLE:
            status = Table(show_header=False, box=None)
            status.add_column("Outil", style="bold")
            status.add_column("Statut")
            status.add_row("ffmpeg", "[green]✓[/]" if ffmpeg_ok else "[red]✗[/]")
            status.add_row("whisper", "[green]✓[/]" if whisper_ok else "[red]✗[/]")
            console.print(Panel(status, title="Vérification outils", expand=False))
        else:
            print(f"ffmpeg: {'OK' if ffmpeg_ok else 'MISSING'}")
            print(f"whisper: {'OK' if whisper_ok else 'MISSING'}")

        if not (ffmpeg_ok and whisper_ok):
            print("[!] Il manque un outil requis. Abort.")
            sys.exit(1)

        # choix interactifs
        model = args.model or ask_choice("Choisis la taille du modèle Whisper :", MODELS, "small")
        language = args.language
        if language is None:
            lang_input = input("Langue source de l'audio (ex: en, fr, es) [auto-detection]: ").strip()
            if lang_input != "":
                language = lang_input
        translate_to_en = args.translate_to_en
        if not translate_to_en:
            translate_to_en = yes_no("Veux-tu traduire vers l'anglais ?", False)

        # résumé
        if RICH_AVAILABLE:
            table = Table(title="Résumé des choix", expand=False)
            table.add_column("Clé", style="bold")
            table.add_column("Valeur")
            table.add_row("Vidéo", str(video))
            table.add_row("Modèle Whisper", model)
            table.add_row("Langue source", language or "Auto-détection")
            table.add_row("Mode", "Traduction → anglais" if translate_to_en else "Transcription seule")
            table.add_row("Nettoyage .wav", "non" if args.no_clean else "oui")
            table.add_row("Log", str(args.log) if args.log else "aucun")
            console.print(table)
        else:
            print(f"Vidéo: {video}")
            print(f"Modèle: {model}")
            print(f"Langue source: {language or 'auto'}")
            print(f"Mode: {'Traduction vers anglais' if translate_to_en else 'Transcription'}")
            print(f"Nettoyage .wav: {'non' if args.no_clean else 'oui'}")
            if args.log:
                print(f"Log: {args.log}")

        if not yes_no("Démarrer le traitement avec ces paramètres ?", True):
            print("Annulé.")
            sys.exit(0)

        # logging initial
        if args.log:
            with open(args.log, "a", encoding="utf-8") as lf:
                lf.write(f"\n=== Run at {human_readable_time(start_time)} ===\n")
                lf.write(f"Video: {video}\nModel: {model}\nLang: {language}\nTranslateToEn: {translate_to_en}\n")

        # pipeline
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                transient=False,
            ) as progress:
                t1 = progress.add_task("Extraction audio...", total=1)
                try:
                    extract_audio(video, wav)
                    progress.update(t1, advance=1, description="[green]Audio extrait")
                except Exception as e:
                    progress.stop()
                    console.print(f"[red][!] Échec extraction audio: {e}[/]")
                    sys.exit(1)

                t2 = progress.add_task("Whisper (transcription/traduction)...", total=1)
                try:
                    run_whisper(wav, model, language, translate_to_en)
                    progress.update(t2, advance=1, description="[green]Whisper terminé")
                except Exception as e:
                    progress.update(t2, description="[red]Échec Whisper")
                    console.print(f"[red][!] Whisper a échoué: {e}[/]")

                if not args.no_clean:
                    t3 = progress.add_task("Nettoyage WAV...", total=1)
                    if wav.exists():
                        try:
                            wav.unlink()
                            progress.update(t3, advance=1, description="[green]WAV supprimé")
                        except Exception as e:
                            progress.update(t3, description=f"[red]Erreur cleanup: {e}")
        else:
            try:
                extract_audio(video, wav)
                print("[+] Audio extrait.")
            except Exception as e:
                print(f"[!] Échec extraction audio: {e}")
                sys.exit(1)
            try:
                run_whisper(wav, model, language, translate_to_en)
                print("[+] Whisper terminé.")
            except Exception as e:
                print(f"[!] Whisper a échoué: {e}")
            if not args.no_clean and wav.exists():
                try:
                    wav.unlink()
                    print("[+] WAV supprimé.")
                except Exception:
                    pass

        # résultat final
        detected_lang = find_detected_language(basename)
        end_time = datetime.datetime.now()
        duration_total = end_time - start_time

        # bannière de fin
        print_banner("Success !", "✅")

        if RICH_AVAILABLE:
            result = Table(show_header=False)
            result.add_column("Clé", style="bold")
            result.add_column("Valeur")
            result.add_row(".srt généré", str(srt_file) if srt_file.exists() else "[red]Non généré[/]")
            result.add_row("Langue détectée", detected_lang or "Inconnue")
            result.add_row("Durée totale", str(duration_total).split(".")[0])
            console.print(result)
            if not srt_file.exists():
                console.print("[yellow]Attention: .srt introuvable, vérifie la sortie de Whisper.[/]")
        else:
            print(f".srt: {srt_file} {'(existe)' if srt_file.exists() else '(manquant)'}")
            print(f"Langue détectée: {detected_lang or 'Inconnue'}")
            print(f"Temps total: {duration_total}")

        if args.log:
            with open(args.log, "a", encoding="utf-8") as lf:
                lf.write(f".srt exists: {srt_file.exists()}\n")
                lf.write(f"Detected lang: {detected_lang}\n")
                lf.write(f"Elapsed: {duration_total}\n")

    except KeyboardInterrupt:
        print("\n[!] Interrompu par l'utilisateur.")
        sys.exit(1)
    except Exception as exc:
        print(f"[!] Erreur fatale: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
