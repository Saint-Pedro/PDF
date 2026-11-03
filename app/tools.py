"""Declarative tool registry. Each tool describes its options and the
frontend builds the form automatically. To add a tool, add an entry here.
User-facing texts are bilingual: L("English", "Français")."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import convert as cv
from . import engines
from . import pdfops as ops
from . import progress


def L(en: str, fr: str) -> dict:
    return {"en": en, "fr": fr}


CATEGORIES = [
    {"id": "organize", "label": L("Organize", "Organiser")},
    {"id": "optimize", "label": L("Optimize", "Optimiser")},
    {"id": "to_pdf", "label": L("Convert to PDF", "Convertir en PDF")},
    {"id": "from_pdf", "label": L("Convert from PDF", "Convertir depuis PDF")},
    {"id": "edit", "label": L("Edit", "Modifier")},
    {"id": "security", "label": L("Security", "Sécurité")},
]

RANGE_HINT = L("e.g. 1-3, 5, 8-", "Ex. : 1-3, 5, 8-")
PAGES_ALL = L("Pages (empty = all)", "Pages (vide = toutes)")


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


def split_handler(files, o, wd):
    outs = []
    for f in progress.each(files):
        outs += ops.split(f, wd, o)
    return outs


TOOLS: list[dict] = [
    # ---------------------------------------------------------- Organize
    dict(id="merge", cat="organize", icon="merge", color="#e5322d",
         title=L("Merge PDF", "Fusionner PDF"), desc=L("Combine several PDFs in the order you want.", "Combinez plusieurs PDF dans l'ordre de votre choix."),
         accept=["pdf"], multiple=True, min_files=2, mode="files",
         options=[opt("bookmarks", "checkbox", L("Add a bookmark per file", "Créer un signet par fichier"), default=False)],
         handler=lambda files, o, wd: ops.merge(files, wd / "merged.pdf", o)),
    dict(id="split", cat="organize", icon="split", color="#e5322d",
         title=L("Split PDF", "Diviser PDF"), desc=L("Split a PDF by ranges, every N pages or page by page.", "Séparez un PDF par plages, toutes les N pages ou page par page."),
         accept=["pdf"], multiple=False, mode="files",
         options=[opt("mode", "select", L("Mode", "Mode"), default="ranges", choices=[
             ["ranges", L("By ranges", "Par plages")], ["every", L("Every N pages", "Toutes les N pages")], ["each", L("Every page", "Chaque page")]]),
             opt("ranges", "text", L("Ranges", "Plages"), default="1-2", hint=RANGE_HINT, show_if={"mode": "ranges"}),
             opt("merge_output", "checkbox", L("Merge ranges into one PDF", "Fusionner les plages en un seul PDF"), show_if={"mode": "ranges"}),
             opt("every", "number", L("Number of pages", "Nombre de pages"), default=1, min=1, show_if={"mode": "every"})],
         handler=split_handler),
    dict(id="organize", cat="organize", icon="grid", color="#e5322d",
         title=L("Organize PDF", "Organiser PDF"), desc=L("Reorder, rotate, delete or add pages.", "Réordonnez, faites pivoter, supprimez ou ajoutez des pages."),
         accept=["pdf"], multiple=False, mode="pages",
         options=[], handler=single(ops.organize)),
    dict(id="remove", cat="organize", icon="trash", color="#e5322d",
         title=L("Remove pages", "Supprimer des pages"), desc=L("Delete the pages you don't need.", "Retirez les pages inutiles de votre PDF."),
         accept=["pdf"], multiple=False, mode="pages", page_action="remove",
         options=[], handler=single(ops.organize)),
    dict(id="extract", cat="organize", icon="extract", color="#e5322d",
         title=L("Extract pages", "Extraire des pages"), desc=L("Create a new PDF with only the pages you want.", "Créez un nouveau PDF avec seulement les pages voulues."),
         accept=["pdf"], multiple=False, mode="pages", page_action="extract",
         options=[], handler=single(ops.organize)),
    dict(id="rotate", cat="organize", icon="rotate", color="#a855f7",
         title=L("Rotate PDF", "Faire pivoter PDF"), desc=L("Rotate all pages or just some of them.", "Tournez toutes les pages ou seulement certaines."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("angle", "select", L("Rotation", "Rotation"), default="90", choices=[
             ["90", L("90° right", "90° à droite")], ["180", "180°"], ["270", L("90° left", "90° à gauche")]]),
             opt("pages", "text", PAGES_ALL, default="", hint=RANGE_HINT)],
         handler=single(ops.rotate)),
    dict(id="nup", cat="organize", icon="layout", color="#a855f7",
         title=L("Pages per sheet", "Plusieurs pages par feuille"), desc=L("Print 2, 4, 6 or 9 pages on a single sheet.", "Imprimez 2, 4, 6 ou 9 pages sur une seule feuille."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("per_sheet", "select", L("Pages per sheet", "Pages par feuille"), default="2",
                      choices=[["2", "2"], ["4", "4"], ["6", "6"], ["9", "9"]])],
         handler=single(ops.nup)),

    # ---------------------------------------------------------- Optimize
    dict(id="compress", cat="optimize", icon="compress", color="#22a06b",
         title=L("Compress PDF", "Compresser PDF"), desc=L("Reduce file size while keeping good quality.", "Réduisez la taille tout en gardant une bonne qualité."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("level", "cards", L("Compression level", "Niveau de compression"), default="recommended", choices=[
             ["extreme", L("Extreme", "Extrême"), L("Smallest size, lower quality", "Taille minimale, qualité réduite")],
             ["recommended", L("Recommended", "Recommandée"), L("Good balance of size and quality", "Bon équilibre taille / qualité")],
             ["low", L("Low", "Faible"), L("High quality, light compression", "Haute qualité, compression légère")]])],
         handler=single(ops.compress)),
    dict(id="repair", cat="optimize", icon="wrench", color="#22a06b",
         title=L("Repair PDF", "Réparer PDF"), desc=L("Try to recover a damaged PDF.", "Tentez de récupérer un PDF endommagé."),
         accept=["pdf"], multiple=True, mode="files", options=[], handler=single(ops.repair)),
    dict(id="ocr", cat="optimize", icon="scan", color="#22a06b", requires="ocrmypdf",
         title=L("OCR PDF", "OCR PDF"), desc=L("Make a scanned PDF searchable and selectable.", "Rendez un PDF scanné recherchable et copiable."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("lang", "select", L("Document language", "Langue du document"), default="eng+fra", choices=[
             ["eng+fra", L("English + French", "Anglais + français")], ["eng", L("English", "Anglais")], ["fra", L("French", "Français")],
             ["deu", L("German", "Allemand")], ["spa", L("Spanish", "Espagnol")], ["ita", L("Italian", "Italien")]])],
         handler=single(ops.ocr)),
    dict(id="pdfa", cat="optimize", icon="archive", color="#22a06b", requires="ghostscript",
         title=L("PDF to PDF/A", "PDF en PDF/A"), desc=L("Long-term archiving format (ISO 19005).", "Format d'archivage longue durée (ISO 19005)."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("level", "select", L("Level", "Niveau"), default="2", choices=[["1", "PDF/A-1b"], ["2", "PDF/A-2b"], ["3", "PDF/A-3b"]])],
         handler=single(ops.pdfa)),
    dict(id="grayscale", cat="optimize", icon="contrast", color="#22a06b",
         title=L("Grayscale PDF", "Niveaux de gris"), desc=L("Convert a color PDF to black and white.", "Convertissez un PDF couleur en noir et blanc."),
         accept=["pdf"], multiple=True, mode="files", options=[], handler=single(ops.grayscale)),

    # ---------------------------------------------------------- Convert to PDF
    dict(id="any_to_pdf", cat="to_pdf", icon="magic", color="#f59e0b",
         title=L("Anything to PDF", "Tout en PDF"), desc=L("Images, Office, text, Markdown, HTML… one tool for all.", "Images, Office, texte, Markdown, HTML… un seul outil."),
         accept=sorted(cv.ANY_TO_PDF | {"pdf"}), multiple=True, mode="files",
         options=[opt("merge", "checkbox", L("Merge into a single PDF", "Fusionner en un seul PDF"), default=False)],
         handler=to_pdf_each),
    dict(id="img_to_pdf", cat="to_pdf", icon="image", color="#f5b400",
         title=L("Image to PDF", "Image en PDF"), desc=L("JPG, PNG, WEBP, HEIC, TIFF… to PDF, with page layout.", "JPG, PNG, WEBP, HEIC, TIFF… en PDF, avec mise en page."),
         accept=sorted(cv.IMAGE_EXT), multiple=True, mode="files",
         options=[opt("page_size", "select", L("Page size", "Format de page"), default="a4", choices=[
             ["fit", L("Image size", "Taille de l'image")], ["a4", "A4"], ["letter", "US Letter"], ["a3", "A3"], ["a5", "A5"]]),
             opt("orientation", "select", L("Orientation", "Orientation"), default="auto", choices=[
                 ["auto", L("Automatic", "Automatique")], ["portrait", "Portrait"], ["landscape", L("Landscape", "Paysage")]]),
             opt("margin", "select", L("Margins", "Marges"), default="none", choices=[["none", L("None", "Aucune")], ["small", L("Small", "Petites")], ["big", L("Large", "Grandes")]]),
             opt("merge", "checkbox", L("Merge all images", "Fusionner toutes les images"), default=True)],
         handler=images_handler),
    dict(id="word_to_pdf", cat="to_pdf", icon="word", color="#2b6cde",
         title=L("Word to PDF", "Word en PDF"), desc=L("DOCX, DOC, ODT, RTF to PDF.", "DOCX, DOC, ODT, RTF en PDF."),
         accept=sorted(cv.WORD_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="excel_to_pdf", cat="to_pdf", icon="excel", color="#1f9d55",
         title=L("Excel to PDF", "Excel en PDF"), desc=L("XLSX, XLS, ODS, CSV to PDF.", "XLSX, XLS, ODS, CSV en PDF."),
         accept=sorted(cv.EXCEL_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="ppt_to_pdf", cat="to_pdf", icon="ppt", color="#e8590c",
         title=L("PowerPoint to PDF", "PowerPoint en PDF"), desc=L("PPTX, PPT, ODP to PDF.", "PPTX, PPT, ODP en PDF."), requires="libreoffice",
         accept=sorted(cv.PPT_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="html_to_pdf", cat="to_pdf", icon="code", color="#f59e0b",
         title=L("HTML / Markdown to PDF", "HTML / Markdown en PDF"), desc=L("Saved web pages, Markdown or plain text.", "Pages web enregistrées, Markdown ou texte."),
         accept=sorted(cv.HTML_EXT | cv.TEXT_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),

    # ---------------------------------------------------------- Convert from PDF
    dict(id="pdf_to_img", cat="from_pdf", icon="image", color="#f5b400",
         title=L("PDF to image", "PDF en image"), desc=L("Each page to JPG/PNG, or extract embedded images.", "Chaque page en JPG/PNG, ou extraction des images."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("mode", "select", L("Mode", "Mode"), default="pages", choices=[["pages", L("Page → image", "Page → image")], ["extract", L("Extract images", "Extraire les images")]]),
                  opt("format", "select", L("Format", "Format"), default="jpg", choices=[["jpg", "JPG"], ["png", "PNG"], ["webp", "WEBP"]]),
                  opt("dpi", "select", L("Resolution", "Résolution"), default="150", choices=[["72", L("72 dpi (screen)", "72 dpi (écran)")], ["150", "150 dpi"], ["300", L("300 dpi (print)", "300 dpi (impression)")]], show_if={"mode": "pages"})],
         handler=from_pdf(cv.pdf_to_images)),
    dict(id="pdf_to_word", cat="from_pdf", icon="word", color="#2b6cde",
         title=L("PDF to Word", "PDF en Word"), desc=L("Convert to an editable DOCX.", "Convertissez en DOCX éditable."),
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_docx)),
    dict(id="pdf_to_ppt", cat="from_pdf", icon="ppt", color="#e8590c",
         title=L("PDF to PowerPoint", "PDF en PowerPoint"), desc=L("One slide per page (text in speaker notes).", "Une diapositive par page (texte en notes)."),
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_pptx)),
    dict(id="pdf_to_excel", cat="from_pdf", icon="excel", color="#1f9d55",
         title=L("PDF to Excel", "PDF en Excel"), desc=L("Extract tables to XLSX.", "Extrait les tableaux vers XLSX."),
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_xlsx)),
    dict(id="pdf_to_txt", cat="from_pdf", icon="text", color="#64748b",
         title=L("PDF to text", "PDF en texte"), desc=L("Get all the raw text.", "Récupérez tout le texte brut."),
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_text)),

    # ---------------------------------------------------------- Edit
    dict(id="edit", cat="edit", icon="pen", color="#d946ef",
         title=L("Edit PDF", "Modifier PDF"), desc=L("Add text, images, shapes or hide an area.", "Ajoutez du texte, des images, des formes ou masquez une zone."),
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["text", "image", "rect", "signature"],
         options=[], handler=single(ops.edit)),
    dict(id="sign", cat="edit", icon="signature", color="#d946ef",
         title=L("Sign PDF", "Signer PDF"), desc=L("Draw, type or upload your signature.", "Dessinez, tapez ou importez votre signature."),
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["signature", "text"],
         options=[], handler=single(ops.edit)),
    dict(id="watermark", cat="edit", icon="droplet", color="#d946ef",
         title=L("Watermark", "Filigrane"), desc=L("Stamp a translucent text or image over your pages.", "Texte ou image en transparence sur vos pages."),
         accept=["pdf"], multiple=True, mode="files", extra_file={"name": "image", "label": L("Watermark image (optional)", "Image de filigrane (facultatif)"), "accept": ["png", "jpg", "jpeg", "webp"]},
         options=[opt("text", "text", L("Text", "Texte"), default="CONFIDENTIAL"),
                  opt("color", "color", L("Color", "Couleur"), default="#e5322d"),
                  opt("size", "range", L("Size", "Taille"), default=60, min=12, max=160),
                  opt("opacity", "range", L("Opacity (%)", "Opacité (%)"), default=25, min=5, max=100),
                  opt("angle", "range", L("Angle", "Angle"), default=45, min=-90, max=90),
                  opt("layout", "select", L("Layout", "Disposition"), default="center", choices=[["center", L("Centered", "Centré")], ["mosaic", L("Mosaic", "Mosaïque")]]),
                  opt("pages", "text", PAGES_ALL, default="", hint=RANGE_HINT)],
         handler=watermark_handler),
    dict(id="page_numbers", cat="edit", icon="hash", color="#d946ef",
         title=L("Page numbers", "Numéroter les pages"), desc=L("Add custom page numbers.", "Ajoutez des numéros de page personnalisés."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("position", "position", L("Position", "Position"), default="bottom-center"),
                  opt("format", "select", L("Format", "Format"), default="{n}", choices=[
                      ["{n}", "1"], ["Page {n}", "Page 1"], ["{n} / {total}", "1 / 10"], ["Page {n} of {total}", "Page 1 of 10"], ["Page {n} sur {total}", "Page 1 sur 10"], ["- {n} -", "- 1 -"]]),
                  opt("start", "number", L("First number", "Premier numéro"), default=1, min=0),
                  opt("size", "range", L("Size", "Taille"), default=11, min=6, max=36),
                  opt("color", "color", L("Color", "Couleur"), default="#333333"),
                  opt("skip_first", "checkbox", L("Don't number the first page", "Ne pas numéroter la première page"))],
         handler=single(ops.page_numbers)),
    dict(id="crop", cat="edit", icon="crop", color="#d946ef",
         title=L("Crop PDF", "Rogner PDF"), desc=L("Trim margins on every page (in mm).", "Retirez des marges sur toutes les pages (en mm)."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("top", "number", L("Top (mm)", "Haut (mm)"), default=10, min=0), opt("bottom", "number", L("Bottom (mm)", "Bas (mm)"), default=10, min=0),
                  opt("left", "number", L("Left (mm)", "Gauche (mm)"), default=10, min=0), opt("right", "number", L("Right (mm)", "Droite (mm)"), default=10, min=0)],
         handler=single(ops.crop)),
    dict(id="metadata", cat="edit", icon="tag", color="#d946ef",
         title=L("Metadata", "Métadonnées"), desc=L("Edit title, author, subject and keywords.", "Modifiez titre, auteur, sujet et mots-clés."),
         accept=["pdf"], multiple=False, mode="files",
         options=[opt("title", "text", L("Title", "Titre")), opt("author", "text", L("Author", "Auteur")),
                  opt("subject", "text", L("Subject", "Sujet")), opt("keywords", "text", L("Keywords", "Mots-clés"))],
         handler=single(ops.metadata)),
    dict(id="flatten", cat="edit", icon="layers", color="#d946ef",
         title=L("Flatten PDF", "Aplatir PDF"), desc=L("Freeze forms and annotations (pages become images).", "Fige formulaires et annotations (pages en image)."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("dpi", "select", L("Quality", "Qualité"), default="150", choices=[["100", L("Light", "Légère")], ["150", "Standard"], ["220", L("High", "Haute")]])],
         handler=single(ops.flatten)),

    # ---------------------------------------------------------- Security
    dict(id="protect", cat="security", icon="lock", color="#334155",
         title=L("Protect PDF", "Protéger PDF"), desc=L("AES-256 encryption and usage restrictions.", "Chiffrement AES-256 et restrictions d'usage."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("password", "password", L("Password", "Mot de passe"), required=True),
                  opt("confirm", "password", L("Confirm password", "Confirmer le mot de passe"), required=True),
                  opt("no_print", "checkbox", L("Prevent printing", "Interdire l'impression")),
                  opt("no_copy", "checkbox", L("Prevent copying text", "Interdire la copie du texte")),
                  opt("no_edit", "checkbox", L("Prevent editing", "Interdire la modification"))],
         handler=single(ops.protect)),
    dict(id="unlock", cat="security", icon="unlock", color="#334155",
         title=L("Unlock PDF", "Déverrouiller PDF"), desc=L("Remove the password (if you know it).", "Retirez le mot de passe (si vous le connaissez)."),
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("password", "password", L("Current password", "Mot de passe actuel"))],
         handler=single(ops.unlock)),
    dict(id="redact", cat="security", icon="redact", color="#334155",
         title=L("Redact PDF", "Caviarder PDF"), desc=L("Permanently remove sensitive words or areas.", "Supprimez définitivement des mots ou des zones sensibles."),
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["redact"],
         options=[opt("terms", "textarea", L("Words or phrases to redact", "Mots ou expressions à caviarder"), hint=L("One per line (names, IBAN, emails…)", "Un par ligne (noms, IBAN, e-mails…)")),
                  opt("match_case", "checkbox", L("Match case", "Respecter la casse"))],
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
            d["missing"] = {"libreoffice": "LibreOffice", "ghostscript": "Ghostscript", "ocrmypdf": "OCRmyPDF + Tesseract"}.get(req, req)
        out.append(d)
    return out
