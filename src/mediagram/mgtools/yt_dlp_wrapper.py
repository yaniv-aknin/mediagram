#!/usr/bin/env python3
"""
yt-dlp wrapper that outputs JSONL progress for tool integration.

Usage:
    mgtools.yt-dlp URL [options]
"""

import json
import sys
from pathlib import Path

import yt_dlp


def emit_progress(msg_type: str, message: str, **kwargs):
    """Emit a JSONL progress line."""
    data = {
        "type": msg_type,
        "message": message,
        **kwargs,
    }
    print(json.dumps(data), flush=True)


class ProgressHook:
    """Hook for yt-dlp progress callbacks."""

    def __init__(self):
        self.last_percent = None

    def __call__(self, d):
        if d["status"] == "downloading":
            percent_str = d.get("_percent_str", "").strip()
            if percent_str and percent_str != self.last_percent:
                try:
                    percent = float(percent_str.rstrip("%"))
                    eta_seconds = d.get("eta")

                    msg = f"Downloading: {percent_str}"
                    if eta_seconds:
                        msg += f" (ETA: {eta_seconds}s)"

                    emit_progress(
                        "progress",
                        msg,
                        percent=percent,
                        eta_seconds=eta_seconds,
                    )
                    self.last_percent = percent_str
                except (ValueError, TypeError):
                    pass

        elif d["status"] == "finished":
            filename = d.get("filename", "")
            emit_progress("info", f"Download finished: {Path(filename).name}")


def parse_args():
    """Parse command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(description="yt-dlp wrapper with JSONL progress")
    parser.add_argument("url", help="Video URL to download")
    parser.add_argument(
        "--output-dir", default=".", help="Output directory (default: current dir)"
    )
    parser.add_argument(
        "--format",
        default="best",
        choices=["best", "720p", "480p", "360p", "bestaudio"],
        help="Video quality/format",
    )
    parser.add_argument(
        "--extract",
        nargs="+",
        default=["video"],
        choices=["video", "audio", "subtitles"],
        help="What to extract",
    )
    parser.add_argument(
        "--subtitle-langs",
        nargs="+",
        help="Subtitle language codes (e.g., en he)",
    )
    parser.add_argument("--cookies", help="Path to cookies file")

    return parser.parse_args()


def build_format_string(format_choice: str) -> str:
    """Build yt-dlp format string from user choice."""
    format_map = {
        "best": "bestvideo+bestaudio/best",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "bestaudio": "bestaudio/best",
    }
    return format_map.get(format_choice, format_map["best"])


def main():
    args = parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    emit_progress("info", f"Downloading from: {args.url}")
    emit_progress("info", f"Output directory: {output_dir}")

    extract_set = set(args.extract)

    ydl_opts = {
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "progress_hooks": [ProgressHook()],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    if args.cookies and Path(args.cookies).exists():
        ydl_opts["cookiefile"] = args.cookies
        emit_progress("info", f"Using cookies from: {args.cookies}")

    if "video" in extract_set:
        ydl_opts["format"] = build_format_string(args.format)
        emit_progress("info", f"Video format: {args.format}")
    elif "audio" in extract_set:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            }
        ]
        emit_progress("info", "Extracting audio only")

    if "subtitles" in extract_set and args.subtitle_langs:
        ydl_opts["writesubtitles"] = True
        ydl_opts["subtitleslangs"] = args.subtitle_langs
        emit_progress(
            "info", f"Downloading subtitles: {', '.join(args.subtitle_langs)}"
        )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(args.url, download=True)
            title = info.get("title", "video")
            emit_progress("success", f"Successfully downloaded: {title}")
            sys.exit(0)

    except yt_dlp.utils.DownloadError as e:
        emit_progress("error", f"Download failed: {e}", error_details=str(e))
        sys.exit(1)
    except Exception as e:
        emit_progress("error", f"Unexpected error: {e}", error_details=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
