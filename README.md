<p align="center"><img src="static/img/mascot.png" width="140" alt="PDF Studio mascot"></p>

# PDF Studio

**A self-hosted iLovePDF clone that runs 100% locally.** Merge, split, compress, convert, sign, redact… your files never leave your machine.

Available in English, French, Spanish, German and Italian (detected from your browser, switchable in the header).

## Features (34 tools)

| Category | Tools |
|---|---|
| Organize | Merge, split, organize pages visually (reorder / rotate / delete / blank page), remove pages, extract pages, rotate, pages per sheet |
| Optimize | Compress, repair, OCR*, PDF/A*, grayscale |
| Convert to PDF | Anything to PDF, images (JPG, PNG, WEBP, HEIC, TIFF…), Word, Excel, PowerPoint*, HTML / Markdown / text, **web page from a URL*** |
| Convert from PDF | Images (or extract embedded images), Word, PowerPoint, Excel (tables), text |
| Edit | Visual editor (text, images, shapes), sign (draw / type / upload), watermark, page numbers, crop, metadata, flatten |
| Security | Protect (AES-256 + permissions), unlock, true redaction (text is actually removed) |

\* Requires an optional engine (see below).

Highlights:

- **Instant previews in the browser** (pdf.js) — nothing is uploaded to show your PDFs.
- **Merge, organize, remove / extract pages and rotate run entirely in the browser** (pdf-lib).
- **Preview the result before downloading**, with the size before / after.
- **Job queue with real progress**: each job runs in its own process, can be cancelled, and never blocks the others.
- **Privacy you can check**: inputs are deleted as soon as processing ends, results right after download; the UI shows how many files the server holds (0).
- **Built-in Word and Excel renderers**: good DOCX / XLSX → PDF without LibreOffice.
- **Undo / redo** and **full keyboard support** (reorder files and pages, place / move / resize elements in the editor).
- **Installable** as an app from the browser, or as a **desktop application**.

## Run it

### Desktop application (no Python needed)

Download the file for your system from the [Releases](https://github.com/Saint-Pedro/PDF/releases) page:

- **Windows**: `PDF-Studio-windows.zip` → unzip → double-click `PDF Studio.exe`
- **macOS**: `PDF-Studio-macos-arm64.dmg` (Apple Silicon) or `PDF-Studio-macos-intel.dmg` → drag *PDF Studio* to Applications. The app is not notarized: the first time, right-click → *Open*.
- **Linux**: `PDF-Studio-linux.tar.gz` → extract → run `./pdfstudio`

The executables are built automatically by GitHub Actions (`.github/workflows/release.yml`) when a version tag is pushed (`git tag v1.1.0 && git push --tags`).

### From source

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

To build the desktop app yourself: `pip install -r requirements-desktop.txt && pyinstaller packaging/pdfstudio.spec` (output in `dist/`).

### Optional engines (auto-detected)

| Engine | Adds |
|---|---|
| Chrome / Edge / Chromium / Brave | Web page → PDF, better HTML → PDF (the browser already installed is used, nothing to download) |
| LibreOffice | Office → PDF for every format (required for PowerPoint, .xls, .ods); without it, DOCX / XLSX / CSV use the built-in renderers |
| Ghostscript | Better compression, PDF/A, vector grayscale |
| OCRmyPDF + Tesseract | OCR |

PDF → Word uses `pdf2docx` (based on PyMuPDF), included in the desktop builds.

## Customization

- **Branding** (name, logo, mascot, favicon, texts per language, default language, colors, fonts, style, featured and hidden tools) is hard-coded in [`app/branding.json`](app/branding.json). Images live in `static/img/`.
- **Themes**: the *Themes* page offers 8 ready-made themes. The selected theme is stored in `data/theme.json`. Set `ADMIN_PASSWORD` to protect it.
- **Translations**: `static/locales/<lang>.json` (`ui` = interface, `data` = tool texts keyed by their English text). Server messages: `app/i18n.py`. `python tests/check_locales.py` checks that nothing is missing.

## Adding a tool

Add an entry in `app/tools.py` (options are declarative, the form is generated automatically), then translate its texts in `static/locales/*.json`.

## Environment variables

| Variable | Default | |
|---|---|---|
| `PORT`, `HOST` | 8000, 127.0.0.1 | |
| `ADMIN_PASSWORD` | — | protects the Themes page |
| `MAX_UPLOAD_MB` | 500 | per file |
| `MAX_FILES` | 100 | per job |
| `MAX_PAGES` | 5000 | per PDF |
| `WORKERS` | CPU count − 1 (max 4) | jobs running at the same time |
| `JOB_TIMEOUT` | 900 | seconds before a job is stopped |
| `RESULT_TTL` | 900 | seconds before an unclaimed result is deleted |
| `PDFSTUDIO_DATA` | `./data` | theme + temporary job folders |
| `CHROME_PATH` | auto | browser used for web page → PDF |

API docs: http://localhost:8000/api/docs — what's new: [CHANGELOG.md](CHANGELOG.md).

## Stack

FastAPI · pypdf · pypdfium2 · reportlab · Pillow · pdf2docx / PyMuPDF · pdf.js · pdf-lib · vanilla JS (no build step).

## License

PDF Studio is free software released under the [GNU Affero General Public License v3.0 or later](LICENSE).
You may use, modify and redistribute it; if you distribute it, or offer a modified version as a network service,
you must make your source code available under the same license.

Bundled third-party code keeps its own license: pdf.js (Apache-2.0), pdf-lib (MIT), PyMuPDF (AGPL-3.0).
