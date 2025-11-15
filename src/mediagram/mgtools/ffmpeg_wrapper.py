#!/usr/bin/env python3
"""
ffmpeg wrapper that outputs JSONL progress for tool integration.

Usage:
    mgtools.ffmpeg [ffmpeg args...]
"""

import json
import re
import subprocess
import sys


def emit_progress(msg_type: str, message: str, **kwargs):
    """Emit a JSONL progress line."""
    data = {
        "type": msg_type,
        "message": message,
        **kwargs,
    }
    print(json.dumps(data), flush=True)


def parse_duration(duration_str: str) -> float | None:
    """Parse duration string like '00:05:23.45' to seconds."""
    match = re.match(r"(\d+):(\d+):(\d+(?:\.\d+)?)", duration_str)
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return None


def parse_ffmpeg_progress(line: str, total_duration: float | None) -> dict | None:
    """Parse ffmpeg progress line."""
    time_match = re.search(r"time=(\d+:\d+:\d+\.\d+)", line)
    if not time_match:
        return None

    current_time = parse_duration(time_match.group(1))
    if current_time is None:
        return None

    progress_info = {"current_seconds": current_time}

    if total_duration and total_duration > 0:
        percent = (current_time / total_duration) * 100
        progress_info["percent"] = min(100, percent)
        remaining = total_duration - current_time
        progress_info["eta_seconds"] = max(0, remaining)

    speed_match = re.search(r"speed=\s*(\d+(?:\.\d+)?)x", line)
    if speed_match:
        speed = float(speed_match.group(1))
        progress_info["speed_multiplier"] = speed

    return progress_info


def extract_duration(stderr_lines: list[str]) -> float | None:
    """Extract total duration from ffmpeg stderr output."""
    for line in stderr_lines:
        match = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", line)
        if match:
            return parse_duration(match.group(1))
    return None


def main():
    if len(sys.argv) < 2:
        emit_progress("error", "No ffmpeg arguments provided")
        sys.exit(1)

    ffmpeg_args = sys.argv[1:]

    emit_progress("info", f"Running ffmpeg with {len(ffmpeg_args)} arguments")

    try:
        process = subprocess.Popen(
            ["ffmpeg"] + ffmpeg_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
        )

        stderr_buffer = []
        total_duration = None
        last_progress = {}

        while True:
            line = process.stderr.readline()
            if not line:
                break

            stderr_buffer.append(line)

            if total_duration is None and "Duration:" in line:
                total_duration = extract_duration([line])
                if total_duration:
                    emit_progress(
                        "info",
                        f"Processing video (duration: {total_duration:.1f}s)",
                        duration_seconds=total_duration,
                    )

            if "time=" in line:
                progress_info = parse_ffmpeg_progress(line, total_duration)
                if progress_info and progress_info != last_progress:
                    msg = f"Processing: {progress_info['current_seconds']:.1f}s"
                    if "percent" in progress_info:
                        msg += f" ({progress_info['percent']:.1f}%)"

                    emit_progress(
                        "progress",
                        msg,
                        percent=progress_info.get("percent"),
                        eta_seconds=progress_info.get("eta_seconds"),
                        current_seconds=progress_info["current_seconds"],
                    )
                    last_progress = progress_info

        returncode = process.wait()

        if returncode == 0:
            emit_progress("success", "FFmpeg completed successfully")
        else:
            error_lines = [
                line.strip()
                for line in stderr_buffer[-10:]
                if line.strip() and not line.startswith("frame=")
            ]
            error_details = "\n".join(error_lines[-5:])
            emit_progress(
                "error",
                f"FFmpeg failed with exit code {returncode}",
                error_details=error_details,
            )

        sys.exit(returncode)

    except FileNotFoundError:
        emit_progress(
            "error",
            "ffmpeg not found - please install ffmpeg",
            error_details="ffmpeg executable not found in PATH",
        )
        sys.exit(1)
    except Exception as e:
        emit_progress("error", f"Unexpected error: {e}", error_details=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
