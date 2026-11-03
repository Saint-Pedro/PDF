"""Declarative tool registry. Each tool describes its options and the
frontend builds the form automatically. To add a tool, add an entry here.
User-facing texts are bilingual: "English"."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import convert as cv
from . import engines
from . import pdfops as ops
from . import progress


CATEGORIES = [
    {"id": "organize", "label": "Organize"},
    {"id": "optimize", "label": "Optimize"},
    {"id": "to_pdf", "label": "Convert to PDF"},
    {"id": "from_pdf", "label": "Convert from PDF"},
    {"id": "edit", "label": "Edit"},
    {"id": "security", "label": "Security"},
]

RANGE_HINT = "e.g. 1-3, 5, 8-"
PAGES_ALL = "Pages (empty = all)"


def opt(name, type_, label, **kw):
    return {"name": name, "type": type_, "label": label, **kw}


# Handlers: (files, options, work dir) -> Path | list[Path]
Handler = Callable[[list[Path], dict, Path], "Path | list[Path]"]


def single(fn) -> Handler:
    """Apply a file -> file operation to each PDF."""
    def h(files, o, wd):
        return [fn(f, wd / f"{f.stem}_{o['_tool']}.pdf", o) for f in progress.each(files)]
    return h


def to_pdf_each(files, o, wd):
    if o.get("merge") and len(files) > 1:
        pdfs = [cv.to_pdf(f, wd, o) for f in progress.each(files)]
        return ops.merge(pdfs, wd / "merged.pdf", {})
    return [cv.to_pdf(f, wd, o) for f in progress.each(files)]


def images_handler(files, o, wd):
    if o.get("merge", True) and len(files) > 1:
        return cv.images_to_pdf(files, wd / "images.pdf", o)
    return [cv.images_to_pdf([f], wd / f"{f.stem}.pdf", o) for f in progress.each(files)]


def from_pdf(fn):
    def h(files, o, wd):
        outs = []
        for f in progress.each(files):
            r = fn(f, wd, o)
            outs += r if isinstance(r, list) else [r]
        return outs
    return h


def watermark_handler(files, o, wd):
    img = o.get("_image")
    return [ops.watermark(f, wd / f"{f.stem}_watermark.pdf", o, image=img) for f in progress.each(files)]


def url_handler(o, wd):
    from . import webpdf
    url = webpdf.normalize_url(o.get("url", ""))
    host = (url.split("://", 1)[1].split("/")[0] or "page").replace(":", "_")
    return webpdf.render(url, wd / f"{host}.pdf", o)


def split_handler(files, o, wd):
    outs = []
    for f in progress.each(files):
        outs += ops.split(f, wd, o)
    return outs


TOOLS: list[dict] = [
    # ---------------------------------------------------------- Organize
    dict(id="merge", cat="organize", icon="merge", color="#e5322d",
         title="Merge PDF", desc="Combine several PDFs in the order you want.",
         accept=["pdf"], multiple=True, min_files=2, mode="files",
         options=[opt("bookmarks", "checkbox", "Add a bookmark per file", default=False)],
         handler=lambda files, o, wd: ops.merge(files, wd / "merged.pdf", o)),
    dict(id="split", cat="organize", icon="split", color="#e5322d",
         title="Split PDF", desc="Split a PDF by ranges, every N pages or page by page.",
         accept=["pdf"], multiple=False, mode="files",
         options=[opt("mode", "select", "Mode", default="ranges", choices=[
             ["ranges", "By ranges"], ["every", "Every N pages"], ["each", "Every page"]]),
             opt("ranges", "text", "Ranges", default="1-2", hint=RANGE_HINT, show_if={"mode": "ranges"}),
             opt("merge_output", "checkbox", "Merge ranges into one PDF", show_if={"mode": "ranges"}),
             opt("every", "number", "Number of pages", default=1, min=1, show_if={"mode": "every"})],
         handler=split_handler),
    dict(id="organize", cat="organize", icon="grid", color="#e5322d",
         title="Organize PDF", desc="Reorder, rotate, delete or add pages.",
         accept=["pdf"], multiple=False, mode="pages",
         options=[], handler=single(ops.organize)),
    dict(id="remove", cat="organize", icon="trash", color="#e5322d",
         title="Remove pages", desc="Delete the pages you don't need.",
         accept=["pdf"], multiple=False, mode="pages", page_action="remove",
         options=[], handler=single(ops.organize)),
    dict(id="extract", cat="organize", icon="extract", color="#e5322d",
         title="Extract pages", desc="Create a new PDF with only the pages you want.",
         accept=["pdf"], multiple=False, mode="pages", page_action="extract",
         options=[], handler=single(ops.organize)),
    dict(id="rotate", cat="organize", icon="rotate", color="#a855f7",
         title="Rotate PDF", desc="Rotate all pages or just some of them.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("angle", "select", "Rotation", default="90", choices=[
             ["90", "90° right"], ["180", "180°"], ["270", "90° left"]]),
             opt("pages", "text", PAGES_ALL, default="", hint=RANGE_HINT)],
         handler=single(ops.rotate)),
    dict(id="nup", cat="organize", icon="layout", color="#a855f7",
         title="Pages per sheet", desc="Print 2, 4, 6 or 9 pages on a single sheet.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("per_sheet", "select", "Pages per sheet", default="2",
                      choices=[["2", "2"], ["4", "4"], ["6", "6"], ["9", "9"]])],
         handler=single(ops.nup)),

    # ---------------------------------------------------------- Optimize
    dict(id="compress", cat="optimize", icon="compress", color="#22a06b",
         title="Compress PDF", desc="Reduce file size while keeping good quality.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("level", "cards", "Compression level", default="recommended", choices=[
             ["extreme", "Extreme", "Smallest size, lower quality"],
             ["recommended", "Recommended", "Good balance of size and quality"],
             ["low", "Low", "High quality, light compression"]])],
         handler=single(ops.compress)),
    dict(id="repair", cat="optimize", icon="wrench", color="#22a06b",
         title="Repair PDF", desc="Try to recover a damaged PDF.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=single(ops.repair)),
    dict(id="ocr", cat="optimize", icon="scan", color="#22a06b", requires="ocrmypdf",
         title="OCR PDF", desc="Make a scanned PDF searchable and selectable.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("lang", "select", "Document language", default="eng+fra", choices=[
             ["eng+fra", "English + French"], ["eng", "English"], ["fra", "French"],
             ["deu", "German"], ["spa", "Spanish"], ["ita", "Italian"]])],
         handler=single(ops.ocr)),
    dict(id="pdfa", cat="optimize", icon="archive", color="#22a06b", requires="ghostscript",
         title="PDF to PDF/A", desc="Long-term archiving format (ISO 19005).",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("level", "select", "Level", default="2", choices=[["1", "PDF/A-1b"], ["2", "PDF/A-2b"], ["3", "PDF/A-3b"]])],
         handler=single(ops.pdfa)),
    dict(id="grayscale", cat="optimize", icon="contrast", color="#22a06b",
         title="Grayscale PDF", desc="Convert a color PDF to black and white.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=single(ops.grayscale)),

    # ---------------------------------------------------------- Convert to PDF
    dict(id="any_to_pdf", cat="to_pdf", badge="PDF", icon="magic", color="#f59e0b",
         title="Anything to PDF", desc="Images, Office, text, Markdown, HTML… one tool for all.",
         accept=sorted(cv.ANY_TO_PDF | {"pdf"}), multiple=True, mode="files",
         options=[opt("merge", "checkbox", "Merge into a single PDF", default=False)],
         handler=to_pdf_each),
    dict(id="img_to_pdf", cat="to_pdf", badge="PDF", icon="image", color="#f5b400",
         title="Image to PDF", desc="JPG, PNG, WEBP, HEIC, TIFF… to PDF, with page layout.",
         accept=sorted(cv.IMAGE_EXT), multiple=True, mode="files",
         options=[opt("page_size", "select", "Page size", default="a4", choices=[
             ["fit", "Image size"], ["a4", "A4"], ["letter", "US Letter"], ["a3", "A3"], ["a5", "A5"]]),
             opt("orientation", "select", "Orientation", default="auto", choices=[
                 ["auto", "Automatic"], ["portrait", "Portrait"], ["landscape", "Landscape"]]),
             opt("margin", "select", "Margins", default="none", choices=[["none", "None"], ["small", "Small"], ["big", "Large"]]),
             opt("merge", "checkbox", "Merge all images", default=True)],
         handler=images_handler),
    dict(id="word_to_pdf", cat="to_pdf", badge="PDF", icon="word", color="#2b6cde",
         title="Word to PDF", desc="DOCX, DOC, ODT, RTF to PDF.",
         accept=sorted(cv.WORD_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="excel_to_pdf", cat="to_pdf", badge="PDF", icon="excel", color="#1f9d55",
         title="Excel to PDF", desc="XLSX, XLS, ODS, CSV to PDF.",
         accept=sorted(cv.EXCEL_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="ppt_to_pdf", cat="to_pdf", badge="PDF", icon="ppt", color="#e8590c",
         title="PowerPoint to PDF", desc="PPTX, PPT, ODP to PDF.", requires="libreoffice",
         accept=sorted(cv.PPT_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="html_to_pdf", cat="to_pdf", badge="PDF", icon="code", color="#f59e0b",
         title="HTML / Markdown to PDF", desc="Saved web pages, Markdown or plain text.",
         accept=sorted(cv.HTML_EXT | cv.TEXT_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),

    dict(id="url_to_pdf", cat="to_pdf", badge="PDF", icon="globe", color="#0ea5e9", requires="browser",
         title="Web page to PDF", desc="Turn any web address into a clean PDF.",
         accept=[], multiple=False, mode="url",
         options=[opt("url", "url", "Web address", required=True, hint="e.g. https://example.com"),
                  opt("render", "cards", "Rendering", default="screen", choices=[
                      ["screen", "As on screen", "Desktop layout, split into pages"],
                      ["single", "One long page", "Exactly like the screen, no page cuts"],
                      ["print", "Print version", "Uses the site's print layout"]]),
                  opt("page_size", "select", "Page size", default="a4", choices=[["a4", "A4"], ["letter", "US Letter"], ["a3", "A3"], ["legal", "Legal"]], show_if={"render": ["screen", "print"]}),
                  opt("orientation", "select", "Orientation", default="portrait", choices=[["portrait", "Portrait"], ["landscape", "Landscape"]], show_if={"render": ["screen", "print"]}),
                  opt("margin", "select", "Margins", default="small", choices=[["none", "None"], ["small", "Small"], ["normal", "Normal"]], show_if={"render": ["screen", "print"]}),
                  opt("background", "checkbox", "Print background colors and images", default=True),
                  opt("hide_banners", "checkbox", "Hide cookie banners", default=True)],
         handler=lambda files, o, wd: url_handler(o, wd)),

    # ---------------------------------------------------------- Convert from PDF
    dict(id="pdf_to_img", cat="from_pdf", icon="pdf", badge="JPG", color="#f5b400",
         title="PDF to image", desc="Each page to JPG/PNG, or extract embedded images.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("mode", "select", "Mode", default="pages", choices=[["pages", "Page → image"], ["extract", "Extract images"]]),
                  opt("format", "select", "Format", default="jpg", choices=[["jpg", "JPG"], ["png", "PNG"], ["webp", "WEBP"]]),
                  opt("dpi", "select", "Resolution", default="150", choices=[["72", "72 dpi (screen)"], ["150", "150 dpi"], ["300", "300 dpi (print)"]], show_if={"mode": "pages"})],
         handler=from_pdf(cv.pdf_to_images)),
    dict(id="pdf_to_word", cat="from_pdf", icon="pdf", badge="DOC", color="#2b6cde",
         title="PDF to Word", desc="Convert to an editable DOCX.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_docx)),
    dict(id="pdf_to_ppt", cat="from_pdf", icon="pdf", badge="PPT", color="#e8590c",
         title="PDF to PowerPoint", desc="One slide per page (text in speaker notes).",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_pptx)),
    dict(id="pdf_to_excel", cat="from_pdf", icon="pdf", badge="XLS", color="#1f9d55",
         title="PDF to Excel", desc="Extract tables to XLSX.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_xlsx)),
    dict(id="pdf_to_txt", cat="from_pdf", icon="pdf", badge="TXT", color="#64748b",
         title="PDF to text", desc="Get all the raw text.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_text)),

    # ---------------------------------------------------------- Edit
    dict(id="edit", cat="edit", icon="pen", color="#d946ef",
         title="Edit PDF", desc="Add text, images, shapes or hide an area.",
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["text", "image", "rect", "signature"],
         options=[], handler=single(ops.edit)),
    dict(id="sign", cat="edit", icon="signature", color="#d946ef",
         title="Sign PDF", desc="Draw, type or upload your signature.",
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["signature", "text"],
         options=[], handler=single(ops.edit)),
    dict(id="watermark", cat="edit", icon="droplet", color="#d946ef",
         title="Watermark", desc="Stamp a translucent text or image over your pages.",
         accept=["pdf"], multiple=True, mode="files", extra_file={"name": "image", "label": "Watermark image (optional)", "accept": ["png", "jpg", "jpeg", "webp"]},
         options=[opt("text", "text", "Text", default="CONFIDENTIAL"),
                  opt("color", "color", "Color", default="#e5322d"),
                  opt("size", "range", "Size", default=60, min=12, max=160),
                  opt("opacity", "range", "Opacity (%)", default=25, min=5, max=100),
                  opt("angle", "range", "Angle", default=45, min=-90, max=90),
                  opt("layout", "select", "Layout", default="center", choices=[["center", "Centered"], ["mosaic", "Mosaic"]]),
                  opt("pages", "text", PAGES_ALL, default="", hint=RANGE_HINT)],
         handler=watermark_handler),
    dict(id="page_numbers", cat="edit", icon="hash", color="#d946ef",
         title="Page numbers", desc="Add custom page numbers.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("position", "position", "Position", default="bottom-center"),
                  opt("format", "select", "Format", default="{n}", choices=[
                      ["{n}", "1"], ["Page {n}", "Page 1"], ["{n} / {total}", "1 / 10"], ["Page {n} of {total}", "Page 1 of 10"], ["Page {n} sur {total}", "Page 1 sur 10"], ["- {n} -", "- 1 -"]]),
                  opt("start", "number", "First number", default=1, min=0),
                  opt("size", "range", "Size", default=11, min=6, max=36),
                  opt("color", "color", "Color", default="#333333"),
                  opt("skip_first", "checkbox", "Don't number the first page")],
         handler=single(ops.page_numbers)),
    dict(id="crop", cat="edit", icon="crop", color="#d946ef",
         title="Crop PDF", desc="Trim margins on every page (in mm).",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("top", "number", "Top (mm)", default=10, min=0), opt("bottom", "number", "Bottom (mm)", default=10, min=0),
                  opt("left", "number", "Left (mm)", default=10, min=0), opt("right", "number", "Right (mm)", default=10, min=0)],
         handler=single(ops.crop)),
    dict(id="metadata", cat="edit", icon="tag", color="#d946ef",
         title="Metadata", desc="Edit title, author, subject and keywords.",
         accept=["pdf"], multiple=False, mode="files",
         options=[opt("title", "text", "Title"), opt("author", "text", "Author"),
                  opt("subject", "text", "Subject"), opt("keywords", "text", "Keywords")],
         handler=single(ops.metadata)),
    dict(id="flatten", cat="edit", icon="layers", color="#d946ef",
         title="Flatten PDF", desc="Freeze forms and annotations (pages become images).",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("dpi", "select", "Quality", default="150", choices=[["100", "Light"], ["150", "Standard"], ["220", "High"]])],
         handler=single(ops.flatten)),

    # ---------------------------------------------------------- Security
    dict(id="protect", cat="security", icon="lock", color="#334155",
         title="Protect PDF", desc="AES-256 encryption and usage restrictions.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("password", "password", "Password", required=True),
                  opt("confirm", "password", "Confirm password", required=True),
                  opt("no_print", "checkbox", "Prevent printing"),
                  opt("no_copy", "checkbox", "Prevent copying text"),
                  opt("no_edit", "checkbox", "Prevent editing")],
         handler=single(ops.protect)),
    dict(id="unlock", cat="security", icon="unlock", color="#334155",
         title="Unlock PDF", desc="Remove the password (if you know it).",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("password", "password", "Current password")],
         handler=single(ops.unlock)),
    dict(id="redact", cat="security", icon="redact", color="#334155",
         title="Redact PDF", desc="Permanently remove sensitive words or areas.",
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["redact"],
         options=[opt("terms", "textarea", "Words or phrases to redact", hint="One per line (names, IBAN, emails…)"),
                  opt("match_case", "checkbox", "Match case")],
         handler=single(ops.redact)),
]

BY_ID = {t["id"]: t for t in TOOLS}


def public_list() -> list[dict]:
    out = []
    for t in TOOLS:
        d = {k: v for k, v in t.items() if k != "handler"}
        req = t.get("requires")
        d["available"] = engines.has(req) if req else True
        if req and not d["available"]:
            d["missing"] = {"libreoffice": "LibreOffice", "ghostscript": "Ghostscript", "ocrmypdf": "OCRmyPDF + Tesseract", "browser": "Chrome / Edge"}.get(req, req)
        out.append(d)
    return out
