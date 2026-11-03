"""Desktop launcher: starts the local server and opens PDF Studio in its own
window (or in the default browser when no web view is available).

Packaged into a single executable with PyInstaller (see pdfstudio.spec)."""
from __future__ import annotations

import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    d = base / "PDF Studio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(port: int, timeout: float = 30) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


def main() -> None:
    multiprocessing.freeze_support()  # job workers are spawned processes
    if sys.stdout is None or sys.stderr is None:  # windowed build: no console
        sys.stdout = sys.stderr = open(os.devnull, "w")
    os.environ.setdefault("PDFSTUDIO_DATA", str(user_data_dir()))
    import uvicorn
    from app.main import app

    port = int(os.environ.get("PORT") or free_port())
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    if not wait_for(port):
        sys.exit("PDF Studio could not start.")
    url = f"http://127.0.0.1:{port}/"

    try:
        import webview  # pywebview: native window (Edge WebView2 on Windows, WebKit on macOS)
        webview.create_window("PDF Studio", url, width=1320, height=880, min_size=(900, 600))
        webview.start()
    except Exception:
        webbrowser.open(url)
        print(f"PDF Studio is running at {url} — close this window to quit.")
        try:
            while thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    server.should_exit = True
    thread.join(5)


if __name__ == "__main__":
    main()
