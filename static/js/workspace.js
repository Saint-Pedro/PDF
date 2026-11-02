/* ============================================================
   Workspace: file selection, file ordering, page editing
   ============================================================ */
const Workspace = {
  state: null,
  uid: 0,

  open(id) {
    const tool = App.toolsById[id];
    if (!tool) { $("#app").innerHTML = `<div class="empty">${esc(t("err.notfound"))} <a href="/" data-nav>${esc(t("back"))}</a></div>`; return; }
    this.state = { tool, files: [], opts: {}, extra: null, layout: null, items: [] };
    if (App.carry) {
      const carried = App.carry; App.carry = null;
      this.addFiles(carried);
      return;
    }
    this.landing();
  },

  restore() { if (this.state && this.state.files.length) this.render(); else if (this.state) this.landing(); },

  acceptAttr(tool) { return tool.accept.map((e) => "." + e).join(","); },

  landing() {
    const { tool } = this.state;
    const pdfOnly = tool.accept.length === 1 && tool.accept[0] === "pdf";
    const label = t(pdfOnly ? (tool.multiple ? "land.pick_pdf_multi" : "land.pick_pdf") : (tool.multiple ? "land.pick_multi" : "land.pick"));
    $("#app").innerHTML = `
      <section class="tool-landing" ${toolColorStyle(tool)}>
        ${!tool.available ? `<div class="notice">${icon("wrench", 20)}<div>${t("land.missing", { x: esc(tool.missing) })}</div></div>` : ""}
        <h1>${esc(tx(tool.title))}</h1>
        <p>${esc(tx(tool.desc))}</p>
        <button class="btn primary big" id="pick" ${tool.available ? "" : "disabled"}>${icon("upload", 22)} ${esc(label)}</button>
        <div class="drop-hint">${esc(t(tool.multiple ? "land.drop_multi" : "land.drop"))}</div>
        ${!pdfOnly ? `<div class="formats">${esc(t("land.formats", { x: tool.accept.map((e) => e.toUpperCase()).join(", ") }))}</div>` : ""}
      </section>`;
    $("#pick").onclick = () => this.pick();
    this.enableDrop();
  },

  pick(onDone) {
    const { tool } = this.state;
    chooseFiles(this.acceptAttr(tool), tool.multiple, onDone || this.addFiles.bind(this));
  },

  enableDrop() {
    let ov = $(".drop-overlay");
    if (!ov) {
      ov = el(`<div class="drop-overlay"><div>${icon("upload", 48)}<span></span></div></div>`);
      document.body.appendChild(ov);
    }
    $("span", ov).textContent = t("drop.overlay");
    let depth = 0;
    const isFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
    const onPage = () => location.pathname.startsWith("/tool/");
    window.ondragenter = (e) => { if (!isFiles(e) || !onPage()) return; depth++; ov.classList.add("show"); };
    window.ondragleave = (e) => { if (!isFiles(e)) return; depth = Math.max(0, depth - 1); if (!depth) ov.classList.remove("show"); };
    window.ondragover = (e) => { if (isFiles(e)) e.preventDefault(); };
    window.ondrop = (e) => {
      if (!isFiles(e)) return;
      e.preventDefault(); depth = 0; ov.classList.remove("show");
      if (!onPage() || !this.state) return;
      this.addFiles([...e.dataTransfer.files]);
    };
  },

  addFiles(list) {
    const { tool } = this.state;
    const ok = [], bad = [];
    for (const f of list) (tool.accept.includes(extOf(f.name)) ? ok : bad).push(f);
    if (bad.length) toast(t("err.format", { x: bad.map((f) => f.name).join(", ") }), "error");
    if (!ok.length) return;
    const add = tool.multiple ? ok : ok.slice(0, 1);
    if (!tool.multiple) this.state.files = [];
    for (const f of add) this.state.files.push({ id: ++this.uid, file: f });
    this.state.layout = null;
    this.state.items = [];
    this.render();
  },

  render() {
    const { tool } = this.state;
    this.enableDrop();
    if (tool.mode === "editor") return Editor.open(this.state);
    if (tool.mode === "pages") return this.renderPages();
    return this.renderFiles();
  },

  /* ---------------- shared sidebar ---------------- */
  sidebar(extraTop = "") {
    const { tool } = this.state;
    return `<aside class="sidebar" ${toolColorStyle(tool)}>
        <div class="sidebar-head"><h2>${esc(tx(tool.title))}</h2><p>${esc(tx(tool.desc))}</p></div>
        <div class="sidebar-body">${extraTop}<div id="opts" style="display:flex;flex-direction:column;gap:1.1rem"></div><div id="summary"></div></div>
        <div class="sidebar-foot"><button class="btn primary block" id="go">${esc(tx(tool.title))} ${icon("arrow-right", 20)}</button></div>
      </aside>`;
  },

  bindSidebar(getPayload, summary) {
    const { tool, opts } = this.state;
    const upd = () => { if (summary) $("#summary").innerHTML = summary(); };
    renderOptions(tool, opts, $("#opts"), upd);
    if (tool.extra_file) {
      const ef = tool.extra_file;
      const f = el(`<div class="field"><span class="field-label">${esc(tx(ef.label))}</span>
        <div style="display:flex;gap:.5rem;align-items:center"><button class="btn sm" type="button" id="extra-btn">${icon("image", 16)} ${esc(t("ws.choose"))}</button><span class="muted" id="extra-name" style="font-size:.85rem">${esc(this.state.extra ? this.state.extra.name : t("ws.none"))}</span>
        <button class="btn sm ghost ${this.state.extra ? "" : "hidden"}" id="extra-clear" type="button">${icon("x", 14)}</button></div></div>`);
      $("#opts").prepend(f);
      $("#extra-btn", f).onclick = () => chooseFiles(ef.accept.map((e) => "." + e).join(","), false, ([file]) => {
        this.state.extra = file; $("#extra-name").textContent = file.name; $("#extra-clear").classList.remove("hidden");
      });
      $("#extra-clear", f).onclick = () => { this.state.extra = null; $("#extra-name").textContent = t("ws.none"); $("#extra-clear").classList.add("hidden"); };
    }
    upd();
    $("#go").onclick = () => {
      const err = validateOptions(tool, opts);
      if (err) return toast(err, "error");
      const payload = getPayload();
      if (!payload) return;
      runTool(tool, payload.files, { ...opts, ...(payload.opts || {}) }, this.state.extra);
    };
  },

  /* ---------------- files mode ---------------- */
  renderFiles() {
    const { tool, files } = this.state;
    const ordered = ["merge", "img_to_pdf", "any_to_pdf"].includes(tool.id);
    $("#app").innerHTML = `
      <div class="workspace">
        <section class="work-area">
          <div class="work-toolbar">
            <b>${esc(t("ws.files", { n: files.length }))}</b>
            ${ordered && files.length > 1 ? `<span class="muted" style="font-size:.85rem">${esc(t("ws.reorder"))}</span>
              <button class="btn sm ghost" id="sort-az">${esc(t("ws.sort"))}</button><button class="btn sm ghost" id="sort-rev">${esc(t("ws.reverse"))}</button>` : ""}
            <span class="spacer"></span>
          </div>
          <div class="file-grid" id="file-grid"></div>
        </section>
        ${this.sidebar()}
      </div>`;
    const grid = $("#file-grid");
    files.forEach((f, i) => grid.appendChild(this.fileCard(f, i, ordered)));
    if (tool.multiple) {
      const add = el(`<button class="add-card">${icon("plus", 32)}<span>${esc(t("ws.add"))}</span></button>`);
      add.onclick = () => this.pick();
      grid.appendChild(add);
    }
    $("#sort-az") && ($("#sort-az").onclick = () => { files.sort((a, b) => a.file.name.localeCompare(b.file.name, undefined, { numeric: true })); this.renderFiles(); });
    $("#sort-rev") && ($("#sort-rev").onclick = () => { files.reverse(); this.renderFiles(); });
    const min = tool.min_files || 1;
    this.bindSidebar(() => {
      if (files.length < min) { toast(t("ws.min_files", { n: min }), "error"); return null; }
      return { files: files.map((f) => f.file) };
    }, () => {
      const total = files.reduce((s, f) => s + f.file.size, 0);
      return `<div class="summary">${esc(t("ws.files", { n: files.length }))} · ${fmtSize(total)}${files.length < min ? `<br><span style="color:var(--primary)">${esc(t("ws.min_files", { n: min }))}</span>` : ""}</div>`;
    });
  },

  fileCard(entry, i, ordered) {
    const f = entry.file;
    const e = extOf(f.name);
    const card = el(`<div class="file-card" draggable="true" data-id="${entry.id}">
        ${ordered ? `<span class="order-badge">${i + 1}</span>` : ""}
        <div class="card-actions"><button title="${esc(t("ws.remove"))}" data-act="rm">${icon("x", 14)}</button></div>
        <div class="thumb"><span class="ext">${icon("file", 34)}${esc(e)}</span></div>
        <div class="name" title="${esc(f.name)}">${esc(f.name)}</div>
        <div class="meta">${fmtSize(f.size)}<span class="pc"></span></div>
      </div>`);
    const thumb = $(".thumb", card);
    if (["jpg", "jpeg", "png", "webp", "gif", "bmp", "svg", "avif"].includes(e)) {
      thumb.innerHTML = `<img src="${URL.createObjectURL(f)}" alt="">`;
    } else if (e === "pdf") {
      pdfPreview(f).then((d) => {
        if (d.locked) { thumb.innerHTML = `<span class="ext">${icon("lock", 34)}${esc(t("ws.locked"))}</span>`; return; }
        thumb.innerHTML = `<img src="${d.pages[0].src}" alt="">`;
        $(".pc", card).textContent = ` · ${t("ws.pages", { n: d.count })}`;
      }).catch(() => {});
    }
    $('[data-act="rm"]', card).onclick = (ev) => {
      ev.stopPropagation();
      this.state.files = this.state.files.filter((x) => x.id !== entry.id);
      this.state.files.length ? this.renderFiles() : this.landing();
    };
    this.makeSortable(card, this.state.files, () => this.renderFiles());
    return card;
  },

  /* Drag-and-drop reordering (file or page cards) */
  makeSortable(card, arr, rerender, key = "id") {
    card.addEventListener("dragstart", (e) => {
      card.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/x-reorder", card.dataset.id);
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
    card.addEventListener("dragover", (e) => {
      if (![...e.dataTransfer.types].includes("text/x-reorder")) return;
      e.preventDefault();
      card.classList.add("drop-before");
    });
    card.addEventListener("dragleave", () => card.classList.remove("drop-before"));
    card.addEventListener("drop", (e) => {
      const from = e.dataTransfer.getData("text/x-reorder");
      if (!from) return;
      e.preventDefault(); e.stopPropagation();
      card.classList.remove("drop-before");
      const fi = arr.findIndex((x) => String(x[key]) === from);
      const ti = arr.findIndex((x) => String(x[key]) === card.dataset.id);
      if (fi < 0 || ti < 0 || fi === ti) return;
      const [m] = arr.splice(fi, 1);
      arr.splice(fi < ti ? ti - 1 : ti, 0, m);
      rerender();
    });
  },

  /* ---------------- pages mode ---------------- */
  async renderPages() {
    const st = this.state;
    const { tool } = st;
    const file = st.files[0].file;
    const action = tool.page_action || "organize";
    $("#app").innerHTML = `<div class="processing"><div class="spinner"></div><h2>${esc(t("pg.loading"))}</h2></div>`;
    let data;
    try { data = await pdfPreview(file, { width: 240, maxPages: 2000 }); }
    catch { toast(t("pg.unreadable"), "error"); return this.landing(); }
    if (data.locked) { toast(t("pg.locked"), "error"); return this.landing(); }
    if (!st.layout) st.layout = data.pages.map((p, i) => ({ key: "p" + i, src: i, rot: 0, removed: false, selected: false }));
    const zoom = st.zoom || 150;
    const L = st.layout;
    const toolbar = {
      organize: `<button class="btn sm" id="rot-all-l">${icon("rotate-ccw", 16)} ${esc(t("pg.rot_all"))}</button><button class="btn sm" id="rot-all-r">${icon("rotate", 16)} ${esc(t("pg.rot_all"))}</button>
                 <button class="btn sm" id="add-blank">${icon("file-plus", 16)} ${esc(t("pg.blank"))}</button><button class="btn sm" id="reverse">${esc(t("pg.reverse"))}</button><button class="btn sm ghost" id="reset">${icon("undo", 16)} ${esc(t("pg.reset"))}</button>`,
      remove: `<input class="input" id="range" placeholder="${esc(t("pg.range_rm"))}" style="width:170px"><button class="btn sm" id="apply-range">${esc(t("pg.mark"))}</button><button class="btn sm ghost" id="reset">${icon("undo", 16)} ${esc(t("pg.keep_all"))}</button>`,
      extract: `<input class="input" id="range" placeholder="${esc(t("pg.range_ex"))}" style="width:170px"><button class="btn sm" id="apply-range">${esc(t("pg.select"))}</button><button class="btn sm" id="sel-all">${esc(t("pg.all"))}</button><button class="btn sm" id="sel-odd">${esc(t("pg.odd"))}</button><button class="btn sm" id="sel-even">${esc(t("pg.even"))}</button><button class="btn sm ghost" id="reset">${esc(t("pg.none"))}</button>`,
    }[action];
    const tip = { organize: "pg.tip_org", remove: "pg.tip_rm", extract: "pg.tip_ex" }[action];
    $("#app").innerHTML = `
      <div class="workspace">
        <section class="work-area">
          <div class="work-toolbar">${toolbar}<span class="spacer"></span>
            <label class="muted" style="display:flex;gap:.4rem;align-items:center;font-size:.85rem">${icon("search", 14)}<input type="range" min="100" max="300" value="${zoom}" id="zoom" style="width:110px"></label></div>
          <p class="muted" style="margin:-.4rem 0 1rem;font-size:.85rem">${esc(t(tip))}</p>
          <div class="page-grid" id="page-grid" style="--page-w:${zoom}px"></div>
        </section>
        ${this.sidebar()}
      </div>`;
    const grid = $("#page-grid");
    const redraw = () => this.renderPages();
    L.forEach((it, idx) => {
      const p = it.blank ? null : data.pages[it.src];
      const card = el(`<div class="page-card ${it.removed ? "removed" : ""} ${it.selected ? "selected" : ""}" draggable="${action === "organize"}" data-id="${it.key}">
          <div class="card-actions">${action === "organize" ? `<button data-a="l" title="${esc(t("pg.rot_l"))}">${icon("rotate-ccw", 14)}</button><button data-a="r" title="${esc(t("pg.rot_r"))}">${icon("rotate", 14)}</button><button data-a="d" title="${esc(t("pg.del"))}">${icon("trash", 14)}</button>` : ""}</div>
          <div class="pthumb">${p ? `<img src="${p.src}" style="transform:rotate(${it.rot}deg) scale(${it.rot % 180 ? p.w / p.h : 1})" alt="">` : `<div class="blank-page">${esc(t("pg.blank_page"))}</div>`}</div>
          <div class="pnum">${it.blank ? esc(t("pg.blank_lbl")) : it.src + 1}</div>
        </div>`);
      if (action === "organize") {
        card.querySelector('[data-a="l"]').onclick = (e) => { e.stopPropagation(); it.rot = (it.rot + 270) % 360; redraw(); };
        card.querySelector('[data-a="r"]').onclick = (e) => { e.stopPropagation(); it.rot = (it.rot + 90) % 360; redraw(); };
        card.querySelector('[data-a="d"]').onclick = (e) => { e.stopPropagation(); L.splice(idx, 1); redraw(); };
        this.makeSortable(card, L, redraw, "key");
      } else {
        card.onclick = () => {
          if (action === "remove") it.removed = !it.removed; else it.selected = !it.selected;
          card.classList.toggle(action === "remove" ? "removed" : "selected");
          upd();
        };
      }
      grid.appendChild(card);
    });
    const parse = (spec) => {
      const n = data.count, set = new Set();
      for (const part of spec.split(/[,;]/)) {
        const m = part.trim().match(/^(\d*)\s*-\s*(\d*)$/);
        if (m) { const a = +(m[1] || 1), b = +(m[2] || n); for (let k = a; k <= Math.min(b, n); k++) set.add(k - 1); }
        else if (/^\d+$/.test(part.trim())) set.add(+part.trim() - 1);
      }
      return set;
    };
    const bind = (id, fn) => { const b = $("#" + id); if (b) b.onclick = () => { fn(); redraw(); }; };
    bind("rot-all-l", () => L.forEach((x) => (x.rot = (x.rot + 270) % 360)));
    bind("rot-all-r", () => L.forEach((x) => (x.rot = (x.rot + 90) % 360)));
    bind("add-blank", () => L.push({ key: "b" + Date.now(), blank: true, rot: 0 }));
    bind("reverse", () => L.reverse());
    bind("reset", () => { st.layout = null; });
    bind("sel-all", () => L.forEach((x) => (x.selected = true)));
    bind("sel-odd", () => L.forEach((x) => (x.selected = x.src % 2 === 0)));
    bind("sel-even", () => L.forEach((x) => (x.selected = x.src % 2 === 1)));
    bind("apply-range", () => { const s = parse($("#range").value); L.forEach((x) => { if (s.has(x.src)) action === "remove" ? (x.removed = true) : (x.selected = true); }); });
    $("#zoom").oninput = (e) => { st.zoom = +e.target.value; grid.style.setProperty("--page-w", e.target.value + "px"); };

    const finalLayout = () => {
      if (action === "remove") return L.filter((x) => !x.removed);
      if (action === "extract") return L.filter((x) => x.selected);
      return L;
    };
    const upd = () => {
      const fl = finalLayout();
      const key = { remove: "pg.sum_rm", extract: "pg.sum_ex", organize: "pg.sum_org" }[action];
      const vars = action === "remove" ? { a: L.length - fl.length, b: fl.length } : action === "extract" ? { a: fl.length, b: L.length } : { a: fl.length };
      $("#summary").innerHTML = `<div class="summary">${t(key, vars)}</div>`;
    };
    this.bindSidebar(() => {
      const fl = finalLayout();
      if (!fl.length) { toast(t(action === "extract" ? "pg.need_one" : "pg.not_empty"), "error"); return null; }
      return { files: [file], opts: { layout: fl.map((x) => (x.blank ? { blank: true } : { src: x.src, rot: x.rot })) } };
    }, null);
    upd();
  },
};
