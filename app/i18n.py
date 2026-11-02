"""French translations of server messages (English is the default)."""
from __future__ import annotations

import re

FR: list[tuple[str, str]] = [
    (r"Add at least one element to the document\.", "Ajoutez au moins un élément sur le document."),
    (r"No file was produced\.", "Aucun fichier produit."),
    (r"No images found in this PDF\.", "Aucune image trouvée dans ce PDF."),
    (r"No matches found\.", "Aucune occurrence trouvée."),
    (r"No pages specified\.", "Aucune page indiquée."),
    (r"Invalid format\.", "Format invalide."),
    (r"Ghostscript is required for PDF/A conversion\.", "Ghostscript est nécessaire pour la conversion PDF/A."),
    (r"Unable to read this PDF\.", "Impossible de lire ce PDF."),
    (r"You cannot remove every page\.", "Impossible de supprimer toutes les pages."),
    (r"Enter words to redact or draw areas\.", "Indiquez des mots à caviarder ou dessinez des zones."),
    (r"Enter a password\.", "Indiquez un mot de passe."),
    (r"The resulting document would be empty\.", "Le document résultant serait vide."),
    (r"The file is too damaged to be repaired\.", "Le fichier est trop endommagé pour être réparé."),
    (r"Passwords do not match\.", "Les mots de passe ne correspondent pas."),
    (r"LibreOffice produced no file\.", "LibreOffice n'a produit aucun fichier."),
    (r"LibreOffice is not installed\.", "LibreOffice n'est pas installé."),
    (r"Margins are too large for the page\.", "Marges trop grandes pour la page."),
    (r"Admin password required\.", "Mot de passe administrateur requis."),
    (r"Incorrect password\.", "Mot de passe incorrect."),
    (r"OCRmyPDF \(and Tesseract\) must be installed for OCR\.", "OCRmyPDF (et Tesseract) doit être installé pour l'OCR."),
    (r"Invalid options\.", "Options invalides."),
    (r"Unknown tool\.", "Outil inconnu."),
    (r"This tool requires (.+)\.", r"Cet outil nécessite \1."),
    (r"Unexpected error: (.*)", r"Erreur inattendue : \1"),
    (r"File too large \(max (\d+) MB\)\.", r"Fichier trop volumineux (max \1 Mo)."),
    (r"Unsupported format: \.(\w+)", r"Format .\1 non pris en charge."),
    (r"Install LibreOffice to convert \.(\w+) files\.", r"Installez LibreOffice pour convertir les fichiers .\1."),
    (r'Invalid range: "(.*)"', r"Plage invalide : « \1 »"),
    (r'Empty range: "(.*)"', r"Plage vide : « \1 »"),
    (r"(\S+) failed: (.*)", r"\1 a échoué : \2"),
    (r'"(.+)" is not a format accepted by this tool\.', r"« \1 » n'est pas un format accepté par cet outil."),
    (r'"(.+)" is password-protected\.', r"« \1 » est protégé par mot de passe."),
]
_FR = [(re.compile(p, re.S), r) for p, r in FR]


def translate(msg: str, lang: str | None) -> str:
    if not msg or not (lang or "").lower().startswith("fr"):
        return msg
    for rx, rep in _FR:
        if rx.fullmatch(msg):
            return rx.sub(rep, msg)
    return msg
