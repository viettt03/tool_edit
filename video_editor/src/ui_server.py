from __future__ import annotations

import json
import mimetypes
import plistlib
import re
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .douyin.collector import (
    DouyinPageCollector,
    DouyinVerificationRequired,
)
from .douyin.downloader import is_douyin_url, is_douyin_video_url
from .tiktok_uploader import TikTokAutomation


PROJECT_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_DIR / "web"
VIDEO_DIR = PROJECT_DIR / "input" / "videos"
OUTPUT_DIR = PROJECT_DIR / "output"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def open_in_browser(url: str, browser: str) -> None:
    """Open a Douyin verification page in the user's regular browser."""

    app_name = "Safari" if browser == "safari" else "Google Chrome"
    subprocess.Popen(["open", "-a", app_name, url])


def browser_user_agent(browser_name: str) -> str:
    version = "151.0.0.0"

    if browser_name == "chrome":
        plist_path = Path(
            "/Applications/Google Chrome.app/Contents/Info.plist"
        )
        try:
            with plist_path.open("rb") as plist_file:
                version = str(plistlib.load(plist_file).get("KSVersion", version))
            major = version.split(".", 1)[0]
            version = f"{major}.0.0.0"
        except (FileNotFoundError, OSError, plistlib.InvalidFileException):
            pass

    return (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{version} Safari/537.36"
    )


def normalize_source(value: str) -> str:
    """Turn a Douyin modal link into the direct video URL yt-dlp expects."""

    value = value.strip()
    parsed = urlparse(value)
    modal_id = parse_qs(parsed.query).get("modal_id", [None])[0]

    if (
        modal_id
        and re.fullmatch(r"\d{15,20}", modal_id)
        and parsed.hostname
        and parsed.hostname.lower().endswith("douyin.com")
    ):
        return f"https://www.douyin.com/video/{modal_id}"

    return value


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, payload: dict) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "Đang chuẩn bị tải...",
            "items": [],
            "logs": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._run,
            args=(job_id, payload),
            daemon=True,
        )
        thread.start()
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return json.loads(json.dumps(job)) if job else None

    def update(self, job_id: str, **changes) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(changes)

    def add_log(self, job_id: str, message: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["logs"].append(message)
                self._jobs[job_id]["logs"] = self._jobs[job_id]["logs"][-12:]

    def _run(self, job_id: str, payload: dict) -> None:
        try:
            self.update(
                job_id,
                status="running",
                message="Đang lấy danh sách video...",
            )

            mode = payload.get("mode", "video")
            value = str(payload.get("value", "")).strip()
            limit = int(payload.get("limit", 10))
            browser = str(payload.get("browser", "chrome"))
            user_agent = browser_user_agent(browser)

            if not value:
                raise ValueError("Bạn chưa nhập link hoặc từ khóa.")

            if mode == "video":
                urls = self._parse_video_urls(value)
            else:
                collector = DouyinPageCollector(
                    browser_name=browser,
                    user_agent=user_agent,
                    status_callback=lambda message, url: self.update(
                        job_id,
                        status="waiting_verification",
                        message=message,
                        verification_url=url,
                        verification_browser=browser,
                    ),
                )
                candidate_limit = min(max(limit * 3, limit), 100)
                if mode == "user":
                    urls = collector.collect_user(value, candidate_limit)
                elif mode == "keyword":
                    urls = collector.search(value, candidate_limit)
                else:
                    raise ValueError("Chế độ tải không hợp lệ.")

                self.update(
                    job_id,
                    status="running",
                    message="Đang sắp xếp video theo ngày đăng mới nhất...",
                    progress=2,
                )
                urls = self._sort_urls_by_date(
                    urls,
                    browser=browser,
                    user_agent=user_agent,
                )[:limit]

            self.update(
                job_id,
                message=f"Đã tìm thấy {len(urls)} video, bắt đầu tải...",
                progress=3,
            )
            self._download_urls(job_id, urls, browser, user_agent)

        except DouyinVerificationRequired as error:
            self.add_log(job_id, "Douyin yêu cầu CAPTCHA, đã mở Chrome để xác minh.")
            try:
                open_in_browser(error.url, browser)
                message = (
                    "Douyin yêu cầu xác minh. Chrome đã được mở, hãy kéo CAPTCHA "
                    "thủ công rồi bấm Tải video xuống lại."
                )
            except OSError as open_error:
                self.add_log(job_id, f"Không mở được trình duyệt: {open_error}")
                message = (
                    "Douyin yêu cầu xác minh CAPTCHA. Hãy mở trang Douyin bằng "
                    "Chrome, xác minh thủ công rồi bấm Tải video xuống lại."
                )
            self.update(
                job_id,
                status="needs_verification",
                message=message,
                verification_url=error.url,
                verification_browser=browser,
            )
        except Exception as error:
            self.add_log(job_id, f"Lỗi: {error}")
            self.update(
                job_id,
                status="failed",
                message=str(error),
            )

    def _download_urls(
        self,
        job_id: str,
        urls: list[str],
        browser: str,
        user_agent: str,
    ) -> None:
        try:
            import yt_dlp
            from yt_dlp.utils import DownloadError
        except ImportError as error:
            raise RuntimeError(
                "Chưa cài yt-dlp. Hãy chạy pip install -r requirements.txt"
            ) from error

        VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        progress_lock = threading.Lock()
        progress_state = {
            "done": 0,
            "percent": {index: 0 for index in range(len(urls))},
        }

        def download_one(index: int, url: str) -> dict:
            def progress_hook(data: dict) -> None:
                with progress_lock:
                    if data.get("status") == "downloading":
                        downloaded = data.get("downloaded_bytes", 0)
                        total = data.get("total_bytes") or data.get("total_bytes_estimate")
                        if total:
                            progress_state["percent"][index] = min(
                                99,
                                int(downloaded * 100 / total),
                            )
                            average = sum(progress_state["percent"].values()) / len(urls)
                            self.update(
                                job_id,
                                progress=max(3, int(average)),
                                message=(
                                    f"Đang tải song song • {progress_state['done']}/"
                                    f"{len(urls)} video hoàn tất"
                                ),
                            )
                    elif data.get("status") == "finished":
                        self.add_log(
                            job_id,
                            f"Đã tải: {Path(data.get('filename', '')).name}",
                        )

            class UILogger:
                def debug(self, message: str) -> None:
                    if message and not message.startswith("[debug]"):
                        self_outer.add_log(job_id, message)

                def info(self, message: str) -> None:
                    if message:
                        self_outer.add_log(job_id, message)

                def warning(self, message: str) -> None:
                    if message:
                        self_outer.add_log(job_id, f"Cảnh báo: {message}")

                def error(self, message: str) -> None:
                    if message:
                        self_outer.add_log(job_id, f"Lỗi tải: {message}")

            self_outer = self
            options = {
                "format": (
                    "download_addr-3/"
                    "h264_540p_1736751-3/"
                    "b[ext=mp4]/b"
                ),
                "merge_output_format": "mp4",
                "outtmpl": str(VIDEO_DIR / "%(id)s.%(ext)s"),
                "noplaylist": True,
                "restrictfilenames": True,
                "continuedl": True,
                "overwrites": False,
                "retries": 2,
                "quiet": True,
                "no_warnings": False,
                "cookiesfrombrowser": (browser, None, None, None),
                "http_headers": {
                    "User-Agent": user_agent,
                    "Referer": "https://www.douyin.com/",
                },
                "progress_hooks": [progress_hook],
                "logger": UILogger(),
            }

            try:
                with yt_dlp.YoutubeDL(options) as downloader:
                    info = downloader.extract_info(url, download=True)
                video_id = str(info.get("id", "")) if info else ""
                output_file = self._find_video(video_id)
                if output_file:
                    return {
                        "url": url,
                        "status": "downloaded",
                        "file": output_file.name,
                        "title": info.get("title") if info else None,
                    }
                return {
                    "url": url,
                    "status": "failed",
                    "error": "Không tìm thấy file sau khi tải.",
                }
            except DownloadError as error:
                return {
                    "url": url,
                    "status": "failed",
                    "error": str(error),
                }
            except Exception as error:
                return {
                    "url": url,
                    "status": "failed",
                    "error": str(error),
                }

        items: list[dict | None] = [None] * len(urls)
        max_workers = min(3, len(urls))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(download_one, index, url): index
                for index, url in enumerate(urls)
            }
            for future in as_completed(futures):
                index = futures[future]
                items[index] = future.result()
                with progress_lock:
                    progress_state["done"] += 1
                    progress_state["percent"][index] = 100
                    completed = progress_state["done"]
                self.update(
                    job_id,
                    items=[item for item in items if item is not None],
                    progress=int(completed * 100 / len(urls)),
                    message=f"Đã xử lý {completed}/{len(urls)} video",
                )

        items = [item for item in items if item is not None]

        failed = sum(item["status"] == "failed" for item in items)
        self.update(
            job_id,
            status="failed" if failed == len(items) else "completed",
            progress=100,
            message=(
                f"Tải xong {len(items) - failed}/{len(items)} video"
                if failed
                else f"Đã tải xong {len(items)} video"
            ),
        )

    @staticmethod
    def _parse_video_urls(value: str) -> list[str]:
        raw_urls = [line.strip() for line in value.splitlines() if line.strip()]
        urls: list[str] = []
        seen: set[str] = set()

        if not raw_urls:
            raise ValueError("Bạn chưa nhập link video.")

        if len(raw_urls) > 100:
            raise ValueError("Tối đa 100 link trong một lượt tải.")

        for raw_url in raw_urls:
            url = normalize_source(raw_url)
            if not is_douyin_video_url(url):
                raise ValueError(
                    f"Link không hợp lệ: {raw_url}. "
                    "Hãy dùng link video Douyin."
                )
            if url not in seen:
                seen.add(url)
                urls.append(url)

        return urls

    @staticmethod
    def _find_video(video_id: str) -> Path | None:
        if not video_id:
            return None
        candidates = sorted(
            path
            for path in VIDEO_DIR.glob(f"{video_id}.*")
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        )
        return next(
            (path for path in candidates if path.suffix.lower() == ".mp4"),
            candidates[0] if candidates else None,
        )

    @staticmethod
    def _sort_urls_by_date(
        urls: list[str],
        browser: str,
        user_agent: str,
    ) -> list[str]:
        """Sort collected video URLs by published timestamp, newest first."""

        try:
            import yt_dlp
        except ImportError:
            return urls

        metadata: list[tuple[str, int, int]] = []
        options = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "ignoreerrors": True,
            "cookiesfrombrowser": (browser, None, None, None),
            "http_headers": {
                "User-Agent": user_agent,
                "Referer": "https://www.douyin.com/",
            },
        }

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                for index, url in enumerate(urls):
                    try:
                        info = downloader.extract_info(url, download=False)
                        timestamp = int(info.get("timestamp") or 0) if info else 0
                    except Exception:
                        timestamp = 0
                    metadata.append((url, timestamp, index))
        except Exception:
            return urls

        metadata.sort(key=lambda item: item[1], reverse=True)
        return [url for url, _timestamp, _index in metadata]


JOBS = JobStore()
TIKTOK = TikTokAutomation(PROJECT_DIR)


class UIHandler(BaseHTTPRequestHandler):
    server_version = "Cliproom/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/api/videos":
            self._send_json({"videos": list_videos()})
            return

        if parsed.path == "/api/tiktok/videos":
            self._send_json({"videos": list_upload_videos()})
            return

        if parsed.path == "/api/tiktok/status":
            self._send_json(TIKTOK.get_state())
            return

        if parsed.path.startswith("/api/jobs/"):
            job = JOBS.get(parsed.path.rsplit("/", 1)[-1])
            if job is None:
                self._send_json({"error": "Không tìm thấy job."}, 404)
            else:
                self._send_json(job)
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/api/download":
            try:
                payload = self._read_json()
                job_id = JOBS.create(payload)
                self._send_json({"job_id": job_id}, 202)
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, 400)
            return

        if parsed.path == "/api/open-folder":
            try:
                subprocess.Popen(["open", str(VIDEO_DIR)])
                self._send_json({"ok": True})
            except OSError as error:
                self._send_json({"error": str(error)}, 500)
            return

        if parsed.path == "/api/open-browser":
            try:
                payload = self._read_json()
                url = str(payload.get("url", "")).strip()
                browser = str(payload.get("browser", "chrome"))
                if not is_douyin_url(url):
                    raise ValueError("Chỉ được mở URL Douyin.")
                open_in_browser(url, browser)
                self._send_json({"ok": True})
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, 400)
            return

        if parsed.path == "/api/tiktok/start":
            try:
                self._send_json(TIKTOK.start_auto_upload(), 202)
            except FileNotFoundError as error:
                self._send_json({"error": str(error)}, 400)
            except Exception as error:
                self._send_json({"error": str(error)}, 500)
            return

        if parsed.path == "/api/tiktok/prepare":
            try:
                payload = self._read_json()
                filename = str(payload.get("filename", "")).strip()
                caption = str(payload.get("caption", "")).strip()
                file_path = resolve_upload_video(filename)
                if file_path is None:
                    raise ValueError("Video không hợp lệ hoặc không nằm trong thư viện local.")
                job_id = TIKTOK.prepare_upload(file_path, caption)
                self._send_json({"job_id": job_id}, 202)
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, 400)
            except Exception as error:
                self._send_json({"error": str(error)}, 500)
            return

        if parsed.path == "/api/tiktok/close":
            TIKTOK.close()
            self._send_json({"ok": True})
            return

        self._send_json({"error": "Endpoint không tồn tại."}, 404)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Dữ liệu gửi lên không hợp lệ.")
        return payload

    def _serve_static(self, request_path: str) -> None:
        relative = request_path.lstrip("/") or "index.html"
        target = (WEB_DIR / relative).resolve()

        try:
            target.relative_to(WEB_DIR.resolve())
        except ValueError:
            self._send_json({"error": "Đường dẫn không hợp lệ."}, 403)
            return

        if not target.is_file():
            target = WEB_DIR / "index.html"

        content_type = mimetypes.guess_type(target.name)[0] or "text/plain"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def list_videos() -> list[dict]:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    videos = []

    for path in sorted(
        VIDEO_DIR.iterdir(),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        videos.append(
            {
                "name": path.name,
                "size": path.stat().st_size,
                "modified": datetime.fromtimestamp(
                    path.stat().st_mtime,
                    timezone.utc,
                ).isoformat(),
            }
        )

    return videos


def list_upload_videos() -> list[dict]:
    """List local videos that can be handed to the TikTok uploader."""

    videos: list[dict] = []
    seen: set[str] = set()
    for directory, group in ((VIDEO_DIR, "Local library"), (OUTPUT_DIR, "Output")):
        if not directory.exists():
            continue
        for path in sorted(
            directory.iterdir(),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            if path.name in seen:
                continue
            seen.add(path.name)
            videos.append(
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        path.stat().st_mtime,
                        timezone.utc,
                    ).isoformat(),
                    "group": group,
                }
            )
    return videos


def resolve_upload_video(filename: str) -> Path | None:
    """Resolve a filename from the two known local video directories only."""

    if not filename or Path(filename).name != filename:
        return None
    for directory in (VIDEO_DIR, OUTPUT_DIR):
        candidate = (directory / filename).resolve()
        try:
            candidate.relative_to(directory.resolve())
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix.lower() in VIDEO_EXTENSIONS:
            return candidate
    return None


def main() -> None:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8765), UIHandler)
    print("Cliproom running at http://127.0.0.1:8765")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Cliproom.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
