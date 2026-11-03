/* ============================================================
   Simple operations done entirely in the browser with pdf-lib
   (merge, organize, remove / extract pages, rotate): instant and
   nothing is uploaded. Anything unsupported falls back to the server.
   ============================================================ */
const ClientOps = {
  lib: null,
  async load() {
    if (!this.lib) {
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "/static/vendor/pdf-lib/pdf-lib.min.js";
        s.onload = resolve; s.onerror = reject;
        document.head.appendChild(s);
      });
      this.lib = window.PDFLib;
    }
    return this.lib;
  },

  supports(tool, files, opts) {
    if (!files.length || !files.every((f) => extOf(f.name) === "pdf")) return false;
    if (tool.id === "merge") return !opts.bookmarks;
    if (["organize", "remove", "extract"].includes(tool.id)) return files.length === 1;
    if (tool.id === "rotate") return files.length === 1;
    return false;
  },

  async run(tool, files, opts) {
    const L = await this.load();
    const load = async (f) => L.PDFDocument.load(await f.arrayBuffer(), { updateMetadata: false }); // throws on encrypted files
    let out, name;
    if (tool.id === "merge") {
      out = await L.PDFDocument.create();
      for (const f of files) {
        const src = await load(f);
        const pages = await out.copyPages(src, src.getPageIndices());
        pages.forEach((p) => out.addPage(p));
      }
      name = "merged.pdf";
    } else if (tool.id === "rotate") {
      out = await load(files[0]);
      const n = out.getPageCount();
      const sel = (opts.pages || "").trim() ? parseRanges(opts.pages, n) : [...Array(n).keys()];
      for (const i of sel) {
        const p = out.getPage(i);
        p.setRotation(L.degrees((p.getRotation().angle + Number(opts.angle || 90)) % 360));
      }
      name = files[0].name.replace(/\.pdf$/i, "") + "_rotate.pdf";
    } else {
      const src = await load(files[0]);
      out = await L.PDFDocument.create();
      const first = src.getPage(0).getSize();
      for (const item of opts.layout || []) {
        if (item.blank) { out.addPage([first.width, first.height]); continue; }
        const [p] = await out.copyPages(src, [item.src]);
        if (item.rot) p.setRotation(L.degrees((p.getRotation().angle + item.rot) % 360));
        out.addPage(p);
      }
      if (!out.getPageCount()) throw new Error("empty");
      name = files[0].name.replace(/\.pdf$/i, "") + `_${tool.id}.pdf`;
    }
    const bytes = await out.save();
    return { blob: new Blob([bytes], { type: "application/pdf" }), name };
  },
};

function parseRanges(spec, n) {
  const set = new Set();
  for (const part of String(spec).split(/[,;]/)) {
    const m = part.trim().match(/^(\d*)\s*-\s*(\d*)$/);
    if (m) { const a = +(m[1] || 1), b = +(m[2] || n); for (let k = Math.max(1, a); k <= Math.min(b, n); k++) set.add(k - 1); }
    else if (/^\d+$/.test(part.trim()) && +part.trim() <= n && +part.trim() >= 1) set.add(+part.trim() - 1);
  }
  return [...set].sort((a, b) => a - b);
}
