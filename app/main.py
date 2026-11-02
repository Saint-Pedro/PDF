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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from . import engines, pdfops
from .tools import BY_ID, CATEGORIES, public_list

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
DATA = Path(os.environ.get("PDFSTUDIO_DATA", ROOT / "data"))
ASSETS = DATA / "assets"
BRANDING_FILE = DATA / "branding.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "500"))
ASSETS.mkdir(parents=True, exist_ok=True)

DEFAULT_BRANDING: dict = json.loads((ROOT / "app" / "default_branding.json").read_text("utf-8"))

app = FastAPI(title="PDF Studio", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")


# ------------------------------------------------------------------ branding
def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load_branding() -> dict:
    if BRANDING_FILE.exists():
        try:
            return deep_merge(DEFAULT_BRANDING, json.loads(BRANDING_FILE.read_text("utf-8")))
        except Exception:
            pass
    return DEFAULT_BRANDING


def check_admin(pw: str | None):
    if ADMIN_PASSWORD and not secrets.compare_digest(pw or "", ADMIN_PASSWORD):
        raise HTTPException(401, "Mot de passe administrateur requis.")


@app.get("/", response_class=HTMLResponse)
@app.get("/outil/{_any:path}", response_class=HTMLResponse)
@app.get("/personnaliser", response_class=HTMLResponse)
def index(_any: str = ""):
    b = load_branding()
    html = (STATIC / "index.html").read_text("utf-8")
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    favicon = b.get("favicon") or b.get("logo") or "/static/img/favicon.svg"
    html = (html.replace("{{TITLE}}", esc(b.get("name")))
                .replace("{{FAVICON}}", esc(favicon))
                .replace("{{BRANDING}}", json.dumps(b).replace("</", "<\\/")))
    return HTMLResponse(html)


@app.get("/api/config")
def config():
    return {
        "branding": load_branding(),
        "defaults": DEFAULT_BRANDING,
        "tools": public_list(),
        "categories": CATEGORIES,
        "engines": {k: bool(v) for k, v in engines.detect().items()},
        "admin_protected": bool(ADMIN_PASSWORD),
        "max_mb": MAX_MB,
    }


@app.put("/api/branding")
async def save_branding(request: Request, x_admin_password: str | None = Header(None)):
    check_admin(x_admin_password)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(400, "Format invalide.")
    merged = deep_merge(DEFAULT_BRANDING, data)
    BRANDING_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")
    return merged


@app.delete("/api/branding")
def reset_branding(x_admin_password: str | None = Header(None)):
    check_admin(x_admin_password)
    BRANDING_FILE.unlink(missing_ok=True)
    return DEFAULT_BRANDING


ASSET_EXT = {"logo": {"png", "jpg", "jpeg", "svg", "webp", "gif"},
             "favicon": {"png", "svg", "ico", "jpg", "jpeg", "webp"},
             "font": {"woff2", "woff", "ttf", "otf"},
             "image": {"png", "jpg", "jpeg", "svg", "webp"}}


@app.post("/api/branding/asset")
async def upload_asset(kind: str = Form(...), file: UploadFile = File(...),
                       x_admin_password: str | None = Header(None)):
    check_admin(x_admin_password)
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if kind not in ASSET_EXT or ext not in ASSET_EXT[kind]:
        raise HTTPException(400, f"Type de fichier non accepté pour {kind}.")
    name = f"{kind}-{int(time.time())}-{secrets.token_hex(3)}.{ext}"
    dest = ASSETS / name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/assets/{name}", "name": Path(file.filename or name).stem}


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
                raise HTTPException(413, f"Fichier trop volumineux (max {MAX_MB} Mo).")
            f.write(chunk)
    return dest


@app.post("/api/process/{tool_id}")
async def process(tool_id: str, files: list[UploadFile] = File(...),
                  options: str = Form("{}"), extra: UploadFile | None = File(None)):
    tool = BY_ID.get(tool_id)
    if not tool:
        raise HTTPException(404, "Outil inconnu.")
    if tool.get("requires") and not engines.has(tool["requires"]):
        raise HTTPException(400, f"Cet outil nécessite {tool['requires']}.")
    try:
        opts = json.loads(options or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Options invalides.")
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
                raise HTTPException(400, f"« {p.name} » n'est pas un format accepté par cet outil.")
        if extra is not None and extra.filename:
            opts["_image"] = await store(extra, inp, used)
        in_size = sum(p.stat().st_size for p in paths)

        result = await run_in_threadpool(tool["handler"], paths, opts, out)
        results = result if isinstance(result, list) else [result]
        results = [Path(r) for r in results]
        if not results:
            raise HTTPException(500, "Aucun fichier produit.")
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
        raise HTTPException(500, f"Erreur inattendue : {e}")


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
            raise HTTPException(400, "Impossible de lire ce PDF.")
        return data
    finally:
        shutil.rmtree(work, ignore_errors=True)
