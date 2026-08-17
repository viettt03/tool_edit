from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
ALLOWED_HOSTS = {
    "douyin.com",
    "www.douyin.com",
    "v.douyin.com",
}


@dataclass
class DownloadResult:
    """The outcome of one download attempt."""

    url: str
    status: str
    file: str | None = None
    video_id: str | None = None
    title: str | None = None
    error: str | None = None


def is_douyin_url(url: str) -> bool:
    """Return True for supported public Douyin URL hosts."""

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")

    return (
        parsed.scheme in {"http", "https"}
        and hostname in ALLOWED_HOSTS
        and bool(parsed.path)
    )


def is_douyin_video_url(url: str) -> bool:
    """Return True for a direct Douyin video URL or short share URL."""

    if not is_douyin_url(url):
        return False

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")

    if hostname == "v.douyin.com":
        return True

    return bool(re.fullmatch(r"/video/\d+/?", parsed.path))


def read_url_list(path: Path) -> list[str]:
    """Read one public Douyin URL per line.

    Empty lines and lines beginning with ``#`` are ignored.  Failing early on
    non-Douyin URLs prevents accidentally downloading unrelated content.
    """

    if not path.exists():
        raise FileNotFoundError(f"URL list not found: {path}")

    urls: list[str] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        url = raw_line.strip()

        if not url or url.startswith("#"):
            continue

        if not is_douyin_video_url(url):
            raise ValueError(
                f"Invalid Douyin URL at line {line_number}: {url}"
            )

        urls.append(url)

    if not urls:
        raise ValueError(f"No Douyin URLs found in {path}")

    return urls


class DouyinDownloader:
    """Download user-supplied public Douyin videos into the render input.

    ``yt-dlp`` handles the site-specific extraction.  This class intentionally
    does not implement search, login, CAPTCHA solving, or access-control
    bypasses.
    """

    def __init__(
        self,
        output_directory: Path,
        cookies_file: Path | None = None,
    ) -> None:
        self.output_directory = output_directory
        self.cookies_file = cookies_file

    def download(self, urls: list[str]) -> list[DownloadResult]:
        """Download each URL and continue after an individual failure."""

        if not urls:
            raise ValueError("URL list is empty.")

        invalid_urls = [url for url in urls if not is_douyin_video_url(url)]
        if invalid_urls:
            raise ValueError(
                "Only public Douyin URLs are supported. "
                f"Invalid URL: {invalid_urls[0]}"
            )

        if self.cookies_file is not None and not self.cookies_file.is_file():
            raise FileNotFoundError(
                f"Cookies file not found: {self.cookies_file}"
            )

        try:
            import yt_dlp
            from yt_dlp.utils import DownloadError
        except ImportError as error:
            raise RuntimeError(
                "yt-dlp is not installed. Run: pip install -r requirements.txt"
            ) from error

        self.output_directory.mkdir(parents=True, exist_ok=True)

        options = {
            # Prefer a broadly compatible MP4 result for the existing FFmpeg
            # pipeline, while keeping a single-file fallback available.
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
            "merge_output_format": "mp4",
            "outtmpl": str(self.output_directory / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "restrictfilenames": True,
            "continuedl": True,
            "overwrites": False,
            "retries": 2,
            "quiet": False,
            "no_warnings": False,
        }

        if self.cookies_file is not None:
            options["cookiefile"] = str(self.cookies_file)

        results: list[DownloadResult] = []

        with yt_dlp.YoutubeDL(options) as downloader:
            for url in urls:
                results.append(
                    self._download_one(
                        downloader,
                        DownloadError,
                        url,
                    )
                )

        return results

    def _download_one(
        self,
        downloader,
        download_error_type,
        url: str,
    ) -> DownloadResult:
        try:
            info = downloader.extract_info(url, download=True)

            if not info:
                return DownloadResult(
                    url=url,
                    status="failed",
                    error="yt-dlp returned no video information",
                )

            video_id = str(info.get("id") or "") or None
            title = info.get("title")
            output_file = self._find_output_file(video_id)

            if output_file is None:
                return DownloadResult(
                    url=url,
                    status="failed",
                    video_id=video_id,
                    title=title,
                    error="Download completed but no video file was found",
                )

            self._write_metadata(
                output_file=output_file,
                source_url=url,
                info=info,
            )

            return DownloadResult(
                url=url,
                status="downloaded",
                file=str(output_file),
                video_id=video_id,
                title=title,
            )

        except download_error_type as error:
            return DownloadResult(
                url=url,
                status="failed",
                error=str(error),
            )

    def _find_output_file(self, video_id: str | None) -> Path | None:
        if not video_id:
            return None

        candidates = sorted(
            path
            for path in self.output_directory.glob(f"{video_id}.*")
            if path.is_file()
            and path.suffix.lower() in VIDEO_EXTENSIONS
            and not path.name.endswith(".part")
        )

        # The merge step should normally leave an MP4.  If the source only
        # offers another container, it is still usable by the current scanner.
        return next(
            (path for path in candidates if path.suffix.lower() == ".mp4"),
            candidates[0] if candidates else None,
        )

    def _write_metadata(
        self,
        output_file: Path,
        source_url: str,
        info: dict,
    ) -> None:
        metadata = {
            "source_url": source_url,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "id": info.get("id"),
            "title": info.get("title"),
            "uploader": info.get("uploader") or info.get("channel"),
            "duration": info.get("duration"),
            "width": info.get("width"),
            "height": info.get("height"),
            "webpage_url": info.get("webpage_url") or source_url,
            "file": output_file.name,
        }

        metadata_file = output_file.with_suffix(".json")
        metadata_file.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def format_result(result: DownloadResult) -> str:
    """Format a compact CLI status line."""

    if result.status == "downloaded":
        return f"OK   {result.file}"

    return f"FAIL {result.url}: {result.error}"


def result_as_dict(result: DownloadResult) -> dict:
    """Serialize a result without exposing the internal dataclass."""

    return asdict(result)
