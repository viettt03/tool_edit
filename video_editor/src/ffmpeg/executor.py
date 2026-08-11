import json
import subprocess
from pathlib import Path


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
