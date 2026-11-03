"""Web page / HTML to PDF using the Chrome-based browser already installed on the
machine (Chrome, Edge, Chromium, Brave), driven headless through the Chrome
DevTools Protocol. No extra download: Edge ships with Windows.

Three rendering modes:
* ``print``  – what you get when printing the page from the browser (uses the
  site's print stylesheet, paginated);
* ``screen`` – the page as displayed on a desktop screen, paginated;
* ``single`` – the page as displayed on screen, as one long page (no cuts).

Before printing, the page is scrolled to the bottom (lazy-loaded images) and
cookie / consent banners can be hidden."""
from __future__ import annotations

import base64
import glob
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from . import progress

CANDIDATES = [
    # Windows
    r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
    r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
    r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
    r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe",
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]
LINUX_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"]

HIDE_BANNERS_JS = r"""
(() => {
  const words = /(cookie|consent|gdpr|rgpd|cmp|onetrust|didomi|axeptio|tarteaucitron|quantcast|usercentrics|cookiebot)/i;
  for (const el of document.querySelectorAll('body *')) {
    const s = getComputedStyle(el);
    const tag = (el.id || '') + ' ' + (typeof el.className === 'string' ? el.className : '');
    if ((s.position === 'fixed' || s.position === 'sticky') && words.test(tag)) el.style.setProperty('display', 'none', 'important');
  }
  for (const el of document.querySelectorAll('[id*=cookie i],[class*=cookie-banner i],[id*=consent i],[class*=consent i],#onetrust-consent-sdk,#didomi-host,#axeptio_overlay,#tarteaucitronRoot,#CybotCookiebotDialog,#usercentrics-root'))
    el.style.setProperty('display', 'none', 'important');
  document.documentElement.style.setProperty('overflow', 'visible', 'important');
  document.body && document.body.style.setProperty('overflow', 'visible', 'important');
})();
"""

SCROLL_JS = r"""
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  let last = -1;
  for (let i = 0; i < 60; i++) {
    window.scrollBy(0, window.innerHeight);
    await sleep(120);
    const h = document.documentElement.scrollHeight;
    if (window.scrollY + window.innerHeight >= h - 2) { if (h === last) break; last = h; }
  }
  window.scrollTo(0, 0);
  await sleep(200);
  return true;
})()
"""


@lru_cache(maxsize=1)
def find_browser() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    for c in CANDIDATES:
        p = os.path.expandvars(c)
        if "%" not in p and os.path.exists(p):
            return p
    for name in LINUX_NAMES:
        p = shutil.which(name)
        if p:
            return p
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux*/chrome", str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux*/chrome")):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


# ------------------------------------------------------------------ minimal WebSocket client (CDP over localhost)
class _WS:
    def __init__(self, url: str, timeout: float = 60):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {u.path}{'?' + u.query if u.query else ''} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
               f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("Browser connection failed.")
            resp += chunk
        if b" 101 " not in resp.split(b"\r\n")[0]:
            raise RuntimeError("Browser connection failed.")
        self.buf = resp.split(b"\r\n\r\n", 1)[1]

    def _recv(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buf)))
            if not chunk:
                raise RuntimeError("Browser connection closed.")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text: str) -> None:
        data = text.encode()
        mask = os.urandom(4)
        n = len(data)
        head = bytes([0x81])
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(head + mask + masked)

    def recv(self) -> str:
        message = b""
        while True:
            b1, b2 = self._recv(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv(8))[0]
            payload = self._recv(n)
            if op == 0x8:
                raise RuntimeError("Browser connection closed.")
            if op == 0x9:  # ping
                continue
            message += payload
            if fin:
                return message.decode("utf-8", "replace")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class _CDP:
    def __init__(self, ws_url: str):
        self.ws = _WS(ws_url)
        self.n = 0
        self.events: list[dict] = []

    def call(self, method: str, params: dict | None = None, timeout: float = 60) -> dict:
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        end = time.time() + timeout
        self.ws.sock.settimeout(timeout)
        while time.time() < end:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"Browser error: {msg['error'].get('message')}")
                return msg.get("result", {})
            self.events.append(msg)
        raise RuntimeError("The browser did not respond in time.")

    def wait_event(self, names: set[str], timeout: float) -> bool:
        end = time.time() + timeout
        for e in self.events:
            if e.get("method") in names or e.get("params", {}).get("name") in names:
                self.events.clear()
                return True
        while time.time() < end:
            self.ws.sock.settimeout(max(0.1, end - time.time()))
            try:
                msg = json.loads(self.ws.recv())
            except (socket.timeout, TimeoutError):
                return False
            if msg.get("method") in names or msg.get("params", {}).get("name") in names:
                return True
        return False


PAPER = {"a4": (8.27, 11.69), "letter": (8.5, 11.0), "a3": (11.69, 16.54), "legal": (8.5, 14.0)}
MARGINS = {"none": 0.0, "small": 0.4, "normal": 0.8}


def render(target: str, out: Path, opts: dict) -> Path:
    """target: http(s) URL or local file path."""
    exe = find_browser()
    if not exe:
        raise RuntimeError("A Chrome-based browser (Chrome, Edge, Chromium or Brave) is required.")
    profile = tempfile.mkdtemp(prefix="pdfstudio-browser-")
    proc = subprocess.Popen(
        [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
         "--hide-scrollbars", "--mute-audio", "--disable-background-networking", "--disable-sync",
         "--remote-debugging-port=0", f"--user-data-dir={profile}", "--no-sandbox",
         *os.environ.get("PDFSTUDIO_CHROME_ARGS", "").split(), "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp = None
    try:
        progress.update(0.05, "browser")
        port_file = Path(profile) / "DevToolsActivePort"
        for _ in range(200):
            if port_file.exists() and port_file.read_text().strip():
                break
            if proc.poll() is not None:
                raise RuntimeError("The browser could not be started.")
            time.sleep(0.05)
        port = int(port_file.read_text().splitlines()[0])
        targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10).read())
        page = next(t for t in targets if t.get("type") == "page")
        cdp = _CDP(page["webSocketDebuggerUrl"])
        mode = opts.get("render", "print")
        width_px = 1280
        cdp.call("Page.enable")
        cdp.call("Page.setLifecycleEventsEnabled", {"enabled": True})
        if mode in ("screen", "single"):
            cdp.call("Emulation.setEmulatedMedia", {"media": "screen"})
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width_px, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        url = target if "://" in target else Path(target).resolve().as_uri()
        progress.update(0.15, "loading")
        nav = cdp.call("Page.navigate", {"url": url}, timeout=60)
        if nav.get("errorText"):
            raise RuntimeError(f"Unable to open the page ({nav['errorText']}).")
        cdp.wait_event({"Page.loadEventFired"}, timeout=45)
        cdp.wait_event({"networkIdle"}, timeout=8)
        progress.update(0.5, "scrolling")
        cdp.call("Runtime.evaluate", {"expression": SCROLL_JS, "awaitPromise": True}, timeout=30)
        if opts.get("hide_banners", True):
            cdp.call("Runtime.evaluate", {"expression": HIDE_BANNERS_JS})
        time.sleep(0.4)
        progress.update(0.75, "printing")
        landscape = opts.get("orientation") == "landscape"
        margin = MARGINS.get(opts.get("margin", "small"), 0.4)
        params = {"printBackground": bool(opts.get("background", True)), "landscape": landscape,
                  "marginTop": margin, "marginBottom": margin, "marginLeft": margin, "marginRight": margin,
                  "displayHeaderFooter": False}
        if mode == "single":
            h = cdp.call("Runtime.evaluate", {"expression": "Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)", "returnByValue": True})
            height_px = int(h.get("result", {}).get("value") or 2000)
            params.update({"paperWidth": width_px / 96, "paperHeight": min(height_px / 96 + 0.1, 200),
                           "marginTop": 0, "marginBottom": 0, "marginLeft": 0, "marginRight": 0, "landscape": False,
                           "pageRanges": "1"})
        else:
            w, h = PAPER.get(opts.get("page_size", "a4"), PAPER["a4"])
            params.update({"paperWidth": w, "paperHeight": h, "preferCSSPageSize": mode == "print"})
            if mode == "screen":  # fit the 1280 px desktop layout to the paper width
                usable = (h if landscape else w) - 2 * margin
                params["scale"] = max(0.1, min(1.0, usable * 96 / width_px))
        res = cdp.call("Page.printToPDF", params, timeout=120)
        out.write_bytes(base64.b64decode(res["data"]))
        progress.update(1.0)
        return out
    finally:
        if cdp is not None:
            try:
                cdp.call("Browser.close", timeout=3)
            except Exception:
                pass
            cdp.ws.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def normalize_url(raw: str) -> str:
    u = (raw or "").strip()
    if not u:
        raise ValueError("Enter a web address.")
    if "://" not in u:
        u = "https://" + u
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("Enter a valid web address (http or https).")
    return u
