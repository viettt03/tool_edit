from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from queue import Empty, Queue
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


class TikTokAutomation:
    """Attach Playwright to a visible Chrome session for upload handoff.

    The user owns the login and any verification step. This class only prepares
    the upload in TikTok Studio and deliberately stops before the Post button.
    """

    UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?lang=en"
    CDP_HOST = "127.0.0.1"
    CDP_PORT = int(os.environ.get("CLIPROOM_TIKTOK_CDP_PORT", "9222"))
    DEFAULT_CAPTION = "Một câu chuyện ngắn đáng nghe đến cuối. #kechuyen #truyenngan"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.profile_dir = project_dir / ".playwright" / "tiktok-profile"
        self.cdp_url = f"http://{self.CDP_HOST}:{self.CDP_PORT}"
        self._commands: Queue[dict[str, Any]] = Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "status": "closed",
            "message": "TikTok chưa được mở.",
            "profile_dir": str(self.profile_dir),
            "job": None,
        }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._run,
                    name="cliproom-tiktok-browser",
                    daemon=True,
                )
                self._thread.start()
            self._state.update(
                status="starting",
                message="Đang mở Chrome thường. Nếu chưa đăng nhập, hãy đăng nhập thủ công trên cửa sổ vừa mở.",
            )
        self._commands.put({"action": "open"})
        return self.get_state()

    def start_auto_upload(self) -> dict[str, Any]:
        """Open TikTok, wait for manual login, then prepare the final video."""

        file_path = self.default_video_path()
        if file_path is None:
            raise FileNotFoundError(
                "Chưa có output/final.mp4. Hãy dựng video cuối trước khi đăng TikTok."
            )

        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "status": "waiting_login",
            "progress": 0,
            "message": "Hãy đăng nhập TikTok và xử lý xác minh thủ công trên Chrome.",
            "file": file_path.name,
            "caption": self.default_caption(),
        }
        with self._lock:
            self._state["job"] = job
            self._state.update(
                status="starting",
                message=(
                    "Đang mở Chrome thường. Sau khi bạn đăng nhập và xác minh, "
                    "Cliproom sẽ tự upload output/final.mp4."
                ),
            )
        self._ensure_thread()
        self._commands.put(
            {
                "action": "open_auto",
                "job_id": job_id,
                "file_path": str(file_path),
                "caption": self.default_caption(),
            }
        )
        return self.get_state()

    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._run,
                    name="cliproom-tiktok-browser",
                    daemon=True,
                )
                self._thread.start()

    def default_video_path(self) -> Path | None:
        final_video = self.project_dir / "output" / "final.mp4"
        if final_video.is_file():
            return final_video
        return None

    def default_caption(self) -> str:
        caption_file = self.project_dir / "output" / "tiktok_caption.txt"
        try:
            caption = caption_file.read_text(encoding="utf-8").strip()
        except OSError:
            caption = ""
        if caption:
            return caption[:2200]

        generated = self._caption_from_subtitles()
        return (generated or self.DEFAULT_CAPTION)[:2200]

    def _caption_from_subtitles(self) -> str:
        subtitle_file = self.project_dir / "output" / "subtitles.srt"
        try:
            raw = subtitle_file.read_text(encoding="utf-8")
        except OSError:
            return ""

        blocks = re.split(r"\n\s*\n", raw.strip())
        lines: list[str] = []
        for block in blocks[:5]:
            parts = [line.strip() for line in block.splitlines()]
            text_lines = [
                line for line in parts
                if line and not line.isdigit() and "-->" not in line
            ]
            if text_lines:
                lines.append(" ".join(text_lines))

        transcript = re.sub(r"\s+", " ", " ".join(lines)).strip()
        if not transcript:
            return ""
        return f"{transcript[:850].rstrip(' ,.;')}… #kechuyen #truyenngan #ngontinh"

    def prepare_upload(self, file_path: Path, caption: str) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "Đang xếp lượt upload...",
            "file": file_path.name,
        }
        with self._lock:
            self._state["job"] = job
            self._state["status"] = "queued"
            self._state["message"] = "Đang chuẩn bị upload lên TikTok."
        self.start()
        self._commands.put(
            {
                "action": "prepare_upload",
                "job_id": job_id,
                "file_path": str(file_path),
                "caption": caption,
            }
        )
        return job_id

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state, ensure_ascii=False))

    def close(self) -> None:
        self._commands.put({"action": "close"})
        with self._lock:
            self._state.update(
                status="closed",
                message="Đã yêu cầu đóng cửa sổ TikTok.",
            )

    def _set_state(self, **changes: Any) -> None:
        with self._lock:
            self._state.update(changes)

    def _set_job(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._state.get("job")
            if isinstance(job, dict) and job.get("id") == job_id:
                job.update(changes)

    def _run(self) -> None:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            self._set_state(
                status="failed",
                message=(
                    "Chưa cài Playwright. Hãy chạy: "
                    "./.venv/bin/python -m pip install -r requirements.txt"
                ),
            )
            self._set_job("", status="failed", message=str(error))
            return

        try:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            self._ensure_normal_chrome()
            with sync_playwright() as playwright:
                browser = self._connect_to_chrome(playwright)
                contexts = browser.contexts
                if not contexts:
                    raise RuntimeError("Chrome đã mở nhưng chưa có phiên làm việc để kết nối.")
                context = contexts[0]
                page = context.pages[0] if context.pages else context.new_page()
                self._set_state(
                    status="browser_open",
                    message=(
                        "Đã kết nối Chrome thường. Đăng nhập TikTok/Gmail và xử lý xác minh "
                        "thủ công nếu được hỏi."
                    ),
                )

                while True:
                    try:
                        command = self._commands.get(timeout=0.25)
                    except Empty:
                        continue

                    action = command.get("action")
                    if action == "close":
                        break
                    if action == "open":
                        self._open_upload_page(page, PlaywrightTimeoutError)
                    elif action == "open_auto":
                        self._open_upload_page(page, PlaywrightTimeoutError)
                        self._wait_for_login_then_upload(
                            page,
                            command,
                            PlaywrightTimeoutError,
                        )
                    elif action == "prepare_upload":
                        self._process_upload(page, command, PlaywrightTimeoutError)
        except Exception as error:
            self._set_state(
                status="failed",
                message=f"Không mở được TikTok bằng Playwright: {error}",
            )
        finally:
            with self._lock:
                if self._state.get("status") not in {"ready_to_post", "failed"}:
                    self._state.update(
                        status="closed",
                        message="Cửa sổ TikTok đã đóng.",
                    )

    def _ensure_normal_chrome(self) -> None:
        """Start a visible, non-headless Chrome instance with remote debugging."""

        if self._cdp_is_available():
            return

        chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if not chrome_path.exists():
            raise FileNotFoundError(
                "Không tìm thấy Google Chrome tại /Applications/Google Chrome.app."
            )

        subprocess.Popen(
            [
                str(chrome_path),
                f"--remote-debugging-port={self.CDP_PORT}",
                f"--user-data-dir={self.profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--new-window",
                self.UPLOAD_URL,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _cdp_is_available(self) -> bool:
        try:
            with urlopen(f"{self.cdp_url}/json/version", timeout=0.8):
                return True
        except (OSError, URLError):
            return False

    def _connect_to_chrome(self, playwright: Any) -> Any:
        deadline = time.monotonic() + 30
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                return playwright.chromium.connect_over_cdp(self.cdp_url)
            except Exception as error:
                last_error = error
                time.sleep(0.5)
        raise RuntimeError(
            f"Không kết nối được Chrome qua cổng {self.CDP_PORT}: {last_error}"
        )

    def _open_upload_page(self, page: Any, timeout_error: type[Exception]) -> None:
        try:
            if "tiktok.com" not in page.url or "/tiktokstudio/upload" not in page.url:
                page.goto(self.UPLOAD_URL, wait_until="domcontentloaded", timeout=45_000)
            self._set_state(
                status="browser_open",
                message=(
                    "TikTok Studio đã mở. Hãy đăng nhập thủ công nếu cần, "
                    "rồi chọn video trong Cliproom."
                ),
            )
        except timeout_error:
            self._set_state(
                status="browser_open",
                message=(
                    "TikTok đang tải lâu hơn dự kiến. Hãy kiểm tra cửa sổ Chrome, "
                    "đăng nhập thủ công rồi thử chuẩn bị upload lại."
                ),
            )

    def _wait_for_login_then_upload(
        self,
        page: Any,
        command: dict[str, Any],
        timeout_error: type[Exception],
    ) -> None:
        """Wait for the authenticated upload UI without touching login/CAPTCHA."""

        job_id = str(command["job_id"])
        self._set_state(
            status="waiting_login",
            message=(
                "Bạn chỉ cần đăng nhập và xử lý xác minh thủ công. "
                "Cliproom sẽ tự tiếp tục khi TikTok Studio sẵn sàng."
            ),
        )
        self._set_job(
            job_id,
            status="waiting_login",
            progress=0,
            message="Đang chờ bạn đăng nhập/xác minh trên Chrome...",
        )

        for _ in range(600):
            if self._has_close_command():
                return
            if self._upload_ui_ready(page):
                self._process_upload(page, command, timeout_error)
                return
            page.wait_for_timeout(1_000)

        message = "Đã chờ 10 phút nhưng TikTok Studio chưa sẵn sàng upload."
        self._set_job(job_id, status="failed", message=message)
        self._set_state(status="failed", message=message)

    def _has_close_command(self) -> bool:
        try:
            command = self._commands.get_nowait()
        except Empty:
            return False
        return command.get("action") == "close"

    @staticmethod
    def _upload_ui_ready(page: Any) -> bool:
        try:
            if "/tiktokstudio/upload" not in page.url:
                return False
            if page.locator('input[type="file"]').count() > 0:
                return True
            for text in ("Select video", "Upload video", "Choose video"):
                if page.get_by_text(text, exact=True).first.is_visible(timeout=400):
                    return True
        except Exception:
            return False
        return False

    def _process_upload(
        self,
        page: Any,
        command: dict[str, Any],
        timeout_error: type[Exception],
    ) -> None:
        job_id = str(command["job_id"])
        file_path = Path(str(command["file_path"])).resolve()
        caption = str(command.get("caption", "")).strip()
        self._set_job(job_id, status="running", progress=5, message="Đang mở trang upload TikTok...")
        self._set_state(status="uploading", message="Đang upload video lên TikTok...")

        try:
            if not file_path.is_file():
                raise FileNotFoundError(f"Không tìm thấy video: {file_path.name}")

            if "tiktok.com" not in page.url or "/tiktokstudio/upload" not in page.url:
                page.goto(self.UPLOAD_URL, wait_until="domcontentloaded", timeout=45_000)

            file_input = self._find_file_input(page, timeout_error)
            if file_input is None:
                raise RuntimeError(
                    "Chưa thấy ô chọn video. Hãy đăng nhập TikTok trên cửa sổ Chrome "
                    "rồi bấm chuẩn bị upload lại."
                )

            self._set_file_input_files(page, file_path)
            self._set_job(job_id, progress=40, message="TikTok đang xử lý video...")
            self._set_state(status="processing", message="TikTok đang xử lý video...")

            caption_box = self._find_caption_box(page, timeout_error)
            if caption_box is None:
                raise RuntimeError(
                    "Đã chọn video nhưng chưa tìm thấy ô caption. "
                    "Giao diện TikTok có thể đang yêu cầu thao tác tiếp trên Chrome."
                )
            if caption:
                caption_box.fill(caption)

            self._set_job(
                job_id,
                status="ready_to_post",
                progress=100,
                message="Đã upload và điền caption. Hãy kiểm tra rồi bấm Post trên TikTok.",
            )
            self._set_state(
                status="ready_to_post",
                message="Đã chuẩn bị xong. Kiểm tra video/caption trên Chrome rồi bấm Post.",
            )
        except timeout_error:
            self._set_job(
                job_id,
                status="failed",
                message="TikTok xử lý quá lâu. Hãy kiểm tra Chrome và thử lại.",
            )
            self._set_state(status="failed", message="TikTok xử lý quá lâu. Hãy kiểm tra Chrome.")
        except Exception as error:
            self._set_job(job_id, status="failed", message=str(error))
            self._set_state(status="failed", message=str(error))

    @staticmethod
    def _find_file_input(page: Any, timeout_error: type[Exception]) -> Any | None:
        selectors = [
            'input[type="file"]',
            'input[accept*="video"]',
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                locator.wait_for(state="attached", timeout=12_000)
                return locator
            except timeout_error:
                continue

        buttons = [
            'button:has-text("Select video")',
            'button:has-text("Upload")',
            '[role="button"]:has-text("Select video")',
        ]
        for selector in buttons:
            button = page.locator(selector).first
            try:
                if button.is_visible(timeout=1_000):
                    button.click()
                    page.locator('input[type="file"]').first.wait_for(
                        state="attached",
                        timeout=12_000,
                    )
                    return page.locator('input[type="file"]').first
            except timeout_error:
                continue
            except Exception:
                continue
        return None

    @staticmethod
    def _set_file_input_files(page: Any, file_path: Path) -> None:
        """Set a local file through CDP so large files stay on this Mac.

        Playwright's normal set_input_files transfers the file to the browser
        when connected over CDP and rejects files above 50MB. Chrome is local,
        so DOM.setFileInputFiles can hand it the filesystem path directly.
        """

        session = page.context.new_cdp_session(page)
        try:
            session.send("DOM.enable")
            document = session.send(
                "DOM.getDocument",
                {"depth": -1, "pierce": True},
            )
            root_id = document["root"]["nodeId"]
            node_id = 0
            for selector in (
                'input[type="file"]',
                'input[accept*="video"]',
            ):
                result = session.send(
                    "DOM.querySelector",
                    {"nodeId": root_id, "selector": selector},
                )
                node_id = result.get("nodeId", 0)
                if node_id:
                    break
            if not node_id:
                raise RuntimeError("Không tìm thấy ô chọn file trên TikTok Studio.")
            session.send(
                "DOM.setFileInputFiles",
                {
                    "files": [str(file_path)],
                    "nodeId": node_id,
                },
            )
        finally:
            try:
                session.detach()
            except Exception:
                pass

    @staticmethod
    def _find_caption_box(page: Any, timeout_error: type[Exception]) -> Any | None:
        selectors = [
            'textarea[placeholder*="caption" i]',
            'textarea[placeholder*="describe" i]',
            '[contenteditable="true"]',
            '[role="textbox"]',
            'textarea',
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=30_000)
                return locator
            except timeout_error:
                continue
        return None
