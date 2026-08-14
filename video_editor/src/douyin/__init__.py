"""Douyin ingestion helpers.

The downloader only accepts public Douyin URLs supplied by the user.  It does
not search Douyin or automate login/CAPTCHA flows.
"""

from .collector import DouyinPageCollector, build_search_url, is_douyin_user_url
from .downloader import (
    DownloadResult,
    DouyinDownloader,
    is_douyin_video_url,
    read_url_list,
)

__all__ = [
    "DownloadResult",
    "DouyinDownloader",
    "DouyinPageCollector",
    "build_search_url",
    "is_douyin_user_url",
    "is_douyin_video_url",
    "read_url_list",
]
