import json
import subprocess
import sys
from pathlib import Path


def _print_safely(message: str) -> None:
    """Keep logging from crashing on legacy Windows console encodings."""
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        print(message.encode(encoding, errors="backslashreplace").decode(encoding))


def run_command(
    command: list[str],
    description: str = "",
) -> None:

    if description:
        _print_safely(f"\n> {description}")

    _print_safely(
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
        encoding="utf-8",
        errors="replace",
    )

    if process.returncode != 0:
        _print_safely("\nFFmpeg ERROR:")
        _print_safely(process.stderr)
        raise RuntimeError(
            f"FFmpeg command failed "
            f"with exit code {process.returncode}"
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
        encoding="utf-8",
        errors="replace",
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
