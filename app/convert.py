"""Conversions to / from PDF.

Strategy (inspired by Filee): built-in engine first when it gives a good
result, external engine (LibreOffice, pdf2docx…) when installed and more
faithful, built-in fallback otherwise — the app works without installing anything."""
from __future__ import annotations

import html
import io
import re
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, A5, letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle, ListFlowable, ListItem)

from . import engines, progress
from .pdfops import open_reader, pdfium_safe

try:  # HEIC/HEIF when pillow-heif is installed
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
except Exception:
    pass

IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tif", "tiff", "heic", "heif", "avif", "ico", "tga", "ppm", "jfif"}
WORD_EXT = {"doc", "docx", "docm", "dot", "dotx", "odt", "fodt", "ott", "rtf", "wpd", "wps", "pages"}
EXCEL_EXT = {"xls", "xlsx", "xlsm", "xlt", "xltx", "ods", "fods", "csv", "tsv", "numbers"}
PPT_EXT = {"ppt", "pptx", "pptm", "pps", "ppsx", "pot", "potx", "odp", "fodp", "key"}
TEXT_EXT = {"txt", "log", "md", "markdown", "json", "xml", "yaml", "yml", "ini", "py", "js", "css", "sql"}
HTML_EXT = {"html", "htm", "xhtml"}
VECTOR_EXT = {"svg", "odg", "vsd", "vsdx", "cdr", "emf", "wmf", "eps"}
OFFICE_EXT = WORD_EXT | EXCEL_EXT | PPT_EXT | VECTOR_EXT | HTML_EXT
ANY_TO_PDF = IMAGE_EXT | OFFICE_EXT | TEXT_EXT

PAGE_SIZES = {"a4": A4, "a3": A3, "a5": A5, "letter": letter}


def ext(p: Path) -> str:
    return p.suffix.lower().lstrip(".")


# ------------------------------------------------------------------ images
def images_to_pdf(files: list[Path], out: Path, opts: dict) -> Path:
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    size_key = opts.get("page_size", "fit")
    orient = opts.get("orientation", "auto")
    margin = {"none": 0, "small": 10 * mm, "big": 25 * mm}.get(opts.get("margin", "none"), 0)
    c = canvas.Canvas(str(out))
    for fi, f in enumerate(files):
        progress.step(fi, len(files))
        img = Image.open(f)
        frames = []
        try:
            for k in range(getattr(img, "n_frames", 1)):
                img.seek(k)
                frames.append(ImageOps.exif_transpose(img.copy()))
                if ext(f) in ("gif", "webp"):
                    break  # first frame only for animations
        except EOFError:
            pass
        for fr in frames or [img]:
            if fr.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", fr.size, "white")
                fr = fr.convert("RGBA")
                bg.paste(fr, mask=fr.split()[-1])
                fr = bg
            elif fr.mode != "RGB" and fr.mode != "L":
                fr = fr.convert("RGB")
            iw, ih = fr.size
            if size_key == "fit":
                pw, ph = iw * 72 / 96 + 2 * margin, ih * 72 / 96 + 2 * margin
            else:
                pw, ph = PAGE_SIZES.get(size_key, A4)
                land = (orient == "landscape") or (orient == "auto" and iw > ih)
                if land:
                    pw, ph = landscape((pw, ph))
            c.setPageSize((pw, ph))
            aw, ah = pw - 2 * margin, ph - 2 * margin
            sc = min(aw / iw, ah / ih)
            dw, dh = iw * sc, ih * sc
            c.drawImage(ImageReader(fr), (pw - dw) / 2, (ph - dh) / 2, dw, dh)
            c.showPage()
    c.save()
    return out


# ------------------------------------------------------------------ text / markdown (built-in)
def _styles():
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15)
    code = ParagraphStyle("code", parent=body, fontName="Courier", fontSize=9, leading=12,
                          backColor=colors.HexColor("#f4f4f5"), borderPadding=6)
    return ss, body, code


def _inline_md(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", t)
    t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<link href="\2" color="blue">\1</link>', t)
    return t


def text_to_pdf(src: Path, out: Path, opts: dict) -> Path:
    raw = src.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    ss, body, code = _styles()
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm, title=src.stem)
    story = []
    if ext(src) in ("md", "markdown"):
        lines = text.splitlines()
        i = 0
        para: list[str] = []

        def flush():
            if para:
                story.append(Paragraph(_inline_md(" ".join(para)), body))
                para.clear()

        while i < len(lines):
            ln = lines[i]
            if ln.strip().startswith("```"):
                flush()
                block = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    block.append(lines[i])
                    i += 1
                story.append(Preformatted("\n".join(block), code))
                story.append(Spacer(1, 6))
            elif m := re.match(r"^(#{1,6})\s+(.*)", ln):
                flush()
                lvl = min(len(m.group(1)), 4)
                story.append(Paragraph(_inline_md(m.group(2)), ss[f"Heading{lvl}"]))
            elif re.match(r"^\s*([-*+]|\d+\.)\s+", ln):
                flush()
                items = []
                ordered = bool(re.match(r"^\s*\d+\.", ln))
                while i < len(lines) and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                    items.append(ListItem(Paragraph(_inline_md(re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i])), body)))
                    i += 1
                story.append(ListFlowable(items, bulletType="1" if ordered else "bullet"))
                continue
            elif re.match(r"^\s*(---|\*\*\*)\s*$", ln):
                flush()
                story.append(Spacer(1, 10))
            elif not ln.strip():
                flush()
            else:
                para.append(ln.strip())
            i += 1
        flush()
    else:
        story.append(Preformatted(text, ParagraphStyle("plain", parent=body, fontName="Courier", fontSize=9, leading=12)))
    if not story:
        story.append(Spacer(1, 1))
    doc.build(story)
    return out


# ------------------------------------------------------------------ simple Office fallbacks
def docx_to_pdf_native(src: Path, out: Path, opts: dict) -> Path:
    import docx  # python-docx

    d = docx.Document(str(src))
    ss, body, _ = _styles()
    story = []
    for block in d.element.body.iterchildren():
        tag = block.tag.split("}")[-1]
        if tag == "p":
            p = docx.text.paragraph.Paragraph(block, d)
            txt = "".join(
                (f"<b>{html.escape(r.text)}</b>" if r.bold else f"<i>{html.escape(r.text)}</i>" if r.italic else html.escape(r.text))
                for r in p.runs
            )
            style = (p.style.name or "").lower() if p.style is not None else ""
            if style.startswith("heading") or style.startswith("titre"):
                lvl = re.findall(r"\d", style)
                story.append(Paragraph(txt, ss[f"Heading{min(int(lvl[0]) if lvl else 1, 4)}"]))
            elif style == "title":
                story.append(Paragraph(txt, ss["Title"]))
            elif txt.strip():
                story.append(Paragraph(txt, body))
            else:
                story.append(Spacer(1, 6))
        elif tag == "tbl":
            t = docx.table.Table(block, d)
            data = [[Paragraph(html.escape(c.text), body) for c in row.cells] for row in t.rows]
            if data:
                tbl = Table(data, repeatRows=1)
                tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                         ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story += [tbl, Spacer(1, 8)]
    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm).build(story or [Spacer(1, 1)])
    return out


def sheet_to_pdf_native(src: Path, out: Path, opts: dict) -> Path:
    from . import xlsx_render
    if ext(src) in ("csv", "tsv"):
        return xlsx_render.csv_to_pdf(src, out)
    return xlsx_render.xlsx_to_pdf(src, out)


# ------------------------------------------------------------------ to PDF dispatch
def to_pdf(src: Path, outdir: Path, opts: dict) -> Path:
    e = ext(src)
    out = outdir / f"{src.stem}.pdf"
    if e == "pdf":
        out.write_bytes(src.read_bytes())
        return out
    if e in IMAGE_EXT:
        return images_to_pdf([src], out, opts)
    if e in TEXT_EXT:
        return text_to_pdf(src, out, opts)
    if e in HTML_EXT and engines.has("browser"):
        from . import webpdf
        return webpdf.render(str(src), out, {"render": "print", "margin": "small"})
    if e in OFFICE_EXT:
        if engines.has("libreoffice"):
            return engines.libreoffice_convert(src, "pdf", outdir)
        if e in ("docx", "docm", "dotx"):
            from . import docx_render
            try:
                return docx_render.docx_to_pdf(src, out)
            except Exception:  # unusual document: simplified rendering rather than nothing
                return docx_to_pdf_native(src, out, opts)
        if e in ("xlsx", "xlsm", "xltx", "csv", "tsv"):
            return sheet_to_pdf_native(src, out, opts)
        raise RuntimeError(f"Install LibreOffice to convert .{e} files.")
    raise RuntimeError(f"Unsupported format: .{e}")


# ------------------------------------------------------------------ from PDF
@pdfium_safe
def pdf_to_images(src: Path, outdir: Path, opts: dict) -> list[Path]:
    fmt = opts.get("format", "jpg")
    dpi = int(opts.get("dpi", 150))
    doc = pdfium.PdfDocument(str(src))
    outs = []
    if opts.get("mode") == "extract":  # extract embedded images
        r = open_reader(src)
        k = 0
        for pi, page in enumerate(r.pages):
            for img in page.images:
                k += 1
                pil = img.image
                if pil is None:
                    continue
                p = outdir / f"{src.stem}_img{k:03d}.{ 'png' if fmt == 'png' else 'jpg'}"
                (pil.convert("RGB") if fmt != "png" else pil).save(p, quality=92)
                outs.append(p)
        if not outs:
            raise ValueError("No images found in this PDF.")
        return outs
    for i in range(len(doc)):
        progress.step(i, len(doc))
        img = doc[i].render(scale=dpi / 72).to_pil()
        p = outdir / f"{src.stem}_{i+1:03d}.{fmt}"
        if fmt == "png":
            img.save(p, optimize=True)
        else:
            img.convert("RGB").save(p, "WEBP" if fmt == "webp" else "JPEG", quality=int(opts.get("quality", 90)))
        outs.append(p)
    return outs


def pdf_to_docx(src: Path, outdir: Path, opts: dict) -> Path:
    out = outdir / f"{src.stem}.docx"
    if engines.has("pdf2docx"):
        from pdf2docx import Converter
        cv = Converter(str(src))
        try:
            cv.convert(str(out))
        finally:
            cv.close()
        return out
    if engines.has("libreoffice"):
        return engines.libreoffice_convert(src, "docx:MS Word 2007 XML", outdir, infilter="writer_pdf_import")
    import docx
    d = docx.Document()
    for i, page in enumerate(open_reader(src).pages):
        if i:
            d.add_page_break()
        for para in (page.extract_text() or "").split("\n\n"):
            d.add_paragraph(para)
    d.save(str(out))
    return out


@pdfium_safe
def pdf_to_pptx(src: Path, outdir: Path, opts: dict) -> Path:
    from pptx import Presentation
    from pptx.util import Emu

    out = outdir / f"{src.stem}.pptx"
    doc = pdfium.PdfDocument(str(src))
    prs = Presentation()
    w0, h0 = doc[0].get_size()
    prs.slide_width = Emu(int(w0 * 12700))
    prs.slide_height = Emu(int(h0 * 12700))
    blank = prs.slide_layouts[6]
    for i in range(len(doc)):
        progress.step(i, len(doc))
        img = doc[i].render(scale=2).to_pil().convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=88)
        buf.seek(0)
        s = prs.slides.add_slide(blank)
        s.shapes.add_picture(buf, 0, 0, prs.slide_width, prs.slide_height)
        txt = doc[i].get_textpage().get_text_range()
        if txt.strip():
            s.notes_slide.notes_text_frame.text = txt
    prs.save(str(out))
    return out


def pdf_to_xlsx(src: Path, outdir: Path, opts: dict) -> Path:
    import openpyxl
    out = outdir / f"{src.stem}.xlsx"
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    found = False
    if engines.has("pdfplumber"):
        import pdfplumber
        with pdfplumber.open(str(src)) as pdf:
            for pi, page in enumerate(pdf.pages, 1):
                for ti, table in enumerate(page.extract_tables(), 1):
                    ws = wb.create_sheet(f"P{pi}-T{ti}"[:31])
                    for row in table:
                        ws.append([(c or "").strip() for c in row])
                    found = True
    if not found:  # fallback: one row per text line, columns split on multiple spaces
        ws = wb.create_sheet("Texte")
        for page in open_reader(src).pages:
            for ln in (page.extract_text() or "").splitlines():
                ws.append(re.split(r"\s{2,}|\t", ln.strip()))
    wb.save(str(out))
    return out


@pdfium_safe
def pdf_to_text(src: Path, outdir: Path, opts: dict) -> Path:
    out = outdir / f"{src.stem}.txt"
    doc = pdfium.PdfDocument(str(src))
    parts = [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    out.write_text("\n\n\f".join(parts), "utf-8")
    return out
