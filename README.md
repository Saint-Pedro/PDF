<p align="center"><img src="static/img/logo.png" width="140" alt="PDF Studio logo"></p>

# PDF Studio

**A self-hosted iLovePDF clone that runs 100% locally.** Merge, split, compress, convert, sign, redact… your files never leave your machine.

English by default, with an EN/FR toggle in the header.

## Features (31 tools)

| Category | Tools |
|---|---|
| Organize | Merge, split, organize pages visually (reorder / rotate / delete / blank page), remove pages, extract pages, rotate, pages per sheet |
| Optimize | Compress, repair, OCR*, PDF/A*, grayscale |
| Convert to PDF | Anything to PDF, images (JPG, PNG, WEBP, HEIC, TIFF…), Word, Excel, PowerPoint*, HTML / Markdown / text |
| Convert from PDF | Images (or extract embedded images), Word, PowerPoint, Excel (tables), text |
| Edit | Visual editor (text, images, shapes), sign (draw / type / upload), watermark, page numbers, crop, metadata, flatten |
| Security | Protect (AES-256 + permissions), unlock, true redaction (text is actually removed) |

After each job you can chain the result straight into another tool.

\* Requires an optional engine (see below).

## Run it

**Linux / macOS**
```bash
./run.sh
```
**Windows**: double-click `run.bat`.

**Docker** (all optional engines included)
```bash
docker compose up -d --build
```

Then open http://localhost:8000. Requires Python 3.10+.

### Optional engines (auto-detected)

Most tools work with Python packages only. Heavier engines are used when installed:

| Engine | Adds |
|---|---|
| LibreOffice | Office → PDF for every format (required for PowerPoint, .xls, .ods); without it, XLSX/CSV use the built-in renderer and DOCX a simplified one |
| Ghostscript | Better compression, PDF/A, vector grayscale |
| OCRmyPDF + Tesseract | OCR |

Note: `pdf2docx` (better PDF → Word) depends on PyMuPDF (AGPL). Fine for local use; remove it from `requirements.txt` if you redistribute the app.

## Customization

- **Branding** (name, logo, favicon, texts, default language, default colors / fonts / style, featured and hidden tools) is hard-coded in [`app/branding.json`](app/branding.json). Logo and favicon live in `static/img/`.
- **Themes**: the *Themes* page offers 8 ready-made themes (Classic, Ocean, Forest, Midnight, Brutalist, Pastel, Corporate, Terracotta). The selected theme is stored in `data/theme.json`. Set `ADMIN_PASSWORD` to protect it.
- **Translations**: UI strings are in `static/js/i18n.js`, tool texts in `app/tools.py`, server messages in `app/i18n.py`.

## Adding a tool

Add an entry in `app/tools.py`. Options are declarative, so the form is generated automatically.

## Environment variables

`PORT`, `HOST`, `ADMIN_PASSWORD`, `MAX_UPLOAD_MB` (default 500), `PDFSTUDIO_DATA` (default `./data`).

API docs: http://localhost:8000/api/docs

## Stack

FastAPI · pypdf · pypdfium2 · reportlab · Pillow · vanilla JS (no build step).
