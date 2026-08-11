from pathlib import Path

from ..ffmpeg.executor import (
    get_duration,
    run_command,
)


def prepare_narration(
    input_file: Path,
    output_file: Path,
    speed: float,
) -> float:

    if not input_file.exists():

        raise FileNotFoundError(
            input_file
        )

    if speed <= 0:

        raise ValueError(
            "Audio speed must be > 0"
        )

    if speed == 1.0:

        # Convert sang WAV nhưng không đổi tốc độ
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_file),
            "-vn",
            "-c:a",
            "pcm_s16le",
            str(output_file),
        ]

    else:

        filters = []

        remaining = speed

        while remaining > 2.0:

            filters.append(
                "atempo=2.0"
            )

            remaining /= 2.0

        while remaining < 0.5:

            filters.append(
                "atempo=0.5"
            )

            remaining /= 0.5

        filters.append(
            f"atempo={remaining}"
        )

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_file),
            "-vn",
            "-filter:a",
            ",".join(filters),
            "-c:a",
            "pcm_s16le",
            str(output_file),
        ]

    run_command(
        command,
        "Preparing narration audio",
    )

    return get_duration(output_file)
