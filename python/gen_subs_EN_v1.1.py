#!/usr/bin/env python3
import argparse
import datetime
import json
import logging
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

# Optional UI
try:
    import pyfiglet
    FIGLET_AVAILABLE = True
except ImportError:
    FIGLET_AVAILABLE = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import (
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeElapsedColumn,
        Progress,
    )
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

MODELS = ["tiny", "base", "small", "medium", "large"]
WHISPER_EXTS = [".srt", ".json", ".tsv", ".txt", ".vtt"]  # expected outputs
BANNER_COLORS = ["magenta", "cyan", "green", "yellow", "blue", "red", "bright_blue", "bright_magenta"]

@dataclass
class RunResult:
    video: Path
    wav: Path
    srt: Path
    detected_language: Optional[str]
    duration: datetime.timedelta
    whisper_succeeded: bool

def setup_logger(log_path: Optional[Path]) -> logging.Logger:
    logger = logging.getLogger("AutoGenSubTitles")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    if log_path:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.debug("Logging to file: %s", log_path)
    return logger

def random_banner_color() -> str:
    return random.choice(BANNER_COLORS)

def print_banner(title: str, subtitle: Optional[str], logger: logging.Logger):
    color = random_banner_color()
    if RICH_AVAILABLE and console:
        if FIGLET_AVAILABLE:
            fig = pyfiglet.figlet_format(title, font="slant")
            console.print(Panel(Text(fig, justify="center"), style=f"bold {color}", subtitle=subtitle or ""))
        else:
            console.print(Panel(f"[bold {color}]{title}[/]", title=subtitle or "", style=color))
    else:
        logger.info("=== %s === %s", title, subtitle or "")

def ask_choice(prompt: str, options: list[str], default: str) -> str:
    if RICH_AVAILABLE and console:
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
            print("Invalid choice.")

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

def run_cmd_streamed(cmd, logger: logging.Logger):
    if isinstance(cmd, (list, tuple)):
        display = " ".join(cmd)
    else:
        display = str(cmd)
    logger.debug("Executing: %s", display)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout
    for line in process.stdout:
        logger.info(line.rstrip())
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"Command failed ({display}) exit={process.returncode}")

def extract_audio(video_path: Path, wav_path: Path, logger: logging.Logger):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le",
        str(wav_path),
    ]
    logger.debug("Running FFmpeg: %s", " ".join(cmd))
    run_cmd_streamed(cmd, logger)

def run_whisper(wav_path: Path, model: str, language: Optional[str], translate: bool, logger: logging.Logger):
    task = "translate" if translate else "transcribe"
    cmd = ["whisper", str(wav_path), "--model", model, "--task", task]
    if language:
        cmd += ["--language", language]
    logger.debug("Running Whisper: %s", " ".join(cmd))
    run_cmd_streamed(cmd, logger)

def move_whisper_outputs(video_base: Path, target_dir: Path, logger: logging.Logger):
    stem = video_base.stem
    for ext in WHISPER_EXTS:
        src = Path(f"{stem}{ext}")
        if src.exists():
            dest = target_dir / src.name
            try:
                src.replace(dest)
                logger.debug("Moved %s -> %s", src, dest)
            except Exception as e:
                logger.warning("Could not move %s to %s: %s", src, dest, e)

def move_video_into_dir(video: Path, target_dir: Path, logger: logging.Logger) -> Path:
    dest = target_dir / video.name
    if dest.exists():
        base = video.stem
        suffix = video.suffix
        i = 1
        while True:
            candidate = target_dir / f"{base}_{i}{suffix}"
            if not candidate.exists():
                dest = candidate
                break
            i += 1
    try:
        shutil.move(str(video), str(dest))
        logger.debug("Moved video %s -> %s", video, dest)
        return dest
    except Exception as e:
        logger.warning("Failed to move video %s to %s: %s", video, dest, e)
        return video  # fallback original

def find_detected_language(srt_base: Path, logger: logging.Logger) -> Optional[str]:
    json_path = srt_base.with_suffix(".json")
    if not json_path.exists():
        return None
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("language") or data.get("language_detected") or None
    except Exception:
        return None

def check_tools() -> Tuple[bool, bool]:
    import shutil
    return shutil.which("ffmpeg") is not None, shutil.which("whisper") is not None

def process_video(
    video: Path,
    model: str,
    language: Optional[str],
    translate_to_en: bool,
    clean_wav: bool,
    overwrite: bool,
    skip_if_exists: bool,
    logger: logging.Logger,
    out_dir: Path,
) -> RunResult:
    base = video.with_suffix("")  # original base in cwd (for whisper outputs)
    wav = out_dir / f"{video.stem}.wav"
    srt = out_dir / f"{video.stem}.srt"

    # skip / overwrite logic
    if srt.exists():
        if skip_if_exists:
            logger.info(".srt exists and skip_if_exists enabled, skipping Whisper step.")
            detected = find_detected_language(out_dir / video.stem, logger)
            return RunResult(video=video, wav=wav, srt=srt, detected_language=detected, duration=datetime.timedelta(0), whisper_succeeded=True)
        if not overwrite:
            logger.info(".srt exists and overwrite disabled, skipping Whisper step.")
            detected = find_detected_language(out_dir / video.stem, logger)
            return RunResult(video=video, wav=wav, srt=srt, detected_language=detected, duration=datetime.timedelta(0), whisper_succeeded=True)

    extract_audio(video, wav, logger)
    logger.info("WAV file location: %s (exists: %s)", wav.resolve(), wav.exists())

    try:
        run_whisper(wav, model, language, translate_to_en, logger)
        whisper_ok = True
    except Exception as e:
        logger.error("Whisper failed: %s", e)
        whisper_ok = False

    # move whisper outputs from cwd into out_dir
    move_whisper_outputs(base, out_dir, logger)

    if clean_wav and wav.exists():
        try:
            wav.unlink()
            logger.debug("Temporary WAV removed.")
        except Exception as e:
            logger.warning("Failed to remove WAV: %s", e)

    detected = find_detected_language(out_dir / video.stem, logger)
    return RunResult(video=video, wav=wav, srt=srt, detected_language=detected, duration=datetime.timedelta(0), whisper_succeeded=whisper_ok)

def main():
    parser = argparse.ArgumentParser(description="AutoGenSubTitles – Whisper + FFmpeg transcription/translation")
    parser.add_argument("video", type=Path, help="Source video file (.mp4)")
    parser.add_argument("--model", choices=MODELS, default=None, help="Whisper model size")
    parser.add_argument("--language", "-l", default=None, help="Source audio language (e.g. fr, en); empty = autodetect")
    parser.add_argument("--translate-to-en", action="store_true", help="Translate to English")
    parser.add_argument("--no-clean", action="store_true", help="Do not remove intermediate .wav (default is to clean)")
    parser.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing .srt (default is overwrite)")
    parser.add_argument("--no-skip", action="store_true", help="Do not skip if .srt exists (default is skip)")
    parser.add_argument("--log", type=Path, default=None, help="Log file path")
    args = parser.parse_args()

    logger = setup_logger(args.log)
    start_time = datetime.datetime.now()

    if RICH_AVAILABLE and console:
        console.clear()
    print_banner("AutoGenSubTitles", "v1.1", logger)

    try:
        video = args.video
        if not video.exists():
            logger.error("Video not found: %s", video)
            sys.exit(1)

        model = args.model or ask_choice("Choose Whisper model size:", MODELS, "small")
        language = args.language
        if language is None:
            lang_input = input("Source audio language (e.g., en, fr, es) [auto-detect]: ").strip()
            if lang_input:
                language = lang_input

        # output folder
        if not sys.stdin.isatty():
            out_dir = Path.cwd() / video.stem
        else:
            name = input(f"Output folder name (default: '{video.stem}'): ").strip() or video.stem
            out_dir = Path.cwd() / name
        out_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Output folder: %s", out_dir.resolve())

        # interactive choices (after folder)
        clean_wav = yes_no("Clean .wav after run?", True) if sys.stdin.isatty() else not args.no_clean
        overwrite = not args.no_overwrite
        skip_if_exists = not args.no_skip

        # translate prompt if not provided
        translate_to_en = args.translate_to_en or (yes_no("Translate to English?", False) if sys.stdin.isatty() else False)

        # summary of choices
        if RICH_AVAILABLE and console:
            conf = Table(title="Configuration", expand=False)
            conf.add_column("Key", style="bold")
            conf.add_column("Value")
            conf.add_row("Video", str(video))
            conf.add_row("Whisper model", model)
            conf.add_row("Source language", language or "Auto-detect")
            conf.add_row("Translate to English", "yes" if translate_to_en else "no")
            conf.add_row("Clean .wav", "yes" if clean_wav else "no")
            conf.add_row("Overwrite .srt", "yes" if overwrite else "no")
            conf.add_row("Skip if .srt exists", "yes" if skip_if_exists else "no")
            conf.add_row("Output directory", str(out_dir.resolve()))
            console.print(conf)
        else:
            logger.info("Video: %s", video)
            logger.info("Model: %s", model)
            logger.info("Language: %s", language or "auto")
            logger.info("Translate to English: %s", translate_to_en)
            logger.info("Clean WAV: %s", clean_wav)
            logger.info("Overwrite SRT: %s", overwrite)
            logger.info("Skip if exists: %s", skip_if_exists)
            logger.info("Output directory: %s", out_dir.resolve())

        if not yes_no("Start processing?", True):
            logger.info("Cancelled.")
            sys.exit(0)

        ffmpeg_ok, whisper_ok = check_tools()
        if RICH_AVAILABLE and console:
            status = Table(show_header=False, box=None)
            status.add_column("Tool", style="bold")
            status.add_column("Status")
            status.add_row("ffmpeg", "[green]✓[/]" if ffmpeg_ok else "[red]✗[/]")
            status.add_row("whisper", "[green]✓[/]" if whisper_ok else "[red]✗[/]")
            console.print(Panel(status, title="Tool check", expand=False))
        else:
            logger.info("ffmpeg: %s", "OK" if ffmpeg_ok else "MISSING")
            logger.info("whisper: %s", "OK" if whisper_ok else "MISSING")

        if not (ffmpeg_ok and whisper_ok):
            logger.error("Missing tool(s), aborting.")
            sys.exit(1)

        if RICH_AVAILABLE and console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                transient=True,
            ) as progress:
                task = progress.add_task("Processing...", total=None)
                result = process_video(
                    video=video,
                    model=model,
                    language=language,
                    translate_to_en=translate_to_en,
                    clean_wav=clean_wav,
                    overwrite=overwrite,
                    skip_if_exists=skip_if_exists,
                    logger=logger,
                    out_dir=out_dir,
                )
                progress.update(task, description="[green]Done")
        else:
            result = process_video(
                video=video,
                model=model,
                language=language,
                translate_to_en=translate_to_en,
                clean_wav=clean_wav,
                overwrite=overwrite,
                skip_if_exists=skip_if_exists,
                logger=logger,
                out_dir=out_dir,
            )

        # move video into output directory (after processing)
        new_video_path = move_video_into_dir(video, out_dir, logger)
        if new_video_path != video:
            result.video = new_video_path  # update if moved

        end_time = datetime.datetime.now()
        total_duration = end_time - start_time
        result.duration = total_duration

        print_banner("Result", "OK!", logger)
        if RICH_AVAILABLE and console:
            final = Table(show_header=False)
            final.add_column("Key", style="bold")
            final.add_column("Value")
            final.add_row(".srt", str(result.srt) if result.srt.exists() else "[red]Missing[/]")
            final.add_row("Detected language", result.detected_language or "Unknown")
            final.add_row("Whisper succeeded", "Yes" if result.whisper_succeeded else "No")
            final.add_row("Video location", str(result.video))
            final.add_row("Total duration", str(total_duration).split(".")[0])
            console.print(final)
        else:
            logger.info(".srt: %s", f"{result.srt} (exists)" if result.srt.exists() else f"{result.srt} (missing)")
            logger.info("Detected language: %s", result.detected_language or "Unknown")
            logger.info("Whisper succeeded: %s", result.whisper_succeeded)
            logger.info("Video location: %s", result.video)
            logger.info("Total duration: %s", total_duration)

    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        sys.exit(1)

if __name__ == "__main__":
    main()
