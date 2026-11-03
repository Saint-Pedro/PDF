"""Native Word (DOCX) to PDF renderer, used when LibreOffice is not installed.

Supports: style inheritance (document defaults, paragraph / character / table
styles, theme fonts), run formatting (font, size, bold, italic, underline,
strike, color, highlight, superscript / subscript, caps, hidden text),
paragraph formatting (alignment, spacing, line spacing, indents, shading,
page breaks, keep with next), numbered and bulleted lists, tables (column
widths, merged cells, borders, shading, vertical alignment, header rows,
conditional first-row style), inline and floating images, hyperlinks,
fields (page numbers), headers / footers and per-section page setup."""
from __future__ import annotations

import copy
import html
import io
import re
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

from . import progress
from .fonts import pick_font

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
V = "urn:schemas-microsoft-com:vml"


def q(tag: str) -> str:
    pfx, name = tag.split(":")
    return "{%s}%s" % ({"w": W, "a": A, "r": R, "wp": WP, "v": V}[pfx], name)


def wval(el, attr="w:val", default=None):
    if el is None:
        return default
    return el.get(q(attr), default)


def on(el) -> bool | None:
    """Toggle property: <w:b/> = on, <w:b w:val="0"/> = off, absent = None."""
    if el is None:
        return None
    return wval(el) not in ("0", "false", "off", "none")


def tw(v, default=0.0) -> float:  # twips -> points
    try:
        return float(v) / 20
    except (TypeError, ValueError):
        return default


HIGHLIGHT = {"yellow": "#FFFF00", "green": "#00FF00", "cyan": "#00FFFF", "magenta": "#FF00FF", "blue": "#0000FF",
             "red": "#FF0000", "darkBlue": "#000080", "darkCyan": "#008080", "darkGreen": "#008000",
             "darkMagenta": "#800080", "darkRed": "#800000", "darkYellow": "#808000", "darkGray": "#808080",
             "lightGray": "#C0C0C0", "black": "#000000", "white": "#FFFFFF"}
TAB = "\x02TAB\x02"
BULLETS = {"": "•", "": "▪", "": "➢", "": "✓", "": "❖", "": "➔", "o": "◦", "": "◦", "•": "•"}


class HRule(Flowable):
    def __init__(self, width, color="#000000", thickness=0.5):
        super().__init__()
        self.width, self.color, self.thickness = width, color, thickness

    def wrap(self, aw, ah):
        return aw, self.thickness + 2

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 1, self.width, 1)


class TabLine(Flowable):
    """One line of text segments aligned on tab stops (left / center / right)."""

    def __init__(self, items, style, indent=0.0):
        super().__init__()
        self.items, self.style, self.indent = items, style, indent

    def wrap(self, aw, ah):
        self._aw = aw
        return aw, self.style.leading

    def draw(self):
        x_end = 0.0
        for seg, kind, pos in self.items:
            if not seg.strip():
                continue
            p = Paragraph(seg, self.style)
            p.wrap(self._aw, 1000)
            w = max(p.getActualLineWidths0() or [0])
            if kind == "center":
                x = pos - w / 2
            elif kind in ("right", "end"):
                x = pos - w
            else:
                x = max(pos, x_end)
            x = max(x + self.indent, x_end)
            p.drawOn(self.canv, x, 0)
            x_end = x + w


class DocxRenderer:
    def __init__(self, path: Path):
        import docx  # python-docx, used for package / part access
        self.doc = docx.Document(str(path))
        self.part = self.doc.part
        self.tmp = Path(tempfile.mkdtemp(prefix="docx-img-"))
        self._img_n = 0
        self.styles = {}
        self.default_style = {}
        st = self.doc.styles.element
        for s in st.findall(q("w:style")):
            sid = s.get(q("w:styleId"))
            self.styles[sid] = s
            if s.get(q("w:default")) in ("1", "true"):
                self.default_style[s.get(q("w:type"))] = sid
        dd = st.find(q("w:docDefaults"))
        self.def_rpr = dd.find(f"{q('w:rPrDefault')}/{q('w:rPr')}") if dd is not None else None
        self.def_ppr = dd.find(f"{q('w:pPrDefault')}/{q('w:pPr')}") if dd is not None else None
        self.theme_fonts = self._theme_fonts()
        self.numbering = self._load_numbering()
        self.counters: dict[tuple[str, int], int] = {}
        self.fields_mode = "body"
        self._prev_style = None
        self._last_para = None

    # ------------------------------------------------------------ package helpers
    def _theme_fonts(self) -> dict:
        out = {"major": "Calibri Light", "minor": "Calibri"}
        try:
            for rel in self.part.rels.values():
                if rel.reltype.endswith("/theme"):
                    root = ET.fromstring(rel.target_part.blob)
                    for kind in ("major", "minor"):
                        el = root.find(f".//{{{A}}}{kind}Font/{{{A}}}latin")
                        if el is not None and el.get("typeface"):
                            out[kind] = el.get("typeface")
        except Exception:
            pass
        return out

    def _load_numbering(self):
        try:
            el = self.part.numbering_part.element
        except Exception:
            return None
        nums, abstract = {}, {}
        for an in el.findall(q("w:abstractNum")):
            abstract[an.get(q("w:abstractNumId"))] = an
        for n in el.findall(q("w:num")):
            aid = wval(n.find(q("w:abstractNumId")))
            overrides = {}
            for ov in n.findall(q("w:lvlOverride")):
                overrides[int(ov.get(q("w:ilvl"), 0))] = ov
            nums[n.get(q("w:numId"))] = (abstract.get(aid), overrides)
        return nums

    def _level(self, num_id: str, ilvl: int):
        if not self.numbering or num_id not in self.numbering:
            return None, 1
        an, overrides = self.numbering[num_id]
        lvl, start = None, 1
        ov = overrides.get(ilvl)
        if ov is not None:
            lvl = ov.find(q("w:lvl"))
            so = ov.find(q("w:startOverride"))
            if so is not None:
                start = int(wval(so, default=1))
        if lvl is None and an is not None:
            lvl = next((l for l in an.findall(q("w:lvl")) if int(l.get(q("w:ilvl"), 0)) == ilvl), None)
        if lvl is not None and ov is None:
            st = lvl.find(q("w:start"))
            if st is not None:
                start = int(wval(st, default=1))
        return lvl, start

    def image_path(self, rid: str) -> str | None:
        try:
            blob = self.part.related_parts[rid].blob
            img = Image.open(io.BytesIO(blob))
            img.load()
        except Exception:
            return None  # EMF / WMF / missing
        self._img_n += 1
        p = self.tmp / f"img{self._img_n}.png"
        if img.mode not in ("RGB", "RGBA", "L", "LA"):
            img = img.convert("RGBA")
        img.save(p)
        return str(p)

    # ------------------------------------------------------------ style resolution
    def _style_chain(self, sid: str | None) -> list:
        chain, seen = [], set()
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            s = self.styles[sid]
            chain.append(s)
            sid = wval(s.find(q("w:basedOn")))
        return list(reversed(chain))

    def _rpr_props(self, rpr, props: dict) -> None:
        if rpr is None:
            return
        f = rpr.find(q("w:rFonts"))
        if f is not None:
            name = f.get(q("w:ascii")) or f.get(q("w:hAnsi"))
            theme = f.get(q("w:asciiTheme")) or f.get(q("w:hAnsiTheme"))
            if theme:
                name = self.theme_fonts["major" if theme.startswith("major") else "minor"]
            if name:
                props["font"] = name
        sz = rpr.find(q("w:sz"))
        if sz is not None and wval(sz):
            props["size"] = float(wval(sz)) / 2
        for tag, key in (("w:b", "bold"), ("w:i", "italic"), ("w:strike", "strike"), ("w:dstrike", "strike"),
                         ("w:caps", "caps"), ("w:vanish", "hidden")):
            v = on(rpr.find(q(tag)))
            if v is not None:
                props[key] = v
        u = rpr.find(q("w:u"))
        if u is not None:
            props["underline"] = wval(u, default="single") != "none"
        c = rpr.find(q("w:color"))
        if c is not None and wval(c) and wval(c) != "auto":
            props["color"] = "#" + wval(c)
        hl = rpr.find(q("w:highlight"))
        if hl is not None and wval(hl) in HIGHLIGHT:
            props["highlight"] = HIGHLIGHT[wval(hl)]
        shd = rpr.find(q("w:shd"))
        if shd is not None and wval(shd, "w:fill") not in (None, "auto", "FFFFFF"):
            props["highlight"] = "#" + wval(shd, "w:fill")
        va = rpr.find(q("w:vertAlign"))
        if va is not None:
            props["valign"] = wval(va)

    def _ppr_props(self, ppr, props: dict) -> None:
        if ppr is None:
            return
        jc = ppr.find(q("w:jc"))
        if jc is not None:
            props["jc"] = wval(jc)
        sp = ppr.find(q("w:spacing"))
        if sp is not None:
            for a, k in (("w:before", "before"), ("w:after", "after"), ("w:line", "line")):
                if sp.get(q(a)) is not None:
                    props[k] = float(sp.get(q(a)))
            if sp.get(q("w:lineRule")):
                props["lineRule"] = sp.get(q("w:lineRule"))
            if sp.get(q("w:beforeAutospacing")) in ("1", "true"):
                props["before"] = 280
            if sp.get(q("w:afterAutospacing")) in ("1", "true"):
                props["after"] = 280
        ind = ppr.find(q("w:ind"))
        if ind is not None:
            for a, k in (("w:left", "left"), ("w:start", "left"), ("w:right", "right"), ("w:end", "right"),
                         ("w:firstLine", "firstLine"), ("w:hanging", "hanging")):
                if ind.get(q(a)) is not None:
                    props[k] = float(ind.get(q(a)))
            if ind.get(q("w:firstLine")) is not None:
                props.pop("hanging", None)
            if ind.get(q("w:hanging")) is not None:
                props.pop("firstLine", None)
        for tag, key in (("w:pageBreakBefore", "pageBreakBefore"), ("w:keepNext", "keepNext"),
                         ("w:contextualSpacing", "contextual")):
            v = on(ppr.find(q(tag)))
            if v is not None:
                props[key] = v
        shd = ppr.find(q("w:shd"))
        if shd is not None and wval(shd, "w:fill") not in (None, "auto"):
            props["shd"] = "#" + wval(shd, "w:fill")
        npr = ppr.find(q("w:numPr"))
        if npr is not None:
            nid = wval(npr.find(q("w:numId")))
            if nid is not None:
                props["numId"] = nid
            il = npr.find(q("w:ilvl"))
            if il is not None:
                props["ilvl"] = int(wval(il, default=0))
        bdr = ppr.find(q("w:pBdr"))
        if bdr is not None:
            for side in ("top", "bottom"):
                b = bdr.find(q("w:" + side))
                if b is not None and wval(b) not in (None, "nil", "none"):
                    props["border_" + side] = ("#" + (wval(b, "w:color") or "000000")).replace("#auto", "#000000"), \
                        max(0.25, float(wval(b, "w:sz", 4)) / 8)

    def para_props(self, p, table_ctx: dict | None = None) -> tuple[dict, dict, str | None]:
        ppr = p.find(q("w:pPr"))
        sid = wval(ppr.find(q("w:pStyle"))) if ppr is not None else None
        sid = sid or self.default_style.get("paragraph")
        pp, rp = {}, {}
        self._ppr_props(self.def_ppr, pp)
        self._rpr_props(self.def_rpr, rp)
        if table_ctx:
            self._ppr_props(table_ctx.get("ppr"), pp)
            self._rpr_props(table_ctx.get("rpr"), rp)
        for s in self._style_chain(sid):
            self._ppr_props(s.find(q("w:pPr")), pp)
            self._rpr_props(s.find(q("w:rPr")), rp)
        if table_ctx and table_ctx.get("cond_props"):
            rp.update(table_ctx["cond_props"])
        if ppr is not None:
            self._ppr_props(ppr, pp)
            self._rpr_props(ppr.find(q("w:rPr")), {})  # paragraph mark only
        if pp.get("numId") not in (None, "0"):
            lvl, _ = self._level(pp["numId"], pp.get("ilvl", 0))
            if lvl is not None:
                base = {}
                self._ppr_props(lvl.find(q("w:pPr")), base)
                for k in ("left", "hanging", "firstLine"):
                    if k in base and not (ppr is not None and ppr.find(q("w:ind")) is not None):
                        pp[k] = base[k]
        return pp, rp, sid

    def run_props(self, r, base_rp: dict) -> dict:
        props = dict(base_rp)
        rpr = r.find(q("w:rPr"))
        if rpr is not None:
            rs = wval(rpr.find(q("w:rStyle")))
            for s in self._style_chain(rs):
                self._rpr_props(s.find(q("w:rPr")), props)
            self._rpr_props(rpr, props)
        return props

    # ------------------------------------------------------------ inline content
    def markup(self, p, rp: dict, avail_w: float) -> tuple[str, float, bool]:
        """Paragraph runs -> reportlab markup. Returns (markup, max font size, has_page_break)."""
        parts: list[str] = []
        max_size = rp.get("size", 11)
        page_break = False
        field = {"state": None, "instr": ""}
        images: list[tuple[str, float, float]] = []
        self._last_images = images

        def emit_text(t: str, props: dict):
            nonlocal max_size
            if props.get("hidden") or not t:
                return
            if "\t" in t:  # tabs are kept outside of tags so tab-stop layout can split on them
                pieces = t.split("\t")
                for i, piece in enumerate(pieces):
                    if i:
                        parts.append(TAB)
                    emit_text(piece, props)
                return
            if props.get("caps"):
                t = t.upper()
            size = props.get("size", 11)
            max_size = max(max_size, size)
            font = pick_font(props.get("font"), bool(props.get("bold")), bool(props.get("italic")))
            s = html.escape(t)
            s = s.replace("\x01PAGE\x01", "§§PAGE§§").replace("\x01NUMPAGES\x01", "§§NUMPAGES§§")
            s = f'<font face="{font}" size="{size:g}" color="{props.get("color", "#000000")}">{s}</font>'
            if props.get("underline"):
                s = f"<u>{s}</u>"
            if props.get("strike"):
                s = f"<strike>{s}</strike>"
            if props.get("valign") == "superscript":
                s = f"<super>{s}</super>"
            elif props.get("valign") == "subscript":
                s = f"<sub>{s}</sub>"
            if props.get("highlight"):
                s = f'<span backColor="{props["highlight"]}">{s}</span>'
            parts.append(s)

        def walk(node, link: str | None = None):
            nonlocal page_break
            for ch in node:
                tag = ch.tag
                if tag == q("w:r"):
                    props = self.run_props(ch, rp)
                    for el in ch:
                        t = el.tag
                        if t == q("w:fldChar"):
                            ft = el.get(q("w:fldCharType"))
                            if ft == "begin":
                                field["state"], field["instr"] = "instr", ""
                            elif ft == "separate":
                                field["state"] = "result"
                                code = field["instr"].strip().split(" ")[0].upper() if field["instr"].strip() else ""
                                if code in ("PAGE", "NUMPAGES") and self.fields_mode == "header":
                                    emit_text("\x01PAGE\x01" if code == "PAGE" else "\x01NUMPAGES\x01", props)
                                    field["state"] = "skip"
                            elif ft == "end":
                                if field["state"] == "instr":  # field without cached result
                                    code = field["instr"].strip().split(" ")[0].upper() if field["instr"].strip() else ""
                                    if code in ("PAGE", "NUMPAGES") and self.fields_mode == "header":
                                        emit_text("\x01PAGE\x01" if code == "PAGE" else "\x01NUMPAGES\x01", props)
                                field["state"] = None
                        elif t == q("w:instrText"):
                            field["instr"] += el.text or ""
                        elif field["state"] in ("instr", "skip"):
                            continue
                        elif t == q("w:t"):
                            emit_text(el.text or "", props)
                        elif t == q("w:tab"):
                            emit_text("\t", props)
                        elif t in (q("w:br"), q("w:cr")):
                            if el.get(q("w:type")) == "page":
                                page_break = True
                            else:
                                parts.append("<br/>")
                        elif t == q("w:noBreakHyphen"):
                            emit_text("-", props)
                        elif t == q("w:sym"):
                            ch_ = chr(int(el.get(q("w:char"), "2022"), 16))
                            emit_text(BULLETS.get(ch_, ch_), props)
                        elif t == q("w:drawing") or t.endswith("}AlternateContent") or t == q("w:pict"):
                            for path, cx, cy in self.drawings(el, avail_w):
                                images.append((path, cx, cy))
                                parts.append(f'<img src="{path}" width="{cx:.1f}" height="{cy:.1f}" valign="bottom"/>')
                elif tag == q("w:hyperlink"):
                    walk(ch, link)
                elif tag == q("w:fldSimple"):
                    code = (ch.get(q("w:instr")) or "").strip().split(" ")[0].upper()
                    if code in ("PAGE", "NUMPAGES") and self.fields_mode == "header":
                        emit_text("\x01PAGE\x01" if code == "PAGE" else "\x01NUMPAGES\x01", self.run_props(ch, rp))
                    else:
                        walk(ch, link)
                elif tag in (q("w:ins"), q("w:smartTag"), q("w:customXml"), q("w:bdo"), q("w:dir")):
                    walk(ch, link)
                elif tag == q("w:sdt"):
                    c = ch.find(q("w:sdtContent"))
                    if c is not None:
                        walk(c, link)
                # w:del, w:proofErr, bookmarks… are ignored
        walk(p)
        return "".join(parts), max_size, page_break

    def drawings(self, el, avail_w: float) -> list[tuple[str, float, float]]:
        out = []
        for blip in el.iter(q("a:blip")):
            rid = blip.get(q("r:embed")) or blip.get(q("r:link"))
            if not rid:
                continue
            # size from the closest wp:extent
            cx = cy = None
            for ext in el.iter(q("wp:extent")):
                cx, cy = int(ext.get("cx", 0)) / 12700, int(ext.get("cy", 0)) / 12700
                break
            path = self.image_path(rid)
            if not path:
                continue
            if not cx or not cy:
                with Image.open(path) as im:
                    cx, cy = im.width * 0.75, im.height * 0.75
            if cx > avail_w:
                cy, cx = cy * avail_w / cx, avail_w
            out.append((path, cx, cy))
            break  # AlternateContent: first choice only
        if not out:
            for im in el.iter(q("v:imagedata")):
                rid = im.get(q("r:id"))
                path = self.image_path(rid) if rid else None
                if path:
                    with Image.open(path) as img:
                        cx, cy = img.width * 0.75, img.height * 0.75
                    if cx > avail_w:
                        cy, cx = cy * avail_w / cx, avail_w
                    out.append((path, cx, cy))
                    break
        return out

    # ------------------------------------------------------------ list labels
    def list_label(self, pp: dict, rp: dict) -> tuple[str | None, tuple | None]:
        nid = pp.get("numId")
        if nid in (None, "0"):
            return None, None
        ilvl = pp.get("ilvl", 0)
        lvl, start = self._level(nid, ilvl)
        if lvl is None:
            return None, None
        an_key = nid
        if self.numbering and nid in self.numbering and self.numbering[nid][0] is not None:
            an_key = self.numbering[nid][0].get(q("w:abstractNumId"))
        key = (an_key, ilvl)
        self.counters[key] = self.counters.get(key, start - 1) + 1
        for k in list(self.counters):
            if k[0] == an_key and k[1] > ilvl:
                del self.counters[k]
        fmt = wval(lvl.find(q("w:numFmt")), default="decimal")
        text = wval(lvl.find(q("w:lvlText")), default="%1.")
        lprops = dict(rp)
        self._rpr_props(lvl.find(q("w:rPr")), lprops)
        if fmt == "bullet":
            label = "".join(BULLETS.get(ch, ch) for ch in text) or "•"
            if lprops.get("font", "").lower() in ("symbol", "wingdings"):
                lprops.pop("font")
        elif fmt == "none":
            label = ""
        else:
            def render(i: int) -> str:
                lv_, st_ = self._level(nid, i)
                f_ = wval(lv_.find(q("w:numFmt")), default="decimal") if lv_ is not None else "decimal"
                n = self.counters.get((an_key, i), st_)
                return self._fmt_num(n, f_)
            label = re.sub(r"%(\d)", lambda m: render(int(m.group(1)) - 1), text)
        font = pick_font(lprops.get("font"), bool(lprops.get("bold")), bool(lprops.get("italic")))
        size = lprops.get("size", 11)
        return label, (font, size, lprops.get("color", "#000000"))

    @staticmethod
    def _fmt_num(n: int, fmt: str) -> str:
        if fmt in ("lowerLetter", "upperLetter"):
            s = ""
            k = n
            while k > 0:
                k, r = divmod(k - 1, 26)
                s = chr(97 + r) + s
            return s.upper() if fmt == "upperLetter" else s
        if fmt in ("lowerRoman", "upperRoman"):
            vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
                    (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
            s, k = "", n
            for v, r in vals:
                while k >= v:
                    s += r
                    k -= v
            return s.upper() if fmt == "upperRoman" else s
        if fmt == "decimalZero":
            return f"{n:02d}"
        return str(n)

    # ------------------------------------------------------------ paragraphs
    def tab_stops(self, p, sid) -> list[tuple[str, float]]:
        stops: dict[float, str] = {}
        sources = [s.find(q("w:pPr")) for s in self._style_chain(sid)] + [p.find(q("w:pPr"))]
        for ppr in sources:
            tabs = ppr.find(q("w:tabs")) if ppr is not None else None
            if tabs is None:
                continue
            for t in tabs.findall(q("w:tab")):
                pos = tw(t.get(q("w:pos")))
                if wval(t) == "clear":
                    stops.pop(pos, None)
                else:
                    stops[pos] = wval(t, default="left")
        return sorted(stops.items())

    def paragraph(self, p, avail_w: float, table_ctx: dict | None = None, prev_style: str | None = None) -> list:
        pp, rp, sid = self.para_props(p, table_ctx)
        text, max_size, page_break = self.markup(p, rp, avail_w)
        images = list(getattr(self, "_last_images", []))
        size = rp.get("size", 11)
        line = pp.get("line", 240)
        rule = pp.get("lineRule", "auto")
        if rule == "exact":
            leading = tw(line)
        elif rule == "atLeast":
            leading = max(tw(line), max_size * 1.2)
        else:
            leading = max_size * 1.17 * (line / 240)
        before, after = tw(pp.get("before", 0)), tw(pp.get("after", 0))
        if pp.get("contextual") and prev_style == sid:
            before = 0
            last = getattr(self, "_last_para", None)
            if last is not None:
                last.style.spaceAfter = 0
        left, right = tw(pp.get("left", 0)), tw(pp.get("right", 0))
        first = tw(pp.get("firstLine", 0)) - tw(pp.get("hanging", 0))
        align = {"center": TA_CENTER, "right": TA_RIGHT, "end": TA_RIGHT, "both": TA_JUSTIFY, "distribute": TA_JUSTIFY}.get(pp.get("jc"), TA_LEFT)
        font = pick_font(rp.get("font"), bool(rp.get("bold")), bool(rp.get("italic")))
        style = ParagraphStyle(
            "p", fontName=font, fontSize=size, leading=leading, alignment=align,
            spaceBefore=before, spaceAfter=after, leftIndent=max(0, left), rightIndent=max(0, right),
            firstLineIndent=first, textColor=rp.get("color", "#000000"), keepWithNext=bool(pp.get("keepNext")),
            backColor=pp.get("shd"), allowWidows=1, allowOrphans=0)
        label, label_font = (None, None) if table_ctx and table_ctx.get("no_lists") else self.list_label(pp, rp)
        if images:
            leading = max(leading, max(h for _, _, h in images) + 2)
            style.leading = leading
        out: list = []
        if pp.get("pageBreakBefore"):
            out.append(PageBreak())
        if pp.get("border_top"):
            out.append(HRule(avail_w - left - right, *pp["border_top"]))
        if label is not None:
            style.bulletIndent = max(0, left + first)
            style.firstLineIndent = 0
            style.bulletFontName, style.bulletFontSize, style.bulletColor = label_font
        if not (TAB in text and not label and not images and any(k in ("center", "right", "end") for _, k in self.tab_stops(p, sid))):
            text = text.replace(TAB, "&nbsp;" * 6)
        only_images = images and not re.sub(r"<img[^>]*/>|<[^>]+>|&nbsp;|\s", "", text)
        tabbed = TAB in text and not label and not images
        stops = self.tab_stops(p, sid) if tabbed else []
        if only_images:
            from reportlab.platypus import Image as RLImage
            for path, cx, cy in images:
                im = RLImage(path, width=cx, height=cy)
                im.hAlign = {TA_CENTER: "CENTER", TA_RIGHT: "RIGHT"}.get(align, "LEFT")
                out.append(Spacer(1, before))
                out.append(im)
                out.append(Spacer(1, after))
        elif stops and any(k in ("center", "right", "end") for _, k in stops):
            # Tab stops (typical in headers/footers): position each segment on one line
            segs = text.split(TAB)
            kinds = ["left"] + [k for _, k in stops]
            pos = [0.0] + [x for x, _ in stops]
            items = [(seg, kinds[i] if i < len(kinds) else "left", pos[i] if i < len(pos) else 0.0) for i, seg in enumerate(segs)]
            st = ParagraphStyle("t", parent=style, alignment=TA_LEFT, leftIndent=0, rightIndent=0, firstLineIndent=0,
                                spaceBefore=0, spaceAfter=0)
            out += [Spacer(1, before), TabLine(items, st, left), Spacer(1, after)]
        elif text.strip() or label:
            try:
                para = Paragraph(text or "&nbsp;", style, bulletText=label if label else None)
            except Exception:  # malformed markup: fall back to plain text
                plain = re.sub(r"<[^>]+>", "", text)
                para = Paragraph(html.escape(html.unescape(plain)) or "&nbsp;", style)
            out.append(para)
            self._last_para = para
        else:
            out.append(Spacer(1, leading + before + after) if not page_break else Spacer(1, 0))
            self._last_para = None
        if pp.get("border_bottom"):
            out.append(HRule(avail_w - left - right, *pp["border_bottom"]))
        if page_break:
            out.append(PageBreak())
        out_sid = sid
        return out if out_sid is None else out + [("__style__", out_sid)]

    # ------------------------------------------------------------ tables
    def _borders(self, el, out: dict) -> None:
        if el is None:
            return
        for side in ("top", "left", "bottom", "right", "insideH", "insideV", "start", "end"):
            b = el.find(q("w:" + side))
            if b is None:
                continue
            key = {"start": "left", "end": "right"}.get(side, side)
            val = wval(b)
            if val in ("nil", "none"):
                out[key] = None
            else:
                color = wval(b, "w:color", "000000")
                out[key] = (("#" + color) if color not in ("auto", None) else "#000000", max(0.25, float(wval(b, "w:sz", 4)) / 8))

    def table(self, tbl, avail_w: float) -> list:
        tblpr = tbl.find(q("w:tblPr"))
        sid = wval(tblpr.find(q("w:tblStyle"))) if tblpr is not None else None
        sid = sid or self.default_style.get("table")
        borders, ppr, rpr, first_row, cell_shd = {}, None, None, None, None
        conds: dict[str, object] = {}
        mar = {"left": 5.4, "right": 5.4, "top": 0.0, "bottom": 0.0}
        look_first = True
        for s in self._style_chain(sid):
            spr = s.find(q("w:tblPr"))
            if spr is not None:
                self._borders(spr.find(q("w:tblBorders")), borders)
                cm = spr.find(q("w:tblCellMar"))
                if cm is not None:
                    for side in ("left", "right", "top", "bottom", "start", "end"):
                        e = cm.find(q("w:" + side))
                        if e is not None:
                            mar[{"start": "left", "end": "right"}.get(side, side)] = tw(e.get(q("w:w")))
            ppr = s.find(q("w:pPr")) if s.find(q("w:pPr")) is not None else ppr
            rpr = s.find(q("w:rPr")) if s.find(q("w:rPr")) is not None else rpr
            tcpr = s.find(q("w:tcPr"))
            if tcpr is not None and tcpr.find(q("w:shd")) is not None:
                cell_shd = wval(tcpr.find(q("w:shd")), "w:fill")
            for cond in s.findall(q("w:tblStylePr")):
                conds[cond.get(q("w:type"))] = cond
                if cond.get(q("w:type")) == "firstRow":
                    first_row = cond
        look_col, look_band = False, True
        if tblpr is not None:
            self._borders(tblpr.find(q("w:tblBorders")), borders)
            look = tblpr.find(q("w:tblLook"))
            if look is not None:
                fc, nb = look.get(q("w:firstColumn")), look.get(q("w:noHBand"))
                lv = int(look.get(q("w:val"), "0"), 16) if look.get(q("w:val")) else 0
                look_col = fc in ("1", "true") if fc is not None else bool(lv & 0x0080)
                look_band = not (nb in ("1", "true")) if nb is not None else not bool(lv & 0x0200)
            if look is not None:
                fr = look.get(q("w:firstRow"))
                if fr is not None:
                    look_first = fr in ("1", "true")
                elif look.get(q("w:val")):
                    look_first = bool(int(look.get(q("w:val")), 16) & 0x0020)
        grid = [tw(g.get(q("w:w"))) for g in tbl.findall(f"{q('w:tblGrid')}/{q('w:gridCol')}")]
        rows = tbl.findall(q("w:tr"))
        if not rows:
            return []
        ncols = max(len(grid), max(sum(int(wval(tc.find(f"{q('w:tcPr')}/{q('w:gridSpan')}"), default=1)) for tc in tr.findall(q("w:tc"))) for tr in rows))
        if len(grid) < ncols or not all(grid):
            grid = [avail_w / ncols] * ncols
        total = sum(grid)
        if total > avail_w:
            grid = [g * avail_w / total for g in grid]
        data = [["" for _ in range(ncols)] for _ in rows]
        cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), mar["left"]), ("RIGHTPADDING", (0, 0), (-1, -1), mar["right"]),
                ("TOPPADDING", (0, 0), (-1, -1), mar["top"] + 1), ("BOTTOMPADDING", (0, 0), (-1, -1), mar["bottom"] + 1)]
        vmerge_start: dict[int, int] = {}
        header_rows = 0
        row_heights: list[float | None] = []
        for ri, tr in enumerate(rows):
            trpr = tr.find(q("w:trPr"))
            if trpr is not None and trpr.find(q("w:tblHeader")) is not None and header_rows == ri:
                header_rows += 1
            h = trpr.find(q("w:trHeight")) if trpr is not None else None
            row_heights.append(tw(h.get(q("w:val"))) if h is not None and h.get(q("w:hRule")) == "exact" else None)
            ci = 0
            is_first = ri == 0 and look_first and first_row is not None
            for tc in tr.findall(q("w:tc")):
                if ci >= ncols:
                    break
                tcpr = tc.find(q("w:tcPr"))
                span = int(wval(tcpr.find(q("w:gridSpan")), default=1)) if tcpr is not None else 1
                span = max(1, min(span, ncols - ci))
                vm = tcpr.find(q("w:vMerge")) if tcpr is not None else None
                cw = sum(grid[ci:ci + span])
                if vm is not None and wval(vm) != "restart":
                    start = vmerge_start.get(ci)
                    if start is not None:
                        cmds.append(("SPAN", (ci, start), (ci + span - 1, ri)))
                    ci += span
                    continue
                if vm is not None:
                    vmerge_start[ci] = ri
                else:
                    vmerge_start.pop(ci, None)
                if span > 1:
                    cmds.append(("SPAN", (ci, ri), (ci + span - 1, ri)))
                ctx = {"ppr": ppr, "rpr": rpr}
                # conditional formats, lowest priority first
                active = []
                body_ri = ri - (1 if look_first and first_row is not None else 0)
                if look_band and body_ri >= 0 and not is_first:
                    active.append(conds.get("band1Horz" if body_ri % 2 == 0 else "band2Horz"))
                if look_col and ci == 0:
                    active.append(conds.get("firstCol"))
                if is_first:
                    active.append(first_row)
                active = [a for a in active if a is not None]
                if active:
                    cond_props: dict = {}
                    for a in active:
                        self._rpr_props(a.find(q("w:rPr")), cond_props)
                    ctx["cond_props"] = cond_props
                inner_w = max(cw - mar["left"] - mar["right"], 10)
                flows = self.blocks(list(tc), inner_w, ctx)
                data[ri][ci] = [f for f in flows if not isinstance(f, PageBreak)] or ""
                # shading
                fill = cell_shd
                for a in active:
                    fs = a.find(f"{q('w:tcPr')}/{q('w:shd')}")
                    if fs is not None and wval(fs, "w:fill") not in (None, "auto"):
                        fill = wval(fs, "w:fill")
                if tcpr is not None and tcpr.find(q("w:shd")) is not None:
                    fill = wval(tcpr.find(q("w:shd")), "w:fill") or fill
                if fill and fill not in ("auto",):
                    cmds.append(("BACKGROUND", (ci, ri), (ci + span - 1, ri), "#" + fill))
                va = wval(tcpr.find(q("w:vAlign"))) if tcpr is not None else None
                if va in ("center", "bottom"):
                    cmds.append(("VALIGN", (ci, ri), (ci + span - 1, ri), {"center": "MIDDLE", "bottom": "BOTTOM"}[va]))
                # borders: table defaults, first-row style, then cell overrides
                cb = {"top": borders.get("insideH") if ri > 0 else borders.get("top"),
                      "bottom": borders.get("insideH") if ri < len(rows) - 1 else borders.get("bottom"),
                      "left": borders.get("insideV") if ci > 0 else borders.get("left"),
                      "right": borders.get("insideV") if ci + span < ncols else borders.get("right")}
                for a in active:
                    fb: dict = {}
                    self._borders(a.find(f"{q('w:tcPr')}/{q('w:tcBorders')}"), fb)
                    cb.update({k: v for k, v in fb.items() if k in cb})
                if tcpr is not None:
                    own: dict = {}
                    self._borders(tcpr.find(q("w:tcBorders")), own)
                    cb.update({k: v for k, v in own.items() if k in cb})
                for side, cmd in (("top", "LINEABOVE"), ("bottom", "LINEBELOW"), ("left", "LINEBEFORE"), ("right", "LINEAFTER")):
                    if cb.get(side):
                        color, width = cb[side]
                        cmds.append((cmd, (ci, ri), (ci + span - 1, ri), width, color))
                ci += span
        t = Table(data, colWidths=grid, rowHeights=row_heights if any(row_heights) else None,
                  repeatRows=header_rows, hAlign={"center": "CENTER", "right": "RIGHT", "end": "RIGHT"}.get(
                      wval(tblpr.find(q("w:jc"))) if tblpr is not None else None, "LEFT"))
        t.setStyle(TableStyle(cmds))
        return [t, Spacer(1, 2)]

    # ------------------------------------------------------------ block iteration
    def blocks(self, children, avail_w: float, table_ctx: dict | None = None) -> list:
        out: list = []
        prev_style = self._prev_style if table_ctx is None else None
        for el in children:
            if el.tag == q("w:p"):
                items = self.paragraph(el, avail_w, table_ctx, prev_style)
                prev_style = None
                for it in items:
                    if isinstance(it, tuple) and it[0] == "__style__":
                        prev_style = it[1]
                    else:
                        out.append(it)
                if table_ctx is None:
                    ppr = el.find(q("w:pPr"))
                    if ppr is not None and ppr.find(q("w:sectPr")) is not None:
                        out.append(("__section__", ppr.find(q("w:sectPr"))))
            elif el.tag == q("w:tbl"):
                out += self.table(el, avail_w)
                prev_style = None
                self._prev_style, self._last_para = None, None
            elif el.tag == q("w:sdt"):
                c = el.find(q("w:sdtContent"))
                if c is not None:
                    out += self.blocks(list(c), avail_w, table_ctx)
        if table_ctx is None:
            self._prev_style = prev_style
        return out

    # ------------------------------------------------------------ page setup
    @staticmethod
    def page_setup(sect) -> dict:
        pg = sect.find(q("w:pgSz")) if sect is not None else None
        mar = sect.find(q("w:pgMar")) if sect is not None else None
        w, h = tw(wval(pg, "w:w", 11906)), tw(wval(pg, "w:h", 16838))
        if wval(pg, "w:orient") == "landscape" and w < h:
            w, h = h, w
        m = {k: tw(wval(mar, "w:" + k, d)) for k, d in (("top", 1417), ("bottom", 1417), ("left", 1417), ("right", 1417),
                                                        ("header", 708), ("footer", 708))}
        refs = {}
        if sect is not None:
            for kind in ("headerReference", "footerReference"):
                for ref in sect.findall(q("w:" + kind)):
                    refs[(kind, ref.get(q("w:type"), "default"))] = ref.get(q("r:id"))
        title_pg = sect is not None and sect.find(q("w:titlePg")) is not None and on(sect.find(q("w:titlePg")))
        return {"w": w, "h": h, "m": m, "refs": refs, "title_pg": title_pg}

    def hf_flowables(self, rid: str | None, avail_w: float) -> list:
        if not rid:
            return []
        try:
            part = self.part.related_parts[rid]
            root = part.element if hasattr(part, "element") else ET.fromstring(part.blob)
        except Exception:
            return []
        saved_part, self.part = self.part, part  # images in headers live in the header part
        self.fields_mode = "header"
        try:
            flows = [f for f in self.blocks(list(root), avail_w, {"no_lists": True}) if not isinstance(f, tuple)]
        finally:
            self.part, self.fields_mode = saved_part, "body"
        return flows

    def render(self, out: Path) -> Path:
        body = self.doc.element.body
        children = [c for c in body if c.tag != q("w:sectPr")]
        sects = [c.find(f"{q('w:pPr')}/{q('w:sectPr')}") for c in children if c.tag == q("w:p") and c.find(f"{q('w:pPr')}/{q('w:sectPr')}") is not None]
        sects.append(body.find(q("w:sectPr")))
        setups = [self.page_setup(s) for s in sects]
        # inherit header/footer references from previous sections
        for i in range(1, len(setups)):
            for k, v in setups[i - 1]["refs"].items():
                setups[i]["refs"].setdefault(k, v)

        n = len(children) or 1
        progress.update(0.05)
        story: list = []
        sect_i = 0
        first_w = setups[0]["w"] - setups[0]["m"]["left"] - setups[0]["m"]["right"]
        avail = first_w
        for i, el in enumerate(children):
            if i % 20 == 0:
                progress.update(0.05 + 0.6 * i / n)
            for f in self.blocks([el], avail):
                if isinstance(f, tuple) and f[0] == "__section__":
                    sect_i += 1
                    if sect_i < len(setups):
                        st = setups[sect_i]
                        avail = st["w"] - st["m"]["left"] - st["m"]["right"]
                        typ = wval(f[1].find(q("w:type")), default="nextPage")
                        story.append(NextPageTemplate(f"s{sect_i}"))
                        if typ != "continuous":
                            story.append(PageBreak())
                else:
                    story.append(f)
        if not story:
            story.append(Spacer(1, 1))

        uses_numpages = False
        hf: dict = {}
        for si, st in enumerate(setups):
            aw = st["w"] - st["m"]["left"] - st["m"]["right"]
            for (kind, typ), rid in st["refs"].items():
                flows = self.hf_flowables(rid, aw)
                hf[(si, kind, typ)] = flows
                uses_numpages |= any("§§NUMPAGES§§" in (getattr(f, "text", "") + "".join(t for t, _, _ in getattr(f, "items", []))) for f in flows)

        def make_on_page(si: int, total: list[int]):
            st = setups[si]

            def on_page(canv, doc):
                page_in_sect = getattr(doc, "_sect_page", {}).get(si, 0) + 1
                doc._sect_page = {**getattr(doc, "_sect_page", {}), si: page_in_sect}
                typ = "first" if st["title_pg"] and page_in_sect == 1 else ("even" if canv.getPageNumber() % 2 == 0 and (si, "headerReference", "even") in hf else "default")
                aw = st["w"] - st["m"]["left"] - st["m"]["right"]
                for kind in ("headerReference", "footerReference"):
                    flows = hf.get((si, kind, typ)) if typ != "default" else hf.get((si, kind, "default"))
                    if typ == "first" and flows is None:
                        flows = []
                    if not flows:
                        continue
                    flows = [self._page_fields(f, canv.getPageNumber(), total[0]) for f in flows]
                    hh = sum(f.wrap(aw, st["h"])[1] for f in flows)
                    if kind == "headerReference":
                        y = st["h"] - st["m"]["header"] - hh
                    else:
                        y = st["m"]["footer"]
                    fr = Frame(st["m"]["left"], y, aw, hh + 4, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
                    fr.addFromList(flows, canv)
            return on_page

        def build(target, total: list[int]):
            doc = BaseDocTemplate(target, pagesize=(setups[0]["w"], setups[0]["h"]), title=self.doc.core_properties.title or "",
                                  author=self.doc.core_properties.author or "")
            templates = []
            for si, st in enumerate(setups):
                m = st["m"]
                frame = Frame(m["left"], m["bottom"], st["w"] - m["left"] - m["right"], st["h"] - m["top"] - m["bottom"],
                              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id=f"f{si}")
                templates.append(PageTemplate(id=f"s{si}", frames=[frame], pagesize=(st["w"], st["h"]), onPage=make_on_page(si, total)))
            doc.addPageTemplates(templates)
            doc.build(copy.deepcopy(story) if uses_numpages else story)
            return doc

        total = [0]
        if uses_numpages:
            buf = io.BytesIO()
            build(buf, total)
            from pypdf import PdfReader
            buf.seek(0)
            total[0] = len(PdfReader(buf).pages)
        progress.update(0.75)
        build(str(out), total)
        return out

    @staticmethod
    def _page_fields(f, page: int, total: int):
        sub = lambda t: t.replace("§§PAGE§§", str(page)).replace("§§NUMPAGES§§", str(total or ""))
        if isinstance(f, Paragraph) and "§§" in f.text:
            return Paragraph(sub(f.text), f.style, bulletText=getattr(f, "bulletText", None))
        if isinstance(f, TabLine):
            return TabLine([(sub(t), k, x) for t, k, x in f.items], f.style, f.indent)
        return f


def docx_to_pdf(src: Path, out: Path) -> Path:
    r = DocxRenderer(src)
    try:
        return r.render(out)
    finally:
        import shutil
        shutil.rmtree(r.tmp, ignore_errors=True)
