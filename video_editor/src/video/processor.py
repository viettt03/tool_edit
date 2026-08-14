from pathlib import Path

from ..ffmpeg.executor import ffmpeg_binary, run_command


def build_filter(
    count: int,
    width: int,
    height: int,
    fps: int,
) -> str:

    filters = []

    for i in range(count):

        filters.append(
            f"[{i}:v]"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},"
            "setsar=1,"
            f"setpts=PTS-STARTPTS"
            f"[v{i}]"
        )

    concat_inputs = "".join(
        f"[v{i}]"
        for i in range(count)
    )

    filters.append(
        f"{concat_inputs}"
        f"concat=n={count}:v=1:a=0"
        "[vout]"
    )

    return ";".join(filters)


def render_video_sequence(
    videos: list[Path],
    output: Path,
    width: int,
    height: int,
    fps: int,
    duration: float,
    codec: str,
    preset: str,
    crf: int,
    threads: int = 0,
) -> None:

    inputs = []

    for video in videos:

        inputs.extend(
            [
                "-i",
                str(video),
            ]
        )

    filter_complex = build_filter(
        len(videos),
        width,
        height,
        fps,
    )

    command = [
        ffmpeg_binary(),
        "-y",
        *inputs,

        "-filter_complex",
        filter_complex,

        "-map",
        "[vout]",

        "-t",
        str(duration),

        "-an",

        "-c:v",
        codec,

        "-preset",
        preset,

        "-crf",
        str(crf),
    ]

    if threads > 0:

        command.extend(
            [
                "-threads",
                str(threads),
            ]
        )

    command.append(
        str(output)
    )

    run_command(
        command,
        "Rendering video sequence",
    )
