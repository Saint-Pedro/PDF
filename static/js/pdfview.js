/* ============================================================
   PDF rendering in the browser (pdf.js): no upload needed for previews.
   ============================================================ */
const PDFView = {
  lib: null,
  cache: new WeakMap(), // File/Blob -> Promise<view>
  queue: [],
  active: 0,

  async load() {
    if (!this.lib) {
      this.lib = await import("/static/vendor/pdfjs/pdf.min.mjs");
      this.lib.GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/pdf.worker.min.mjs";
    }
    return this.lib;
  },

  /* open(file) -> { count, size(i), thumb(i, width), destroy() }; throws {locked:true} */
  open(file) {
    if (this.cache.has(file)) return this.cache.get(file);
    const p = this._open(file);
    this.cache.set(file, p);
    p.catch(() => this.cache.delete(file));
    return p;
  },

  async _open(file) {
    const lib = await this.load();
    const data = new Uint8Array(await file.arrayBuffer());
    let doc;
    try {
      doc = await lib.getDocument({
        data, cMapUrl: "/static/vendor/pdfjs/cmaps/", cMapPacked: true,
        standardFontDataUrl: "/static/vendor/pdfjs/standard_fonts/", isEvalSupported: false,
      }).promise;
    } catch (e) {
      if (e && e.name === "PasswordException") throw { locked: true };
      throw e;
    }
    const sizes = new Map();
    const urls = new Map();
    const first = await doc.getPage(1);
    const v1 = first.getViewport({ scale: 1 });
    sizes.set(0, { w: v1.width, h: v1.height });
    const view = {
      doc, count: doc.numPages,
      size(i) { return sizes.get(i) || sizes.get(0); },
      async exactSize(i) {
        if (!sizes.has(i)) {
          const pg = await doc.getPage(i + 1);
          const v = pg.getViewport({ scale: 1 });
          sizes.set(i, { w: v.width, h: v.height });
        }
        return sizes.get(i);
      },
      thumb(i, width) {
        const key = `${i}:${width}`;
        if (!urls.has(key)) urls.set(key, PDFView._schedule(() => PDFView._render(doc, i, width, sizes)));
        return urls.get(key);
      },
      destroy() { urls.forEach((p) => p.then((u) => URL.revokeObjectURL(u)).catch(() => {})); doc.destroy(); },
    };
    return view;
  },

  _schedule(fn) {
    return new Promise((resolve, reject) => {
      this.queue.push({ fn, resolve, reject });
      this._pump();
    });
  },
  _pump() {
    while (this.active < 2 && this.queue.length) {
      const job = this.queue.shift();
      this.active++;
      job.fn().then(job.resolve, job.reject).finally(() => { this.active--; this._pump(); });
    }
  },

  async _render(doc, i, width, sizes) {
    const page = await doc.getPage(i + 1);
    const base = page.getViewport({ scale: 1 });
    sizes.set(i, { w: base.width, h: base.height });
    const scale = (width * Math.min(window.devicePixelRatio || 1, 2)) / base.width;
    const vp = page.getViewport({ scale });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(vp.width);
    canvas.height = Math.ceil(vp.height);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    await page.render({ canvasContext: ctx, viewport: vp }).promise;
    page.cleanup();
    const blob = await new Promise((r) => canvas.toBlob(r, "image/jpeg", 0.85));
    return URL.createObjectURL(blob);
  },
};

/* Lazy thumbnails: <img data-lazy> filled when scrolled into view. */
const LazyThumbs = {
  observer: null,
  watch(img, loader) {
    if (!this.observer) {
      this.observer = new IntersectionObserver((entries) => {
        for (const en of entries) {
          if (!en.isIntersecting) continue;
          this.observer.unobserve(en.target);
          const fn = en.target._loader;
          if (fn) fn();
        }
      }, { rootMargin: "400px" });
    }
    img._loader = async () => {
      try {
        img.src = await loader();
        img.closest(".skeleton")?.classList.remove("skeleton");
        img.classList.add("loaded");
      } catch { /* keep the skeleton */ }
    };
    this.observer.observe(img);
  },
};
