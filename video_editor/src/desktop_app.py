from __future__ import annotations

import shutil
import subprocess
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from .ui_server import UIHandler, VIDEO_DIR, WEB_DIR


HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


def open_desktop_window() -> None:
    """Open the local UI as a standalone Chrome app window on macOS."""

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if shutil.which("open") and Path(chrome).exists():
        subprocess.Popen(
            [
                "open",
                "-na",
                "Google Chrome",
                "--args",
                f"--app={URL}",
            ]
        )
        return

    webbrowser.open(URL)


def main() -> None:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), UIHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    open_desktop_window()
    print(f"Cliproom app running at {URL}")
    print("Press Ctrl+C to close the app server.")

    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Cliproom.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
