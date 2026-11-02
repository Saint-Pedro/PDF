"""Native Excel (XLSX / CSV) to PDF renderer, used when LibreOffice is not installed.

Honors what matters for printed spreadsheets: print area, column widths, row
heights, merged cells, fills (incl. theme colors + tint), borders, fonts
(family, size, bold, italic, underline, color), alignment and wrapping, text
overflow into empty neighbours, number/date formats, page setup (paper size,
orientation, margins, fit to page, centering), header/footer, gridlines,
manual row breaks and embedded images."""
from __future__ import annotations

import colorsys
import csv
import datetime as dt
import io
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

import openpyxl
from openpyxl.styles.colors import COLOR_INDEX
from openpyxl.utils.cell import get_column_letter, range_boundaries
from reportlab.lib.pagesizes import A3, A4, A5, LEGAL, LETTER, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PAPER = {1: LETTER, 5: LEGAL, 8: A3, 9: A4, 11: A5}
PAD = 2.0  # cell padding (pt)

# ------------------------------------------------------------------ fonts
FONT_FILES = {
    "calibri": [("calibri.ttf", "carlito-regular.ttf"), ("calibrib.ttf", "carlito-bold.ttf"),
                ("calibrii.ttf", "carlito-italic.ttf"), ("calibriz.ttf", "carlito-bolditalic.ttf")],
    "arial": [("arial.ttf", "liberationsans-regular.ttf"), ("arialbd.ttf", "arial bold.ttf", "liberationsans-bold.ttf"),
              ("ariali.ttf", "arial italic.ttf", "liberationsans-italic.ttf"), ("arialbi.ttf", "arial bold italic.ttf", "liberationsans-bolditalic.ttf")],
    "times new roman": [("times.ttf", "times new roman.ttf", "liberationserif-regular.ttf"), ("timesbd.ttf", "times new roman bold.ttf", "liberationserif-bold.ttf"),
                        ("timesi.ttf", "times new roman italic.ttf", "liberationserif-italic.ttf"), ("timesbi.ttf", "times new roman bold italic.ttf", "liberationserif-bolditalic.ttf")],
    "courier new": [("cour.ttf", "courier new.ttf", "liberationmono-regular.ttf"), ("courbd.ttf", "courier new bold.ttf", "liberationmono-bold.ttf"),
                    ("couri.ttf", "courier new italic.ttf", "liberationmono-italic.ttf"), ("courbi.ttf", "courier new bold italic.ttf", "liberationmono-bolditalic.ttf")],
    "cambria": [("caladea-regular.ttf",), ("caladea-bold.ttf",), ("caladea-italic.ttf",), ("caladea-bolditalic.ttf",)],
    "verdana": [("verdana.ttf",), ("verdanab.ttf", "verdana bold.ttf"), ("verdanai.ttf", "verdana italic.ttf"), ("verdanaz.ttf", "verdana bold italic.ttf")],
    "tahoma": [("tahoma.ttf",), ("tahomabd.ttf", "tahoma bold.ttf"), ("tahoma.ttf",), ("tahomabd.ttf", "tahoma bold.ttf")],
    "segoe ui": [("segoeui.ttf",), ("segoeuib.ttf",), ("segoeuii.ttf",), ("segoeuiz.ttf",)],
    "dejavu sans": [("dejavusans.ttf",), ("dejavusans-bold.ttf",), ("dejavusans-oblique.ttf",), ("dejavusans-boldoblique.ttf",)],
}
FALLBACK_FAMILIES = ["calibri", "arial", "dejavu sans"]
BUILTIN = {"sans": ["Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"],
           "serif": ["Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"],
           "mono": ["Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique"]}


@lru_cache(maxsize=1)
def _font_index() -> dict[str, str]:
    dirs = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
            Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
            Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path("/System/Library/Fonts/Supplemental"),
            Path.home() / "Library/Fonts", Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts",
            Path.home() / ".local/share/fonts"]
    idx: dict[str, str] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.lower().endswith(".ttf"):
                    idx.setdefault(f.lower(), os.path.join(root, f))
    return idx


@lru_cache(maxsize=None)
def _family_fonts(family: str) -> list[str] | None:
    """Register the 4 styles of a family; returns reportlab font names or None."""
    spec = FONT_FILES.get(family)
    if not spec:
        return None
    idx = _font_index()
    names = []
    for style_i, candidates in enumerate(spec):
        path = next((idx[c] for c in candidates if c in idx), None)
        if not path:
            if style_i == 0:
                return None
            names.append(names[0])  # missing style: reuse regular
            continue
        name = f"x-{family}-{style_i}"
        try:
            pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            if style_i == 0:
                return None
            name = names[0]
        names.append(name)
    return names


def pick_font(name: str | None, bold: bool, italic: bool) -> str:
    fam = (name or "calibri").strip().lower()
    style = (2 if italic else 0) + (1 if bold else 0)
    for f in [fam] + FALLBACK_FAMILIES:
        fonts = _family_fonts(f)
        if fonts:
            return fonts[style]
    kind = "serif" if any(k in fam for k in ("times", "serif", "georgia", "cambria", "garamond")) else \
        "mono" if any(k in fam for k in ("courier", "mono", "consolas")) else "sans"
    return BUILTIN[kind][style]


# ------------------------------------------------------------------ colors
def _theme_colors(wb) -> list[str]:
    default = ["FFFFFF", "000000", "E7E6E6", "44546A", "4472C4", "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47", "0563C1", "954F72"]
    raw = getattr(wb, "loaded_theme", None)
    if not raw:
        return default
    try:
        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        root = ET.fromstring(raw)
        scheme = root.find(".//a:clrScheme", ns)
        vals = {}
        for child in scheme:
            tag = child.tag.split("}")[1]
            el = child[0]
            vals[tag] = el.get("val") if el.tag.endswith("srgbClr") else el.get("lastClr") or ("FFFFFF" if tag == "lt1" else "000000")
        order = ["lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"]
        return [vals.get(k, d) for k, d in zip(order, default)]
    except Exception:
        return default


def _tint(hex6: str, tint: float) -> str:
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    r, g, b = colorsys.hls_to_rgb(h, max(0, min(1, l)), s)
    return "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def resolve_color(color, theme: list[str], default: str | None = None) -> str | None:
    if color is None:
        return default
    try:
        t = color.type
        if t == "rgb" and isinstance(color.rgb, str):
            rgb = color.rgb[-6:]
            if color.rgb.startswith("00") and len(color.rgb) == 8 and color.rgb != "00000000":
                pass  # Excel ignores alpha
            elif color.rgb == "00000000":
                return default
        elif t == "theme" and color.theme is not None and color.theme < len(theme):
            rgb = theme[color.theme]
        elif t == "indexed" and color.indexed is not None:
            if color.indexed in (64, 65):
                return default
            rgb = COLOR_INDEX[color.indexed][-6:] if color.indexed < len(COLOR_INDEX) else None
        else:
            return default
        if not rgb:
            return default
        if color.tint:
            rgb = _tint(rgb, color.tint)
        return "#" + rgb
    except Exception:
        return default


# ------------------------------------------------------------------ value formatting
def _fmt_number(v: float, fmt: str) -> str:
    sections = fmt.split(";")
    sec = sections[0]
    if v < 0 and len(sections) > 1 and sections[1]:
        sec, v = sections[1], -v
    elif v == 0 and len(sections) > 2 and sections[2]:
        sec = sections[2]
    sec = re.sub(r"\[[^\]]*\]", "", sec)  # [Red], [$€-40C]…
    lits: list[str] = []
    sec = re.sub(r'"([^"]*)"', lambda m: (lits.append(m.group(1)), f"\x00{len(lits) - 1}\x00")[1], sec)
    sec = re.sub(r"\\(.)", lambda m: (lits.append(m.group(1)), f"\x00{len(lits) - 1}\x00")[1], sec)
    sec = sec.replace("_", "").replace("*", "")
    m = re.search(r"[0#?][0#?,. ]*", sec)
    if not m:
        out = sec
    else:
        core = m.group(0)
        pct = "%" in sec
        val = v * 100 if pct else v
        dec = len(core.split(".")[1].rstrip(" ")) if "." in core else 0
        thousands = "," in core.split(".")[0] or " " in core.strip()
        euro = "€" in fmt or "\u20ac" in "".join(lits)
        s = f"{abs(val):,.{dec}f}" if thousands else f"{abs(val):.{dec}f}"
        if euro:  # French conventions
            s = s.replace(",", "\u202f").replace(".", ",")
        if val < 0 and len(sections) == 1:
            s = "-" + s
        out = sec[:m.start()] + s + sec[m.end():]
    out = re.sub(r"\x00(\d+)\x00", lambda mm: lits[int(mm.group(1))], out)
    return out.strip() if out.strip() else ""


def _fmt_date(v, fmt: str) -> str:
    f = re.sub(r"\[[^\]]*\]", "", fmt.split(";")[0]).replace('"', "").replace("\\", "")
    tokens = re.findall(r"yyyy|yy|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|ss|s|AM/PM|am/pm|.", f, flags=re.I)
    out, prev_h = [], False
    for i, tk in enumerate(tokens):
        low = tk.lower()
        nxt = "".join(tokens[i + 1:i + 3]).lower()
        if low in ("yyyy",):
            out.append(f"{v.year:04d}")
        elif low == "yy":
            out.append(f"{v.year % 100:02d}")
        elif low in ("mm", "m") and (prev_h or nxt.startswith(":s") or nxt.startswith("s")):
            out.append(f"{v.minute:02d}" if low == "mm" else str(v.minute))
        elif low == "mmmm":
            out.append(v.strftime("%B"))
        elif low == "mmm":
            out.append(v.strftime("%b"))
        elif low == "mm":
            out.append(f"{v.month:02d}")
        elif low == "m":
            out.append(str(v.month))
        elif low == "dddd":
            out.append(v.strftime("%A"))
        elif low == "ddd":
            out.append(v.strftime("%a"))
        elif low == "dd":
            out.append(f"{v.day:02d}")
        elif low == "d":
            out.append(str(v.day))
        elif low in ("hh", "h"):
            hv = getattr(v, "hour", 0)
            out.append(f"{hv:02d}" if low == "hh" else str(hv))
            prev_h = True
            continue
        elif low in ("ss", "s"):
            sv = getattr(v, "second", 0)
            out.append(f"{sv:02d}" if low == "ss" else str(sv))
        elif low == "am/pm":
            out.append("AM" if getattr(v, "hour", 0) < 12 else "PM")
        else:
            out.append(tk)
        if low not in (":",):
            prev_h = prev_h and low in (":",)
    return "".join(out)


def format_value(v, fmt: str | None) -> str:
    fmt = fmt or "General"
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        if fmt == "General":
            if isinstance(v, dt.datetime):
                return v.strftime("%d/%m/%Y %H:%M") if (v.hour or v.minute) else v.strftime("%d/%m/%Y")
            return v.strftime("%d/%m/%Y") if isinstance(v, dt.date) else v.strftime("%H:%M")
        try:
            return _fmt_date(v, fmt)
        except Exception:
            return str(v)
    if isinstance(v, (int, float)):
        if fmt == "General" or fmt == "@":
            if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
                return str(int(v))
            return f"{v:.10g}"
        try:
            return _fmt_number(float(v), fmt)
        except Exception:
            return str(v)
    return str(v)


# ------------------------------------------------------------------ layout helpers
def col_width_pt(ws, col: int, default_w: float) -> float:
    dim = ws.column_dimensions.get(get_column_letter(col))
    w = None
    if dim is not None:
        if dim.hidden:
            return 0.0
        w = dim.width if dim.customWidth or dim.width else None
    if w is None:
        w = _group_width(ws, col)
    if w is None:
        w = default_w
    if w is False:
        return 0.0
    px = round(w * 7) if w > 0 else 0  # stored width already includes cell padding
    return px * 0.75


def _group_width(ws, col: int):
    for dim in ws.column_dimensions.values():
        if dim.min and dim.max and dim.min <= col <= dim.max and dim.min != dim.max:
            if dim.hidden:
                return False
            return dim.width or None
    return None


def print_area(ws) -> tuple[int, int, int, int] | None:
    pa = ws.print_area
    if pa:
        first = pa.split(",")[0] if isinstance(pa, str) else pa[0]
        ref = first.split("!")[-1].replace("$", "")
        try:
            c1, r1, c2, r2 = range_boundaries(ref)
            return c1, r1, c2, r2
        except Exception:
            pass
    # Used range: cells with a value, a fill or a border
    minr = minc = 10 ** 9
    maxr = maxc = 0
    for row in ws.iter_rows():
        for c in row:
            has = c.value not in (None, "") or (c.fill is not None and c.fill.fill_type == "solid") or \
                (c.border is not None and any(getattr(c.border, s).style for s in ("left", "right", "top", "bottom")))
            if has:
                minr, minc = min(minr, c.row), min(minc, c.column)
                maxr, maxc = max(maxr, c.row), max(maxc, c.column)
    for mr in ws.merged_cells.ranges:  # merged cells only store style on their first cell
        tl = ws.cell(mr.min_row, mr.min_col)
        if tl.value not in (None, "") or (tl.fill is not None and tl.fill.fill_type == "solid"):
            minr, minc = min(minr, mr.min_row), min(minc, mr.min_col)
            maxr, maxc = max(maxr, mr.max_row), max(maxc, mr.max_col)
    for img in getattr(ws, "_images", []):
        try:
            a = img.anchor._from
            r0, c0 = a.row + 1, a.col + 1
            minr, minc = min(minr, r0), min(minc, c0)
            # extend to cover the image size
            w_left, cc = img.width * 0.75 + a.colOff / 12700, c0
            while w_left > 0:
                w_left -= col_width_pt(ws, cc, 8.43) or 48
                maxc = max(maxc, cc)
                cc += 1
            h_left, rr = img.height * 0.75 + a.rowOff / 12700, r0
            while h_left > 0:
                d = ws.row_dimensions.get(rr)
                h_left -= (d.ht if d is not None and d.ht else 15)
                maxr = max(maxr, rr)
                rr += 1
        except Exception:
            pass
    if maxr == 0:
        return None
    return minc, minr, maxc, maxr


BORDER_W = {"hair": 0.25, "thin": 0.5, "dotted": 0.5, "dashed": 0.5, "dashDot": 0.5, "dashDotDot": 0.5,
            "medium": 1.0, "mediumDashed": 1.0, "mediumDashDot": 1.0, "mediumDashDotDot": 1.0, "slantDashDot": 1.0,
            "thick": 1.6, "double": 1.6}
BORDER_DASH = {"dotted": [0.6, 1.2], "dashed": [3, 2], "mediumDashed": [4, 2], "dashDot": [3, 1.5, 0.6, 1.5],
               "mediumDashDot": [4, 2, 1, 2], "dashDotDot": [3, 1.2, 0.6, 1.2, 0.6, 1.2], "hair": [0.5, 0.7]}


def _header_text(part, page: int, pages: int, sheet: str, fname: str) -> tuple[str, bool, bool, float]:
    if part is None or not part.text:
        return "", False, False, 10
    txt = part.text
    font = (part.font or "").lower()
    bold = any(k in font for k in ("bold", "gras"))
    italic = any(k in font for k in ("italic", "italique"))
    size = float(part.size or 10)
    now = dt.datetime.now()
    rep = {"&P": str(page), "&N": str(pages), "&D": now.strftime("%d/%m/%Y"), "&T": now.strftime("%H:%M"),
           "&A": sheet, "&F": fname, "&Z": "", "&&": "&"}
    for k, v in rep.items():
        txt = txt.replace(k, v).replace(k.lower(), v)
    txt = re.sub(r'&"[^"]*"|&\d+|&[A-Za-z]', "", txt)
    return txt, bold, italic, size


# ------------------------------------------------------------------ main render
def render_workbook(wb, out: Path, title: str = "") -> Path:
    theme = _theme_colors(wb)
    c = canvas.Canvas(str(out))
    c.setTitle(title)
    any_page = False
    for ws in wb.worksheets:
        if getattr(ws, "sheet_state", "visible") != "visible":
            continue
        if _render_sheet(c, ws, theme, title):
            any_page = True
    if not any_page:
        c.setPageSize(A4)
        c.showPage()
    c.save()
    return out


def _render_sheet(c: canvas.Canvas, ws, theme: list[str], fname: str) -> bool:
    area = print_area(ws)
    if not area:
        return False
    c1, r1, c2, r2 = area
    fmt = ws.sheet_format
    default_w = fmt.defaultColWidth or ((fmt.baseColWidth or 8) + 0.43) if fmt else 8.43
    default_h = (fmt.defaultRowHeight if fmt and fmt.defaultRowHeight else 15.0)

    cols = list(range(c1, c2 + 1))
    rows = list(range(r1, r2 + 1))
    cw = {col: col_width_pt(ws, col, default_w) for col in cols}
    colx, x = {}, 0.0
    for col in cols:
        colx[col] = x
        x += cw[col]
    total_w = x

    # merges
    merge_of: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for mr in ws.merged_cells.ranges:
        if mr.max_row < r1 or mr.min_row > r2 or mr.max_col < c1 or mr.min_col > c2:
            continue
        for rr in range(mr.min_row, mr.max_row + 1):
            for cc in range(mr.min_col, mr.max_col + 1):
                merge_of[(rr, cc)] = (mr.min_row, mr.min_col, min(mr.max_row, r2), min(mr.max_col, c2))

    # row heights (auto-fit rows without an explicit height that contain wrapped text)
    rh = {}
    for r in rows:
        d = ws.row_dimensions.get(r)
        if d is not None and d.hidden:
            rh[r] = 0.0
            continue
        h = d.ht if d is not None and d.ht is not None else None
        if h is None:
            h = default_h
            for col in cols:
                cell = ws.cell(r, col)
                if cell.value is None or (r, col) in merge_of:
                    continue
                if cell.alignment is not None and cell.alignment.wrap_text:
                    size = float(cell.font.sz or 11) if cell.font else 11
                    fn = pick_font(cell.font.name if cell.font else None, bool(cell.font and cell.font.b), bool(cell.font and cell.font.i))
                    n = len(_wrap(format_value(cell.value, cell.number_format), fn, size, max(cw[col] - 2 * PAD, 4)))
                    h = max(h, n * size * 1.22 + 2 * PAD)
        rh[r] = h

    # page setup
    ps = ws.page_setup
    paper = PAPER.get(int(ps.paperSize) if ps.paperSize else 9, A4)
    pw, ph = landscape(paper) if (ps.orientation or "").lower() == "landscape" else paper
    pm = ws.page_margins
    ml, mr_, mt, mb = (float(v if v is not None else d) * 72 for v, d in ((pm.left, .7), (pm.right, .7), (pm.top, .75), (pm.bottom, .75)))
    mh, mf = float(pm.header if pm.header is not None else .3) * 72, float(pm.footer if pm.footer is not None else .3) * 72
    avail_w, avail_h = pw - ml - mr_, ph - mt - mb
    total_h = sum(rh.values())
    fit = bool(ws.sheet_properties.pageSetUpPr and ws.sheet_properties.pageSetUpPr.fitToPage)
    if fit:
        fw = 1 if ps.fitToWidth is None else int(ps.fitToWidth)
        fh = 1 if ps.fitToHeight is None else int(ps.fitToHeight)
        scale = 1.0
        if fw:
            scale = min(scale, avail_w * fw / total_w if total_w else 1)
        if fh:
            scale = min(scale, avail_h * fh / total_h if total_h else 1)
    else:
        scale = (ps.scale or 100) / 100
    if total_w * scale > avail_w:  # columns never split across pages: shrink to width
        scale = avail_w / total_w
    scale = max(scale, 0.1)

    # pagination by rows
    breaks = {b.id for b in (ws.row_breaks.brk if ws.row_breaks else [])}
    pages: list[list[int]] = [[]]
    used = 0.0
    for r in rows:
        h = rh[r] * scale
        if pages[-1] and (used + h > avail_h + 0.01):
            pages.append([])
            used = 0.0
        pages[-1].append(r)
        used += h
        if r in breaks:
            pages.append([])
            used = 0.0
    pages = [p for p in pages if p]

    po = ws.print_options
    hcenter = bool(po and po.horizontalCentered)
    vcenter = bool(po and po.verticalCentered)
    grid = bool(po and po.gridLines)

    for pi, prow in enumerate(pages, 1):
        c.setPageSize((pw, ph))
        # header / footer
        for part_name, y in (("oddHeader", ph - mh), ("oddFooter", mf)):
            hf = getattr(ws, part_name, None)
            if hf is None:
                continue
            for pos in ("left", "center", "right"):
                txt, b, it, size = _header_text(getattr(hf, pos, None), pi, len(pages), ws.title, fname)
                if not txt:
                    continue
                c.setFillColor("#000000")
                c.setFont(pick_font("calibri", b, it), size)
                yy = y - size if part_name == "oddHeader" else y
                if pos == "left":
                    c.drawString(ml, yy, txt)
                elif pos == "center":
                    c.drawCentredString(pw / 2, yy, txt)
                else:
                    c.drawRightString(pw - mr_, yy, txt)

        page_h = sum(rh[r] for r in prow)
        rowy, y = {}, 0.0
        for r in prow:
            rowy[r] = y
            y += rh[r]
        ox = ml + ((avail_w - total_w * scale) / 2 if hcenter else 0)
        oy = ph - mt - ((avail_h - page_h * scale) / 2 if vcenter else 0)
        c.saveState()
        c.translate(ox, oy)
        c.scale(scale, scale)
        pset = set(prow)

        def rect_of(r0, c0, r1_, c1_):
            rs = [r for r in range(r0, r1_ + 1) if r in pset]
            if not rs:
                return None
            x0 = colx[c0]
            x1 = colx[c1_] + cw[c1_]
            y0 = rowy[rs[0]]
            y1 = rowy[rs[-1]] + rh[rs[-1]]
            return x0, y0, x1 - x0, y1 - y0

        # 1) fills
        for r in prow:
            for col in cols:
                m = merge_of.get((r, col))
                if m and (r, col) != (m[0], m[1]) and not (r == prow[0] and col == m[1] and m[0] < r):
                    continue
                cell = ws.cell(m[0], m[1]) if m else ws.cell(r, col)
                if cell.fill is None or cell.fill.fill_type != "solid":
                    continue
                color = resolve_color(cell.fill.fgColor, theme) or resolve_color(cell.fill.bgColor, theme)
                if not color:
                    continue
                box = rect_of(max(m[0], prow[0]) if m else r, m[1] if m else col, m[2] if m else r, m[3] if m else col)
                if box:
                    bx, by, bw, bh = box
                    c.setFillColor(color)
                    c.rect(bx, -by - bh, bw, bh, stroke=0, fill=1)

        # 2) gridlines
        if grid:
            c.setStrokeColor("#c8c8c8")
            c.setLineWidth(0.3)
            for r in prow:
                c.line(0, -rowy[r], total_w, -rowy[r])
            c.line(0, -page_h, total_w, -page_h)
            for col in cols:
                c.line(colx[col], 0, colx[col], -page_h)
            c.line(total_w, 0, total_w, -page_h)

        # 3) text
        for r in prow:
            for col in cols:
                m = merge_of.get((r, col))
                if m and (r, col) != (m[0], m[1]):
                    # top-left of a merge on a previous page: draw it on this page's first row
                    if not (r == prow[0] and col == m[1] and m[0] < r):
                        continue
                cell = ws.cell(m[0], m[1]) if m else ws.cell(r, col)
                if cell.value is None or cell.value == "":
                    continue
                box = rect_of(max(m[0], prow[0]) if m else r, m[1] if m else col, m[2] if m else r, m[3] if m else col)
                if not box or box[2] <= 0 or box[3] <= 0:
                    continue
                _draw_text(c, ws, cell, box, theme, cols, colx, cw, merge_of, r, col, m)

        # 4) borders
        for r in prow:
            for col in cols:
                cell = ws.cell(r, col)
                bd = cell.border
                if bd is None:
                    continue
                x0, y0 = colx[col], rowy[r]
                x1, y1 = x0 + cw[col], y0 + rh[r]
                m = merge_of.get((r, col))
                for side, (ax, ay, bx_, by_), inner in (
                        ("top", (x0, y0, x1, y0), m and r > m[0]),
                        ("bottom", (x0, y1, x1, y1), m and r < m[2]),
                        ("left", (x0, y0, x0, y1), m and col > m[1]),
                        ("right", (x1, y0, x1, y1), m and col < m[3])):
                    s = getattr(bd, side)
                    if not s or not s.style or inner:
                        continue
                    c.setStrokeColor(resolve_color(s.color, theme, "#000000"))
                    c.setLineWidth(BORDER_W.get(s.style, 0.5))
                    c.setDash(*([BORDER_DASH[s.style]] if s.style in BORDER_DASH else [[]]))
                    c.setLineCap(0 if s.style in BORDER_DASH else 2)
                    if s.style == "double":
                        c.setLineWidth(0.4)
                        off = 0.9
                        if side in ("top", "bottom"):
                            c.line(ax, -(ay - off), bx_, -(by_ - off))
                            c.line(ax, -(ay + off), bx_, -(by_ + off))
                        else:
                            c.line(ax - off, -ay, bx_ - off, -by_)
                            c.line(ax + off, -ay, bx_ + off, -by_)
                    else:
                        c.line(ax, -ay, bx_, -by_)
        c.setDash([])

        # 5) images
        for img in getattr(ws, "_images", []):
            try:
                a = img.anchor._from
                r0, c0 = a.row + 1, a.col + 1
                if r0 not in pset or c0 not in colx:
                    continue
                ix = colx[c0] + a.colOff / 12700
                iy = rowy[r0] + a.rowOff / 12700
                iw, ih = img.width * 0.75, img.height * 0.75
                data = img._data()
                c.drawImage(ImageReader(io.BytesIO(data)), ix, -iy - ih, iw, ih, mask="auto")
            except Exception:
                continue
        c.restoreState()
        c.showPage()
    return True


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    for para in str(text).split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            trial = w if not cur else cur + " " + w
            if pdfmetrics.stringWidth(trial, font, size) <= width or not cur:
                cur = trial
                while pdfmetrics.stringWidth(cur, font, size) > width and len(cur) > 1:  # very long word
                    k = len(cur)
                    while k > 1 and pdfmetrics.stringWidth(cur[:k], font, size) > width:
                        k -= 1
                    lines.append(cur[:k])
                    cur = cur[k:]
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _draw_text(c, ws, cell, box, theme, cols, colx, cw, merge_of, r, col, m):
    x, y, w, h = box
    f = cell.font
    size = float(f.sz or 11) if f else 11.0
    bold, italic = bool(f and f.b), bool(f and f.i)
    font = pick_font(f.name if f else None, bold, italic)
    color = resolve_color(f.color if f else None, theme, "#000000")
    if cell.hyperlink and color == "#000000":
        color = "#0563C1"
    underline = bool(f and f.u) or bool(cell.hyperlink)
    text = format_value(cell.value, cell.number_format)
    al = cell.alignment
    horiz = (al.horizontal if al and al.horizontal else "general")
    vert = (al.vertical if al and al.vertical else "bottom")
    wrap = bool(al and al.wrap_text)
    if horiz == "general":
        horiz = "right" if isinstance(cell.value, (int, float, dt.date, dt.datetime)) and not isinstance(cell.value, bool) else "left"
    if horiz in ("fill", "distributed", "justify"):
        horiz = "left" if horiz != "distributed" else "center"
    if horiz == "centerContinuous":
        horiz = "center"
    indent = (al.indent or 0) * size * 0.9 if al else 0

    if al and al.shrink_to_fit and not wrap:
        tw = pdfmetrics.stringWidth(text, font, size)
        if tw > w - 2 * PAD and tw > 0:
            size = max(4.0, size * (w - 2 * PAD) / tw)

    is_num = isinstance(cell.value, (int, float, dt.date, dt.datetime)) and not isinstance(cell.value, bool)
    if is_num and not wrap and pdfmetrics.stringWidth(text, font, size) > w - 2 * PAD:
        text = "#" * max(1, int((w - 2 * PAD) / max(pdfmetrics.stringWidth("#", font, size), 1)))  # like Excel
    lines = _wrap(text, font, size, max(w - 2 * PAD - indent, 4)) if wrap else text.split("\n")
    lh = size * 1.22
    th = lh * len(lines)
    if vert in ("top",):
        ty = y + PAD
    elif vert in ("center", "justify", "distributed"):
        ty = y + (h - th) / 2
    else:
        ty = y + h - PAD - th

    # clipping region (non-wrapped text overflows into empty neighbours)
    cx0, cx1 = x, x + w
    if not wrap and not m:
        tw = max(pdfmetrics.stringWidth(ln, font, size) for ln in lines) if lines else 0
        if tw > w - 2 * PAD:
            def empty(cc):
                if cc not in colx or (r, cc) in merge_of:
                    return False
                v = ws.cell(r, cc).value
                return v is None or v == ""
            if horiz in ("left", "center"):
                cc = col + 1
                while empty(cc) and cx1 - cx0 < tw + 2 * PAD + indent:
                    cx1 += cw[cc]
                    cc += 1
            if horiz in ("right", "center"):
                cc = col - 1
                while empty(cc) and cx1 - cx0 < tw + 2 * PAD:
                    cx0 -= cw[cc]
                    cc -= 1
    c.saveState()
    p = c.beginPath()
    p.rect(cx0, -y - h, cx1 - cx0, h)
    c.clipPath(p, stroke=0, fill=0)
    c.setFillColor(color)
    c.setStrokeColor(color)
    c.setFont(font, size)
    for i, ln in enumerate(lines):
        base = -(ty + i * lh + size * 0.93)
        lw = pdfmetrics.stringWidth(ln, font, size)
        if horiz == "center":
            lx = x + (w - lw) / 2
        elif horiz == "right":
            lx = x + w - PAD - lw - indent
        else:
            lx = x + PAD + indent
        c.drawString(lx, base, ln)
        if underline and ln:
            c.setLineWidth(max(0.4, size / 18))
            c.line(lx, base - size * 0.12, lx + lw, base - size * 0.12)
    c.restoreState()


# ------------------------------------------------------------------ entry points
def xlsx_to_pdf(src: Path, out: Path) -> Path:
    wb = openpyxl.load_workbook(str(src), data_only=True)
    return render_workbook(wb, out, src.stem)


def csv_to_pdf(src: Path, out: Path) -> Path:
    raw = src.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if src.suffix.lower() == ".tsv":
        dialect = "excel-tab"
    else:
        try:
            dialect = csv.Sniffer().sniff(txt[:4000], ";,\t|")
        except csv.Error:
            dialect = "excel"
    rows = list(csv.reader(io.StringIO(txt), dialect))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = src.stem[:31] or "Sheet1"
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    thin = Side(style="thin", color="FFBFBFBF")
    widths: dict[int, int] = {}
    for ri, row in enumerate(rows, 1):
        for ci, v in enumerate(row, 1):
            cell = ws.cell(ri, ci, v)  # keep the original text (locale-specific numbers)
            num = v.strip().replace("\u202f", "").replace("\xa0", "").replace(" ", "")
            if ri > 1 and re.fullmatch(r"[-+]?\d+([.,]\d+)*\s*[€$%]?", num):
                cell.alignment = Alignment(horizontal="right")
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if ri == 1:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="FFF2F2F2")
            widths[ci] = max(widths.get(ci, 0), min(len(v), 60))
    for ci, wv in widths.items():
        ws.column_dimensions[get_column_letter(ci)].width = max(6, wv * 1.1 + 2)
    total = sum(max(6, wv * 1.1 + 2) for wv in widths.values())
    ws.page_setup.orientation = "landscape" if total > 95 else "portrait"
    ws.page_setup.paperSize = 9
    from openpyxl.worksheet.properties import PageSetupProperties
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "1:1"
    return render_workbook(wb, out, src.stem)
