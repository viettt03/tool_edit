from pathlib import Path

from .audio.processor import prepare_narration
from .config import VideoConfig
from .renderer.renderer import render_final_video
from .subtitle.srt import write_ass
from .subtitle.whisper import VietnameseWhisper
from .video.scanner import scan_videos
from .video.selector import select_videos


def _remove_previous_outputs(config: VideoConfig, processed_audio: Path) -> None:
    """Remove only artifacts owned by this renderer, never the whole output folder."""
    legacy_intermediate = config.output_directory / "video.mp4"
    for artifact in (
        config.subtitle_file,
        processed_audio,
        legacy_intermediate,
        config.final_video,
    ):
        if artifact.exists():
            artifact.unlink()


def main() -> None:
    # Change settings in config.py; main deliberately does not override them.
    config = VideoConfig()
    width, height = config.get_resolution()

    config.output_directory.mkdir(parents=True, exist_ok=True)
    processed_audio = config.output_directory / "narration_processed.wav"
    _remove_previous_outputs(config, processed_audio)

    print("\n========================================")
    print("1. PREPARING AUDIO")
    print("========================================")
    narration_audio, duration = prepare_narration(
        config.narration_audio,
        processed_audio,
        config.audio_speed,
    )
    print(f"Audio duration: {duration / 60:.2f} minutes")

    print("\n========================================")
    print("2. SPEECH TO TEXT")
    print("========================================")
    whisper = VietnameseWhisper(
        model_name=config.whisper_model,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type,
        language=config.language,
        beam_size=config.whisper_beam_size,
    )
    segments = whisper.transcribe(narration_audio)
    write_ass(
        segments=segments,
        output=config.subtitle_file,
        width=width,
        height=height,
        max_words=config.subtitle_max_words,
        primary_colour="&H0030E6FF",
        secondary_colour="&H0030E6FF",
        outline_colour="&H002A6A25",
        back_colour="&H00000000",
        bold=1,
        border_style=1,
        outline=10,
        shadow=1,
    )

    print("\n========================================")
    print("3. SELECTING VIDEOS")
    print("========================================")
    videos = scan_videos(config.video_directory)
    print(f"Found {len(videos)} videos")
    selected = select_videos(
        videos,
        duration,
        randomize=config.randomize_videos,
        avoid_consecutive_duplicate=config.avoid_consecutive_duplicate,
    )
    print(f"Selected {len(selected)} clips")

    print("\n========================================")
    print("4. RENDERING FINAL VIDEO (ONE PASS)")
    print("========================================")
    render_final_video(
        videos=selected,
        narration=narration_audio,
        music=config.background_music,
        subtitles=config.subtitle_file,
        output=config.final_video,
        width=width,
        height=height,
        fps=config.fps,
        duration=duration,
        music_volume=config.music_volume,
        narration_volume=config.narration_volume,
        codec=config.video_codec,
        audio_codec=config.audio_codec,
        audio_bitrate=config.audio_bitrate,
        crf=config.crf,
        preset=config.preset,
        threads=config.threads,
        logo=config.logo_file if config.logo_file and config.logo_file.exists() else None,
        blur_side_background=config.blur_side_background,
        blur_side_width_ratio=config.blur_side_width_ratio,
        subtitle_blur_background=config.subtitle_blur_background,
        subtitle_blur_width_ratio=config.subtitle_blur_width_ratio,
        subtitle_blur_height_ratio=config.subtitle_blur_height_ratio,
        subtitle_blur_bottom_margin_ratio=config.subtitle_blur_bottom_margin_ratio,
    )

    print("\n========================================")
    print("DONE")
    print("========================================")
    print(f"Output: {config.final_video}")


if __name__ == "__main__":
    main()
