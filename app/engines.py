"""Détection des moteurs externes facultatifs (idée reprise de Filee :
le cœur fonctionne en natif, les moteurs lourds ne servent qu'en bonus)."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path


def _which(*names: str) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    # Emplacements courants Windows / macOS pour LibreOffice
    for p in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ):
        if any(n.startswith("soffice") for n in names) and os.path.exists(p):
            return p
    return None


def _module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


@lru_cache(maxsize=1)
def detect() -> dict[str, str | bool | None]:
    return {
        "libreoffice": _which("soffice", "libreoffice"),
        "ghostscript": _which("gs", "gswin64c", "gswin32c"),
        "ocrmypdf": _which("ocrmypdf"),
        "tesseract": _which("tesseract"),
        "pdf2docx": _module("pdf2docx"),
        "pdfplumber": _module("pdfplumber"),
        "pptx": _module("pptx"),
        "docx": _module("docx"),
        "openpyxl": _module("openpyxl"),
        "markdown": _module("markdown"),
        "heif": _module("pillow_heif"),
    }


def has(name: str) -> bool:
    return bool(detect().get(name))


def run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if res.returncode != 0:
        err = (res.stderr or res.stdout or b"").decode("utf-8", "ignore")[-800:]
        raise RuntimeError(f"{Path(cmd[0]).name} failed: {err}")
    return res


def libreoffice_convert(src: Path, fmt: str, outdir: Path, infilter: str | None = None) -> Path:
    """Convertit avec LibreOffice headless. Profil isolé pour pouvoir lancer
    plusieurs conversions en parallèle sans conflit de verrou."""
    soffice = detect()["libreoffice"]
    if not soffice:
        raise RuntimeError("LibreOffice is not installed.")
    with tempfile.TemporaryDirectory(prefix="lo-profile-") as prof:
        cmd = [
            str(soffice),
            f"-env:UserInstallation=file://{Path(prof).as_posix()}",
            "--headless", "--norestore", "--nologo",
        ]
        if infilter:
            cmd.append(f"--infilter={infilter}")
        cmd += ["--convert-to", fmt, "--outdir", str(outdir), str(src)]
        run(cmd, timeout=600)
    ext = fmt.split(":")[0]
    out = outdir / f"{src.stem}.{ext}"
    if not out.exists():
        raise RuntimeError("LibreOffice produced no file.")
    return out
