"""Built-in PDF operations (pypdf + pypdfium2 + reportlab + Pillow)."""
from __future__ import annotations

import base64
import functools
import threading
import io
import re
from pathlib import Path
from typing import Callable

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.constants import UserAccessPermissions as Perm
from pypdf.generic import RectangleObject
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from . import engines, progress

MM = 72 / 25.4

# PDFium is not thread-safe: every access goes through this lock.
PDFIUM_LOCK = threading.RLock()


def pdfium_safe(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        with PDFIUM_LOCK:
            return fn(*a, **kw)
    return wrapper


# ---------------------------------------------------------------- helpers
def parse_ranges(spec: str, total: int) -> list[list[int]]:
    """'1-3, 5, 8-' -> [[0,1,2],[4],[7..total-1]] (indices base 0)."""
    groups: list[list[int]] = []
    for part in re.split(r"[,;]", spec or ""):
        part = part.strip().lower()
        if not part:
            continue
        if part in ("all", "tout", "toutes"):
            groups.append(list(range(total)))
            continue
        m = re.fullmatch(r"(\d*)\s*-\s*(\d*)", part)
        if m:
            a = int(m.group(1) or 1)
            b = int(m.group(2) or total)
        elif part.isdigit():
            a = b = int(part)
        else:
            raise ValueError(f'Invalid range: "{part}"')
        a, b = max(1, a), min(total, b)
        if a > b:
            raise ValueError(f'Empty range: "{part}"')
        groups.append(list(range(a - 1, b)))
    if not groups:
        raise ValueError("No pages specified.")
    return groups


def flat_pages(spec: str, total: int) -> list[int]:
    seen: list[int] = []
    for g in parse_ranges(spec, total):
        for i in g:
            if i not in seen:
                seen.append(i)
    return seen


def open_reader(path: Path, password: str | None = None) -> PdfReader:
    r = PdfReader(str(path), strict=False)
    if r.is_encrypted:
        if not r.decrypt(password or ""):
            raise ValueError(f'"{path.name}" is password-protected.')
    return r


def save(writer: PdfWriter, out: Path) -> Path:
    with open(out, "wb") as f:
        writer.write(f)
    return out


def hex_color(c: str, default: str = "#000000") -> HexColor:
    try:
        return HexColor(c or default)
    except Exception:
        return HexColor(default)


def overlay_pages(writer: PdfWriter, pages: list[int] | None,
                  draw: Callable[[canvas.Canvas, float, float, int, int], None]) -> None:
    """Draw over each page with reportlab, taking the page rotation and the
    MediaBox origin into account."""
    total = len(writer.pages)
    targets = range(total) if pages is None else pages
    for i in targets:
        page = writer.pages[i]
        page.transfer_rotation_to_content()
        box = page.mediabox
        w, h = float(box.width), float(box.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))
        draw(c, w, h, i, total)
        c.save()
        buf.seek(0)
        ov = PdfReader(buf).pages[0]
        page.merge_transformed_page(ov, Transformation().translate(float(box.left), float(box.bottom)))


def data_url_image(data_url: str) -> Image.Image:
    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
    return Image.open(io.BytesIO(base64.b64decode(b64)))


# ---------------------------------------------------------------- organize
def merge(files: list[Path], out: Path, opts: dict) -> Path:
    w = PdfWriter()
    for f in progress.each(files):
        r = open_reader(f)
        w.append(r, outline_item=f.stem if opts.get("bookmarks") else None)
    return save(w, out)


def split(file: Path, outdir: Path, opts: dict) -> list[Path]:
    r = open_reader(file)
    n = len(r.pages)
    mode = opts.get("mode", "ranges")
    if mode == "each":
        groups = [[i] for i in range(n)]
    elif mode == "every":
        k = max(1, int(opts.get("every") or 1))
        groups = [list(range(i, min(i + k, n))) for i in range(0, n, k)]
    else:
        groups = parse_ranges(opts.get("ranges", ""), n)
    if opts.get("merge_output") and mode == "ranges":
        groups = [[i for g in groups for i in g]]
    outs = []
    for gi, g in enumerate(groups, 1):
        w = PdfWriter()
        for i in g:
            w.add_page(r.pages[i])
        label = f"{g[0]+1}" if len(g) == 1 else f"{g[0]+1}-{g[-1]+1}"
        outs.append(save(w, outdir / f"{file.stem}_p{label}.pdf"))
    return outs


def select_pages(file: Path, out: Path, keep: list[int], rotations: dict[int, int] | None = None) -> Path:
    r = open_reader(file)
    w = PdfWriter()
    for i in keep:
        p = w.add_page(r.pages[i])
        rot = (rotations or {}).get(i, 0)
        if rot:
            p.rotate(rot)
    return save(w, out)


def remove_pages(file: Path, out: Path, opts: dict) -> Path:
    n = len(open_reader(file).pages)
    drop = set(flat_pages(opts.get("pages", ""), n))
    keep = [i for i in range(n) if i not in drop]
    if not keep:
        raise ValueError("You cannot remove every page.")
    return select_pages(file, out, keep)


def extract_pages(file: Path, out: Path, opts: dict) -> Path:
    n = len(open_reader(file).pages)
    return select_pages(file, out, flat_pages(opts.get("pages", ""), n))


def organize(file: Path, out: Path, opts: dict) -> Path:
    """opts['layout'] = [{"src": 0, "rot": 90}, ...] produced by the page editor."""
    layout = opts.get("layout") or []
    n = len(open_reader(file).pages)
    if not layout:
        layout = [{"src": i, "rot": 0} for i in range(n)]
    r = open_reader(file)
    w = PdfWriter()
    for item in layout:
        if item.get("blank"):
            ref = r.pages[0].mediabox
            w.add_blank_page(width=float(ref.width), height=float(ref.height))
            continue
        p = w.add_page(r.pages[int(item["src"])])
        if int(item.get("rot", 0)) % 360:
            p.rotate(int(item["rot"]) % 360)
    if not len(w.pages):
        raise ValueError("The resulting document would be empty.")
    return save(w, out)


def rotate(file: Path, out: Path, opts: dict) -> Path:
    r = open_reader(file)
    w = PdfWriter(clone_from=r)
    angle = int(opts.get("angle", 90))
    pages = opts.get("pages", "").strip()
    targets = flat_pages(pages, len(w.pages)) if pages else range(len(w.pages))
    for i in targets:
        w.pages[i].rotate(angle)
    return save(w, out)


def nup(file: Path, out: Path, opts: dict) -> Path:
    per = int(opts.get("per_sheet", 2))
    cols, rows = {2: (2, 1), 4: (2, 2), 6: (3, 2), 9: (3, 3)}.get(per, (2, 1))
    r = open_reader(file)
    W, H = 595.28, 841.89  # A4 portrait
    if cols > rows:
        W, H = H, W
    w = PdfWriter()
    srcs = list(r.pages)
    for s in range(0, len(srcs), per):
        sheet = w.add_blank_page(width=W, height=H)
        cw, ch = W / cols, H / rows
        for k, p in enumerate(srcs[s:s + per]):
            p.transfer_rotation_to_content()
            pw, ph = float(p.mediabox.width), float(p.mediabox.height)
            sc = min((cw - 12) / pw, (ch - 12) / ph)
            col, row = k % cols, k // cols
            tx = col * cw + (cw - pw * sc) / 2 - float(p.mediabox.left) * sc
            ty = H - (row + 1) * ch + (ch - ph * sc) / 2 - float(p.mediabox.bottom) * sc
            sheet.merge_transformed_page(p, Transformation().scale(sc).translate(tx, ty))
    return save(w, out)


# ---------------------------------------------------------------- optimize
def compress(file: Path, out: Path, opts: dict) -> Path:
    level = opts.get("level", "recommended")
    quality, max_px, gs_preset = {
        "extreme": (40, 1100, "/screen"),
        "recommended": (65, 1700, "/ebook"),
        "low": (82, 2600, "/printer"),
    }.get(level, (65, 1700, "/ebook"))
    candidates: list[Path] = []

    # 1) built-in: re-encode images + deduplicate objects
    r = open_reader(file)
    w = PdfWriter(clone_from=r)
    for pi, page in enumerate(w.pages):
        progress.step(pi, len(w.pages) * (1.6 if engines.detect()["ghostscript"] else 1.1))
        try:
            for img in page.images:
                pil = img.image
                if pil is None or pil.width * pil.height < 40_000:
                    continue
                if max(pil.size) > max_px:
                    pil.thumbnail((max_px, max_px), Image.LANCZOS)
                if pil.mode not in ("RGB", "L"):
                    pil = pil.convert("RGB")
                img.replace(pil, quality=quality)
        except Exception:
            pass  # unusual image: keep it as is
        try:
            page.compress_content_streams()
        except Exception:
            pass
    w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    native = out.with_name(out.stem + ".native.pdf")
    save(w, native)
    candidates.append(native)

    # 2) Ghostscript when available (often much better)
    gs = engines.detect()["ghostscript"]
    if gs:
        g = out.with_name(out.stem + ".gs.pdf")
        try:
            engines.run([str(gs), "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6",
                         f"-dPDFSETTINGS={gs_preset}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                         "-dDetectDuplicateImages=true", f"-sOutputFile={g}", str(file)])
            candidates.append(g)
        except Exception:
            pass
    best = min(candidates + [file], key=lambda p: p.stat().st_size)
    out.write_bytes(best.read_bytes())
    for c in candidates:
        c.unlink(missing_ok=True)
    return out


def repair(file: Path, out: Path, opts: dict) -> Path:
    gs = engines.detect()["ghostscript"]
    if gs:
        try:
            engines.run([str(gs), "-o", str(out), "-sDEVICE=pdfwrite", "-dQUIET", str(file)])
            return out
        except Exception:
            pass
    r = PdfReader(str(file), strict=False)
    w = PdfWriter()
    for p in r.pages:
        try:
            w.add_page(p)
        except Exception:
            continue
    if not len(w.pages):
        raise ValueError("The file is too damaged to be repaired.")
    return save(w, out)


def ocr(file: Path, out: Path, opts: dict) -> Path:
    exe = engines.detect()["ocrmypdf"]
    if not exe:
        raise RuntimeError("OCRmyPDF (and Tesseract) must be installed for OCR.")
    lang = opts.get("lang", "fra+eng")
    engines.run([str(exe), "--skip-text", "-l", lang, "--output-type", "pdf", str(file), str(out)], timeout=1800)
    return out


def pdfa(file: Path, out: Path, opts: dict) -> Path:
    gs = engines.detect()["ghostscript"]
    if not gs:
        raise RuntimeError("Ghostscript is required for PDF/A conversion.")
    level = opts.get("level", "2")
    engines.run([str(gs), f"-dPDFA={level}", "-dBATCH", "-dNOPAUSE", "-dQUIET",
                 "-sColorConversionStrategy=RGB", "-sDEVICE=pdfwrite",
                 "-dPDFACompatibilityPolicy=1", f"-sOutputFile={out}", str(file)])
    return out


@pdfium_safe
def rasterize(file: Path, out: Path, opts: dict, pages: set[int] | None = None,
              mutate: Callable[[Image.Image, int, float], None] | None = None) -> Path:
    """Turn pages into images (flatten, grayscale, true redaction)."""
    dpi = int(opts.get("dpi", 150))
    gray = bool(opts.get("grayscale"))
    doc = pdfium.PdfDocument(str(file))
    src = open_reader(file)
    w = PdfWriter()
    for i in range(len(doc)):
        progress.step(i, len(doc))
        if pages is not None and i not in pages:
            w.add_page(src.pages[i])
            continue
        page = doc[i]
        pw, ph = page.get_size()
        scale = dpi / 72
        img = page.render(scale=scale).to_pil().convert("RGB")
        if mutate:
            mutate(img, i, scale)
        if gray:
            img = img.convert("L")
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(pw, ph))
        c.drawImage(ImageReader(img), 0, 0, pw, ph)
        c.save()
        buf.seek(0)
        w.add_page(PdfReader(buf).pages[0])
    return save(w, out)


def grayscale(file: Path, out: Path, opts: dict) -> Path:
    gs = engines.detect()["ghostscript"]
    if gs:
        try:
            engines.run([str(gs), "-sDEVICE=pdfwrite", "-sColorConversionStrategy=Gray",
                         "-dProcessColorModel=/DeviceGray", "-dNOPAUSE", "-dBATCH", "-dQUIET",
                         f"-sOutputFile={out}", str(file)])
            return out
        except Exception:
            pass
    return rasterize(file, out, {**opts, "grayscale": True})


def flatten(file: Path, out: Path, opts: dict) -> Path:
    return rasterize(file, out, opts)


# ---------------------------------------------------------------- edit
POSITIONS = {
    "bottom-center": ("c", "b"), "bottom-right": ("r", "b"), "bottom-left": ("l", "b"),
    "top-center": ("c", "t"), "top-right": ("r", "t"), "top-left": ("l", "t"),
    "center": ("c", "m"),
}


def _place(c: canvas.Canvas, text: str, w: float, h: float, pos: str, size: float, margin: float):
    hx, vy = POSITIONS.get(pos, ("c", "b"))
    y = {"b": margin, "t": h - margin - size, "m": h / 2 - size / 2}[vy]
    if hx == "c":
        c.drawCentredString(w / 2, y, text)
    elif hx == "r":
        c.drawRightString(w - margin, y, text)
    else:
        c.drawString(margin, y, text)


def page_numbers(file: Path, out: Path, opts: dict) -> Path:
    w = PdfWriter(clone_from=open_reader(file))
    fmt = opts.get("format") or "{n}"
    start = int(opts.get("start", 1))
    size = float(opts.get("size", 11))
    color = hex_color(opts.get("color"), "#333333")
    skip_first = bool(opts.get("skip_first"))
    pos = opts.get("position", "bottom-center")
    margin = float(opts.get("margin", 12)) * MM / 1.0 if opts.get("margin") else 28

    def draw(c, pw, ph, i, total):
        if skip_first and i == 0:
            return
        n = i + start - (1 if skip_first else 0)
        c.setFont("Helvetica", size)
        c.setFillColor(color)
        _place(c, fmt.replace("{n}", str(n)).replace("{total}", str(total + start - 1 - (1 if skip_first else 0))),
               pw, ph, pos, size, margin)

    overlay_pages(w, None, draw)
    return save(w, out)


def watermark(file: Path, out: Path, opts: dict, image: Path | None = None) -> Path:
    w = PdfWriter(clone_from=open_reader(file))
    text = opts.get("text") or "CONFIDENTIAL"
    size = float(opts.get("size", 60))
    opacity = float(opts.get("opacity", 30)) / 100
    angle = float(opts.get("angle", 45))
    color = hex_color(opts.get("color"), "#e5322d")
    mosaic = opts.get("layout") == "mosaic"
    pages = opts.get("pages", "").strip()
    targets = flat_pages(pages, len(w.pages)) if pages else None
    img_reader = ImageReader(str(image)) if image else None

    def stamp(c, x, y):
        c.saveState()
        c.translate(x, y)
        c.rotate(angle)
        if img_reader:
            iw, ih = img_reader.getSize()
            tw = size * 4
            th = tw * ih / iw
            c.drawImage(img_reader, -tw / 2, -th / 2, tw, th, mask="auto")
        else:
            c.setFont("Helvetica-Bold", size)
            c.drawCentredString(0, -size / 3, text)
        c.restoreState()

    def draw(c, pw, ph, i, total):
        c.setFillColor(color)
        c.setFillAlpha(opacity)
        c.setStrokeAlpha(opacity)
        if mosaic:
            step = size * 6
            y = -ph
            while y < ph * 2:
                x = -pw
                while x < pw * 2:
                    stamp(c, x, y)
                    x += step
                y += step / 1.6
        else:
            stamp(c, pw / 2, ph / 2)

    overlay_pages(w, targets, draw)
    return save(w, out)


def crop(file: Path, out: Path, opts: dict) -> Path:
    w = PdfWriter(clone_from=open_reader(file))
    t, r_, b, l = (float(opts.get(k, 0) or 0) * MM for k in ("top", "right", "bottom", "left"))
    for p in w.pages:
        mb = p.mediabox
        box = RectangleObject([float(mb.left) + l, float(mb.bottom) + b, float(mb.right) - r_, float(mb.top) - t])
        if box.width <= 10 or box.height <= 10:
            raise ValueError("Margins are too large for the page.")
        p.cropbox = box
        p.mediabox = box
    return save(w, out)


def metadata(file: Path, out: Path, opts: dict) -> Path:
    w = PdfWriter(clone_from=open_reader(file))
    meta = {f"/{k.capitalize()}": v for k, v in opts.items()
            if k in ("title", "author", "subject", "keywords", "creator") and v}
    w.add_metadata(meta)
    return save(w, out)


def edit(file: Path, out: Path, opts: dict) -> Path:
    """Add texts / images / signatures placed in the editor.
    items: [{type:'text'|'image'|'rect', page, x, y, w, h (fractions 0-1 from the top-left corner),
             text, size (fraction of the page height), color, src (dataURL)}]"""
    items = opts.get("items") or []
    if not items:
        raise ValueError("Add at least one element to the document.")
    w = PdfWriter(clone_from=open_reader(file))
    by_page: dict[int, list[dict]] = {}
    for it in items:
        by_page.setdefault(int(it.get("page", 0)), []).append(it)

    def draw(c, pw, ph, i, total):
        for it in by_page.get(i, []):
            x = float(it["x"]) * pw
            top = float(it["y"]) * ph
            iw = float(it.get("w", 0.2)) * pw
            ih = float(it.get("h", 0.05)) * ph
            if it["type"] == "image":
                img = data_url_image(it["src"])
                c.drawImage(ImageReader(img), x, ph - top - ih, iw, ih, mask="auto")
            elif it["type"] == "rect":
                c.setFillColor(hex_color(it.get("color"), "#ffffff"))
                c.rect(x, ph - top - ih, iw, ih, stroke=0, fill=1)
            else:
                fs = float(it.get("size", 0.02)) * ph
                c.setFillColor(hex_color(it.get("color"), "#000000"))
                font = {"serif": "Times-Roman", "mono": "Courier"}.get(it.get("font"), "Helvetica")
                if it.get("bold"):
                    font = {"Times-Roman": "Times-Bold", "Courier": "Courier-Bold"}.get(font, "Helvetica-Bold")
                c.setFont(font, fs)
                for li, line in enumerate(str(it.get("text", "")).split("\n")):
                    c.drawString(x, ph - top - fs * 0.85 - li * fs * 1.2, line)

    overlay_pages(w, sorted(by_page), draw)
    return save(w, out)


@pdfium_safe
def redact(file: Path, out: Path, opts: dict) -> Path:
    """True redaction: find the terms, draw black boxes, then turn affected
    pages into images (the text is really gone)."""
    terms = [t.strip() for t in re.split(r"[\n,;]", opts.get("terms", "")) if t.strip()]
    areas = opts.get("items") or []
    if not terms and not areas:
        raise ValueError("Enter words to redact or draw areas.")
    doc = pdfium.PdfDocument(str(file))
    hits: dict[int, list[tuple[float, float, float, float]]] = {}
    for i in range(len(doc)):
        page = doc[i]
        tp = page.get_textpage()
        for term in terms:
            s = tp.search(term, match_case=bool(opts.get("match_case")))
            while (m := s.get_next()) is not None:
                idx, cnt = m
                for k in range(tp.count_rects(idx, cnt)):
                    hits.setdefault(i, []).append(("pt", *tp.get_rect(k)))
    for a in areas:
        hits.setdefault(int(a["page"]), []).append(("frac", a["x"], a["y"], a["w"], a["h"]))
    if not hits:
        raise ValueError("No matches found.")
    sizes = {i: doc[i].get_size() for i in hits}
    color = opts.get("color") or "#000000"

    def mutate(img: Image.Image, i: int, scale: float):
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        pw, ph = sizes[i]
        for h in hits.get(i, []):
            if h[0] == "pt":
                _, l, b, r, t = h
                d.rectangle([l * scale - 1, (ph - t) * scale - 1, r * scale + 1, (ph - b) * scale + 1], fill=color)
            else:
                _, x, y, ww, hh = h
                d.rectangle([x * img.width, y * img.height, (x + ww) * img.width, (y + hh) * img.height], fill=color)

    return rasterize(file, out, {"dpi": opts.get("dpi", 200)}, pages=set(hits), mutate=mutate)


# ---------------------------------------------------------------- security
def protect(file: Path, out: Path, opts: dict) -> Path:
    pw = opts.get("password") or ""
    if len(pw) < 1:
        raise ValueError("Enter a password.")
    if opts.get("confirm") is not None and opts.get("confirm") != pw:
        raise ValueError("Passwords do not match.")
    w = PdfWriter(clone_from=open_reader(file))
    perms = Perm.PRINT | Perm.PRINT_TO_REPRESENTATION | Perm.EXTRACT | Perm.MODIFY | Perm.ADD_OR_MODIFY | Perm.FILL_FORM_FIELDS | Perm.ASSEMBLE_DOC | Perm.EXTRACT_TEXT_AND_GRAPHICS
    if opts.get("no_print"):
        perms &= ~(Perm.PRINT | Perm.PRINT_TO_REPRESENTATION)
    if opts.get("no_copy"):
        perms &= ~(Perm.EXTRACT | Perm.EXTRACT_TEXT_AND_GRAPHICS)
    if opts.get("no_edit"):
        perms &= ~(Perm.MODIFY | Perm.ADD_OR_MODIFY | Perm.ASSEMBLE_DOC)
    w.encrypt(user_password=pw, owner_password=opts.get("owner_password") or pw,
              permissions_flag=perms, algorithm="AES-256")
    return save(w, out)


def unlock(file: Path, out: Path, opts: dict) -> Path:
    r = PdfReader(str(file), strict=False)
    if r.is_encrypted and not r.decrypt(opts.get("password") or ""):
        raise ValueError("Incorrect password.")
    w = PdfWriter(clone_from=r)
    return save(w, out)


# ---------------------------------------------------------------- previews
@pdfium_safe
def thumbnails(file: Path, width: int = 220, max_pages: int = 400, password: str | None = None) -> dict:
    doc = pdfium.PdfDocument(str(file), password=password)
    pages = []
    for i in range(min(len(doc), max_pages)):
        p = doc[i]
        pw, ph = p.get_size()
        img = p.render(scale=width / pw).to_pil()
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=72)
        pages.append({"w": pw, "h": ph, "src": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()})
    return {"count": len(doc), "pages": pages}
