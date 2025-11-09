import asyncio
import json
import sys
from pathlib import Path

from ..callbacks import ProgressMessage, SuccessMessage, ErrorMessage
from . import tool, get_tool_subdir


async def run_jsonl_subprocess(cmd: list[str], tool_name: str, cwd: Path | None = None):
    """
    Run a subprocess that emits JSONL progress and yield appropriate messages.

    Expected JSONL format from subprocess:
    - {"type": "progress", "message": "...", "percent": 50, "eta_seconds": 30}
    - {"type": "success", "message": "..."}
    - {"type": "error", "message": "...", "error_details": "..."}
    - {"type": "info", "message": "..."}

    Yields:
        ProgressMessage, SuccessMessage, or ErrorMessage based on subprocess output
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )

        output_lines = []
        success_received = False

        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode().strip()
            if not line_str:
                continue

            try:
                data = json.loads(line_str)
                msg_type = data.get("type")
                message = data.get("message", "")

                if msg_type == "progress":
                    percent = data.get("percent")
                    eta_seconds = data.get("eta_seconds")
                    completion_ratio = percent / 100 if percent is not None else None
                    eta_minutes = eta_seconds / 60 if eta_seconds is not None else None

                    yield ProgressMessage(
                        text=message,
                        completion_ratio=completion_ratio,
                        completion_eta_minutes=eta_minutes,
                    )

                elif msg_type == "success":
                    success_received = True
                    yield SuccessMessage(text=message)

                elif msg_type == "error":
                    error_details = data.get("error_details", "")
                    full_message = f"{message}\n{error_details}" if error_details else message
                    yield ErrorMessage(text=full_message)
                    return

                elif msg_type == "info":
                    output_lines.append(message)

            except json.JSONDecodeError:
                output_lines.append(line_str)

        returncode = await process.wait()

        if success_received:
            return

        if returncode == 0:
            summary = "\n".join(output_lines[-5:]) if output_lines else f"{tool_name} completed successfully"
            yield SuccessMessage(text=summary)
        else:
            error_output = "\n".join(output_lines[-10:]) if output_lines else f"{tool_name} failed"
            yield ErrorMessage(text=f"{tool_name} failed with exit code {returncode}\n{error_output}")

    except FileNotFoundError:
        yield ErrorMessage(text=f"Error: {cmd[0]} not found - is it installed?")
    except Exception as e:
        yield ErrorMessage(text=f"Error running {tool_name}: {e}")


@tool
async def ffmpeg(args: list[str]):
    """Run ffmpeg with arbitrary arguments for media processing.

    This tool provides access to the full power of ffmpeg. You can use it to:
    - Convert between formats
    - Scale/resize videos
    - Extract audio
    - Add/burn subtitles
    - Trim/cut videos
    - Concatenate files
    - And much more

    Args:
        args: List of ffmpeg arguments (do NOT include 'ffmpeg' itself, just the args)

    Example args for common operations:
    - Scale video to 720p: ["-i", "input.mp4", "-vf", "scale=-2:720", "output.mp4"]
    - Extract audio: ["-i", "input.mp4", "-vn", "-acodec", "copy", "output.m4a"]
    - Burn subtitles: ["-i", "input.mp4", "-vf", "subtitles=subs.srt", "output.mp4"]
    - Convert format: ["-i", "input.webm", "-c", "copy", "output.mp4"]
    """
    tool_subdir = get_tool_subdir()
    if not tool_subdir:
        yield ErrorMessage(text="Error: No working directory configured")
        return

    cmd = [sys.executable, "-m", "mediagram.mgtools.ffmpeg_wrapper"] + args

    async for message in run_jsonl_subprocess(cmd, "ffmpeg", cwd=tool_subdir):
        yield message


@tool
async def youtube_download(
    url: str,
    format: str = "best",
    extract: list[str] | None = None,
    subtitle_langs: list[str] | None = None,
):
    """Download video, audio, and/or subtitles from YouTube or other supported sites.

    Args:
        url: The URL of the video to download
        format: Video quality/format - "best", "720p", "480p", "360p", or "bestaudio"
        extract: List of what to extract - can include "video", "audio", "subtitles"
        subtitle_langs: List of subtitle language codes to download (e.g., ["en", "he"])
    """
    if extract is None:
        extract = ["video"]

    tool_subdir = get_tool_subdir()
    if not tool_subdir:
        yield ErrorMessage(text="Error: No working directory configured")
        return

    cookies_file = Path.home() / ".mediagram.d" / "cookies.txt"

    cmd = [
        sys.executable,
        "-m",
        "mediagram.mgtools.yt_dlp_wrapper",
        url,
        "--output-dir",
        str(tool_subdir),
        "--format",
        format,
        "--extract",
    ] + list(extract)

    if subtitle_langs:
        cmd.extend(["--subtitle-langs"] + subtitle_langs)

    if cookies_file.exists():
        cmd.extend(["--cookies", str(cookies_file)])

    async for message in run_jsonl_subprocess(cmd, "youtube_download", cwd=tool_subdir):
        yield message
