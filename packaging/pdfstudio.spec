# PyInstaller spec — build with:  pyinstaller packaging/pdfstudio.spec
# Produces: Windows "PDF Studio.exe" (single file), macOS "PDF Studio.app", Linux "pdfstudio".
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

ROOT = Path(SPECPATH).parent
ICONS = ROOT / "packaging" / "icons"

datas = [
    (str(ROOT / "static"), "static"),
    (str(ROOT / "app" / "branding.json"), "app"),
    (str(ROOT / "CHANGELOG.md"), "."),
]
datas += collect_data_files("reportlab")
datas += collect_data_files("pypdfium2_raw")
datas += collect_data_files("docx")
datas += collect_data_files("pptx")
datas += collect_data_files("pymupdf")  # PyMuPDF resources (used by pdf2docx for PDF → Word)
binaries = collect_dynamic_libs("pypdfium2_raw")
hiddenimports = collect_submodules("app") + collect_submodules("uvicorn") + [
    "multipart", "python_multipart", "pdfplumber", "openpyxl", "pptx", "docx", "webview",
] + collect_submodules("pdf2docx")

a = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "numpy.tests", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PDF Studio", console=False,
              icon=str(ICONS / "pdfstudio.icns"))
    coll = COLLECT(exe, a.binaries, a.datas, name="PDF Studio")
    app = BUNDLE(coll, name="PDF Studio.app", icon=str(ICONS / "pdfstudio.icns"),
                 bundle_identifier="com.pdfstudio.app",
                 info_plist={"CFBundleShortVersionString": open(ROOT / "app" / "__init__.py").read().split('"')[1],
                             "NSHighResolutionCapable": True})
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
              name="PDF Studio" if sys.platform == "win32" else "pdfstudio",
              console=False, icon=str(ICONS / "pdfstudio.ico"), upx=False)
