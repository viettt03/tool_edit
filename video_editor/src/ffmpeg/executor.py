import json
import os
import shutil
import subprocess
from pathlib import Path


def ffmpeg_binary() -> str:
    """Prefer the Homebrew full build, which includes libass subtitles."""

    configured = os.environ.get("FFMPEG_BINARY")
    if configured:
        return configured

    full_build = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    if full_build.is_file():
        return str(full_build)

    return shutil.which("ffmpeg") or "ffmpeg"


def run_command(
    command: list[str],
    description: str = "",
) -> None:

    if description:
        print(f"\n▶ {description}")

    print(
        " ".join(
            f'"{x}"' if " " in x else x
            for x in command
        )
    )

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if process.returncode != 0:

        print(process.stderr)

        raise RuntimeError(
            f"FFmpeg command failed."
        )


def get_duration(
    file: Path,
) -> float:

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(file),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    data = json.loads(
        result.stdout
    )

    return float(
        data["format"]["duration"]
    )


def get_video_duration(
    file: Path,
) -> float:

    return get_duration(file)
