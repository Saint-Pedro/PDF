"""Protection against malicious or oversized files (checked before a job starts)."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "500"))   # per file
MAX_FILES = int(os.environ.get("MAX_FILES", "100"))           # per job
MAX_PAGES = int(os.environ.get("MAX_PAGES", "5000"))          # per PDF
MAX_UNZIPPED_MB = int(os.environ.get("MAX_UNZIPPED_MB", "1024"))
MAX_ZIP_RATIO = 200  # uncompressed / compressed

ZIP_BASED = {"docx", "docm", "dotx", "xlsx", "xlsm", "xltx", "pptx", "pptm", "potx", "ppsx",
             "odt", "ods", "odp", "odg", "ott", "ots", "otp", "epub", "pages", "numbers", "key"}


def check_file(path: Path) -> None:
    """Raise ValueError if the file looks dangerous."""
    ext = path.suffix.lower().lstrip(".")
    size = path.stat().st_size
    if ext in ZIP_BASED:
        try:
            with zipfile.ZipFile(path) as z:
                total = sum(i.file_size for i in z.infolist())
                if len(z.infolist()) > 20000 or total > MAX_UNZIPPED_MB * 1024 * 1024 or (size and total / size > MAX_ZIP_RATIO):
                    raise ValueError(f'"{path.name}" was rejected (suspicious compressed content).')
        except zipfile.BadZipFile:
            if ext not in ("pages", "numbers", "key"):
                raise ValueError(f'"{path.name}" is corrupted or not a valid document.')
    elif ext == "pdf":
        from pypdf import PdfReader
        try:
            r = PdfReader(str(path), strict=False)
            if r.is_encrypted:
                return  # page count unknown until unlocked
            n = len(r.pages)
        except Exception:
            return  # let the tool decide (Repair can handle broken files)
        if n > MAX_PAGES:
            raise ValueError(f'"{path.name}" has too many pages (max {MAX_PAGES}).')
