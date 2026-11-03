"""Job queue: every job runs in its own process.

* Jobs never block each other (PDFium is not thread-safe, so a process per job
  is what allows real parallelism) and a stuck job can be killed.
* Progress is reported through a small JSON file written by the worker.
* Input files are deleted as soon as processing ends; the result is deleted as
  soon as it has been downloaded, or after a short TTL.
* The jobs folder is wiped at startup, so a crash never leaves files behind.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import secrets
import shutil
import threading
import time
import traceback
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

QUEUED, RUNNING, DONE, ERROR, CANCELLED = "queued", "running", "done", "error", "cancelled"


@dataclass
class Job:
    id: str
    tool_id: str
    dir: Path
    inputs: list[str]
    opts: dict
    in_size: int
    status: str = QUEUED
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    error: str | None = None
    result: dict | None = None
    process: mp.Process | None = None


def worker_main(tool_id: str, inputs: list[str], opts: dict, job_dir: str) -> None:
    """Entry point of a job process."""
    import warnings
    from PIL import Image

    from . import progress
    from .tools import BY_ID

    warnings.simplefilter("error", Image.DecompressionBombWarning)
    Image.MAX_IMAGE_PIXELS = int(os.environ.get("MAX_IMAGE_PIXELS", "180000000"))
    jd = Path(job_dir)
    progress.init(str(jd / "progress.json"))
    res: dict
    try:
        out = jd / "out"
        out.mkdir(exist_ok=True)
        if opts.get("_image"):
            opts["_image"] = Path(opts["_image"])
        result = BY_ID[tool_id]["handler"]([Path(p) for p in inputs], opts, out)
        results = [Path(r) for r in (result if isinstance(result, list) else [result])]
        if not results:
            raise RuntimeError("No file was produced.")
        if len(results) == 1:
            final = results[0]
        else:
            progress.update(0.98, "zip")
            final = jd / f"{tool_id}_{time.strftime('%Y%m%d-%H%M%S')}.zip"
            with zipfile.ZipFile(final, "w", zipfile.ZIP_DEFLATED) as z:
                for r in results:
                    z.write(r, r.name)
        res = {"ok": True, "path": str(final), "name": final.name, "size": final.stat().st_size,
               "count": len(results), "files": [r.name for r in results][:500]}
    except (ValueError, RuntimeError) as e:
        res = {"ok": False, "error": str(e)}
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        res = {"ok": False, "error": "File rejected: image too large."}
    except Exception as e:  # pragma: no cover
        traceback.print_exc()
        res = {"ok": False, "error": f"Unexpected error: {e}"}
    finally:
        shutil.rmtree(jd / "in", ignore_errors=True)  # inputs are deleted right away
    (jd / "result.json").write_text(json.dumps(res), "utf-8")
    progress.update(1.0)


class JobManager:
    def __init__(self, root: Path, workers: int, timeout: int, max_queue: int, ttl: int):
        self.root = root
        self.workers = max(1, workers)
        self.timeout = timeout
        self.max_queue = max_queue
        self.ttl = ttl
        self.jobs: dict[str, Job] = {}
        self.reserved: set[str] = set()  # job dirs being uploaded
        self.lock = threading.Lock()
        self.ctx = mp.get_context("spawn")
        shutil.rmtree(root, ignore_errors=True)  # leftovers from a crash
        root.mkdir(parents=True, exist_ok=True)
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ---------------------------------------------------------------- API
    def new_dir(self) -> tuple[str, Path]:
        jid = secrets.token_urlsafe(12)
        d = self.root / jid
        (d / "in").mkdir(parents=True)
        self.reserved.add(jid)
        return jid, d

    def discard(self, jid: str) -> None:
        self.reserved.discard(jid)
        shutil.rmtree(self.root / jid, ignore_errors=True)

    def pending(self) -> int:
        with self.lock:
            return sum(1 for j in self.jobs.values() if j.status in (QUEUED, RUNNING))

    def submit(self, job: Job) -> None:
        with self.lock:
            self.jobs[job.id] = job
            self.reserved.discard(job.id)

    def get(self, jid: str) -> Job | None:
        return self.jobs.get(jid)

    def position(self, job: Job) -> int:
        with self.lock:
            queued = sorted((j for j in self.jobs.values() if j.status == QUEUED), key=lambda j: j.created)
            return next((i for i, j in enumerate(queued) if j.id == job.id), -1) + 1

    def progress(self, job: Job) -> tuple[float, str | None]:
        if job.status == DONE:
            return 1.0, None
        try:
            d = json.loads((job.dir / "progress.json").read_text())
            return float(d.get("progress", 0)), d.get("label")
        except Exception:
            return 0.0, None

    def delete(self, jid: str) -> bool:
        with self.lock:
            job = self.jobs.pop(jid, None)
        if not job:
            return False
        if job.process is not None and job.process.is_alive():
            job.process.terminate()
            job.process.join(5)
        shutil.rmtree(job.dir, ignore_errors=True)
        return True

    def stored_files(self) -> int:
        return sum(len(files) for _, _, files in os.walk(self.root))

    def shutdown(self) -> None:
        self._stop = True
        for jid in list(self.jobs):
            self.delete(jid)

    # ---------------------------------------------------------------- loop
    def _loop(self) -> None:
        last_janitor = 0.0
        while not self._stop:
            try:
                self._tick()
                if time.time() - last_janitor > 30:
                    self._janitor()
                    last_janitor = time.time()
            except Exception:  # pragma: no cover
                traceback.print_exc()
            time.sleep(0.15)

    def _tick(self) -> None:
        with self.lock:
            jobs = list(self.jobs.values())
        running = [j for j in jobs if j.status == RUNNING]
        for j in running:
            p = j.process
            if p is None:
                continue
            if not p.is_alive():
                p.join()
                self._finish(j)
            elif self.timeout and time.time() - (j.started or 0) > self.timeout:
                p.terminate()
                p.join(5)
                j.status, j.error, j.finished = ERROR, "Processing took too long and was stopped.", time.time()
                shutil.rmtree(j.dir, ignore_errors=True)
        free = self.workers - sum(1 for j in jobs if j.status == RUNNING)
        for j in sorted((j for j in jobs if j.status == QUEUED), key=lambda j: j.created)[:max(0, free)]:
            j.process = self.ctx.Process(target=worker_main, args=(j.tool_id, j.inputs, j.opts, str(j.dir)), daemon=True)
            j.status, j.started = RUNNING, time.time()
            j.process.start()

    def _finish(self, j: Job) -> None:
        j.finished = time.time()
        try:
            res = json.loads((j.dir / "result.json").read_text("utf-8"))
        except Exception:
            res = {"ok": False, "error": "Unexpected error: the worker stopped."}
        if res.get("ok"):
            j.status, j.result = DONE, res
        else:
            j.status, j.error = ERROR, res.get("error")
            shutil.rmtree(j.dir, ignore_errors=True)

    def _janitor(self) -> None:
        now = time.time()
        for jid, j in list(self.jobs.items()):
            if j.status in (DONE, ERROR, CANCELLED) and now - (j.finished or now) > self.ttl:
                self.delete(jid)
        # directories that no longer belong to a job
        for d in self.root.iterdir():
            if d.name not in self.jobs and d.name not in self.reserved and now - d.stat().st_mtime > 60:
                shutil.rmtree(d, ignore_errors=True)
