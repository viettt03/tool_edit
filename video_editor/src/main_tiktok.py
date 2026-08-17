from pathlib import Path

from .audio.processor import prepare_narration_segment
from .config import VideoConfig
from .renderer.renderer import render_final_video
from .subtitle.srt import write_ass
from .subtitle.whisper import VietnameseWhisper
from .video.scanner import scan_videos
from .video.selector import select_videos


TIKTOK_START_SECONDS = 0.0
TIKTOK_MAX_DURATION_SECONDS = 5 * 60


def _remove_previous_tiktok_outputs(
    subtitle_file: Path,
    processed_audio: Path,
    final_video: Path,
) -> None:
    for artifact in (subtitle_file, processed_audio, final_video):
        if artifact.exists():
            artifact.unlink()


def main() -> None:
    config = VideoConfig(
        video_format="vertical",
        subtitle_file=Path("output/tiktok_subtitles.ass"),
        final_video=Path("output/tiktok_final.mp4"),
    )
    width, height = config.get_resolution()

    config.output_directory.mkdir(parents=True, exist_ok=True)
    processed_audio = config.output_directory / "tiktok_narration.wav"
    _remove_previous_tiktok_outputs(
        config.subtitle_file,
        processed_audio,
        config.final_video,
    )

    print("\n========================================")
    print("1. PREPARING TIKTOK AUDIO")
    print("========================================")
    narration_audio, duration = prepare_narration_segment(
        input_file=config.narration_audio,
        output_file=processed_audio,
        speed=config.audio_speed,
        start_seconds=TIKTOK_START_SECONDS,
        max_duration=TIKTOK_MAX_DURATION_SECONDS,
    )
    print(f"TikTok audio duration: {duration / 60:.2f} minutes")

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
    )

    print("\n========================================")
    print("3. SELECTING VERTICAL VIDEOS")
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
    print("4. RENDERING TIKTOK VIDEO")
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
    )

    print("\n========================================")
    print("DONE")
    print("========================================")
    print(f"Output: {config.final_video}")


if __name__ == "__main__":
    main()
