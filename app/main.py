from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import HTTPException as FastHTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from . import engines, pdfops
from .i18n import translate
from .tools import BY_ID, CATEGORIES, public_list

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
DATA = Path(os.environ.get("PDFSTUDIO_DATA", ROOT / "data"))
THEME_FILE = DATA / "theme.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "500"))
DATA.mkdir(parents=True, exist_ok=True)

# Branding is hard-coded in app/branding.json; only the chosen theme preset is stored at runtime.
BRANDING: dict = json.loads((ROOT / "app" / "branding.json").read_text("utf-8"))

app = FastAPI(title="PDF Studio", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.exception_handler(FastHTTPException)
async def http_error(request: Request, exc: FastHTTPException):
    detail = translate(str(exc.detail), request.headers.get("x-lang"))
    return JSONResponse({"detail": detail}, status_code=exc.status_code)


# ------------------------------------------------------------------ branding
def load_branding() -> dict:
    b = dict(BRANDING)
    if THEME_FILE.exists():
        try:
            b["preset"] = json.loads(THEME_FILE.read_text("utf-8")).get("preset")
        except Exception:
            pass
    return b


def check_admin(pw: str | None):
    if ADMIN_PASSWORD and not secrets.compare_digest(pw or "", ADMIN_PASSWORD):
        raise HTTPException(401, "Admin password required.")


@app.get("/", response_class=HTMLResponse)
@app.get("/tool/{_any:path}", response_class=HTMLResponse)
@app.get("/themes", response_class=HTMLResponse)
def index(_any: str = ""):
    b = load_branding()
    html = (STATIC / "index.html").read_text("utf-8")
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    html = (html.replace("{{TITLE}}", esc(b.get("name")))
                .replace("{{FAVICON}}", esc(b.get("favicon") or b.get("logo") or "/static/img/favicon.svg"))
                .replace("{{BRANDING}}", json.dumps(b).replace("</", "<\\/")))
    return HTMLResponse(html)


@app.get("/api/config")
def config():
    return {
        "branding": load_branding(),
        "tools": public_list(),
        "categories": CATEGORIES,
        "engines": {k: bool(v) for k, v in engines.detect().items()},
        "admin_protected": bool(ADMIN_PASSWORD),
        "max_mb": MAX_MB,
    }


@app.put("/api/theme")
async def save_theme(request: Request, x_admin_password: str | None = Header(None)):
    check_admin(x_admin_password)
    data = await request.json()
    preset = data.get("preset") if isinstance(data, dict) else None
    if preset is not None and not (isinstance(preset, str) and re.fullmatch(r"[a-z0-9_-]{1,40}", preset)):
        raise HTTPException(400, "Invalid format.")
    THEME_FILE.write_text(json.dumps({"preset": preset}), "utf-8")
    return load_branding()


# ------------------------------------------------------------------ traitement
def safe_name(name: str) -> str:
    name = Path(name or "fichier").name
    name = re.sub(r"[^\w.\- ()À-ÿ]", "_", name).strip() or "fichier"
    return name[:150]


async def store(upload: UploadFile, folder: Path, used: set[str]) -> Path:
    name = safe_name(upload.filename)
    stem, suf = Path(name).stem, Path(name).suffix
    k = 1
    while name.lower() in used:
        k += 1
        name = f"{stem} ({k}){suf}"
    used.add(name.lower())
    dest = folder / name
    size = 0
    with dest.open("wb") as f:
        while chunk := await upload.read(1 << 20):
            size += len(chunk)
            if size > MAX_MB * 1024 * 1024:
                raise HTTPException(413, f"File too large (max {MAX_MB} MB).")
            f.write(chunk)
    return dest


@app.post("/api/process/{tool_id}")
async def process(tool_id: str, files: list[UploadFile] = File(...),
                  options: str = Form("{}"), extra: UploadFile | None = File(None)):
    tool = BY_ID.get(tool_id)
    if not tool:
        raise HTTPException(404, "Unknown tool.")
    if tool.get("requires") and not engines.has(tool["requires"]):
        raise HTTPException(400, f"This tool requires {tool['requires']}.")
    try:
        opts = json.loads(options or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid options.")
    opts["_tool"] = tool_id

    work = Path(tempfile.mkdtemp(prefix="pdfstudio-"))
    cleanup = BackgroundTask(shutil.rmtree, work, ignore_errors=True)
    try:
        inp = work / "in"
        out = work / "out"
        inp.mkdir()
        out.mkdir()
        used: set[str] = set()
        paths = [await store(f, inp, used) for f in files]
        accept = set(tool["accept"])
        for p in paths:
            if p.suffix.lower().lstrip(".") not in accept:
                raise HTTPException(400, f'"{p.name}" is not a format accepted by this tool.')
        if extra is not None and extra.filename:
            opts["_image"] = await store(extra, inp, used)
        in_size = sum(p.stat().st_size for p in paths)

        result = await run_in_threadpool(tool["handler"], paths, opts, out)
        results = result if isinstance(result, list) else [result]
        results = [Path(r) for r in results]
        if not results:
            raise HTTPException(500, "No file was produced.")
        if len(results) == 1:
            final = results[0]
        else:
            final = work / f"{tool_id}_{time.strftime('%Y%m%d-%H%M%S')}.zip"
            with zipfile.ZipFile(final, "w", zipfile.ZIP_DEFLATED) as z:
                for r in results:
                    z.write(r, r.name)
        headers = {
            "X-Input-Size": str(in_size),
            "X-Output-Size": str(final.stat().st_size),
            "X-File-Count": str(len(results)),
            "Access-Control-Expose-Headers": "X-Input-Size, X-Output-Size, X-File-Count, Content-Disposition",
        }
        return FileResponse(final, filename=final.name, headers=headers, background=cleanup)
    except HTTPException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    except (ValueError, RuntimeError) as e:
        shutil.rmtree(work, ignore_errors=True)
        raise HTTPException(400, str(e))
    except Exception as e:  # pragma: no cover
        shutil.rmtree(work, ignore_errors=True)
        raise HTTPException(500, f"Unexpected error: {e}")


@app.post("/api/preview")
async def preview(file: UploadFile = File(...), width: int = Form(220), password: str = Form(""),
                  max_pages: int = Form(500)):
    work = Path(tempfile.mkdtemp(prefix="pdfstudio-prev-"))
    try:
        p = await store(file, work, set())
        try:
            data = await run_in_threadpool(pdfops.thumbnails, p, min(max(width, 60), 1400), max(1, min(max_pages, 2000)), password or None)
        except Exception as e:
            msg = str(e).lower()
            if "password" in msg:
                return JSONResponse({"error": "password"}, status_code=423)
            raise HTTPException(400, "Unable to read this PDF.")
        return data
    finally:
        shutil.rmtree(work, ignore_errors=True)
