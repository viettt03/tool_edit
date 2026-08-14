from pathlib import Path

from ..ffmpeg.executor import (
    ffmpeg_binary,
    get_duration,
    run_command,
)


def _escape_filter_path(path: Path) -> str:
    """Escape a local path for FFmpeg filter arguments."""

    return (
        str(path.resolve())
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
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
        _escape_filter_path(subtitles)
    )

    video_filter = (
        f"subtitles=filename='{subtitle_path}'"
    )

    if music:

        command = [
            ffmpeg_binary(),
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
            ffmpeg_binary(),
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


def render_story_video(
    video: Path,
    narration: Path,
    music: Path | None,
    subtitles: Path | None,
    logo: Path | None,
    output: Path,
    width: int,
    height: int,
    duration: float,
    *,
    narration_volume: float = 1.0,
    music_volume: float = 0.10,
    codec: str = "libx264",
    audio_codec: str = "aac",
    crf: int = 22,
    preset: str = "veryfast",
    threads: int = 0,
) -> None:
    """Render a story video in the style of the supplied sample.

    The single Douyin source is looped from its first frame until the Vbee
    narration ends.  A blurred copy fills the canvas, the original video is
    kept in the centre with a subtle zoom, and optional logo/subtitle/waveform
    layers are added in the same FFmpeg pass.
    """

    if duration <= 0:
        raise ValueError("Video duration must be > 0")

    inputs = [
        "-stream_loop",
        "-1",
        "-i",
        str(video),
        "-i",
        str(narration),
    ]
    music_index: int | None = None
    logo_index: int | None = None
    next_index = 2
    if music:
        music_index = next_index
        inputs.extend(["-stream_loop", "-1", "-i", str(music)])
        next_index += 1
    if logo:
        logo_index = next_index
        inputs.extend(["-i", str(logo)])

    # The first layer is the enlarged/blurred source.  The second layer keeps
    # the original aspect ratio in the centre, which creates the two soft side
    # panels when the source is a vertical Douyin clip.
    filters = [
        (
            f"[0:v]fps=30,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "boxblur=luma_radius=24:luma_power=1,"
            "eq=brightness=-0.08[bg]"
        ),
        (
            "[0:v]fps=30,"
            f"scale=-2:{height}:force_original_aspect_ratio=decrease,"
            "scale=w='iw*1.06':h='ih*1.06',"
            "setsar=1[fg]"
        ),
        "[bg][fg]overlay=(W-w)/2:(H-h)/2:format=auto[canvas]",
    ]
    current_video = "canvas"

    if logo_index is not None:
        filters.extend(
            [
                f"[{logo_index}:v]scale=w='min(iw*0.24,{width // 2})':h=-1:force_original_aspect_ratio=decrease[logo]",
                f"[{current_video}][logo]overlay=W-w-42:42:format=auto[with_logo]",
            ]
        )
        current_video = "with_logo"

    # showwaves is keyed against black so only the white waveform remains.
    filters.extend(
        [
            (
                "[1:a]volume=6,showwaves="
                f"s={max(720, width - 520)}x140:mode=cline:colors=white:rate=30:"
                "scale=sqrt:draw=full,"
                "format=rgba,colorkey=black:0.12:0.08,"
                "colorchannelmixer=aa=0.72[wave]"
            ),
            f"[{current_video}][wave]overlay=(W-w)/2:(H-h)/2:format=auto[with_wave]",
        ]
    )
    current_video = "with_wave"

    if subtitles:
        subtitle_path = _escape_filter_path(subtitles)
        filters.append(
            (
                f"[{current_video}]subtitles=filename='{subtitle_path}':"
                "force_style='FontName=Arial,FontSize=30,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,"
                "Outline=3,Shadow=1,Alignment=2,MarginV=70'"
                "[vout]"
            )
        )
    else:
        filters.append(f"[{current_video}]null[vout]")

    if music_index is not None:
        filters.extend(
            [
                f"[1:a]volume={narration_volume}[voice]",
                f"[{music_index}:a]volume={music_volume}[music]",
                "[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            ]
        )
    else:
        filters.append(f"[1:a]volume={narration_volume}[aout]")

    command = [
        ffmpeg_binary(),
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-t",
        str(duration),
        "-c:v",
        codec,
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        audio_codec,
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
    ]
    if threads > 0:
        command.extend(["-threads", str(threads)])
    command.append(str(output))

    run_command(command, "Rendering story video")
