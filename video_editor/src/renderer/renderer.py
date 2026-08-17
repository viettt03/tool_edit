from pathlib import Path

from ..ffmpeg.executor import run_command
from ..video.processor import build_video_filter


def _escape_filter_path(path: Path) -> str:
    """Escape a path used inside an FFmpeg filter graph."""
    escaped = path.resolve().as_posix()
    for character in ("\\", ":", "'", ",", "[", "]"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _video_encoding_options(codec: str, preset: str, crf: int) -> list[str]:
    """Return quality options appropriate for the selected video encoder."""
    if codec == "h264_nvenc":
        # NVENC does not use x264's CRF option. p4 is a balanced speed/quality preset.
        nvenc_preset = preset if preset.startswith("p") else "p4"
        return [
            "-preset",
            nvenc_preset,
            "-rc",
            "vbr",
            "-cq",
            str(crf),
            "-b:v",
            "0",
        ]

    return ["-preset", preset, "-crf", str(crf)]


def render_final_video(
    videos: list[Path],
    narration: Path,
    music: Path | None,
    subtitles: Path,
    output: Path,
    width: int,
    height: int,
    fps: int,
    duration: float,
    music_volume: float,
    narration_volume: float,
    codec: str,
    audio_codec: str,
    audio_bitrate: str,
    crf: int,
    preset: str,
    threads: int = 0,
) -> None:
    """Render clips, subtitles, narration, and music in one FFmpeg pass."""
    if not videos:
        raise ValueError("At least one video is required.")
    if not narration.exists():
        raise FileNotFoundError(narration)
    if not subtitles.exists():
        raise FileNotFoundError(subtitles)
    if music is not None and not music.exists():
        raise FileNotFoundError(music)

    output.parent.mkdir(parents=True, exist_ok=True)
    video_count = len(videos)
    narration_index = video_count

    filters = [
        build_video_filter(
            count=video_count,
            width=width,
            height=height,
            fps=fps,
            output_label="vconcat",
        ),
        (
            f"[vconcat]subtitles=filename='{_escape_filter_path(subtitles)}'"
            ":charenc=UTF-8[vout]"
        ),
        (
            f"[{narration_index}:a]volume={narration_volume},"
            "asetpts=PTS-STARTPTS[voice]"
        ),
    ]

    if music is not None:
        music_index = narration_index + 1
        filters.extend(
            [
                (
                    f"[{music_index}:a]volume={music_volume},"
                    "asetpts=PTS-STARTPTS[music]"
                ),
                (
                    "[voice][music]amix=inputs=2:duration=first:"
                    "dropout_transition=2[aout]"
                ),
            ]
        )
    else:
        filters.append("[voice]anull[aout]")

    input_args: list[str] = []
    for video in videos:
        input_args.extend(["-i", str(video)])
    input_args.extend(["-i", str(narration)])
    if music is not None:
        input_args.extend(["-stream_loop", "-1", "-i", str(music)])

    command = ["ffmpeg", "-y"]
    if threads > 0:
        command.extend(
            ["-threads", str(threads), "-filter_complex_threads", str(threads)]
        )

    command.extend(
        [
            *input_args,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            codec,
            *_video_encoding_options(codec, preset, crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            audio_codec,
            "-b:a",
            audio_bitrate,
            "-movflags",
            "+faststart",
            str(output),
        ]
    )

    run_command(command, "Rendering final video (one pass)")
