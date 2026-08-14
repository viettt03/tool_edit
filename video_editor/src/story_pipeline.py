"""End-to-end story-to-video pipeline.

Input can be a copied Douyin transcript (TXT) or the audio of a downloaded
video.  The pipeline translates source text to Vietnamese, sends it to Vbee,
creates Vietnamese subtitles with Whisper, then renders one source video from
the beginning with a blurred side background, logo and waveform.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from .audio.processor import prepare_narration
from .renderer.renderer import render_story_video
from .subtitle.srt import write_srt
from .subtitle.whisper import VietnameseWhisper
from .vbee_client import VbeeClient


def _split_for_translation(text: str, max_chars: int = 4200) -> list[str]:
    """Split text into chunks accepted by common online translators."""

    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n{paragraph}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = ""
        while len(paragraph) > max_chars:
            chunks.append(paragraph[:max_chars])
            paragraph = paragraph[max_chars:]
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


def translate_to_vietnamese(text: str, source: str = "auto") -> str:
    """Translate copied source text using the configured online translator."""

    try:
        from deep_translator import GoogleTranslator
    except ImportError as error:
        raise RuntimeError(
            "Chưa có bộ dịch. Hãy chạy: "
            "./.venv/bin/python -m pip install -r requirements.txt"
        ) from error

    translator = GoogleTranslator(source=source, target="vi")
    translated: list[str] = []
    chunks = _split_for_translation(text)
    for index, chunk in enumerate(chunks, 1):
        print(f"Đang dịch đoạn {index}/{len(chunks)}...")
        try:
            result = translator.translate(chunk)
        except Exception as error:
            raise RuntimeError(
                f"Dịch đoạn {index} thất bại: {error}. "
                "Bạn có thể chạy lại với --no-translate nếu text đã là tiếng Việt."
            ) from error
        if result:
            translated.append(result.strip())
    return "\n\n".join(translated)


def extract_source_text_from_video(
    video: Path,
    model_name: str,
    device: str,
    compute_type: str,
    language: str,
) -> str:
    """Transcribe Chinese narration from a source video when no TXT exists."""

    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise RuntimeError(
            "Chưa có faster-whisper. Hãy chạy pip install -r requirements.txt"
        ) from error

    print(f"Đang nhận diện lời thoại nguồn ({language})...")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        str(video),
        language=language,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=True,
    )
    text = "\n".join(segment.text.strip() for segment in segments if segment.text.strip())
    if not text:
        raise RuntimeError("Không nhận diện được lời thoại trong video nguồn.")
    return text


def find_source_video(video_directory: Path) -> Path:
    candidates = sorted(
        path
        for path in video_directory.glob("*")
        if path.is_file()
        and path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi"}
        and "previous_downloads" not in path.parts
    )
    if not candidates:
        raise FileNotFoundError(
            f"Không tìm thấy video trong {video_directory}. "
            "Hãy tải video Douyin vào input/videos trước."
        )
    return candidates[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dịch truyện, tạo audio Vbee và ghép thành video kể chuyện."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--source-text",
        type=Path,
        default=Path("input/story_zh.txt"),
        help="File transcript/text đã copy từ Douyin (mặc định input/story_zh.txt).",
    )
    source.add_argument(
        "--source-video",
        type=Path,
        help="Tùy chọn: lấy lời thoại tiếng Trung từ audio video bằng Whisper.",
    )
    parser.add_argument(
        "--video",
        type=Path,
        help="Video Douyin dùng từ đầu. Mặc định lấy video đầu tiên trong input/videos.",
    )
    parser.add_argument(
        "--logo",
        type=Path,
        default=Path("input/logo.png"),
        help="Logo PNG nền trong suốt (mặc định input/logo.png).",
    )
    parser.add_argument(
        "--music",
        type=Path,
        default=Path("input/music.mp3"),
        help="Nhạc nền tùy chọn; dùng --no-music để tắt.",
    )
    parser.add_argument("--no-music", action="store_true")
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Bỏ bước dịch nếu source text đã là tiếng Việt.",
    )
    parser.add_argument(
        "--source-language",
        default="auto",
        help="Ngôn ngữ nguồn cho bộ dịch, mặc định auto (ví dụ zh-CN).",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--video-format",
        choices=("horizontal", "vertical"),
        default="horizontal",
        help="Mặc định ngang 1920x1080 để giống video mẫu; có thể chọn vertical.",
    )
    parser.add_argument("--voice-code", default=os.getenv("VBEE_VOICE_CODE", ""))
    parser.add_argument("--tts-max-chars", type=int, default=3500)
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--whisper-device", default="cpu")
    parser.add_argument("--whisper-compute-type", default="int8")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    source_file = output_dir / "story_source.txt"
    if args.source_video:
        source_text = extract_source_text_from_video(
            args.source_video,
            args.whisper_model,
            args.whisper_device,
            args.whisper_compute_type,
            args.source_language if args.source_language != "auto" else "zh",
        )
        source_file.write_text(source_text, encoding="utf-8")
    else:
        if not args.source_text.is_file():
            raise FileNotFoundError(
                f"Không tìm thấy {args.source_text}. Hãy tạo file này và dán transcript vào."
            )
        source_text = args.source_text.read_text(encoding="utf-8").strip()

    if not source_text:
        raise ValueError("Nội dung truyện đang trống.")

    if args.no_translate:
        vietnamese_text = source_text
    else:
        vietnamese_text = translate_to_vietnamese(
            source_text,
            source=args.source_language,
        )
    vietnamese_file = output_dir / "story_vi.txt"
    vietnamese_file.write_text(vietnamese_text + "\n", encoding="utf-8")

    client = VbeeClient(
        app_id=os.getenv("VBEE_APP_ID", ""),
        token=os.getenv("VBEE_TOKEN", ""),
        voice_code=args.voice_code,
    )
    narration = output_dir / "narration_vbee.mp3"
    client.synthesize_long_text(
        vietnamese_text,
        narration,
        max_chars=args.tts_max_chars,
    )

    processed_audio = output_dir / "narration_vbee_processed.wav"
    duration = prepare_narration(narration, processed_audio, speed=1.0)

    print("\nĐang tạo phụ đề tiếng Việt...")
    whisper = VietnameseWhisper(
        model_name=args.whisper_model,
        device=args.whisper_device,
        compute_type=args.whisper_compute_type,
    )
    segments = whisper.transcribe(processed_audio)
    subtitles = output_dir / "story_subtitles.srt"
    write_srt(segments, subtitles, max_chars=42)

    video = args.video or find_source_video(Path("input/videos"))
    if not video.is_file():
        raise FileNotFoundError(f"Không tìm thấy video nguồn: {video}")
    logo = args.logo if args.logo.is_file() else None
    music = None if args.no_music or not args.music.is_file() else args.music
    width, height = ((1920, 1080) if args.video_format == "horizontal" else (1080, 1920))

    final_video = output_dir / "story_final.mp4"
    render_story_video(
        video=video,
        narration=processed_audio,
        music=music,
        subtitles=subtitles,
        logo=logo,
        output=final_video,
        width=width,
        height=height,
        duration=duration,
    )

    print("\n========================================")
    print("HOÀN TẤT STORY PIPELINE")
    print("========================================")
    print(f"Bản dịch: {vietnamese_file}")
    print(f"Audio Vbee: {narration}")
    print(f"Phụ đề: {subtitles}")
    print(f"Video: {final_video}")


if __name__ == "__main__":
    main()
