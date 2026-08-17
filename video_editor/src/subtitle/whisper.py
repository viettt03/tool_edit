from dataclasses import dataclass
from pathlib import Path


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
        language: str = "vi",
        beam_size: int = 3,
    ) -> None:
        if beam_size < 1:
            raise ValueError("Whisper beam_size must be at least 1.")

        print(f"\nLoading Whisper model: {model_name}")
        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "faster-whisper is not installed. Run: pip install -r requirements.txt"
            ) from error

        self.model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )
        self.language = language
        self.beam_size = beam_size

    def transcribe(
        self,
        audio_file: Path,
    ) -> list[SubtitleSegment]:
        print("\nTranscribing Vietnamese audio...")
        segments, info = self.model.transcribe(
            str(audio_file),
            language=self.language,
            vad_filter=True,
            beam_size=self.beam_size,
            # The ASS writer uses segment timings, not individual word timings.
            # Skipping alignment makes transcription materially faster on CPU.
            word_timestamps=False,
            condition_on_previous_text=True,
        )

        results: list[SubtitleSegment] = []
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

        print(f"Language: {info.language}")
        print(f"Segments: {len(results)}")

        return results
