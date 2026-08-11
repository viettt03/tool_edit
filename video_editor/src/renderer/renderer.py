from pathlib import Path

from ..ffmpeg.executor import (
    get_duration,
    run_command,
)


def render_final_video(
    video: Path,
    narration: Path,
    music: Path | None,
    subtitles: Path,
    output: Path,
    music_volume: float,
    narration_volume: float,
    codec: str,
    audio_codec: str,
    crf: int,
    preset: str,
    threads: int = 0,
) -> None:

    duration = get_duration(
        narration
    )

    subtitle_path = (
        str(subtitles.resolve())
        .replace("\\", "/")
        .replace(":", "\\:")
    )

    video_filter = (
        f"subtitles='{subtitle_path}'"
    )

    if music:

        command = [
            "ffmpeg",
            "-y",

            "-i",
            str(video),

            "-i",
            str(narration),

            "-stream_loop",
            "-1",

            "-i",
            str(music),

            "-filter_complex",

            (
                f"[1:a]"
                f"volume={narration_volume}"
                "[voice];"

                f"[2:a]"
                f"volume={music_volume}"
                "[music];"

                "[voice][music]"
                "amix=inputs=2:"
                "duration=first:"
                "dropout_transition=2"
                "[aout]"
            ),

            "-map",
            "0:v:0",

            "-map",
            "[aout]",

            "-vf",
            video_filter,

            "-t",
            str(duration),

            "-c:v",
            codec,

            "-preset",
            preset,

            "-crf",
            str(crf),

            "-c:a",
            audio_codec,

            "-b:a",
            "192k",

            "-movflags",
            "+faststart",
        ]

    else:

        command = [
            "ffmpeg",
            "-y",

            "-i",
            str(video),

            "-i",
            str(narration),

            "-map",
            "0:v:0",

            "-map",
            "1:a:0",

            "-vf",
            video_filter,

            "-t",
            str(duration),

            "-c:v",
            codec,

            "-preset",
            preset,

            "-crf",
            str(crf),

            "-c:a",
            audio_codec,

            "-b:a",
            "192k",

            "-movflags",
            "+faststart",
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
        "Rendering final video",
    )
