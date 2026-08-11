from pathlib import Path

from .config import VideoConfig

from .audio.processor import (
    prepare_narration,
)

from .subtitle.whisper import (
    VietnameseWhisper,
)

from .subtitle.srt import (
    write_srt,
)

from .video.scanner import (
    scan_videos,
)

from .video.selector import (
    select_videos,
)

from .video.processor import (
    render_video_sequence,
)

from .renderer.renderer import (
    render_final_video,
)


def main():

    # ==================================================
    # CONFIG
    # ==================================================

    config = VideoConfig(

        narration_audio=Path(
            "input/narration.mp3"
        ),

        background_music=Path(
            "input/music.mp3"
        ),

        video_directory=Path(
            "input/videos"
        ),

        # ------------------------------------------
        # Audio speed
        # ------------------------------------------

        audio_speed=1.0,

        # ------------------------------------------
        # Video format
        # ------------------------------------------

        # vertical
        # horizontal

        video_format="vertical",

        # ------------------------------------------
        # Audio
        # ------------------------------------------

        narration_volume=1.0,

        music_volume=0.12,

        # ------------------------------------------
        # Whisper CPU
        # ------------------------------------------

        whisper_model="small",

        whisper_device="cpu",

        whisper_compute_type="int8",

        # ------------------------------------------
        # FFmpeg CPU
        # ------------------------------------------

        video_codec="libx264",

        audio_codec="aac",

        crf=22,

        preset="veryfast",

        threads=0,
    )

    # ==================================================
    # CREATE OUTPUT DIRECTORY
    # ==================================================

    config.output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ==================================================
    # 1. PREPARE AUDIO
    # ==================================================

    print(
        "\n"
        "========================================\n"
        "1. PREPARING AUDIO\n"
        "========================================"
    )

    processed_audio = (
        config.output_directory
        / "narration_processed.wav"
    )

    duration = prepare_narration(
        config.narration_audio,
        processed_audio,
        config.audio_speed,
    )

    print(
        f"Audio duration: "
        f"{duration / 60:.2f} minutes"
    )

    # ==================================================
    # 2. SPEECH TO TEXT
    # ==================================================

    print(
        "\n"
        "========================================\n"
        "2. SPEECH TO TEXT\n"
        "========================================"
    )

    whisper = VietnameseWhisper(
        model_name=config.whisper_model,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type,
    )

    segments = whisper.transcribe(
        processed_audio
    )

    write_srt(
        segments,
        config.subtitle_file,
        config.subtitle_max_chars,
    )

    # ==================================================
    # 3. SCAN VIDEOS
    # ==================================================

    print(
        "\n"
        "========================================\n"
        "3. SCANNING VIDEOS\n"
        "========================================"
    )

    videos = scan_videos(
        config.video_directory
    )

    print(
        f"Found {len(videos)} videos"
    )

    # ==================================================
    # 4. SELECT VIDEOS
    # ==================================================

    print(
        "\n"
        "========================================\n"
        "4. SELECTING VIDEOS\n"
        "========================================"
    )

    selected = select_videos(
        videos,
        duration,
        randomize=config.randomize_videos,
        avoid_consecutive_duplicate=(
            config.avoid_consecutive_duplicate
        ),
    )

    print(
        f"Selected {len(selected)} clips"
    )

    # ==================================================
    # 5. VIDEO RENDER
    # ==================================================

    print(
        "\n"
        "========================================\n"
        "5. RENDERING VIDEO\n"
        "========================================"
    )

    width, height = (
        config.get_resolution()
    )

    video_only = (
        config.output_directory
        / "video.mp4"
    )

    render_video_sequence(
        videos=selected,

        output=video_only,

        width=width,

        height=height,

        fps=config.fps,

        duration=duration,

        codec=config.video_codec,

        preset=config.preset,

        crf=config.crf,

        threads=config.threads,
    )

    # ==================================================
    # 6. FINAL RENDER
    # ==================================================

    print(
        "\n"
        "========================================\n"
        "6. FINAL RENDER\n"
        "========================================"
    )

    render_final_video(
        video=video_only,

        narration=processed_audio,

        music=config.background_music,

        subtitles=config.subtitle_file,

        output=config.final_video,

        music_volume=config.music_volume,

        narration_volume=config.narration_volume,

        codec=config.video_codec,

        audio_codec=config.audio_codec,

        crf=config.crf,

        preset=config.preset,

        threads=config.threads,
    )

    # ==================================================
    # DONE
    # ==================================================

    print(
        "\n"
        "========================================\n"
        "DONE\n"
        "========================================"
    )

    print(
        f"Output: {config.final_video}"
    )


if __name__ == "__main__":
    main()
