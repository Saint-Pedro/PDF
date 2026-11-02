/* ============================================================
   Éditeur visuel : texte, images, formes, signatures, caviardage
   ============================================================ */
const Editor = {
  st: null,
  data: null,
  mode: "select",
  pending: null, // image en attente de placement
  selId: null,

  TOOLS: {
    select: { icon: "arrow-right", label: "Sélection" },
    text: { icon: "type", label: "Texte" },
    signature: { icon: "signature", label: "Signature" },
    image: { icon: "image", label: "Image" },
    rect: { icon: "square", label: "Masquer" },
    redact: { icon: "redact", label: "Zone" },
  },
  FONTS: { sans: "Helvetica, Arial, sans-serif", serif: '"Times New Roman", Times, serif', mono: '"Courier New", Courier, monospace' },

  async open(st) {
    this.st = st;
    this.mode = st.tool.editor_tools.includes("signature") && st.tool.id === "sign" ? "signature" : "select";
    this.selId = null;
    $("#app").innerHTML = `<div class="processing"><div class="spinner"></div><h2>Ouverture du document…</h2></div>`;
    try { this.data = await pdfPreview(st.files[0].file, { width: 1000, maxPages: 300 }); }
    catch { toast("Impossible de lire ce PDF.", "error"); return Workspace.landing(); }
    if (this.data.locked) { toast("Ce PDF est protégé : déverrouillez-le d'abord.", "error"); return Workspace.landing(); }
    this.layout();
    if (st.tool.id === "sign" && !st.items.length) this.signatureModal();
  },

  layout() {
    const { tool } = this.st;
    const tools = ["select", ...tool.editor_tools];
    $("#app").innerHTML = `
      <div class="editor" ${toolColorStyle(tool)}>
        <nav class="ed-tools">${tools.map((t) => `<button data-mode="${t}" class="${this.mode === t ? "active" : ""}">${icon(this.TOOLS[t].icon, 20)}<span>${this.TOOLS[t].label}</span></button>`).join("")}</nav>
        <section class="ed-pages" id="ed-pages"></section>
        ${Workspace.sidebar(`<div id="props"></div>`)}
      </div>`;
    $$(".ed-tools button").forEach((b) => (b.onclick = () => this.setMode(b.dataset.mode)));
    const wrap = $("#ed-pages");
    this.data.pages.forEach((p, i) => {
      const pg = el(`<div class="ed-page" data-page="${i}" style="aspect-ratio:${p.w}/${p.h}"><span class="pno">${i + 1}</span><img src="${p.src}" alt=""></div>`);
      this.bindPage(pg, i);
      wrap.appendChild(pg);
    });
    const ro = new ResizeObserver((ents) => ents.forEach((en) => en.target.style.setProperty("--ph", en.contentRect.height + "px")));
    $$(".ed-page").forEach((p) => ro.observe(p));
    this.st.items.forEach((it) => this.mount(it));
    Workspace.bindSidebar(() => {
      const items = this.st.items.map(({ id, ...rest }) => rest);
      if (tool.id !== "redact" && !items.length) { toast("Ajoutez au moins un élément sur le document.", "error"); return null; }
      return { files: [this.st.files[0].file], opts: { items } };
    }, () => `<div class="summary">${this.st.items.length} élément(s) ajouté(s)</div>`);
    this.props();
    document.onkeydown = (e) => {
      if (!location.pathname.startsWith("/outil/") || !$(".editor")) return;
      if ((e.key === "Delete" || e.key === "Backspace") && this.selId && !e.target.isContentEditable && !/INPUT|TEXTAREA/.test(e.target.tagName)) { this.remove(this.selId); e.preventDefault(); }
      if (e.key === "Escape") { this.select(null); this.setMode("select"); }
    };
  },

  setMode(m) {
    if (m === "signature") return this.signatureModal();
    if (m === "image") return this.pickImage();
    this.mode = m;
    this.pending = null;
    $$(".ed-tools button").forEach((b) => b.classList.toggle("active", b.dataset.mode === m));
    $$(".ed-page").forEach((p) => p.classList.toggle("placing", m !== "select"));
  },

  refreshSummary() { const s = $("#summary"); if (s) s.innerHTML = `<div class="summary">${this.st.items.length} élément(s) ajouté(s)</div>`; },

  /* ---------- placement ---------- */
  bindPage(pg, page) {
    pg.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".ed-item")) return;
      const r = pg.getBoundingClientRect();
      const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
      if (this.mode === "select") { this.select(null); return; }
      if (this.mode === "text") {
        const it = this.add({ type: "text", page, x: fx, y: fy - 0.012, text: "Votre texte", size: 0.022, color: "#111111", font: "sans", bold: false });
        this.setMode("select");
        setTimeout(() => this.editText(it.id), 30);
        return;
      }
      if (this.pending) {
        const { src, ratio } = this.pending;
        const w = 0.28, h = (w * r.width) / ratio / r.height;
        this.add({ type: "image", page, x: Math.min(fx - w / 2, 1 - w), y: Math.min(fy - h / 2, 1 - h), w, h, src, ratio });
        this.setMode("select");
        return;
      }
      if (this.mode === "rect" || this.mode === "redact") {
        e.preventDefault();
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
      }
    });
  },

  add(data, mount = true) {
    const it = { id: "i" + Date.now() + Math.random().toString(36).slice(2, 6), ...data };
    this.st.items.push(it);
    if (mount) { this.mount(it); this.select(it.id); this.refreshSummary(); }
    return it;
  },

  remove(id) {
    this.st.items = this.st.items.filter((x) => x.id !== id);
    $(`.ed-item[data-id="${id}"]`)?.remove();
    if (this.selId === id) this.select(null);
    this.refreshSummary();
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

  mount(it) {
    const pg = $(`.ed-page[data-page="${it.page}"]`);
    if (!pg) return null;
    const inner = it.type === "image" ? `<img src="${it.src}" alt="">` : it.type === "text" ? `<div class="txt">${esc(it.text)}</div>` : "";
    const node = el(`<div class="ed-item ${it.type}" data-id="${it.id}">${inner}<span class="h"></span><button class="del" title="Supprimer">${icon("x", 12)}</button></div>`);
    this.place(node, it);
    pg.appendChild(node);
    $(".del", node).onpointerdown = (e) => { e.stopPropagation(); this.remove(it.id); };
    // déplacer
    node.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".h") || e.target.closest(".del")) return;
      if (e.target.isContentEditable) return;
      e.preventDefault();
      this.select(it.id);
      const r = pg.getBoundingClientRect();
      const sx = e.clientX, sy = e.clientY, ox = it.x, oy = it.y;
      const move = (ev) => {
        it.x = Math.max(-0.05, Math.min(0.98, ox + (ev.clientX - sx) / r.width));
        it.y = Math.max(-0.02, Math.min(0.98, oy + (ev.clientY - sy) / r.height));
        this.place(node, it);
      };
      const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
    });
    if (it.type === "text") node.addEventListener("dblclick", () => this.editText(it.id));
    // redimensionner
    $(".h", node).addEventListener("pointerdown", (e) => {
      e.preventDefault(); e.stopPropagation();
      const r = pg.getBoundingClientRect();
      const sx = e.clientX, sy = e.clientY, ow = it.w, oh = it.h, os = it.size;
      const startW = node.getBoundingClientRect().width;
      const move = (ev) => {
        if (it.type === "text") {
          it.size = Math.max(0.006, os * (startW + ev.clientX - sx) / startW);
        } else {
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

  editText(id) {
    const it = this.st.items.find((x) => x.id === id);
    const node = $(`.ed-item[data-id="${id}"] .txt`);
    if (!it || !node) return;
    node.contentEditable = "true";
    node.focus();
    const sel = getSelection(); const rg = document.createRange(); rg.selectNodeContents(node); sel.removeAllRanges(); sel.addRange(rg);
    node.oninput = () => { it.text = node.innerText.replace(/\n$/, ""); };
    node.onblur = () => { node.contentEditable = "false"; if (!it.text.trim()) this.remove(id); };
  },

  select(id) {
    this.selId = id;
    $$(".ed-item").forEach((n) => n.classList.toggle("sel", n.dataset.id === id));
    this.props();
  },

  /* ---------- panneau de propriétés ---------- */
  props() {
    const box = $("#props");
    if (!box) return;
    const it = this.st.items.find((x) => x.id === this.selId);
    const tool = this.st.tool;
    if (!it) {
      const tips = { redact: "Dessinez des zones à caviarder avec l'outil « Zone », et/ou indiquez des mots ci-dessous. Les pages concernées seront converties en image : le texte masqué est réellement supprimé.",
        sign: "Créez votre signature puis cliquez sur la page pour la placer. Déplacez-la et redimensionnez-la avec la poignée.",
        edit: "Choisissez un outil à gauche puis cliquez sur la page. Double-cliquez sur un texte pour le modifier." };
      box.innerHTML = `<div class="summary">${esc(tips[tool.id] || tips.edit)}</div>`;
      return;
    }
    const up = () => { const n = $(`.ed-item[data-id="${it.id}"]`); if (n) this.place(n, it); };
    let html = "";
    if (it.type === "text") {
      html = `<div class="field"><label>Texte</label><textarea class="input" id="p-text" style="min-height:70px">${esc(it.text)}</textarea></div>
        <div class="field"><label>Taille</label><div class="range-row"><input type="range" id="p-size" min="6" max="80" value="${Math.round(it.size * 1000)}"><output>${Math.round(it.size * 1000)}</output></div></div>
        <div class="cz-row"><div class="field"><label>Couleur</label><input type="color" class="input" id="p-color" value="${it.color}"></div>
        <div class="field"><label>Police</label><select class="input" id="p-font"><option value="sans">Sans serif</option><option value="serif">Serif</option><option value="mono">Mono</option></select></div></div>
        <label class="check"><input type="checkbox" id="p-bold" ${it.bold ? "checked" : ""}> Gras</label>`;
    } else if (it.type === "rect") {
      html = `<div class="field"><label>Couleur de la forme</label><input type="color" class="input" id="p-color" value="${it.color}"></div><div class="hint muted" style="font-size:.8rem">Astuce : un rectangle blanc permet de masquer visuellement un élément (pour une suppression réelle, utilisez « Caviarder »).</div>`;
    } else if (it.type === "redact") {
      html = `<div class="summary">Zone de caviardage sur la page ${it.page + 1}.</div>`;
    } else {
      html = `<div class="summary">Image sur la page ${it.page + 1}. Redimensionnez avec la poignée.</div>`;
    }
    html += `<div style="display:flex;gap:.5rem;flex-wrap:wrap">${it.type !== "text" ? `<button class="btn sm" id="p-all">${icon("layers", 14)} Sur toutes les pages</button>` : ""}<button class="btn sm" id="p-dup">Dupliquer</button><button class="btn sm ghost" id="p-del">${icon("trash", 14)} Supprimer</button></div>`;
    box.innerHTML = `<div style="display:flex;flex-direction:column;gap:1rem">${html}</div>`;
    const on = (id, ev, fn) => { const n = $("#" + id, box); if (n) n[ev] = fn; };
    on("p-text", "oninput", (e) => { it.text = e.target.value; const t = $(`.ed-item[data-id="${it.id}"] .txt`); if (t) t.textContent = it.text; });
    on("p-size", "oninput", (e) => { it.size = e.target.value / 1000; e.target.nextElementSibling.textContent = e.target.value; up(); });
    on("p-color", "oninput", (e) => { it.color = e.target.value; up(); });
    on("p-font", "onchange", (e) => { it.font = e.target.value; up(); });
    on("p-bold", "onchange", (e) => { it.bold = e.target.checked; up(); });
    if ($("#p-font", box)) $("#p-font", box).value = it.font || "sans";
    on("p-del", "onclick", () => this.remove(it.id));
    on("p-dup", "onclick", () => { const { id, ...rest } = it; this.add({ ...rest, x: it.x + 0.02, y: it.y + 0.02 }); });
    on("p-all", "onclick", () => {
      const { id, page, ...rest } = it;
      for (let p = 0; p < this.data.pages.length; p++) if (p !== page) this.add({ ...rest, page: p }, false) && this.mount(this.st.items[this.st.items.length - 1]);
      this.refreshSummary();
      toast(`Copié sur ${this.data.pages.length - 1} page(s)`);
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
      // normalise en PNG (gère SVG / WEBP côté serveur)
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
    $$(".ed-tools button").forEach((b) => b.classList.remove("active"));
    $$(".ed-page").forEach((p) => p.classList.add("placing"));
    toast("Cliquez sur la page pour placer l'élément");
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
    const fonts = ['"Brush Script MT", "Segoe Script", cursive', '"Segoe Script", "Lucida Handwriting", cursive', '"Lucida Handwriting", "Apple Chancery", cursive', '"Snell Roundhand", "Zapfino", cursive', 'cursive'];
    let color = colors[0], tab = "draw", font = fonts[0];
    const m = el(`<div class="modal-back"><div class="modal">
      <div class="modal-head"><h3>Votre signature</h3><button class="icon-btn" data-x>${icon("x", 16)}</button></div>
      <div class="modal-body">
        ${saved.length ? `<div class="field" style="margin-bottom:1rem"><span class="field-label">Signatures récentes</span><div class="saved-sigs">${saved.map((s, i) => `<div class="sig" data-i="${i}"><img src="${s}" alt=""></div>`).join("")}</div></div>` : ""}
        <div class="tabs"><button data-tab="draw" class="active">Dessiner</button><button data-tab="type">Taper</button><button data-tab="upload">Importer</button></div>
        <div data-pane="draw"><canvas class="sig-canvas" width="1100" height="400"></canvas></div>
        <div data-pane="type" class="hidden"><input class="input" id="sig-name" placeholder="Votre nom" value=""><div class="sig-fonts">${fonts.map((f, i) => `<button data-f="${i}" class="${i ? "" : "active"}" style="font-family:${f.replace(/"/g, "&quot;")}">Signature</button>`).join("")}</div></div>
        <div data-pane="upload" class="hidden"><button class="btn" id="sig-up">${icon("upload", 16)} Choisir une image (PNG transparent idéal)</button></div>
        <div class="sig-colors"><span class="muted" style="font-size:.85rem;margin-right:.3rem">Couleur</span>${colors.map((c, i) => `<button data-c="${c}" class="${i ? "" : "active"}" style="background:${c}"></button>`).join("")}<span style="flex:1"></span><button class="btn sm ghost" id="sig-clear">Effacer</button></div>
      </div>
      <div class="modal-foot"><button class="btn" data-x>Annuler</button><button class="btn primary" id="sig-ok">Utiliser</button></div>
    </div></div>`);
    document.body.appendChild(m);
    const close = () => m.remove();
    $$("[data-x]", m).forEach((b) => (b.onclick = close));
    m.onclick = (e) => { if (e.target === m) close(); };
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
    $$(".tabs button", m).forEach((b) => (b.onclick = () => {
      tab = b.dataset.tab;
      $$(".tabs button", m).forEach((x) => x.classList.toggle("active", x === b));
      $$("[data-pane]", m).forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== tab));
      if (tab === "type") setTimeout(() => $("#sig-name", m).focus(), 20);
    }));
    const nameIn = $("#sig-name", m);
    nameIn.oninput = () => $$(".sig-fonts button", m).forEach((b) => (b.textContent = nameIn.value || "Signature"));
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
      if (tab === "draw") { if (!dirty) return toast("Dessinez votre signature.", "error"); out = this.trim(cv); }
      else if (tab === "type") {
        if (!nameIn.value.trim()) return toast("Tapez votre nom.", "error");
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
