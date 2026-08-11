from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel


@dataclass
class SubtitleSegment:

    start: float
    end: float
    text: str


class VietnameseWhisper:

    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ):

        print(
            f"\nLoading Whisper model: "
            f"{model_name}"
        )

        self.model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )

    def transcribe(
        self,
        audio_file: Path,
    ) -> list[SubtitleSegment]:

        print(
            "\nTranscribing Vietnamese audio..."
        )

        segments, info = (
            self.model.transcribe(
                str(audio_file),

                language="vi",

                vad_filter=True,

                beam_size=5,

                condition_on_previous_text=True,
            )
        )

        results = []

        for segment in segments:

            text = segment.text.strip()

            if not text:
                continue

            results.append(
                SubtitleSegment(
                    start=segment.start,
                    end=segment.end,
                    text=text,
                )
            )

        print(
            f"Language: {info.language}"
        )

        print(
            f"Segments: {len(results)}"
        )

        return results
