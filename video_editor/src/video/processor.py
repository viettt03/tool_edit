from pathlib import Path

from ..ffmpeg.executor import ffmpeg_binary, run_command


def build_video_filter(
    count: int,
    width: int,
    height: int,
    fps: int,
    output_label: str = "video",
) -> str:
    """Normalize and concatenate video inputs in a single filter graph."""
    if count < 1:
        raise ValueError("At least one video is required.")

    filters: list[str] = []
    for index in range(count):
        filters.append(
            f"[{index}:v]"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={fps},setsar=1,format=yuv420p,"
            f"setpts=PTS-STARTPTS[v{index}]"
        )

    concat_inputs = "".join(f"[v{index}]" for index in range(count))
    filters.append(f"{concat_inputs}concat=n={count}:v=1:a=0[{output_label}]")
    return ";".join(filters)


def build_filter(
    count: int,
    width: int,
    height: int,
    fps: int,
    output_label: str = "video",
) -> str:
    return build_video_filter(count, width, height, fps, output_label)


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
        output_label="vout",
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

        "-pix_fmt",
        "yuv420p",
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
