"""Progress reporting from inside a job process.

The worker calls ``init(path)``; tool code then calls ``update(fraction)`` or
uses ``span(a, b)`` to map a sub-task onto part of the overall range. The
progress is written to a small JSON file that the server reads. Outside a job
(tests, direct calls) every function is a no-op."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager

_path: str | None = None
_stack: list[tuple[float, float]] = [(0.0, 1.0)]
_last = 0.0
_label: str | None = None


def init(path: str | None) -> None:
    global _path, _stack, _last
    _path, _stack, _last = path, [(0.0, 1.0)], 0.0
    _write(0.0, force=True)


def _write(value: float, force: bool = False) -> None:
    global _last
    if not _path:
        return
    now = time.monotonic()
    if not force and now - _last < 0.15:
        return
    _last = now
    tmp = _path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump({"progress": round(max(0.0, min(1.0, value)), 4), "label": _label}, f)
        os.replace(tmp, _path)
    except OSError:
        pass


def update(fraction: float, label: str | None = None) -> None:
    """Report progress of the current (sub-)task, 0..1."""
    global _label
    if label is not None:
        _label = label
    base, size = _stack[-1]
    _write(base + size * max(0.0, min(1.0, fraction)))


def step(i: int, n: int, label: str | None = None) -> None:
    update(i / n if n else 1.0, label)


@contextmanager
def span(start: float, end: float):
    """Map nested progress updates onto [start, end] of the current range."""
    base, size = _stack[-1]
    _stack.append((base + size * start, size * (end - start)))
    try:
        yield
    finally:
        _stack.pop()
        _write(base + size * end)


def each(items, label: str | None = None):
    """Iterate while splitting the current range evenly between items."""
    items = list(items)
    n = len(items) or 1
    for i, it in enumerate(items):
        with span(i / n, (i + 1) / n):
            update(0, label)
            yield it
