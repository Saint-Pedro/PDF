"""Smoke test: runs every tool on generated files."""
import io, json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.pdfgen import canvas
from app.main import app
from app.tools import TOOLS
from app import engines

c = TestClient(app)
tmp = Path(tempfile.mkdtemp())

def make_pdf(name, n=4):
    p = tmp / name
    cv = canvas.Canvas(str(p))
    for i in range(n):
        cv.drawString(100, 700, f"Page {i+1} - Jean Dupont FR76 1234 confidentiel")
        img = Image.new("RGB", (800, 600), (i * 50 % 255, 120, 200))
        from reportlab.lib.utils import ImageReader
        cv.drawImage(ImageReader(img), 100, 200, 300, 220)
        cv.showPage()
    cv.save()
    return p

pdf1, pdf2 = make_pdf("a.pdf"), make_pdf("b.pdf", 2)
png = tmp / "img.png"; Image.new("RGBA", (400, 300), (255, 0, 0, 128)).save(png)
jpg = tmp / "photo.jpg"; Image.new("RGB", (300, 500), "blue").save(jpg)
import docx; d = docx.Document(); d.add_heading("Titre", 1); d.add_paragraph("Bonjour **monde**"); t = d.add_table(2, 2); t.cell(0,0).text="A"; d.save(tmp / "doc.docx")
import openpyxl; wb = openpyxl.Workbook(); wb.active.append(["Nom", "Montant"]); wb.active.append(["X", 12]); wb.save(tmp / "t.xlsx")
(tmp / "n.md").write_text("# Titre\n\nTexte **gras** et `code`.\n\n- un\n- deux\n\n```\nx = 1\n```\n")
(tmp / "p.html").write_text("<h1>Hello</h1><p>Monde</p>")
from pptx import Presentation; pr = Presentation(); pr.slides.add_slide(pr.slide_layouts[0]).shapes.title.text = "Hi"; pr.save(tmp / "s.pptx")

INPUTS = {
    "merge": [pdf1, pdf2], "img_to_pdf": [png, jpg], "word_to_pdf": [tmp / "doc.docx"],
    "excel_to_pdf": [tmp / "t.xlsx"], "ppt_to_pdf": [tmp / "s.pptx"], "html_to_pdf": [tmp / "n.md", tmp / "p.html"],
    "any_to_pdf": [png, tmp / "doc.docx", tmp / "n.md"],
}
OPTS = {
    "split": {"mode": "ranges", "ranges": "1-2,3-"}, "remove": {"layout": [{"src": 0}, {"src": 2}]},
    "organize": {"layout": [{"src": 3, "rot": 90}, {"src": 0}, {"blank": True}]},
    "extract": {"layout": [{"src": 1}]},
    "protect": {"password": "x", "confirm": "x", "no_print": True}, "unlock": {"password": ""},
    "edit": {"items": [{"type": "text", "page": 0, "x": .1, "y": .1, "text": "Bonjour\nligne 2", "size": .03, "color": "#ff0000"},
                       {"type": "rect", "page": 1, "x": .1, "y": .1, "w": .3, "h": .1}]},
    "redact": {"terms": "Dupont\nFR76", "items": [{"page": 1, "x": .1, "y": .1, "w": .2, "h": .1}]},
    "metadata": {"title": "T", "author": "Moi"}, "any_to_pdf": {"merge": True},
}
import base64
buf = io.BytesIO(); Image.new("RGBA", (200, 80), (0, 0, 0, 0)).save(buf, "PNG")
OPTS["sign"] = {"items": [{"type": "image", "page": 0, "x": .5, "y": .8, "w": .3, "h": .08, "src": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}]}

fail = 0
for t in TOOLS:
    if t.get("requires") and not engines.has(t["requires"]):
        print(f"SKIP {t['id']} (requires {t['requires']})"); continue
    files = INPUTS.get(t["id"], [pdf1])
    opts = {o["name"]: o.get("default") for o in t.get("options", []) if "default" in o}
    opts.update(OPTS.get(t["id"], {}))
    r = c.post(f"/api/process/{t['id']}", files=[("files", (f.name, f.read_bytes())) for f in files], data={"options": json.dumps(opts)})
    ok = r.status_code == 200
    fail += not ok
    print(("OK  " if ok else "ERR ") + t["id"], r.status_code, r.headers.get("content-disposition", "")[:60], "" if ok else r.text[:300])

r = c.post("/api/preview", files={"file": ("a.pdf", pdf1.read_bytes())}); print("preview", r.status_code, r.json()["count"])
r = c.get("/api/config"); print("config", r.status_code, len(r.json()["tools"]))
print("FAILURES:", fail); sys.exit(1 if fail else 0)
