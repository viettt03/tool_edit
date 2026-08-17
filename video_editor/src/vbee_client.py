"""Small Vbee Text-to-Speech client used by the story pipeline.

The API returns a request id first.  This module polls the request until Vbee
returns an ``audio_link`` and then downloads the audio locally.  Long stories
are split into smaller requests so a single API request does not become a
hidden length bottleneck.
"""

from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path


class VbeeError(RuntimeError):
    """Raised when Vbee rejects a request or returns an unusable response."""


def split_text_for_tts(text: str, max_chars: int = 3500) -> list[str]:
    """Split text at paragraph/sentence boundaries for stable TTS requests."""

    if max_chars < 500:
        raise ValueError("max_chars must be at least 500")

    normalized = "\n".join(
        line.strip()
        for line in text.replace("\r\n", "\n").split("\n")
        if line.strip()
    ).strip()

    if not normalized:
        raise ValueError("TTS text is empty")

    chunks: list[str] = []
    current = ""

    # Chinese and Vietnamese stories both use these sentence delimiters.
    sentence_breaks = "。！？!?…;；."

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in normalized.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        sentences: list[str] = []
        start = 0
        for index, character in enumerate(paragraph):
            if character in sentence_breaks:
                sentences.append(paragraph[start : index + 1])
                start = index + 1
        if start < len(paragraph):
            sentences.append(paragraph[start:])

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            candidate = f"{current} {sentence}".strip()
            if len(candidate) <= max_chars:
                current = candidate
                continue

            flush()
            if len(sentence) <= max_chars:
                current = sentence
                continue

            # A single very long line has no safe sentence boundary. Split it
            # mechanically and let Vbee synthesize each part separately.
            for offset in range(0, len(sentence), max_chars):
                piece = sentence[offset : offset + max_chars].strip()
                if piece:
                    chunks.append(piece)

    flush()
    return chunks


class VbeeClient:
    """Client for the public Vbee AIVoice TTS API."""

    endpoint = "https://vbee.vn/api/v1/tts"

    def __init__(
        self,
        app_id: str,
        token: str,
        voice_code: str,
        *,
        audio_type: str = "mp3",
        bitrate: int = 128,
        speed_rate: float = 1.0,
        timeout: int = 60,
        poll_interval: float = 2.0,
        max_wait: int = 900,
    ) -> None:
        self.app_id = app_id.strip()
        self.token = token.strip()
        self.voice_code = voice_code.strip()
        self.audio_type = audio_type
        self.bitrate = bitrate
        self.speed_rate = speed_rate
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_wait = max_wait

        missing = [
            name
            for name, value in (
                ("VBEE_APP_ID", self.app_id),
                ("VBEE_TOKEN", self.token),
                ("VBEE_VOICE_CODE", self.voice_code),
            )
            if not value
        ]
        if missing:
            raise VbeeError(
                "Thiếu cấu hình Vbee: " + ", ".join(missing)
            )

    def synthesize(self, text: str) -> Path:
        """Create one TTS request and return the downloaded audio path."""

        payload = {
            "app_id": self.app_id,
            "response_type": "indirect",
            "input_text": text,
            "voice_code": self.voice_code,
            "audio_type": self.audio_type,
            "bitrate": self.bitrate,
            "speed_rate": str(self.speed_rate),
        }

        response = self._request(
            self.endpoint,
            method="POST",
            payload=payload,
        )
        result = response.get("result") or {}
        request_id = result.get("request_id")
        if not request_id:
            raise VbeeError(self._error_message(response, "Vbee không trả request_id"))

        print(f"Vbee request: {request_id}")
        deadline = time.monotonic() + self.max_wait
        while time.monotonic() < deadline:
            status_response = self._request(
                f"{self.endpoint}/{request_id}",
                method="GET",
            )
            status_result = status_response.get("result") or {}
            status = str(status_result.get("status") or "").upper()
            if status == "SUCCESS" and status_result.get("audio_link"):
                return self._download_audio(str(status_result["audio_link"]))
            if status in {"FAILURE", "FAILED", "ERROR"}:
                raise VbeeError(
                    self._error_message(status_response, f"Vbee xử lý thất bại: {status}")
                )

            progress = status_result.get("progress")
            suffix = f" ({progress}%)" if progress is not None else ""
            print(f"Đang chờ Vbee: {status or 'IN_PROGRESS'}{suffix}")
            time.sleep(self.poll_interval)

        raise VbeeError(
            f"Vbee xử lý quá thời gian chờ ({self.max_wait}s), request_id={request_id}"
        )

    def synthesize_long_text(
        self,
        text: str,
        output: Path,
        *,
        max_chars: int = 3500,
    ) -> None:
        """Synthesize a long story and concatenate all returned audio parts."""

        chunks = split_text_for_tts(text, max_chars=max_chars)
        output.parent.mkdir(parents=True, exist_ok=True)
        parts_dir = output.parent / f".{output.stem}_vbee_parts"
        parts_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []

        try:
            for index, chunk in enumerate(chunks, 1):
                print(f"\nVbee audio {index}/{len(chunks)} ({len(chunk)} ký tự)")
                part = parts_dir / f"part_{index:04d}.{self.audio_type}"
                if not part.exists():
                    downloaded = self.synthesize(chunk)
                    shutil.move(str(downloaded), str(part))
                parts.append(part)

            self._concat_audio(parts, output)
        finally:
            for part in parts_dir.glob("*"):
                try:
                    part.unlink()
                except OSError:
                    pass
            try:
                parts_dir.rmdir()
            except OSError:
                pass

    def _request(
        self,
        url: str,
        *,
        method: str,
        payload: dict | None = None,
    ) -> dict:
        body = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise VbeeError(f"Vbee HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise VbeeError(f"Không kết nối được Vbee: {error.reason}") from error

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise VbeeError(f"Vbee trả về JSON không hợp lệ: {raw[:300]}") from error

        if data.get("status") == 0:
            raise VbeeError(self._error_message(data, "Vbee trả về lỗi"))
        return data

    def _download_audio(self, url: str) -> Path:
        temporary = Path.cwd() / f".vbee_download_{time.time_ns()}.{self.audio_type}"
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Cliproom/1.0"},
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                with temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
            return temporary
        except urllib.error.URLError as error:
            temporary.unlink(missing_ok=True)
            raise VbeeError(f"Không tải được audio từ Vbee: {error.reason}") from error

    @staticmethod
    def _error_message(response: dict, fallback: str) -> str:
        return str(
            response.get("error_message")
            or response.get("error_code")
            or fallback
        )

    @staticmethod
    def _concat_audio(parts: list[Path], output: Path) -> None:
        if not parts:
            raise VbeeError("Không có audio Vbee để ghép")

        # Vbee returns the same format for every part. The concat demuxer
        # avoids decoding/re-encoding the narration a second time.
        list_file = output.parent / f".{output.stem}_vbee_concat.txt"
        list_file.write_text(
            "\n".join(
                f"file '{path.resolve().as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
                for path in parts
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            import subprocess

            command = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(output),
            ]
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode != 0:
                raise VbeeError(
                    "FFmpeg không ghép được các audio Vbee:\n" + result.stderr[-2000:]
                )
        finally:
            list_file.unlink(missing_ok=True)
