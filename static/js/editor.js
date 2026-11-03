/* ============================================================
   Visual editor: text, images, shapes, signatures, redaction
   (mouse, touch and keyboard; undo / redo)
   ============================================================ */
const Editor = {
  st: null,
  view: null,
  mode: "select",
  pending: null, // image waiting to be placed
  selId: null,

  TOOLS: {
    select: { icon: "cursor", label: "ed.select" },
    text: { icon: "type", label: "ed.text" },
    signature: { icon: "signature", label: "ed.signature" },
    image: { icon: "image", label: "ed.image" },
    rect: { icon: "square", label: "ed.rect" },
    redact: { icon: "redact", label: "ed.redact" },
  },
  FONTS: { sans: "Helvetica, Arial, sans-serif", serif: '"Times New Roman", Times, serif', mono: '"Courier New", Courier, monospace' },

  async open(st) {
    this.st = st;
    this.mode = "select";
    this.selId = null;
    if (!st.view) {
      $("#app").innerHTML = `<div class="processing"><div class="mascot-spin">${mascot()}</div><h2>${esc(t("ed.opening"))}</h2></div>`;
      try { st.view = await PDFView.open(st.files[0].file); }
      catch (err) { toast(t(err && err.locked ? "pg.locked" : "pg.unreadable"), "error"); st.files = []; return Workspace.landing(); }
    }
    this.view = st.view;
    if (!st.history) st.history = new History(() => st.items, (v) => { st.items = v; this.remountAll(); });
    activeHistory = st.history;
    this.layout();
    if (st.tool.id === "sign" && !st.items.length) this.signatureModal();
  },

  layout() {
    const { tool } = this.st;
    const tools = ["select", ...tool.editor_tools];
    const view = this.view;
    $("#app").innerHTML = `
      <div class="editor" ${toolColorStyle(tool)}>
        <nav class="ed-tools" role="toolbar" aria-label="${esc(tx(tool.title))}" aria-orientation="vertical">
          ${tools.map((m) => `<button data-mode="${m}" aria-pressed="${this.mode === m}" class="${this.mode === m ? "active" : ""}">${icon(this.TOOLS[m].icon, 20)}<span>${esc(t(this.TOOLS[m].label))}</span></button>`).join("")}
          <span class="ed-sep"></span>${historyButtons()}
        </nav>
        <section class="ed-pages" id="ed-pages"></section>
        ${Workspace.sidebar(`<div id="props"></div><p class="muted small kb-help">${esc(t("ed.kb"))}</p>`)}
      </div>`;
    const sync = bindHistoryButtons(this.st.history);
    this.st.history.onChange = sync;
    $$(".ed-tools [data-mode]").forEach((b) => (b.onclick = () => this.setMode(b.dataset.mode)));
    const wrap = $("#ed-pages");
    for (let i = 0; i < view.count; i++) {
      const s = view.size(i);
      const pg = el(`<div class="ed-page skeleton" data-page="${i}" tabindex="0" role="group" aria-label="${esc(t("pg.page", { n: i + 1 }))}" style="aspect-ratio:${s.w}/${s.h}"><span class="pno" aria-hidden="true">${i + 1}</span><img alt=""></div>`);
      this.bindPage(pg, i);
      wrap.appendChild(pg);
      LazyThumbs.watch($("img", pg), async () => {
        const real = await view.exactSize(i);
        pg.style.aspectRatio = `${real.w}/${real.h}`;
        return view.thumb(i, 900);
      });
    }
    const ro = new ResizeObserver((ents) => ents.forEach((en) => en.target.style.setProperty("--ph", en.contentRect.height + "px")));
    $$(".ed-page").forEach((p) => ro.observe(p));
    this.st.items.forEach((it) => this.mount(it));
    Workspace.bindSidebar(() => {
      const items = this.st.items.map(({ id, ...rest }) => rest);
      if (tool.id !== "redact" && !items.length) { toast(t("ed.need_item"), "error"); return null; }
      return { files: [this.st.files[0].file], opts: { items } };
    }, () => `<div class="summary">${esc(t("ed.items", { n: this.st.items.length }))}</div>`);
    this.props();
    document.onkeydown = (e) => {
      if (!$(".editor") || typingTarget(e)) return;
      if (e.key === "Escape") { this.select(null); this.setMode("select"); }
    };
  },

  remountAll() {
    $$(".ed-item").forEach((n) => n.remove());
    this.st.items.forEach((it) => this.mount(it));
    if (!this.st.items.find((x) => x.id === this.selId)) this.selId = null;
    this.select(this.selId);
    this.refreshSummary();
  },

  setMode(m) {
    if (m === "signature") return this.signatureModal();
    if (m === "image") return this.pickImage();
    this.mode = m;
    this.pending = null;
    $$(".ed-tools [data-mode]").forEach((b) => { b.classList.toggle("active", b.dataset.mode === m); b.setAttribute("aria-pressed", String(b.dataset.mode === m)); });
    $$(".ed-page").forEach((p) => p.classList.toggle("placing", m !== "select"));
  },

  refreshSummary() { const s = $("#summary"); if (s) s.innerHTML = `<div class="summary">${esc(t("ed.items", { n: this.st.items.length }))}</div>`; },

  /* ---------- placement (mouse / touch / keyboard) ---------- */
  placeAt(page, fx, fy) {
    const pg = $(`.ed-page[data-page="${page}"]`);
    const r = pg.getBoundingClientRect();
    if (this.mode === "text") {
      this.st.history.push();
      const it = this.add({ type: "text", page, x: fx, y: fy - 0.012, text: t("ed.your_text"), size: 0.022, color: "#111111", font: "sans", bold: false });
      this.setMode("select");
      setTimeout(() => this.editText(it.id), 30);
      return true;
    }
    if (this.pending) {
      const { src, ratio } = this.pending;
      const w = 0.28, h = (w * r.width) / ratio / r.height;
      this.st.history.push();
      this.add({ type: "image", page, x: Math.max(0, Math.min(fx - w / 2, 1 - w)), y: Math.max(0, Math.min(fy - h / 2, 1 - h)), w, h, src, ratio });
      this.setMode("select");
      return true;
    }
    if (this.mode === "rect" || this.mode === "redact") {
      this.st.history.push();
      this.add({ type: this.mode, page, x: Math.max(0, fx - 0.15), y: Math.max(0, fy - 0.02), w: 0.3, h: 0.04, color: "#ffffff" });
      return true;
    }
    return false;
  },

  bindPage(pg, page) {
    pg.addEventListener("keydown", (e) => {
      if (e.target !== pg || (e.key !== "Enter" && e.key !== " ")) return;
      if (this.mode === "select" && !this.pending) return;
      e.preventDefault();
      // place in the middle of the visible part of the page
      const r = pg.getBoundingClientRect();
      const top = Math.max(r.top, 0), bottom = Math.min(r.bottom, innerHeight);
      this.placeAt(page, 0.5, Math.min(0.95, Math.max(0.05, ((top + bottom) / 2 - r.top) / r.height)));
    });
    pg.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".ed-item")) return;
      const r = pg.getBoundingClientRect();
      const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
      if (this.mode === "select" && !this.pending) { this.select(null); return; }
      if (this.mode === "rect" || this.mode === "redact") {
        e.preventDefault();
        this.st.history.push();
        const it = this.add({ type: this.mode, page, x: fx, y: fy, w: 0.001, h: 0.001, color: "#ffffff" }, false);
        const node = this.mount(it);
        const move = (ev) => {
          const cx = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width)), cy = Math.max(0, Math.min(1, (ev.clientY - r.top) / r.height));
          it.x = Math.min(fx, cx); it.y = Math.min(fy, cy); it.w = Math.abs(cx - fx); it.h = Math.abs(cy - fy);
          this.place(node, it);
        };
        const up = () => {
          window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
          if (it.w < 0.01 || it.h < 0.005) { it.w = Math.max(it.w, 0.2); it.h = Math.max(it.h, 0.03); this.place(node, it); }
          this.select(it.id);
          this.refreshSummary();
        };
        window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
        return;
      }
      this.placeAt(page, fx, fy);
    });
  },

  add(data, mount = true) {
    const it = { id: "i" + Date.now() + Math.random().toString(36).slice(2, 6), ...data };
    this.st.items.push(it);
    if (mount) { this.mount(it); this.select(it.id, true); this.refreshSummary(); }
    return it;
  },

  remove(id) {
    this.st.history.push();
    this.st.items = this.st.items.filter((x) => x.id !== id);
    $(`.ed-item[data-id="${id}"]`)?.remove();
    if (this.selId === id) this.select(null);
    this.refreshSummary();
    announce(t("kb.removed"));
  },

  place(node, it) {
    node.style.left = it.x * 100 + "%";
    node.style.top = it.y * 100 + "%";
    if (it.type === "text") {
      node.style.fontSize = `calc(var(--ph) * ${it.size})`;
      node.style.color = it.color;
      node.style.fontFamily = this.FONTS[it.font] || this.FONTS.sans;
      node.style.fontWeight = it.bold ? "700" : "400";
    } else {
      node.style.width = it.w * 100 + "%";
      node.style.height = it.h * 100 + "%";
      if (it.type === "rect") node.style.background = it.color;
    }
  },

  itemLabel(it) {
    return it.type === "text" ? `${t("ed.text")}: ${it.text}` : it.type === "image" ? t("ed.image") : it.type === "rect" ? t("ed.rect") : t("ed.redact");
  },

  mount(it) {
    const pg = $(`.ed-page[data-page="${it.page}"]`);
    if (!pg) return null;
    const inner = it.type === "image" ? `<img src="${it.src}" alt="">` : it.type === "text" ? `<div class="txt">${esc(it.text)}</div>` : "";
    const node = el(`<div class="ed-item ${it.type}" data-id="${it.id}" tabindex="0" role="button" aria-label="${esc(this.itemLabel(it))}">${inner}<span class="h" aria-hidden="true"></span><button class="del" tabindex="-1" aria-label="${esc(t("ed.del"))}">${icon("x", 12)}</button></div>`);
    this.place(node, it);
    pg.appendChild(node);
    $(".del", node).onpointerdown = (e) => { e.stopPropagation(); this.remove(it.id); };
    node.addEventListener("focus", () => { if (this.selId !== it.id) this.select(it.id); });
    node.addEventListener("keydown", (e) => this.itemKeys(e, it, node));
    // move
    node.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".h") || e.target.closest(".del") || e.target.isContentEditable) return;
      e.preventDefault();
      this.select(it.id);
      const r = pg.getBoundingClientRect();
      const sx = e.clientX, sy = e.clientY, ox = it.x, oy = it.y;
      let pushed = false;
      const move = (ev) => {
        if (!pushed && (Math.abs(ev.clientX - sx) + Math.abs(ev.clientY - sy) > 2)) { this.st.history.push(); pushed = true; }
        it.x = Math.max(-0.05, Math.min(0.98, ox + (ev.clientX - sx) / r.width));
        it.y = Math.max(-0.02, Math.min(0.98, oy + (ev.clientY - sy) / r.height));
        this.place(node, it);
      };
      const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
    });
    if (it.type === "text") node.addEventListener("dblclick", () => this.editText(it.id));
    // resize
    $(".h", node).addEventListener("pointerdown", (e) => {
      e.preventDefault(); e.stopPropagation();
      this.st.history.push();
      const r = pg.getBoundingClientRect();
      const sx = e.clientX, sy = e.clientY, ow = it.w, oh = it.h, os = it.size;
      const startW = node.getBoundingClientRect().width;
      const move = (ev) => {
        if (it.type === "text") it.size = Math.max(0.006, os * (startW + ev.clientX - sx) / startW);
        else {
          it.w = Math.max(0.02, ow + (ev.clientX - sx) / r.width);
          it.h = it.type === "image" && it.ratio ? (it.w * r.width) / it.ratio / r.height : Math.max(0.008, oh + (ev.clientY - sy) / r.height);
        }
        this.place(node, it);
      };
      const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); this.props(); };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
    });
    return node;
  },

  /* Arrows move (Shift = faster), Ctrl + arrows resize, Enter edits text, Delete removes. */
  itemKeys(e, it, node) {
    if (e.target.isContentEditable) {
      if (e.key === "Escape") { e.preventDefault(); node.focus(); }
      return;
    }
    const step = e.shiftKey ? 0.05 : 0.005;
    const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (d) {
      e.preventDefault();
      if (!e.repeat) this.st.history.push();
      if (e.ctrlKey || e.metaKey) {
        if (it.type === "text") it.size = Math.max(0.006, it.size * (1 + (d[0] - d[1]) * (e.shiftKey ? 0.2 : 0.05)));
        else {
          it.w = Math.max(0.02, it.w + d[0] * step);
          it.h = it.type === "image" && it.ratio ? it.w * (this.pageRatio(it.page)) / it.ratio : Math.max(0.008, it.h + d[1] * step);
        }
      } else {
        it.x = Math.max(-0.05, Math.min(0.98, it.x + d[0] * step));
        it.y = Math.max(-0.02, Math.min(0.98, it.y + d[1] * step));
      }
      this.place(node, it);
      return;
    }
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); const p = it.page; this.remove(it.id); $(`.ed-page[data-page="${p}"]`)?.focus(); }
    else if (e.key === "Enter" && it.type === "text") { e.preventDefault(); this.editText(it.id); }
    else if (e.key === "Escape") { e.preventDefault(); this.select(null); $(`.ed-page[data-page="${it.page}"]`)?.focus(); }
  },

  pageRatio(page) {
    const r = $(`.ed-page[data-page="${page}"]`).getBoundingClientRect();
    return r.width / r.height;
  },

  editText(id) {
    const it = this.st.items.find((x) => x.id === id);
    const node = $(`.ed-item[data-id="${id}"] .txt`);
    if (!it || !node) return;
    this.st.history.push();
    node.contentEditable = "true";
    node.focus();
    const sel = getSelection(); const rg = document.createRange(); rg.selectNodeContents(node); sel.removeAllRanges(); sel.addRange(rg);
    node.oninput = () => { it.text = node.innerText.replace(/\n$/, ""); const ta = $("#p-text"); if (ta) ta.value = it.text; };
    node.onblur = () => {
      node.contentEditable = "false";
      if (!it.text.trim()) this.remove(id);
      else node.closest(".ed-item")?.setAttribute("aria-label", this.itemLabel(it));
    };
  },

  select(id, focus = false) {
    this.selId = id;
    $$(".ed-item").forEach((n) => n.classList.toggle("sel", n.dataset.id === id));
    if (focus && id) $(`.ed-item[data-id="${id}"]`)?.focus({ preventScroll: true });
    this.props();
  },

  /* ---------- properties panel ---------- */
  props() {
    const box = $("#props");
    if (!box) return;
    const it = this.st.items.find((x) => x.id === this.selId);
    const tool = this.st.tool;
    if (!it) {
      const tips = { redact: "ed.tip_redact", sign: "ed.tip_sign", edit: "ed.tip_edit" };
      box.innerHTML = `<div class="summary">${esc(t(tips[tool.id] || tips.edit))}</div>`;
      return;
    }
    const up = () => { const n = $(`.ed-item[data-id="${it.id}"]`); if (n) this.place(n, it); };
    let html = "";
    if (it.type === "text") {
      html = `<div class="field"><label for="p-text">${esc(t("ed.p_text"))}</label><textarea class="input" id="p-text" style="min-height:70px">${esc(it.text)}</textarea></div>
        <div class="field"><label for="p-size">${esc(t("ed.p_size"))}</label><div class="range-row"><input type="range" id="p-size" min="6" max="80" value="${Math.round(it.size * 1000)}"><output>${Math.round(it.size * 1000)}</output></div></div>
        <div class="cz-row"><div class="field"><label for="p-color">${esc(t("ed.p_color"))}</label><input type="color" class="input" id="p-color" value="${it.color}"></div>
        <div class="field"><label for="p-font">${esc(t("ed.p_font"))}</label><select class="input" id="p-font"><option value="sans">Sans serif</option><option value="serif">Serif</option><option value="mono">Mono</option></select></div></div>
        <label class="check"><input type="checkbox" id="p-bold" ${it.bold ? "checked" : ""}> ${esc(t("ed.p_bold"))}</label>`;
    } else if (it.type === "rect") {
      html = `<div class="field"><label for="p-color">${esc(t("ed.p_shape"))}</label><input type="color" class="input" id="p-color" value="${it.color}"></div><div class="hint muted small">${esc(t("ed.p_shape_tip"))}</div>`;
    } else if (it.type === "redact") {
      html = `<div class="summary">${esc(t("ed.p_redact", { n: it.page + 1 }))}</div>`;
    } else {
      html = `<div class="summary">${esc(t("ed.p_image", { n: it.page + 1 }))}</div>`;
    }
    html += `<div class="row wrap">${it.type !== "text" ? `<button class="btn sm" id="p-all">${icon("layers", 14)} ${esc(t("ed.all_pages"))}</button>` : ""}<button class="btn sm" id="p-dup">${esc(t("ed.dup"))}</button><button class="btn sm ghost" id="p-del">${icon("trash", 14)} ${esc(t("ed.del"))}</button></div>`;
    box.innerHTML = `<div class="opts">${html}</div>`;
    const on = (id, ev, fn) => { const n = $("#" + id, box); if (n) n[ev] = fn; };
    const once = (id) => { const n = $("#" + id, box); if (n) n.addEventListener("focus", () => this.st.history.push(), { once: true }); };
    ["p-text", "p-size", "p-color", "p-font"].forEach(once);
    on("p-text", "oninput", (e) => { it.text = e.target.value; const tn = $(`.ed-item[data-id="${it.id}"] .txt`); if (tn) tn.textContent = it.text; });
    on("p-size", "oninput", (e) => { it.size = e.target.value / 1000; e.target.nextElementSibling.textContent = e.target.value; up(); });
    on("p-color", "oninput", (e) => { it.color = e.target.value; up(); });
    on("p-font", "onchange", (e) => { it.font = e.target.value; up(); });
    on("p-bold", "onchange", (e) => { this.st.history.push(); it.bold = e.target.checked; up(); });
    if ($("#p-font", box)) $("#p-font", box).value = it.font || "sans";
    on("p-del", "onclick", () => this.remove(it.id));
    on("p-dup", "onclick", () => { this.st.history.push(); const { id, ...rest } = it; this.add({ ...rest, x: it.x + 0.02, y: it.y + 0.02 }); });
    on("p-all", "onclick", () => {
      this.st.history.push();
      const { id, page, ...rest } = it;
      for (let p = 0; p < this.view.count; p++) if (p !== page) this.mount(this.add({ ...rest, page: p }, false));
      this.refreshSummary();
      toast(t("ed.copied", { n: this.view.count - 1 }));
    });
  },

  /* ---------- images ---------- */
  pickImage() {
    chooseFiles("image/png,image/jpeg,image/webp,image/svg+xml", false, ([f]) => {
      const r = new FileReader();
      r.onload = () => this.prepareImage(r.result);
      r.readAsDataURL(f);
    });
  },
  prepareImage(src) {
    const img = new Image();
    img.onload = () => {
      // normalize to PNG (handles SVG / WEBP)
      const c = document.createElement("canvas");
      const scale = Math.min(1, 1600 / Math.max(img.width, img.height));
      c.width = Math.max(1, img.width * scale); c.height = Math.max(1, img.height * scale);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      this.armPlacement(c.toDataURL("image/png"), c.width / c.height);
    };
    img.src = src;
  },
  armPlacement(src, ratio) {
    this.mode = "place";
    this.pending = { src, ratio };
    $$(".ed-tools [data-mode]").forEach((b) => { b.classList.remove("active"); b.setAttribute("aria-pressed", "false"); });
    $$(".ed-page").forEach((p) => p.classList.add("placing"));
    toast(t("ed.place"));
    // keyboard users: focus the first visible page so Enter places the element
    const visible = $$(".ed-page").find((p) => { const r = p.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; });
    visible?.focus({ preventScroll: true });
  },

  /* ---------- signature ---------- */
  savedSigs() { try { return JSON.parse(localStorage.getItem("signatures") || "[]"); } catch { return []; } },
  storeSig(src) { try { const s = [src, ...this.savedSigs().filter((x) => x !== src)].slice(0, 6); localStorage.setItem("signatures", JSON.stringify(s)); } catch {} },

  trim(canvas) {
    const ctx = canvas.getContext("2d");
    const { width: w, height: h } = canvas;
    const d = ctx.getImageData(0, 0, w, h).data;
    let x0 = w, y0 = h, x1 = 0, y1 = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (d[(y * w + x) * 4 + 3] > 10) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    if (x1 <= x0) return null;
    const pad = 6, c = document.createElement("canvas");
    c.width = x1 - x0 + pad * 2; c.height = y1 - y0 + pad * 2;
    c.getContext("2d").drawImage(canvas, x0 - pad, y0 - pad, c.width, c.height, 0, 0, c.width, c.height);
    return c;
  },

  signatureModal() {
    const saved = this.savedSigs();
    const colors = ["#111111", "#1d4ed8", "#b91c1c"];
    const fonts = ['"Brush Script MT", "Segoe Script", cursive', '"Segoe Script", "Lucida Handwriting", cursive', '"Lucida Handwriting", "Apple Chancery", cursive', '"Snell Roundhand", "Zapfino", cursive', "cursive"];
    let color = colors[0], tab = "draw", font = fonts[0];
    const body = `
        ${saved.length ? `<div class="field" style="margin-bottom:1rem"><span class="field-label">${esc(t("sig.recent"))}</span><div class="saved-sigs">${saved.map((s, i) => `<button class="sig" data-i="${i}" aria-label="${esc(t("sig.recent"))} ${i + 1}"><img src="${s}" alt=""></button>`).join("")}</div></div>` : ""}
        <div class="tabs" role="tablist"><button role="tab" aria-selected="true" data-tab="draw" class="active">${esc(t("sig.draw"))}</button><button role="tab" aria-selected="false" data-tab="type">${esc(t("sig.type"))}</button><button role="tab" aria-selected="false" data-tab="upload">${esc(t("sig.upload"))}</button></div>
        <div data-pane="draw"><canvas class="sig-canvas" width="1100" height="400" aria-label="${esc(t("sig.draw"))}"></canvas></div>
        <div data-pane="type" class="hidden"><label class="sr" for="sig-name">${esc(t("sig.name"))}</label><input class="input" id="sig-name" placeholder="${esc(t("sig.name"))}"><div class="sig-fonts">${fonts.map((f, i) => `<button data-f="${i}" class="${i ? "" : "active"}" style="font-family:${f.replace(/"/g, "&quot;")}">${esc(t("sig.sample"))}</button>`).join("")}</div></div>
        <div data-pane="upload" class="hidden"><button class="btn" id="sig-up">${icon("upload", 16)} ${esc(t("sig.upload_btn"))}</button></div>
        <div class="sig-colors"><span class="muted small">${esc(t("sig.color"))}</span>${colors.map((c, i) => `<button data-c="${c}" aria-label="${c}" class="${i ? "" : "active"}" style="background:${c}"></button>`).join("")}<span class="spacer"></span><button class="btn sm ghost" id="sig-clear">${esc(t("sig.clear"))}</button></div>
        <div class="modal-foot inline"><button class="btn" data-x>${esc(t("sig.cancel"))}</button><button class="btn primary" id="sig-ok">${esc(t("sig.use"))}</button></div>`;
    const { el: m, close } = openModal(t("sig.title"), body);
    // Typing is the keyboard-friendly way to sign: open that tab for keyboard users
    const cv = $(".sig-canvas", m), ctx = cv.getContext("2d");
    let drawing = false, last = null, dirty = false;
    const pos = (e) => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * (cv.width / r.width), (e.clientY - r.top) * (cv.height / r.height)]; };
    cv.onpointerdown = (e) => { drawing = true; last = pos(e); cv.setPointerCapture(e.pointerId); };
    cv.onpointermove = (e) => {
      if (!drawing) return;
      const p = pos(e);
      ctx.strokeStyle = color; ctx.lineWidth = 5; ctx.lineCap = "round"; ctx.lineJoin = "round";
      ctx.beginPath(); ctx.moveTo(...last); ctx.lineTo(...p); ctx.stroke();
      last = p; dirty = true;
    };
    cv.onpointerup = () => (drawing = false);
    const showTab = (name) => {
      tab = name;
      $$(".tabs button", m).forEach((x) => { x.classList.toggle("active", x.dataset.tab === name); x.setAttribute("aria-selected", String(x.dataset.tab === name)); });
      $$("[data-pane]", m).forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== name));
      if (name === "type") setTimeout(() => $("#sig-name", m).focus(), 20);
    };
    $$(".tabs button", m).forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));
    $(".tabs", m).addEventListener("keydown", (e) => {
      const order = ["draw", "type", "upload"], i = order.indexOf(tab);
      if (e.key === "ArrowRight") { showTab(order[(i + 1) % 3]); $(`.tabs [data-tab="${tab}"]`, m).focus(); }
      if (e.key === "ArrowLeft") { showTab(order[(i + 2) % 3]); $(`.tabs [data-tab="${tab}"]`, m).focus(); }
    });
    const nameIn = $("#sig-name", m);
    nameIn.oninput = () => $$(".sig-fonts button", m).forEach((b) => (b.textContent = nameIn.value || t("sig.sample")));
    nameIn.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); $("#sig-ok", m).click(); } };
    $$(".sig-fonts button", m).forEach((b) => (b.onclick = () => { font = fonts[+b.dataset.f]; $$(".sig-fonts button", m).forEach((x) => x.classList.toggle("active", x === b)); }));
    $$(".sig-colors [data-c]", m).forEach((b) => (b.onclick = () => {
      color = b.dataset.c;
      $$(".sig-colors [data-c]", m).forEach((x) => x.classList.toggle("active", x === b));
      $$(".sig-fonts button", m).forEach((x) => (x.style.color = color));
    }));
    $("#sig-clear", m).onclick = () => { ctx.clearRect(0, 0, cv.width, cv.height); dirty = false; nameIn.value = ""; nameIn.oninput(); };
    $("#sig-up", m).onclick = () => { close(); this.pickImage(); };
    $$(".saved-sigs .sig", m).forEach((s) => (s.onclick = () => { close(); this.useSignature(saved[+s.dataset.i]); }));
    $("#sig-ok", m).onclick = () => {
      let out;
      if (tab === "draw") { if (!dirty) return toast(t("sig.need_draw"), "error"); out = this.trim(cv); }
      else if (tab === "type") {
        if (!nameIn.value.trim()) return toast(t("sig.need_name"), "error");
        const c = document.createElement("canvas"); c.width = 1400; c.height = 320;
        const x = c.getContext("2d"); x.fillStyle = color; x.font = `120px ${font}`; x.textBaseline = "middle"; x.fillText(nameIn.value, 20, 170);
        out = this.trim(c);
      } else return;
      if (!out) return;
      const src = out.toDataURL("image/png");
      this.storeSig(src);
      close();
      this.useSignature(src);
    };
  },

  useSignature(src) {
    const img = new Image();
    img.onload = () => this.armPlacement(src, img.width / img.height);
    img.src = src;
  },
};
