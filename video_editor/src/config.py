from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoConfig:

    # =========================
    # INPUT
    # =========================

    narration_audio: Path = Path(
        "input/narration.mp3"
    )

    background_music: Path | None = Path(
        "input/music.mp3"
    )

    video_directory: Path = Path(
        "input/videos"
    )

    # =========================
    # OUTPUT
    # =========================

    output_directory: Path = Path(
        "output"
    )

    subtitle_file: Path = Path(
        "output/subtitles.srt"
    )

    final_video: Path = Path(
        "output/final.mp4"
    )

    # =========================
    # AUDIO
    # =========================

    audio_speed: float = 1.3

    narration_volume: float = 1.5

    music_volume: float = 0.5

    # =========================
    # VIDEO
    # =========================

    video_format: str = "horizontal"

    fps: int = 30

    # =========================
    # WHISPER - CPU
    # =========================

    whisper_model: str = "small"

    whisper_device: str = "cpu"

    whisper_compute_type: str = "int8"

    language: str = "vi"

    # =========================
    # SUBTITLE
    # =========================

    subtitle_max_chars: int = 42

    # =========================
    # VIDEO SELECTION
    # =========================

    randomize_videos: bool = True

    avoid_consecutive_duplicate: bool = True

    # =========================
    # FFMPEG CPU ENCODING
    # =========================

    video_codec: str = "libx264"

    audio_codec: str = "aac"

    crf: int = 22

    preset: str = "veryfast"

    # Number of FFmpeg CPU threads
    threads: int = 0

    def get_resolution(self) -> tuple[int, int]:

        if self.video_format == "vertical":
            return 1080, 1920

        if self.video_format == "horizontal":
            return 1920, 1080

        raise ValueError(
            f"Unsupported video format: "
            f"{self.video_format}"
        )
