"""Checks that every language has every UI key and every tool text translated."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.tools import CATEGORIES, TOOLS  # noqa: E402

LOC = ROOT / "static" / "locales"
en = json.loads((LOC / "en.json").read_text("utf-8"))["ui"]
strings = {c["label"] for c in CATEGORIES}
for t in TOOLS:
    strings |= {t["title"], t["desc"]}
    if t.get("extra_file"):
        strings.add(t["extra_file"]["label"])
    for o in t.get("options", []):
        strings.add(o["label"])
        if o.get("hint"):
            strings.add(o["hint"])
        for c in o.get("choices", []):
            strings |= set(c[1:])
# labels that are the same in every language (formats, numbers…)
strings = {s for s in strings if not re.fullmatch(r"[\d°/ .{}A-Z0-9-]+|A\d|US Letter|Legal|Page 1 (of|sur) 10|Page 1|- 1 -|\d+ dpi|PDF/A-\db", s)}

errors = 0
for f in sorted(LOC.glob("*.json")):
    d = json.loads(f.read_text("utf-8"))
    missing_ui = [k for k in en if k not in d["ui"]]
    missing_data = [] if f.stem == "en" else sorted(s for s in strings if s not in d["data"])
    for k in missing_ui:
        print(f"{f.stem}: missing UI key {k}")
    for s in missing_data:
        print(f"{f.stem}: missing translation for {s!r}")
    errors += len(missing_ui) + len(missing_data)
print("OK" if not errors else f"{errors} problem(s)")
sys.exit(1 if errors else 0)
