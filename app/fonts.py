"""Font lookup shared by the native renderers: uses the real Office fonts when
installed (Calibri, Arial…), metric-compatible free fonts otherwise (Carlito,
Liberation…), and the PDF base-14 fonts as a last resort."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_FILES = {
    "calibri": [("calibri.ttf", "carlito-regular.ttf"), ("calibrib.ttf", "carlito-bold.ttf"),
                ("calibrii.ttf", "carlito-italic.ttf"), ("calibriz.ttf", "carlito-bolditalic.ttf")],
    "arial": [("arial.ttf", "liberationsans-regular.ttf"), ("arialbd.ttf", "arial bold.ttf", "liberationsans-bold.ttf"),
              ("ariali.ttf", "arial italic.ttf", "liberationsans-italic.ttf"), ("arialbi.ttf", "arial bold italic.ttf", "liberationsans-bolditalic.ttf")],
    "times new roman": [("times.ttf", "times new roman.ttf", "liberationserif-regular.ttf"), ("timesbd.ttf", "times new roman bold.ttf", "liberationserif-bold.ttf"),
                        ("timesi.ttf", "times new roman italic.ttf", "liberationserif-italic.ttf"), ("timesbi.ttf", "times new roman bold italic.ttf", "liberationserif-bolditalic.ttf")],
    "courier new": [("cour.ttf", "courier new.ttf", "liberationmono-regular.ttf"), ("courbd.ttf", "courier new bold.ttf", "liberationmono-bold.ttf"),
                    ("couri.ttf", "courier new italic.ttf", "liberationmono-italic.ttf"), ("courbi.ttf", "courier new bold italic.ttf", "liberationmono-bolditalic.ttf")],
    "georgia": [("georgia.ttf", "liberationserif-regular.ttf"), ("georgiab.ttf", "liberationserif-bold.ttf"), ("georgiai.ttf", "liberationserif-italic.ttf"), ("georgiaz.ttf", "liberationserif-bolditalic.ttf")],
    "garamond": [("gara.ttf", "liberationserif-regular.ttf"), ("garabd.ttf", "liberationserif-bold.ttf"), ("garait.ttf", "liberationserif-italic.ttf"), ("garabd.ttf", "liberationserif-bolditalic.ttf")],
    "aptos": [("aptos.ttf", "carlito-regular.ttf"), ("aptos-bold.ttf", "carlito-bold.ttf"), ("aptos-italic.ttf", "carlito-italic.ttf"), ("aptos-bold-italic.ttf", "carlito-bolditalic.ttf")],
    "helvetica": [("helvetica.ttf", "liberationsans-regular.ttf", "arial.ttf"), ("helvetica-bold.ttf", "liberationsans-bold.ttf", "arialbd.ttf"), ("helvetica-oblique.ttf", "liberationsans-italic.ttf", "ariali.ttf"), ("helvetica-boldoblique.ttf", "liberationsans-bolditalic.ttf", "arialbi.ttf")],
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
