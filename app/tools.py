"""Registre déclaratif des outils. Chaque outil décrit ses options : le
frontend génère le formulaire tout seul. Pour ajouter un outil, ajoutez une
entrée ici."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import convert as cv
from . import engines
from . import pdfops as ops

CATEGORIES = [
    {"id": "organize", "label": "Organiser"},
    {"id": "optimize", "label": "Optimiser"},
    {"id": "to_pdf", "label": "Convertir en PDF"},
    {"id": "from_pdf", "label": "Convertir depuis PDF"},
    {"id": "edit", "label": "Modifier"},
    {"id": "security", "label": "Sécurité"},
]

RANGE_HINT = "Ex. : 1-3, 5, 8-"


def opt(name, type_, label, **kw):
    return {"name": name, "type": type_, "label": label, **kw}


# Gestionnaires : (fichiers, options, dossier de travail) -> Path | list[Path]
Handler = Callable[[list[Path], dict, Path], "Path | list[Path]"]


def single(fn) -> Handler:
    """Applique une opération fichier→fichier à chaque PDF."""
    def h(files, o, wd):
        return [fn(f, wd / f"{f.stem}_{o['_tool']}.pdf", o) for f in files]
    return h


def to_pdf_each(files, o, wd):
    if o.get("merge") and len(files) > 1:
        pdfs = [cv.to_pdf(f, wd, o) for f in files]
        return ops.merge(pdfs, wd / "fusion.pdf", {})
    return [cv.to_pdf(f, wd, o) for f in files]


def images_handler(files, o, wd):
    if o.get("merge", True) and len(files) > 1:
        return cv.images_to_pdf(files, wd / "images.pdf", o)
    return [cv.images_to_pdf([f], wd / f"{f.stem}.pdf", o) for f in files]


def from_pdf(fn):
    def h(files, o, wd):
        outs = []
        for f in files:
            r = fn(f, wd, o)
            outs += r if isinstance(r, list) else [r]
        return outs
    return h


def watermark_handler(files, o, wd):
    img = o.get("_image")
    return [ops.watermark(f, wd / f"{f.stem}_filigrane.pdf", o, image=img) for f in files]


def split_handler(files, o, wd):
    outs = []
    for f in files:
        outs += ops.split(f, wd, o)
    return outs


TOOLS: list[dict] = [
    # ---------------------------------------------------------- Organiser
    dict(id="merge", cat="organize", icon="merge", color="#e5322d",
         title="Fusionner PDF", desc="Combinez plusieurs PDF dans l'ordre de votre choix.",
         accept=["pdf"], multiple=True, min_files=2, mode="files",
         options=[opt("bookmarks", "checkbox", "Créer un signet par fichier", default=False)],
         handler=lambda files, o, wd: ops.merge(files, wd / "fusion.pdf", o)),
    dict(id="split", cat="organize", icon="split", color="#e5322d",
         title="Diviser PDF", desc="Séparez un PDF par plages, toutes les N pages ou page par page.",
         accept=["pdf"], multiple=False, mode="files",
         options=[opt("mode", "select", "Mode", default="ranges", choices=[
             ["ranges", "Par plages"], ["every", "Toutes les N pages"], ["each", "Chaque page"]]),
             opt("ranges", "text", "Plages", default="1-2", hint=RANGE_HINT, show_if={"mode": "ranges"}),
             opt("merge_output", "checkbox", "Fusionner les plages en un seul PDF", show_if={"mode": "ranges"}),
             opt("every", "number", "Nombre de pages", default=1, min=1, show_if={"mode": "every"})],
         handler=split_handler),
    dict(id="organize", cat="organize", icon="grid", color="#e5322d",
         title="Organiser PDF", desc="Réordonnez, faites pivoter, supprimez ou ajoutez des pages.",
         accept=["pdf"], multiple=False, mode="pages",
         options=[], handler=single(ops.organize)),
    dict(id="remove", cat="organize", icon="trash", color="#e5322d",
         title="Supprimer des pages", desc="Retirez les pages inutiles de votre PDF.",
         accept=["pdf"], multiple=False, mode="pages", page_action="remove",
         options=[], handler=single(ops.organize)),
    dict(id="extract", cat="organize", icon="extract", color="#e5322d",
         title="Extraire des pages", desc="Créez un nouveau PDF avec seulement les pages voulues.",
         accept=["pdf"], multiple=False, mode="pages", page_action="extract",
         options=[], handler=single(ops.organize)),
    dict(id="rotate", cat="organize", icon="rotate", color="#a855f7",
         title="Faire pivoter PDF", desc="Tournez toutes les pages ou seulement certaines.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("angle", "select", "Rotation", default="90", choices=[
             ["90", "90° à droite"], ["180", "180°"], ["270", "90° à gauche"]]),
             opt("pages", "text", "Pages (vide = toutes)", default="", hint=RANGE_HINT)],
         handler=single(ops.rotate)),
    dict(id="nup", cat="organize", icon="layout", color="#a855f7",
         title="Plusieurs pages par feuille", desc="Imprimez 2, 4, 6 ou 9 pages sur une seule feuille.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("per_sheet", "select", "Pages par feuille", default="2",
                      choices=[["2", "2"], ["4", "4"], ["6", "6"], ["9", "9"]])],
         handler=single(ops.nup)),

    # ---------------------------------------------------------- Optimiser
    dict(id="compress", cat="optimize", icon="compress", color="#22a06b",
         title="Compresser PDF", desc="Réduisez la taille tout en gardant une bonne qualité.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("level", "cards", "Niveau de compression", default="recommended", choices=[
             ["extreme", "Extrême", "Taille minimale, qualité réduite"],
             ["recommended", "Recommandée", "Bon équilibre taille / qualité"],
             ["low", "Faible", "Haute qualité, compression légère"]])],
         handler=single(ops.compress)),
    dict(id="repair", cat="optimize", icon="wrench", color="#22a06b",
         title="Réparer PDF", desc="Tentez de récupérer un PDF endommagé.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=single(ops.repair)),
    dict(id="ocr", cat="optimize", icon="scan", color="#22a06b", requires="ocrmypdf",
         title="OCR PDF", desc="Rendez un PDF scanné recherchable et copiable.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("lang", "select", "Langue du document", default="fra+eng", choices=[
             ["fra+eng", "Français + anglais"], ["fra", "Français"], ["eng", "Anglais"],
             ["deu", "Allemand"], ["spa", "Espagnol"], ["ita", "Italien"]])],
         handler=single(ops.ocr)),
    dict(id="pdfa", cat="optimize", icon="archive", color="#22a06b", requires="ghostscript",
         title="PDF en PDF/A", desc="Format d'archivage longue durée (ISO 19005).",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("level", "select", "Niveau", default="2", choices=[["1", "PDF/A-1b"], ["2", "PDF/A-2b"], ["3", "PDF/A-3b"]])],
         handler=single(ops.pdfa)),
    dict(id="grayscale", cat="optimize", icon="contrast", color="#22a06b",
         title="Niveaux de gris", desc="Convertissez un PDF couleur en noir et blanc.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=single(ops.grayscale)),

    # ---------------------------------------------------------- Convertir en PDF
    dict(id="any_to_pdf", cat="to_pdf", icon="magic", color="#f59e0b",
         title="Tout en PDF", desc="Images, Office, texte, Markdown, HTML… un seul outil.",
         accept=sorted(cv.ANY_TO_PDF | {"pdf"}), multiple=True, mode="files",
         options=[opt("merge", "checkbox", "Fusionner en un seul PDF", default=False)],
         handler=to_pdf_each),
    dict(id="img_to_pdf", cat="to_pdf", icon="image", color="#f5b400",
         title="Image en PDF", desc="JPG, PNG, WEBP, HEIC, TIFF… en PDF, avec mise en page.",
         accept=sorted(cv.IMAGE_EXT), multiple=True, mode="files",
         options=[opt("page_size", "select", "Format de page", default="a4", choices=[
             ["fit", "Taille de l'image"], ["a4", "A4"], ["letter", "US Letter"], ["a3", "A3"], ["a5", "A5"]]),
             opt("orientation", "select", "Orientation", default="auto", choices=[
                 ["auto", "Automatique"], ["portrait", "Portrait"], ["landscape", "Paysage"]]),
             opt("margin", "select", "Marges", default="none", choices=[["none", "Aucune"], ["small", "Petites"], ["big", "Grandes"]]),
             opt("merge", "checkbox", "Fusionner toutes les images", default=True)],
         handler=images_handler),
    dict(id="word_to_pdf", cat="to_pdf", icon="word", color="#2b6cde",
         title="Word en PDF", desc="DOCX, DOC, ODT, RTF en PDF.",
         accept=sorted(cv.WORD_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="excel_to_pdf", cat="to_pdf", icon="excel", color="#1f9d55",
         title="Excel en PDF", desc="XLSX, XLS, ODS, CSV en PDF.",
         accept=sorted(cv.EXCEL_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="ppt_to_pdf", cat="to_pdf", icon="ppt", color="#e8590c",
         title="PowerPoint en PDF", desc="PPTX, PPT, ODP en PDF.", requires="libreoffice",
         accept=sorted(cv.PPT_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),
    dict(id="html_to_pdf", cat="to_pdf", icon="code", color="#f59e0b",
         title="HTML / Markdown en PDF", desc="Pages web enregistrées, Markdown ou texte.",
         accept=sorted(cv.HTML_EXT | cv.TEXT_EXT), multiple=True, mode="files", options=[], handler=to_pdf_each),

    # ---------------------------------------------------------- Convertir depuis PDF
    dict(id="pdf_to_img", cat="from_pdf", icon="image", color="#f5b400",
         title="PDF en image", desc="Chaque page en JPG/PNG, ou extraction des images.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("mode", "select", "Mode", default="pages", choices=[["pages", "Page → image"], ["extract", "Extraire les images"]]),
                  opt("format", "select", "Format", default="jpg", choices=[["jpg", "JPG"], ["png", "PNG"], ["webp", "WEBP"]]),
                  opt("dpi", "select", "Résolution", default="150", choices=[["72", "72 dpi (écran)"], ["150", "150 dpi"], ["300", "300 dpi (impression)"]], show_if={"mode": "pages"})],
         handler=from_pdf(cv.pdf_to_images)),
    dict(id="pdf_to_word", cat="from_pdf", icon="word", color="#2b6cde",
         title="PDF en Word", desc="Convertissez en DOCX éditable.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_docx)),
    dict(id="pdf_to_ppt", cat="from_pdf", icon="ppt", color="#e8590c",
         title="PDF en PowerPoint", desc="Une diapositive par page (texte en notes).",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_pptx)),
    dict(id="pdf_to_excel", cat="from_pdf", icon="excel", color="#1f9d55",
         title="PDF en Excel", desc="Extrait les tableaux vers XLSX.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_xlsx)),
    dict(id="pdf_to_txt", cat="from_pdf", icon="text", color="#64748b",
         title="PDF en texte", desc="Récupérez tout le texte brut.",
         accept=["pdf"], multiple=True, mode="files", options=[], handler=from_pdf(cv.pdf_to_text)),

    # ---------------------------------------------------------- Modifier
    dict(id="edit", cat="edit", icon="pen", color="#d946ef",
         title="Modifier PDF", desc="Ajoutez du texte, des images, des formes ou masquez une zone.",
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["text", "image", "rect", "signature"],
         options=[], handler=single(ops.edit)),
    dict(id="sign", cat="edit", icon="signature", color="#d946ef",
         title="Signer PDF", desc="Dessinez, tapez ou importez votre signature.",
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["signature", "text"],
         options=[], handler=single(ops.edit)),
    dict(id="watermark", cat="edit", icon="droplet", color="#d946ef",
         title="Filigrane", desc="Texte ou image en transparence sur vos pages.",
         accept=["pdf"], multiple=True, mode="files", extra_file={"name": "image", "label": "Image de filigrane (facultatif)", "accept": ["png", "jpg", "jpeg", "webp"]},
         options=[opt("text", "text", "Texte", default="CONFIDENTIEL"),
                  opt("color", "color", "Couleur", default="#e5322d"),
                  opt("size", "range", "Taille", default=60, min=12, max=160),
                  opt("opacity", "range", "Opacité (%)", default=25, min=5, max=100),
                  opt("angle", "range", "Angle", default=45, min=-90, max=90),
                  opt("layout", "select", "Disposition", default="center", choices=[["center", "Centré"], ["mosaic", "Mosaïque"]]),
                  opt("pages", "text", "Pages (vide = toutes)", default="", hint=RANGE_HINT)],
         handler=watermark_handler),
    dict(id="page_numbers", cat="edit", icon="hash", color="#d946ef",
         title="Numéroter les pages", desc="Ajoutez des numéros de page personnalisés.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("position", "position", "Position", default="bottom-center"),
                  opt("format", "select", "Format", default="{n}", choices=[
                      ["{n}", "1"], ["Page {n}", "Page 1"], ["{n} / {total}", "1 / 10"], ["Page {n} sur {total}", "Page 1 sur 10"], ["- {n} -", "- 1 -"]]),
                  opt("start", "number", "Premier numéro", default=1, min=0),
                  opt("size", "range", "Taille", default=11, min=6, max=36),
                  opt("color", "color", "Couleur", default="#333333"),
                  opt("skip_first", "checkbox", "Ne pas numéroter la première page")],
         handler=single(ops.page_numbers)),
    dict(id="crop", cat="edit", icon="crop", color="#d946ef",
         title="Rogner PDF", desc="Retirez des marges sur toutes les pages (en mm).",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("top", "number", "Haut (mm)", default=10, min=0), opt("bottom", "number", "Bas (mm)", default=10, min=0),
                  opt("left", "number", "Gauche (mm)", default=10, min=0), opt("right", "number", "Droite (mm)", default=10, min=0)],
         handler=single(ops.crop)),
    dict(id="metadata", cat="edit", icon="tag", color="#d946ef",
         title="Métadonnées", desc="Modifiez titre, auteur, sujet et mots-clés.",
         accept=["pdf"], multiple=False, mode="files",
         options=[opt("title", "text", "Titre"), opt("author", "text", "Auteur"),
                  opt("subject", "text", "Sujet"), opt("keywords", "text", "Mots-clés")],
         handler=single(ops.metadata)),
    dict(id="flatten", cat="edit", icon="layers", color="#d946ef",
         title="Aplatir PDF", desc="Fige formulaires et annotations (pages en image).",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("dpi", "select", "Qualité", default="150", choices=[["100", "Légère"], ["150", "Standard"], ["220", "Haute"]])],
         handler=single(ops.flatten)),

    # ---------------------------------------------------------- Sécurité
    dict(id="protect", cat="security", icon="lock", color="#334155",
         title="Protéger PDF", desc="Chiffrement AES-256 et restrictions d'usage.",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("password", "password", "Mot de passe", required=True),
                  opt("confirm", "password", "Confirmer le mot de passe", required=True),
                  opt("no_print", "checkbox", "Interdire l'impression"),
                  opt("no_copy", "checkbox", "Interdire la copie du texte"),
                  opt("no_edit", "checkbox", "Interdire la modification")],
         handler=single(ops.protect)),
    dict(id="unlock", cat="security", icon="unlock", color="#334155",
         title="Déverrouiller PDF", desc="Retirez le mot de passe (si vous le connaissez).",
         accept=["pdf"], multiple=True, mode="files",
         options=[opt("password", "password", "Mot de passe actuel")],
         handler=single(ops.unlock)),
    dict(id="redact", cat="security", icon="redact", color="#334155",
         title="Caviarder PDF", desc="Supprimez définitivement des mots ou des zones sensibles.",
         accept=["pdf"], multiple=False, mode="editor", editor_tools=["redact"],
         options=[opt("terms", "textarea", "Mots ou expressions à caviarder", hint="Un par ligne (noms, IBAN, e-mails…)"),
                  opt("match_case", "checkbox", "Respecter la casse")],
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
