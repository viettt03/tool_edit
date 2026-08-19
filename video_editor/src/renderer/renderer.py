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
    subtitles: Path | None,
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
    logo: Path | None = None,
    blur_side_background: bool = False,
    blur_side_width_ratio: float = 0.10,
    subtitle_blur_background: bool = False,
    subtitle_blur_width_ratio: float = 0.86,
    subtitle_blur_height_ratio: float = 0.20,
    subtitle_blur_bottom_margin_ratio: float = 0.08,
) -> None:
    """Render clips, subtitles, narration, and music in one FFmpeg pass."""
    if not videos:
        raise ValueError("At least one video is required.")
    if not narration.exists():
        raise FileNotFoundError(narration)
    if subtitles is not None and not subtitles.exists():
        raise FileNotFoundError(subtitles)
    if music is not None and not music.exists():
        raise FileNotFoundError(music)
    if logo is not None and not logo.exists():
        raise FileNotFoundError(logo)
    if not 0 < blur_side_width_ratio <= 0.5:
        raise ValueError("blur_side_width_ratio must be between 0 and 0.5")
    if not 0 < subtitle_blur_width_ratio <= 1:
        raise ValueError("subtitle_blur_width_ratio must be between 0 and 1")
    if not 0 < subtitle_blur_height_ratio <= 0.5:
        raise ValueError("subtitle_blur_height_ratio must be between 0 and 0.5")
    if not 0 <= subtitle_blur_bottom_margin_ratio <= 0.5:
        raise ValueError("subtitle_blur_bottom_margin_ratio must be between 0 and 0.5")

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
    ]
    current_video = "vconcat"

    if blur_side_background:
        side_width = max(1, round(width * blur_side_width_ratio))
        blur_radius = max(2, min(16, side_width // 4))
        chroma_radius = max(1, blur_radius // 2)
        zoom_width = round(width * 1.25)
        zoom_height = round(height * 1.25)
        filters.extend(
            [
                f"[{current_video}]split=2[base][blurbase]",
                (
                    f"[blurbase]scale={zoom_width}:{zoom_height},"
                    f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2,"
                    "split=2[leftsrc][rightsrc]"
                ),
                (
                    f"[leftsrc]crop={side_width}:{height}:0:0,"
                    f"boxblur=luma_radius={blur_radius}:luma_power=1:"
                    f"chroma_radius={chroma_radius}:chroma_power=1[leftblur]"
                ),
                (
                    f"[rightsrc]crop={side_width}:{height}:{width - side_width}:0,"
                    f"boxblur=luma_radius={blur_radius}:luma_power=1:"
                    f"chroma_radius={chroma_radius}:chroma_power=1[rightblur]"
                ),
                "[base][leftblur]overlay=0:0[tmpblur]",
                "[tmpblur][rightblur]overlay=W-w:0[sideblur]",
            ]
        )
        current_video = "sideblur"

    if logo is not None:
        logo_index = video_count + 1 + (1 if music is not None else 0)
        logo_width = max(144, round(width * 0.24))
        logo_x = round(width * 0.035)
        logo_y = round(height * 0.025)
        filters.extend(
            [
                (
                    f"[{logo_index}:v]scale=w='min(iw,{logo_width})':h=-1:"
                    "force_original_aspect_ratio=decrease,format=rgba,"
                    "colorchannelmixer=aa=0.92[logo]"
                ),
                f"[{current_video}][logo]overlay={logo_x}:{logo_y}:format=auto[withlogo]",
            ]
        )
        current_video = "withlogo"

    if subtitles is not None and subtitle_blur_background:
        subtitle_bg_width = max(1, round(width * subtitle_blur_width_ratio))
        subtitle_bg_height = max(1, round(height * subtitle_blur_height_ratio))
        subtitle_bg_x = round((width - subtitle_bg_width) / 2)
        subtitle_bg_y = max(
            0,
            height
            - subtitle_bg_height
            - round(height * subtitle_blur_bottom_margin_ratio),
        )
        subtitle_blur_radius = max(2, min(18, subtitle_bg_height // 8))
        subtitle_chroma_radius = max(1, subtitle_blur_radius // 2)
        filters.extend(
            [
                f"[{current_video}]split=2[subbase][subsrc]",
                (
                    f"[subsrc]crop={subtitle_bg_width}:{subtitle_bg_height}:"
                    f"{subtitle_bg_x}:{subtitle_bg_y},"
                    f"boxblur=luma_radius={subtitle_blur_radius}:luma_power=1:"
                    f"chroma_radius={subtitle_chroma_radius}:chroma_power=1,"
                    "eq=brightness=-0.18:saturation=0.92[subblur]"
                ),
                f"[subbase][subblur]overlay={subtitle_bg_x}:{subtitle_bg_y}:format=auto[subbg]",
            ]
        )
        current_video = "subbg"

    if subtitles is not None:
        filters.append(
            (
                f"[{current_video}]subtitles=filename='{_escape_filter_path(subtitles)}'"
                ":charenc=UTF-8[vout]"
            )
        )
    else:
        filters.append(f"[{current_video}]null[vout]")

    filters.append(
        (
            f"[{narration_index}:a]volume={narration_volume},"
            "asetpts=PTS-STARTPTS[voice]"
        )
    )

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
    if logo is not None:
        input_args.extend(["-loop", "1", "-i", str(logo)])

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
