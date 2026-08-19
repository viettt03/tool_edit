from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoConfig:
    """All user-editable settings for a render."""

    # INPUT
    # narration_audio: Path = Path("input/narration.mp3")
    narration_audio: Path = Path("input/narration.wav")
    background_music: Path | None = Path("input/music1.mp3")
    video_directory: Path = Path("input/videos")
    logo_file: Path | None = Path("input/logo.png")

    # OUTPUT
    output_directory: Path = Path("output")
    subtitle_file: Path = Path("output/subtitles.ass")
    final_video: Path = Path("output/final.mp4")

    # AUDIO
    # Keep 1.0 for a natural voice. Values above 1.0 make the narration faster.
    audio_speed: float = 1.0
    narration_volume: float = 1.0
    music_volume: float = 0.25

    # VIDEO
    video_format: str = "horizontal"  # "vertical" or "horizontal"
    fps: int = 30
    blur_side_background: bool = True
    blur_side_width_ratio: float = 0.05
    subtitle_blur_background: bool = False
    subtitle_blur_width_ratio: float = 0.86
    subtitle_blur_height_ratio: float = 0.20
    subtitle_blur_bottom_margin_ratio: float = 0.08

    # WHISPER
    # "small" gives dependable Vietnamese subtitles. Use "base" for faster CPU runs.
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_beam_size: int = 3
    language: str = "vi"

    # SUBTITLE
    subtitle_max_words: int = 15

    # VIDEO SELECTION
    randomize_videos: bool = True
    avoid_consecutive_duplicate: bool = True

    # ENCODING
    # libx264 is the portable default. See README for hardware-encoder options.
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 22
    preset: str = "veryfast"
    audio_bitrate: str = "192k"
    threads: int = 0  # 0 lets FFmpeg choose.

    def get_resolution(self) -> tuple[int, int]:
        if self.video_format == "vertical":
            return 1080, 1920
        if self.video_format == "horizontal":
            return 1920, 1080
        raise ValueError(f"Unsupported video format: {self.video_format}")
