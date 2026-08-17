from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .whisper import SubtitleSegment


def format_ass_timestamp(seconds: float) -> str:
    total_centiseconds = int(seconds * 100)

    hours = total_centiseconds // 360000
    minutes = (total_centiseconds % 360000) // 6000
    secs = (total_centiseconds % 6000) // 100
    centiseconds = total_centiseconds % 100

    return (
        f"{hours}:"
        f"{minutes:02d}:"
        f"{secs:02d}."
        f"{centiseconds:02d}"
    )


def split_short_text(
    text: str,
    max_words: int = 15,
) -> list[str]:
    if max_words < 1:
        raise ValueError("subtitle_max_words must be at least 1.")
    words = text.strip().split()
    return [" ".join(words[index:index + max_words]) for index in range(0, len(words), max_words)]


def write_ass(
    segments: list[SubtitleSegment],
    output: Path,
    width: int,
    height: int,
    max_words: int = 15,
) -> None:
    """Write subtitles positioned consistently in vertical and horizontal video."""
    if width < 1 or height < 1:
        raise ValueError("Subtitle resolution must be positive.")

    font_size = max(36, round(min(width, height) * 0.065))
    margin_horizontal = round(width * 0.06)
    # Keep text around 69% down the frame in either aspect ratio.
    margin_vertical = round(height * 0.18)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,{margin_horizontal},{margin_horizontal},{margin_vertical},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        file.write(header)
        for segment in segments:
            chunks = split_short_text(
                segment.text,
                max_words=max_words,
            )
            if not chunks:
                continue

            duration = segment.end - segment.start
            chunk_duration = duration / len(chunks)

            for index, chunk in enumerate(chunks):
                start = segment.start + index * chunk_duration
                end = segment.start + (index + 1) * chunk_duration
                words = chunk.split()
                text = " ".join(words)
                text = text.replace("\\", "\\\\")
                text = text.replace("{", "\\{")
                text = text.replace("}", "\\}")
                if len(words) > 8:
                    middle = (len(words) + 1) // 2
                    text = " ".join(words[:middle]) + r"\N" + " ".join(words[middle:])
                file.write(
                    "Dialogue: 0,"
                    f"{format_ass_timestamp(start)},"
                    f"{format_ass_timestamp(end)},"
                    "Default,,0,0,0,,"
                    f"{text}\n"
                )
