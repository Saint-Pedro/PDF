from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import HTTPException as FastHTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from . import __version__, engines, limits
from .i18n import translate
from .jobs import DONE, ERROR, QUEUED, RUNNING, Job, JobManager
from .tools import BY_ID, CATEGORIES, public_list

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
DATA = Path(os.environ.get("PDFSTUDIO_DATA", ROOT / "data"))
THEME_FILE = DATA / "theme.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
DATA.mkdir(parents=True, exist_ok=True)
MAX_QUEUE = int(os.environ.get("MAX_QUEUE", "50"))
_JOBS: JobManager | None = None


def jobs() -> JobManager:
    """Created lazily, in the server process only (spawned workers import this module too)."""
    global _JOBS
    if _JOBS is None:
        _JOBS = JobManager(
            DATA / "jobs",
            workers=int(os.environ.get("WORKERS", max(1, min(4, (os.cpu_count() or 2) - 1)))),
            timeout=int(os.environ.get("JOB_TIMEOUT", "900")),
            max_queue=MAX_QUEUE,
            ttl=int(os.environ.get("RESULT_TTL", "900")),
        )
    return _JOBS

# Branding is hard-coded in app/branding.json; only the chosen theme preset is stored at runtime.
BRANDING: dict = json.loads((ROOT / "app" / "branding.json").read_text("utf-8"))

app = FastAPI(title="PDF Studio", version=__version__, docs_url="/api/docs")
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
        "max_mb": limits.MAX_UPLOAD_MB,
        "version": __version__,
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


# ------------------------------------------------------------------ processing
def safe_name(name: str) -> str:
    name = Path(name or "file").name
    name = re.sub(r"[^\w.\- ()À-ÿ]", "_", name).strip() or "file"
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
            if size > limits.MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(413, f"File too large (max {limits.MAX_UPLOAD_MB} MB).")
            f.write(chunk)
    return dest


def job_view(job: Job, lang: str | None) -> dict:
    prog, label = jobs().progress(job)
    d = {"id": job.id, "tool": job.tool_id, "status": job.status, "progress": prog, "label": label,
         "position": jobs().position(job) if job.status == QUEUED else 0}
    if job.status == ERROR:
        d["error"] = translate(job.error or "", lang)
    if job.status == DONE and job.result:
        r = job.result
        d["result"] = {"name": r["name"], "size": r["size"], "in_size": job.in_size, "count": r["count"], "files": r["files"]}
    return d


async def create_job(tool_id: str, files: list[UploadFile], options: str, extra: UploadFile | None) -> Job:
    tool = BY_ID.get(tool_id)
    if not tool:
        raise HTTPException(404, "Unknown tool.")
    if tool.get("requires") and not engines.has(tool["requires"]):
        raise HTTPException(400, f"This tool requires {tool['requires']}.")
    try:
        opts = json.loads(options or "{}")
        assert isinstance(opts, dict)
    except Exception:
        raise HTTPException(400, "Invalid options.")
    files = [f for f in files if f is not None and f.filename]
    if tool.get("mode") != "url" and not files:
        raise HTTPException(400, "No file received.")
    if len(files) > limits.MAX_FILES:
        raise HTTPException(400, f"Too many files (max {limits.MAX_FILES}).")
    if jobs().pending() >= MAX_QUEUE:
        raise HTTPException(429, "The server is busy, please try again in a moment.")
    opts = {k: v for k, v in opts.items() if not k.startswith("_")}
    opts["_tool"] = tool_id
    jid, jdir = jobs().new_dir()
    try:
        used: set[str] = set()
        paths = [await store(f, jdir / "in", used) for f in files]
        accept = set(tool["accept"])
        for p in paths:
            if p.suffix.lower().lstrip(".") not in accept:
                raise HTTPException(400, f'"{p.name}" is not a format accepted by this tool.')
        if extra is not None and extra.filename:
            if Path(extra.filename).suffix.lower().lstrip(".") not in set(tool.get("extra_file", {}).get("accept", [])):
                raise HTTPException(400, f'"{extra.filename}" is not a format accepted by this tool.')
            opts["_image"] = str(await store(extra, jdir / "in", used))
        for p in paths:
            await run_in_threadpool(limits.check_file, p)
    except HTTPException:
        jobs().discard(jid)
        raise
    except ValueError as e:
        jobs().discard(jid)
        raise HTTPException(400, str(e))
    job = Job(id=jid, tool_id=tool_id, dir=jdir, inputs=[str(p) for p in paths], opts=opts,
              in_size=sum(p.stat().st_size for p in paths))
    jobs().submit(job)
    return job


@app.post("/api/jobs/{tool_id}")
async def start_job(request: Request, tool_id: str, files: list[UploadFile] = File(None),
                    options: str = Form("{}"), extra: UploadFile | None = File(None)):
    job = await create_job(tool_id, files or [], options, extra)
    return job_view(job, request.headers.get("x-lang"))


@app.get("/api/jobs/{jid}")
def job_status(request: Request, jid: str):
    job = jobs().get(jid)
    if not job:
        raise HTTPException(404, "This job no longer exists (its files have been deleted).")
    return job_view(job, request.headers.get("x-lang"))


@app.get("/api/jobs/{jid}/result")
def job_result(jid: str, keep: int = 0):
    job = jobs().get(jid)
    if not job or job.status != DONE or not job.result:
        raise HTTPException(404, "This job no longer exists (its files have been deleted).")
    path = Path(job.result["path"])
    bg = None if keep else BackgroundTask(jobs().delete, jid)  # deleted right after download
    return FileResponse(path, filename=job.result["name"], background=bg)


@app.delete("/api/jobs/{jid}")
def job_delete(jid: str):
    return {"deleted": jobs().delete(jid), "stored_files": jobs().stored_files()}


@app.get("/api/storage")
def storage():
    """Lets the UI prove that nothing is kept on the server."""
    return {"jobs": len(jobs().jobs), "stored_files": jobs().stored_files()}


@app.post("/api/process/{tool_id}")
async def process(tool_id: str, files: list[UploadFile] = File(None),
                  options: str = Form("{}"), extra: UploadFile | None = File(None)):
    """Synchronous API: upload, wait, download (files are deleted afterwards)."""
    job = await create_job(tool_id, files or [], options, extra)
    while job.status in (QUEUED, RUNNING):
        await asyncio.sleep(0.1)
    if job.status != DONE:
        err = job.error or "Unexpected error."
        jobs().delete(job.id)
        raise HTTPException(400, err)
    r = job.result
    headers = {"X-Input-Size": str(job.in_size), "X-Output-Size": str(r["size"]), "X-File-Count": str(r["count"]),
               "Access-Control-Expose-Headers": "X-Input-Size, X-Output-Size, X-File-Count, Content-Disposition"}
    return FileResponse(r["path"], filename=r["name"], headers=headers, background=BackgroundTask(jobs().delete, job.id))


@app.on_event("startup")
def _startup():
    jobs()  # wipe leftovers from a previous crash right away


@app.on_event("shutdown")
def _shutdown():
    if _JOBS is not None:
        _JOBS.shutdown()
