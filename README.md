# PDF Studio

Boîte à outils PDF façon iLovePDF, 100 % locale, personnalisable (nom, logo, couleurs, polices, style).

## Lancer

- **Linux / macOS** : `./run.sh` puis http://localhost:8000
- **Windows** : double-clic sur `run.bat`
- **Docker** (tous les moteurs inclus) : `docker compose up -d --build`

Python 3.10+ requis. Sans rien d'autre, la plupart des outils fonctionnent.
Moteurs facultatifs, détectés automatiquement :

| Moteur | Apporte |
|---|---|
| LibreOffice | Office → PDF haute fidélité (PowerPoint obligatoire) |
| Ghostscript | Meilleure compression, PDF/A, niveaux de gris vectoriels |
| OCRmyPDF + Tesseract | OCR |

## Personnaliser

Bouton **Personnaliser** (ou `/personnaliser`) : thèmes prêts à l'emploi, logo (couleurs détectées automatiquement),
palette générée depuis une couleur avec contrôle de contraste, polices (système, import WOFF2/TTF, Google Fonts),
style des cartes / icônes / en-tête / bandeau, outils masqués ou mis en avant, CSS libre, export/import du thème.
Stocké dans `data/branding.json`. Définir `ADMIN_PASSWORD` pour protéger cette page.

## Ajouter un outil

Ajouter une entrée dans `app/tools.py` (options déclaratives : le formulaire est généré automatiquement).

## Variables

`PORT`, `HOST`, `ADMIN_PASSWORD`, `MAX_UPLOAD_MB`, `PDFSTUDIO_DATA`.

API : http://localhost:8000/api/docs
