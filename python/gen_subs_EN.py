#!/usr/bin/env python3
"""
AutoGenSubTitles – Subtitle generator with Whisper + FFmpeg (Python CLI)

Summary:
  This script takes a .mp4 video, extracts audio optimized for Whisper,
  runs Whisper for transcription or translation to English, cleans up the temporary WAV,
  and displays a summary with progress, styled banner, and detected language.

Features:
  * Choice of Whisper model (tiny, base, small, medium, large)
  * Auto-detect source language or manual override
  * Transcription only or translation to English via Whisper
  * Retro display with ASCII banner (pyfiglet) and colored/progress UI (rich)
  * Automatic verification of required tools in PATH (ffmpeg, whisper)
  * Optional cleanup of intermediate .wav
  * Detection of actual language from Whisper JSON output
  * Optional logging to file
  * Minimal fallback when rich / pyfiglet are missing

Pip prerequisites (install before use):
  pip install rich pyfiglet
  pip install git+https://github.com/openai/whisper.git

External tools required:
  * ffmpeg : must be on PATH
  * whisper : CLI command (installed via pip above)

Examples:
  python gen_subs.py my_video.mp4
  python gen_subs.py my_video.mp4 --model small --language fr --translate-to-en --log run.log
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

# rich for UX
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, Progress
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None  # fallback


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
        raise RuntimeError(f"Command execution failed `{cmd}` : {e}")
    if result.returncode != 0:
        if capture:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            raise RuntimeError(f"Command failed ({cmd})\nstdout: {stdout}\nstderr: {stderr}")
        else:
            raise RuntimeError(f"Command failed ({cmd})")
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
        console.print(Panel(f"{prompt}\n{opt_lines}\n(default: {default})", title="Choice", expand=False))
        while True:
            resp = input(f"Your choice (1-{len(options)}) [default {default}]: ").strip()
            if resp == "":
                return default
            if resp.isdigit():
                idx = int(resp) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            elif resp in options:
                return resp
            console.print("[red]Invalid choice[/]")
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
            print(f"[!] invalid choice.")


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
        print("Answer yes or no.")


def main():
    parser = argparse.ArgumentParser(description="AutoGenSubTitles – Whisper + FFmpeg transcription / translation to English")
    parser.add_argument("video", type=Path, help="Source .mp4 video file")
    parser.add_argument("--model", choices=MODELS, default=None, help="Whisper model size")
    parser.add_argument("--language", "-l", default=None, help="Source language (e.g., fr, en); leave empty for autodetect")
    parser.add_argument("--translate-to-en", action="store_true", help="Translate to English (via Whisper)")
    parser.add_argument("--no-clean", action="store_true", help="Keep intermediate .wav")
    parser.add_argument("--log", type=Path, default=None, help="Optional log file")
    args = parser.parse_args()

    if RICH_AVAILABLE:
        console.clear()
    print_banner("AutoGenSubTitles", "v1")
    start_time = datetime.datetime.now()

    try:
        video = args.video
        if not video.exists():
            raise FileNotFoundError(f"Video not found: {video}")
        basename = video.with_suffix("")
        wav = basename.with_suffix(".wav")
        srt_file = basename.with_suffix(".srt")

        # tool check
        ffmpeg_ok, whisper_ok = check_tools()
        if RICH_AVAILABLE:
            status = Table(show_header=False, box=None)
            status.add_column("Tool", style="bold")
            status.add_column("Status")
            status.add_row("ffmpeg", "[green]✓[/]" if ffmpeg_ok else "[red]✗[/]")
            status.add_row("whisper", "[green]✓[/]" if whisper_ok else "[red]✗[/]")
            console.print(Panel(status, title="Tool check", expand=False))
        else:
            print(f"ffmpeg: {'OK' if ffmpeg_ok else 'MISSING'}")
            print(f"whisper: {'OK' if whisper_ok else 'MISSING'}")

        if not (ffmpeg_ok and whisper_ok):
            print("[!] Missing required tool. Aborting.")
            sys.exit(1)

        # interactive choices
        model = args.model or ask_choice("Choose Whisper model size:", MODELS, "small")
        language = args.language
        if language is None:
            lang_input = input("Source audio language (e.g., en, fr, es) [auto-detect]: ").strip()
            if lang_input != "":
                language = lang_input
        translate_to_en = args.translate_to_en
        if not translate_to_en:
            translate_to_en = yes_no("Translate to English?", False)

        # summary
        if RICH_AVAILABLE:
            table = Table(title="Summary", expand=False)
            table.add_column("Key", style="bold")
            table.add_column("Value")
            table.add_row("Video", str(video))
            table.add_row("Whisper model", model)
            table.add_row("Source language", language or "Auto-detect")
            table.add_row("Mode", "Translate to English" if translate_to_en else "Transcribe only")
            table.add_row("Clean .wav", "no" if args.no_clean else "yes")
            table.add_row("Log", str(args.log) if args.log else "none")
            console.print(table)
        else:
            print(f"Video: {video}")
            print(f"Model: {model}")
            print(f"Source language: {language or 'auto'}")
            print(f"Mode: {'Translate to English' if translate_to_en else 'Transcribe only'}")
            print(f"Clean .wav: {'no' if args.no_clean else 'yes'}")
            if args.log:
                print(f"Log: {args.log}")

        if not yes_no("Start processing with these settings?", True):
            print("Cancelled.")
            sys.exit(0)

        # initial logging
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
                transient=true,
            ) as progress:
                t1 = progress.add_task("Extracting audio...", total=1)
                try:
                    extract_audio(video, wav)
                    progress.update(t1, advance=1, description="[green]Audio extracted")
                except Exception as e:
                    progress.stop()
                    console.print(f"[red][!] Audio extraction failed: {e}[/]")
                    sys.exit(1)

                t2 = progress.add_task("Running Whisper...", total=1)
                try:
                    run_whisper(wav, model, language, translate_to_en)
                    progress.update(t2, advance=1, description="[green]Whisper done")
                except Exception as e:
                    progress.update(t2, description="[red]Whisper failed")
                    console.print(f"[red][!] Whisper failed: {e}[/]")

                if not args.no_clean:
                    t3 = progress.add_task("Cleaning WAV...", total=1)
                    if wav.exists():
                        try:
                            wav.unlink()
                            progress.update(t3, advance=1, description="[green]WAV removed")
                        except Exception as e:
                            progress.update(t3, description=f"[red]Cleanup error: {e}")
        else:
            try:
                extract_audio(video, wav)
                print("[+] Audio extracted.")
            except Exception as e:
                print(f"[!] Audio extraction failed: {e}")
                sys.exit(1)
            try:
                run_whisper(wav, model, language, translate_to_en)
                print("[+] Whisper done.")
            except Exception as e:
                print(f"[!] Whisper failed: {e}")
            if not args.no_clean and wav.exists():
                try:
                    wav.unlink()
                    print("[+] WAV removed.")
                except Exception:
                    pass

        # final result
        detected_lang = find_detected_language(basename)
        end_time = datetime.datetime.now()
        duration_total = end_time - start_time

        # final banner
        print_banner("Success!", "✅")

        if RICH_AVAILABLE:
            result = Table(show_header=False)
            result.add_column("Key", style="bold")
            result.add_column("Value")
            result.add_row(".srt generated", str(srt_file) if srt_file.exists() else "[red]Not generated[/]")
            result.add_row("Detected language", detected_lang or "Unknown")
            result.add_row("Total duration", str(duration_total).split(".")[0])
            console.print(result)
            if not srt_file.exists():
                console.print("[yellow]Warning: .srt missing, check Whisper output.[/]")
        else:
            print(f".srt: {srt_file} {'(exists)' if srt_file.exists() else '(missing)'}")
            print(f"Detected language: {detected_lang or 'Unknown'}")
            print(f"Total time: {duration_total}")

        if args.log:
            with open(args.log, "a", encoding="utf-8") as lf:
                lf.write(f".srt exists: {srt_file.exists()}\n")
                lf.write(f"Detected lang: {detected_lang}\n")
                lf.write(f"Elapsed: {duration_total}\n")

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")
        sys.exit(1)
    except Exception as exc:
        print(f"[!] Fatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
