from __future__ import annotations

import http.cookiejar
import re
import shutil
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote, urlparse

from .downloader import is_douyin_url


VIDEO_URL_PATTERNS = (
    re.compile(
        r"(?:https?:)?//(?:www\.)?douyin\.com/video/"
        r"(?P<id>\d{15,20})"
    ),
    re.compile(
        r"(?:^|[\"'])/video/(?P<id>\d{15,20})(?:[/?#\"'])"
    ),
    re.compile(
        r"[\"'](?:aweme_id|awemeId|video_id|videoId)[\"']?\s*"
        r"[:=]\s*[\"'](?P<id>\d{15,20})[\"']"
    ),
)


def is_douyin_user_url(url: str) -> bool:
    """Return True for a Douyin user/profile URL."""

    if not is_douyin_url(url):
        return False

    return urlparse(url).path.rstrip("/").startswith("/user/")


def build_search_url(keyword: str) -> str:
    """Build Douyin's public video search page URL."""

    keyword = keyword.strip()
    if not keyword:
        raise ValueError("Keyword cannot be empty.")

    return (
        "https://www.douyin.com/search/"
        f"{quote(keyword, safe='')}?type=video"
    )


class DouyinVerificationRequired(RuntimeError):
    """Raised when Douyin returns an interactive browser verification page."""

    def __init__(self, url: str) -> None:
        super().__init__(
            "Douyin yêu cầu xác minh thủ công trong Chrome trước khi lấy kết quả."
        )
        self.url = url


class DouyinPageCollector:
    """Collect public video links from a Douyin user or search page.

    This is deliberately a lightweight public-page collector. It does not
    solve challenges, sign requests, automate login, or bypass access controls.
    """

    def __init__(
        self,
        cookies_file: Path | None = None,
        browser_name: str | None = None,
        user_agent: str | None = None,
        timeout: int = 20,
        status_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self.timeout = timeout
        self.status_callback = status_callback
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        )
        self.cookie_jar = http.cookiejar.MozillaCookieJar()

        if browser_name:
            try:
                from yt_dlp.cookies import extract_cookies_from_browser

                self.cookie_jar = extract_cookies_from_browser(browser_name)
            except Exception as error:
                raise RuntimeError(
                    f"Could not read cookies from {browser_name}: {error}"
                ) from error

        elif cookies_file is not None:
            if not cookies_file.is_file():
                raise FileNotFoundError(
                    f"Cookies file not found: {cookies_file}"
                )

            try:
                self.cookie_jar.load(
                    str(cookies_file),
                    ignore_discard=True,
                    ignore_expires=True,
                )
            except (OSError, http.cookiejar.LoadError) as error:
                raise ValueError(
                    "Cookies file must be in Netscape cookie format."
                ) from error

        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def collect_user(self, user_url: str, limit: int) -> list[str]:
        if not is_douyin_user_url(user_url):
            raise ValueError(
                "User URL must look like "
                "https://www.douyin.com/user/..."
            )

        return self._collect(user_url, limit)

    def search(self, keyword: str, limit: int) -> list[str]:
        return self._collect(build_search_url(keyword), limit)

    def _collect(self, page_url: str, limit: int) -> list[str]:
        if limit < 1:
            raise ValueError("Limit must be at least 1.")

        video_ids = self._collect_from_browser(page_url, limit)

        if not video_ids:
            raise RuntimeError(
                "Douyin page returned no video URLs. The page may require "
                "a fresh cookie, login, CAPTCHA confirmation, or its HTML "
                "format may have changed."
            )

        return [
            f"https://www.douyin.com/video/{video_id}"
            for video_id in video_ids[:limit]
        ]

    def _collect_from_browser(self, page_url: str, limit: int) -> list[str]:
        """Read links from a rendered browser page after manual verification."""

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Chưa cài Playwright. Hãy chạy pip install -r requirements.txt"
            ) from error

        chrome_path = Path(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        profile_dir = Path(tempfile.mkdtemp(prefix="cliproom-douyin-"))
        deadline = time.monotonic() + max(120, self.timeout * 6)
        last_status = ""
        collected_ids: list[str] = []

        try:
            with sync_playwright() as playwright:
                launch_options = {
                    "headless": False,
                    "viewport": {"width": 1440, "height": 960},
                    "locale": "zh-CN",
                    "user_agent": self.user_agent,
                }
                if chrome_path.is_file():
                    launch_options["executable_path"] = str(chrome_path)

                context = playwright.chromium.launch_persistent_context(
                    str(profile_dir),
                    **launch_options,
                )

                try:
                    self._add_douyin_cookies(context)
                    page = context.pages[0] if context.pages else context.new_page()
                    try:
                        page.goto(
                            page_url,
                            wait_until="domcontentloaded",
                            timeout=self.timeout * 1000,
                        )
                    except PlaywrightTimeoutError:
                        # Douyin can keep network requests open after the page
                        # is already usable. Continue with the rendered DOM.
                        pass

                    while time.monotonic() < deadline:
                        html = self._safe_page_content(page)

                        collected_ids = self._extract_video_ids(html)
                        if collected_ids:
                            if len(collected_ids) < limit:
                                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                page.wait_for_timeout(1500)
                                collected_ids = self._extract_video_ids(
                                    self._safe_page_content(page)
                                )
                            if collected_ids:
                                return collected_ids[:limit]

                        if self._page_needs_verification(page, html):
                            message = (
                                "Đang chờ bạn xác minh CAPTCHA trên Chrome. "
                                "Xác minh xong, trang sẽ tự được đọc lại."
                            )
                        else:
                            message = "Đang chờ Douyin render danh sách video..."

                        if message != last_status:
                            last_status = message
                            if self.status_callback:
                                self.status_callback(message, page_url)
                        page.wait_for_timeout(2000)
                finally:
                    context.close()
        except Exception as error:
            if error.__class__.__name__ == "Error" and "Executable doesn't exist" in str(error):
                raise RuntimeError(
                    "Không tìm thấy trình duyệt Chromium để đọc trang Douyin."
                ) from error
            raise
        finally:
            shutil.rmtree(profile_dir, ignore_errors=True)

        raise DouyinVerificationRequired(page_url)

    @staticmethod
    def _safe_page_content(page) -> str:
        try:
            return page.content()
        except Exception as error:
            # During Douyin's client-side redirects the DOM can be briefly
            # unavailable. The next polling iteration will read it again.
            return "" if "page is navigating" in str(error).lower() else ""

    def _add_douyin_cookies(self, context) -> None:
        cookies = []
        for cookie in self.cookie_jar:
            domain = cookie.domain or ".douyin.com"
            if "douyin.com" not in domain:
                continue
            item = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": domain,
                "path": cookie.path or "/",
                "secure": bool(cookie.secure),
                "httpOnly": bool(cookie._rest.get("HttpOnly")),
                "sameSite": "Lax",
            }
            cookies.append(item)

        if cookies:
            context.add_cookies(cookies)

    @staticmethod
    def _page_needs_verification(page, html: str) -> bool:
        try:
            body_text = page.locator("body").inner_text(timeout=1000).lower()
        except Exception:
            body_text = ""
        lowered_html = html.lower()
        return any(
            marker in body_text
            or marker in lowered_html
            for marker in (
                "请完成下列验证后继续",
                "按住左边按钮拖动完成上方拼图",
                "验证码中间页",
                "_$jsvmprt",
            )
        )

    def _fetch(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "User-Agent": self.user_agent,
            },
        )

        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                content_type = response.headers.get_content_charset() or "utf-8"
                html = response.read().decode(content_type, errors="replace")
        except urllib.error.HTTPError as error:
            raise RuntimeError(
                f"Douyin returned HTTP {error.code} for {url}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                f"Could not connect to Douyin: {error.reason}"
            ) from error

        marker_text = html[:4000].lower()
        verification_markers = (
            "验证码中间页",
            "captchaoptions",
            "_$jsvmprt",
        )
        if any(marker in marker_text or marker in html.lower() for marker in verification_markers):
            raise DouyinVerificationRequired(url)

        return html

    @staticmethod
    def _extract_video_ids(html: str) -> list[str]:
        # SSR/JSON responses commonly escape slashes. Normalizing them lets
        # the same patterns handle both HTML links and embedded JSON.
        normalized = (
            html.replace("\\/", "/")
            .replace("\\u002F", "/")
            .replace("\\u002f", "/")
        )

        ids: list[str] = []
        seen: set[str] = set()

        for pattern in VIDEO_URL_PATTERNS:
            for match in pattern.finditer(normalized):
                video_id = match.group("id")
                if video_id in seen:
                    continue
                seen.add(video_id)
                ids.append(video_id)

        return ids
