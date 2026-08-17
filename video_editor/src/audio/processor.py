from pathlib import Path

from ..ffmpeg.executor import (
    get_duration,
    run_command,
)


def prepare_narration(
    input_file: Path,
    output_file: Path,
    speed: float,
) -> tuple[Path, float]:
    """Return the narration file to use and its duration.

    No intermediate file is needed when playback speed is unchanged. Faster
    Whisper can decode the source audio directly, which saves a full pass of
    disk I/O and keeps the original narration available for the final mix.
    """

    if not input_file.exists():

        raise FileNotFoundError(
            input_file
        )

    if speed <= 0:

        raise ValueError(
            "Audio speed must be > 0"
        )

    if speed == 1.0:
        print("Narration speed is 1.0; reusing the source audio.")
        return input_file, get_duration(input_file)

    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining}")

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

    return output_file, get_duration(output_file)


def prepare_narration_segment(
    input_file: Path,
    output_file: Path,
    speed: float,
    start_seconds: float,
    max_duration: float,
) -> tuple[Path, float]:
    """Create a narration segment for short-form renders."""

    if not input_file.exists():
        raise FileNotFoundError(input_file)

    if speed <= 0:
        raise ValueError("Audio speed must be > 0")

    if start_seconds < 0:
        raise ValueError("Audio segment start must be >= 0")

    if max_duration <= 0:
        raise ValueError("Audio segment duration must be > 0")

    source_duration = get_duration(input_file)
    if start_seconds >= source_duration:
        raise ValueError(
            "Audio segment start is beyond the narration duration: "
            f"{start_seconds:.2f}s >= {source_duration:.2f}s"
        )

    segment_duration = min(max_duration, source_duration - start_seconds)

    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    if speed != 1.0:
        filters.append(f"atempo={remaining}")

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-t",
        f"{segment_duration:.3f}",
        "-i",
        str(input_file),
        "-vn",
    ]

    if filters:
        command.extend(["-filter:a", ",".join(filters)])

    command.extend(
        [
            "-c:a",
            "pcm_s16le",
            str(output_file),
        ]
    )

    run_command(command, "Preparing TikTok narration segment")

    return output_file, get_duration(output_file)
