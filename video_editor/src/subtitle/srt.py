from pathlib import Path

from .whisper import SubtitleSegment


def format_timestamp(
    seconds: float,
) -> str:

    total_ms = int(
        seconds * 1000
    )

    hours = (
        total_ms // 3_600_000
    )

    minutes = (
        total_ms % 3_600_000
    ) // 60_000

    seconds = (
        total_ms % 60_000
    ) // 1_000

    milliseconds = (
        total_ms % 1_000
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d},"
        f"{milliseconds:03d}"
    )


def split_text(
    text: str,
    max_chars: int,
) -> str:

    words = text.split()

    lines = []

    current = ""

    for word in words:

        candidate = (
            f"{current} {word}"
            if current
            else word
        )

        if len(candidate) <= max_chars:

            current = candidate

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    if len(lines) <= 2:
        return "\n".join(lines)

    return (
        lines[0]
        + "\n"
        + " ".join(lines[1:])
    )


def write_srt(
    segments: list[SubtitleSegment],
    output: Path,
    max_chars: int = 42,
) -> None:

    with open(
        output,
        "w",
        encoding="utf-8",
    ) as file:

        for index, segment in enumerate(
            segments,
            1,
        ):

            text = split_text(
                segment.text,
                max_chars,
            )

            file.write(
                f"{index}\n"
            )

            file.write(
                f"{format_timestamp(segment.start)} "
                f"--> "
                f"{format_timestamp(segment.end)}\n"
            )

            file.write(
                f"{text}\n\n"
            )
