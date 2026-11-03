/* ============================================================
   Workspace: file selection, file ordering, page editing
   ============================================================ */
const Workspace = {
  state: null,
  uid: 0,

  open(id) {
    const tool = App.toolsById[id];
    if (!tool) return renderNotFound();
    this.state = { tool, files: [], opts: {}, extra: null, layout: null, items: [] };
    if (App.carry) {
      const carried = App.carry; App.carry = null;
      this.addFiles(carried);
      return;
    }
    this.landing();
  },

  restore() {
    activeHistory = null;
    if (!this.state) return;
    if (this.state.tool.mode === "url" && this.state.opts.url) return this.render();
    if (this.state.files.length) this.render(); else this.landing();
  },

  acceptAttr(tool) { return tool.accept.map((e) => "." + e).join(","); },

  landing() {
    const { tool } = this.state;
    if (tool.mode === "url") return this.urlLanding();
    const pdfOnly = tool.accept.length === 1 && tool.accept[0] === "pdf";
    const label = t(pdfOnly ? (tool.multiple ? "land.pick_pdf_multi" : "land.pick_pdf") : (tool.multiple ? "land.pick_multi" : "land.pick"));
    $("#app").innerHTML = `
      <section class="tool-landing" ${toolColorStyle(tool)}>
        ${!tool.available ? `<div class="notice">${icon("wrench", 20)}<div>${t("land.missing", { x: esc(tool.missing) })}</div></div>` : ""}
        ${toolIcon(tool, 30)}
        <h1>${esc(tx(tool.title))}</h1>
        <p>${esc(tx(tool.desc))}</p>
        <button class="btn primary big" id="pick" ${tool.available ? "" : "disabled"}>${icon("upload", 22)} ${esc(label)}</button>
        <div class="drop-hint">${esc(t(tool.multiple ? "land.drop_multi" : "land.drop"))}</div>
        ${!pdfOnly ? `<div class="formats">${esc(t("land.formats", { x: tool.accept.map((e) => e.toUpperCase()).join(", ") }))}</div>` : ""}
        ${ClientOps.supports(tool, [{ name: "a.pdf" }], {}) ? `<div class="local-note">${icon("shield", 14)} ${esc(t("ws.local"))}</div>` : ""}
      </section>`;
    $("#pick").onclick = () => this.pick();
    $("#pick").focus();
    this.enableDrop();
  },

  urlLanding() {
    const { tool, opts } = this.state;
    $("#app").innerHTML = `
      <section class="tool-landing" ${toolColorStyle(tool)}>
        ${!tool.available ? `<div class="notice">${icon("wrench", 20)}<div>${t("land.missing", { x: esc(tool.missing) })}</div></div>` : ""}
        ${toolIcon(tool, 30)}
        <h1>${esc(tx(tool.title))}</h1>
        <p>${esc(tx(tool.desc))}</p>
        <form class="url-form" id="url-form">
          <label class="sr" for="url-in">${esc(tx("Web address"))}</label>
          <input class="input big" id="url-in" type="url" inputmode="url" autocomplete="url" required placeholder="${esc(t("url.placeholder"))}" value="${esc(opts.url || "")}" ${tool.available ? "" : "disabled"}>
          <button class="btn primary big" ${tool.available ? "" : "disabled"}>${esc(t("url.go"))} ${icon("arrow-right", 20)}</button>
        </form>
        <div class="drop-hint">${esc(t("url.note"))}</div>
      </section>`;
    $("#url-in").focus();
    $("#url-form").onsubmit = (e) => {
      e.preventDefault();
      let v = $("#url-in").value.trim();
      if (v && !/^https?:\/\//i.test(v)) v = "https://" + v;
      try { const u = new URL(v); if (!/^https?:$/.test(u.protocol) || !u.hostname.includes(".") && u.hostname !== "localhost") throw 0; }
      catch { return toast(t("url.invalid"), "error"); }
      opts.url = v;
      this.render();
    };
  },

  pick(onDone) {
    const { tool } = this.state;
    chooseFiles(this.acceptAttr(tool), tool.multiple, onDone || this.addFiles.bind(this));
  },

  enableDrop() {
    let ov = $(".drop-overlay");
    if (!ov) {
      ov = el(`<div class="drop-overlay" aria-hidden="true"><div>${mascot()}<span></span></div></div>`);
      document.body.appendChild(ov);
    }
    $("span", ov).textContent = t("drop.overlay");
    let depth = 0;
    const isFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
    const onPage = () => location.pathname.startsWith("/tool/") && this.state?.tool.mode !== "url";
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
    for (const f of add) this.state.files.push({ id: String(++this.uid), file: f });
    Object.assign(this.state, { layout: null, items: [], view: null, history: null });
    this.render();
  },

  render() {
    const { tool } = this.state;
    this.enableDrop();
    activeHistory = null;
    if (tool.mode === "editor") return Editor.open(this.state);
    if (tool.mode === "pages") return this.renderPages();
    if (tool.mode === "url") return this.renderUrl();
    return this.renderFiles();
  },

  /* ---------------- shared sidebar ---------------- */
  sidebar(extraTop = "") {
    const { tool } = this.state;
    return `<aside class="sidebar" ${toolColorStyle(tool)} aria-label="${esc(tx(tool.title))}">
        <div class="sidebar-head"><h2>${esc(tx(tool.title))}</h2><p>${esc(tx(tool.desc))}</p></div>
        <div class="sidebar-body">${extraTop}<div id="opts" class="opts"></div><div id="summary" aria-live="polite"></div></div>
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
        <div class="row"><button class="btn sm" type="button" id="extra-btn">${icon("image", 16)} ${esc(t("ws.choose"))}</button><span class="muted small" id="extra-name">${esc(this.state.extra ? this.state.extra.name : t("ws.none"))}</span>
        <button class="btn sm ghost ${this.state.extra ? "" : "hidden"}" id="extra-clear" type="button" aria-label="${esc(t("ws.remove"))}">${icon("x", 14)}</button></div></div>`);
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

  /* ---------------- URL mode ---------------- */
  renderUrl() {
    const { tool, opts } = this.state;
    $("#app").innerHTML = `
      <div class="workspace">
        <section class="work-area">
          <div class="url-card">${icon("globe", 28)}<div><div class="muted small">${esc(tx("Web address"))}</div><b>${esc(opts.url)}</b></div>
            <button class="btn sm ghost" id="url-edit">${icon("pen", 14)}</button></div>
          <div class="render-help">
            ${["screen", "single", "print"].map((m) => `<div class="render-demo ${opts.render === m ? "on" : ""}" data-m="${m}"><div class="mock mock-${m}"><span></span><span></span><span></span></div><small>${esc(tx({ screen: "As on screen", single: "One long page", print: "Print version" }[m]))}</small></div>`).join("")}
          </div>
        </section>
        ${this.sidebar()}
      </div>`;
    $("#url-edit").onclick = () => this.urlLanding();
    this.bindSidebar(() => ({ files: [] }), () => {
      $$(".render-demo").forEach((d) => d.classList.toggle("on", d.dataset.m === opts.render));
      return "";
    });
  },

  /* ---------------- files mode ---------------- */
  renderFiles(focusId = null) {
    const { tool, files } = this.state;
    const ordered = ["merge", "img_to_pdf", "any_to_pdf"].includes(tool.id);
    $("#app").innerHTML = `
      <div class="workspace">
        <section class="work-area">
          <div class="work-toolbar">
            <b>${esc(t("ws.files", { n: files.length }))}</b>
            ${ordered && files.length > 1 ? `<span class="muted small">${esc(t("ws.reorder"))}</span>
              <button class="btn sm ghost" id="sort-az">${esc(t("ws.sort"))}</button><button class="btn sm ghost" id="sort-rev">${esc(t("ws.reverse"))}</button>` : ""}
            <span class="spacer"></span>
          </div>
          <div class="file-grid" id="file-grid" role="list" aria-label="${esc(t("ws.files", { n: files.length }))}"></div>
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
    const reorder = (fn) => flip("file-grid", () => { fn(); this.renderFiles(); });
    $("#sort-az") && ($("#sort-az").onclick = () => reorder(() => files.sort((a, b) => a.file.name.localeCompare(b.file.name, undefined, { numeric: true }))));
    $("#sort-rev") && ($("#sort-rev").onclick = () => reorder(() => files.reverse()));
    const min = tool.min_files || 1;
    this.bindSidebar(() => {
      if (files.length < min) { toast(t("ws.min_files", { n: min }), "error"); return null; }
      return { files: files.map((f) => f.file) };
    }, () => {
      const total = files.reduce((s, f) => s + f.file.size, 0);
      const local = ClientOps.supports(tool, files.map((f) => f.file), this.state.opts);
      return `<div class="summary">${esc(t("ws.files", { n: files.length }))} · ${fmtSize(total)}${files.length < min ? `<br><span class="warn">${esc(t("ws.min_files", { n: min }))}</span>` : ""}${local ? `<div class="local-note">${icon("shield", 14)} ${esc(t("ws.local"))}</div>` : ""}</div>`;
    });
    if (focusId) $(`.file-card[data-id="${focusId}"]`)?.focus();
  },

  fileCard(entry, i, ordered) {
    const f = entry.file;
    const e = extOf(f.name);
    const card = el(`<div class="file-card" draggable="true" data-id="${entry.id}" tabindex="0" role="listitem" aria-label="${esc(f.name)}${ordered ? `, ${i + 1}` : ""}">
        ${ordered ? `<span class="order-badge" aria-hidden="true">${i + 1}</span>` : ""}
        <div class="card-actions"><button title="${esc(t("ws.remove"))}" aria-label="${esc(t("ws.remove"))} ${esc(f.name)}" data-act="rm" tabindex="-1">${icon("x", 14)}</button></div>
        <div class="thumb skeleton"><span class="ext">${icon("file", 34)}${esc(e)}</span></div>
        <div class="name" title="${esc(f.name)}">${esc(f.name)}</div>
        <div class="meta">${fmtSize(f.size)}<span class="pc"></span></div>
      </div>`);
    const thumb = $(".thumb", card);
    if (["jpg", "jpeg", "png", "webp", "gif", "bmp", "svg", "avif"].includes(e)) {
      const img = el(`<img alt="">`);
      img.onload = () => thumb.classList.remove("skeleton");
      img.src = URL.createObjectURL(f);
      thumb.innerHTML = "";
      thumb.appendChild(img);
    } else if (e === "pdf") {
      PDFView.open(f).then(async (v) => {
        $(".pc", card).textContent = ` · ${t("ws.pages", { n: v.count })}`;
        const url = await v.thumb(0, 170);
        thumb.innerHTML = `<img src="${url}" alt="">`;
        thumb.classList.remove("skeleton");
      }).catch((err) => {
        thumb.classList.remove("skeleton");
        if (err && err.locked) thumb.innerHTML = `<span class="ext">${icon("lock", 34)}${esc(t("ws.locked"))}</span>`;
      });
    } else {
      thumb.classList.remove("skeleton");
    }
    const remove = () => {
      const idx = this.state.files.findIndex((x) => x.id === entry.id);
      this.state.files.splice(idx, 1);
      announce(`${f.name}: ${t("kb.removed")}`);
      if (!this.state.files.length) return this.landing();
      const nextId = (this.state.files[idx] || this.state.files[idx - 1]).id;
      flip("file-grid", () => this.renderFiles(nextId));
    };
    $('[data-act="rm"]', card).onclick = (ev) => { ev.stopPropagation(); remove(); };
    card.addEventListener("keydown", (ev) => this.cardKeys(ev, card, this.state.files, "file-grid", (id) => this.renderFiles(id), { remove }));
    this.makeSortable(card, this.state.files, () => this.renderFiles());
    return card;
  },

  /* Keyboard: arrows move focus; Ctrl/Alt + arrows move the item; Delete removes. */
  cardKeys(ev, card, arr, gridId, rerender, actions = {}) {
    if (typingTarget(ev)) return;
    const cards = $$(`#${gridId} [data-id]`);
    const idx = cards.indexOf(card);
    const cols = Math.max(1, cards.filter((c) => c.offsetTop === cards[0].offsetTop).length);
    const delta = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -cols, ArrowDown: cols, Home: -idx, End: cards.length - 1 - idx }[ev.key];
    if (delta !== undefined) {
      ev.preventDefault();
      const target = Math.max(0, Math.min(cards.length - 1, idx + delta));
      if ((ev.ctrlKey || ev.metaKey || ev.altKey) && arr && target !== idx) {
        actions.before?.();
        const [m] = arr.splice(idx, 1);
        arr.splice(target, 0, m);
        flip(gridId, () => rerender(card.dataset.id));
        announce(t("kb.moved", { n: target + 1 }));
      } else {
        cards[target]?.focus();
      }
      return;
    }
    if ((ev.key === "Delete" || ev.key === "Backspace") && actions.remove) { ev.preventDefault(); actions.remove(); }
    else if ((ev.key === "r" || ev.key === "R") && actions.rotate) { ev.preventDefault(); actions.rotate(ev.shiftKey ? -90 : 90); }
    else if ((ev.key === " " || ev.key === "Enter") && actions.toggle) { ev.preventDefault(); actions.toggle(); }
  },

  /* Drag-and-drop reordering (file or page cards) */
  makeSortable(card, arr, rerender, key = "id", before = null) {
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
      before?.();
      const [m] = arr.splice(fi, 1);
      arr.splice(fi < ti ? ti - 1 : ti, 0, m);
      flip(card.parentElement.id, rerender);
    });
  },

  /* ---------------- pages mode ---------------- */
  async renderPages(focusId = null) {
    const st = this.state;
    const { tool } = st;
    const file = st.files[0].file;
    const action = tool.page_action || "organize";
    if (!st.view) {
      $("#app").innerHTML = `<div class="processing"><div class="mascot-spin">${mascot()}</div><h2>${esc(t("pg.loading"))}</h2></div>`;
      try { st.view = await PDFView.open(file); }
      catch (err) { toast(t(err && err.locked ? "pg.locked" : "pg.unreadable"), "error"); st.files = []; return this.landing(); }
    }
    const view = st.view;
    if (!st.layout) st.layout = [...Array(view.count).keys()].map((i) => ({ key: "p" + i, src: i, rot: 0, removed: false, selected: false }));
    if (!st.history) {
      st.history = new History(() => st.layout, (v) => { st.layout = v; this.renderPages(); });
    }
    activeHistory = st.history;
    const zoom = st.zoom || 150;
    const L = st.layout;
    const toolbar = {
      organize: `<button class="btn sm" id="rot-all-l">${icon("rotate-ccw", 16)} ${esc(t("pg.rot_all_l"))}</button><button class="btn sm" id="rot-all-r">${icon("rotate", 16)} ${esc(t("pg.rot_all_r"))}</button>
                 <button class="btn sm" id="add-blank">${icon("file-plus", 16)} ${esc(t("pg.blank"))}</button><button class="btn sm" id="reverse">${esc(t("pg.reverse"))}</button><button class="btn sm ghost" id="reset">${icon("refresh", 16)} ${esc(t("pg.reset"))}</button>`,
      remove: `<label class="sr" for="range">${esc(t("pg.range_rm"))}</label><input class="input" id="range" placeholder="${esc(t("pg.range_rm"))}" style="width:170px"><button class="btn sm" id="apply-range">${esc(t("pg.mark"))}</button><button class="btn sm ghost" id="reset">${icon("refresh", 16)} ${esc(t("pg.keep_all"))}</button>`,
      extract: `<label class="sr" for="range">${esc(t("pg.range_ex"))}</label><input class="input" id="range" placeholder="${esc(t("pg.range_ex"))}" style="width:170px"><button class="btn sm" id="apply-range">${esc(t("pg.select"))}</button><button class="btn sm" id="sel-all">${esc(t("pg.all"))}</button><button class="btn sm" id="sel-odd">${esc(t("pg.odd"))}</button><button class="btn sm" id="sel-even">${esc(t("pg.even"))}</button><button class="btn sm ghost" id="reset">${esc(t("pg.none"))}</button>`,
    }[action];
    const tip = { organize: "pg.tip_org", remove: "pg.tip_rm", extract: "pg.tip_ex" }[action];
    $("#app").innerHTML = `
      <div class="workspace">
        <section class="work-area">
          <div class="work-toolbar">${historyButtons()}${toolbar}<span class="spacer"></span>
            <label class="muted zoom">${icon("search", 14)}<span class="sr">Zoom</span><input type="range" min="100" max="300" value="${zoom}" id="zoom"></label></div>
          <p class="muted small tip">${esc(t(tip))}</p>
          <div class="page-grid" id="page-grid" role="list" style="--page-w:${zoom}px"></div>
        </section>
        ${this.sidebar()}
      </div>`;
    const syncHist = bindHistoryButtons(st.history);
    st.history.onChange = syncHist;
    const grid = $("#page-grid");
    const redraw = (fid) => this.renderPages(fid);
    const push = () => st.history.push();
    L.forEach((it, idx) => {
      const sz = it.blank ? null : view.size(it.src);
      const label = it.blank ? t("pg.blank_lbl") : t("pg.page", { n: it.src + 1 });
      const state = action === "remove" ? (it.removed ? `, ${t("kb.removed")}` : "") : action === "extract" ? `, ${t(it.selected ? "kb.selected" : "kb.unselected")}` : "";
      const card = el(`<div class="page-card ${it.removed ? "removed" : ""} ${it.selected ? "selected" : ""}" draggable="${action === "organize"}" data-id="${it.key}" tabindex="0" role="listitem"
            ${action !== "organize" ? `aria-pressed="${action === "remove" ? !!it.removed : !!it.selected}"` : ""} aria-label="${esc(label + state)}">
          <div class="card-actions">${action === "organize" ? `<button data-a="l" tabindex="-1" title="${esc(t("pg.rot_l"))}" aria-label="${esc(t("pg.rot_l"))}">${icon("rotate-ccw", 14)}</button><button data-a="r" tabindex="-1" title="${esc(t("pg.rot_r"))}" aria-label="${esc(t("pg.rot_r"))}">${icon("rotate", 14)}</button><button data-a="d" tabindex="-1" title="${esc(t("pg.del"))}" aria-label="${esc(t("pg.del"))}">${icon("trash", 14)}</button>` : ""}</div>
          <div class="pthumb">${sz ? `<div class="pframe skeleton" style="aspect-ratio:${sz.w}/${sz.h};transform:rotate(${it.rot}deg) scale(${it.rot % 180 ? Math.min(sz.w / sz.h, sz.h / sz.w) : 1})"><img alt=""></div>` : `<div class="blank-page">${esc(t("pg.blank_lbl"))}</div>`}</div>
          <div class="pnum" aria-hidden="true">${it.blank ? esc(t("pg.blank_lbl")) : it.src + 1}</div>
        </div>`);
      if (sz) LazyThumbs.watch($("img", card), () => view.thumb(it.src, 260));
      const rotate = (deg) => { push(); it.rot = (it.rot + deg + 360) % 360; redraw(it.key); announce(t("kb.rotated")); };
      const remove = () => {
        push();
        L.splice(idx, 1);
        const nxt = L[idx] || L[idx - 1];
        flip("page-grid", () => redraw(nxt && nxt.key));
        announce(t("kb.removed"));
      };
      const toggle = () => {
        push();
        if (action === "remove") it.removed = !it.removed; else it.selected = !it.selected;
        card.classList.toggle(action === "remove" ? "removed" : "selected");
        card.setAttribute("aria-pressed", String(action === "remove" ? it.removed : it.selected));
        announce(t(action === "remove" ? (it.removed ? "kb.removed" : "kb.unselected") : (it.selected ? "kb.selected" : "kb.unselected")));
        upd();
      };
      if (action === "organize") {
        card.querySelector('[data-a="l"]').onclick = (e) => { e.stopPropagation(); rotate(-90); };
        card.querySelector('[data-a="r"]').onclick = (e) => { e.stopPropagation(); rotate(90); };
        card.querySelector('[data-a="d"]').onclick = (e) => { e.stopPropagation(); remove(); };
        this.makeSortable(card, L, () => redraw(), "key", push);
        card.addEventListener("keydown", (ev) => this.cardKeys(ev, card, L, "page-grid", redraw, { remove, rotate, before: push }));
      } else {
        card.onclick = toggle;
        card.addEventListener("keydown", (ev) => this.cardKeys(ev, card, null, "page-grid", redraw, { toggle }));
      }
      grid.appendChild(card);
    });
    const bind = (id, fn) => { const b = $("#" + id); if (b) b.onclick = () => { push(); fn(); redraw(); }; };
    bind("rot-all-l", () => L.forEach((x) => (x.rot = (x.rot + 270) % 360)));
    bind("rot-all-r", () => L.forEach((x) => (x.rot = (x.rot + 90) % 360)));
    bind("add-blank", () => L.push({ key: "b" + Date.now(), blank: true, rot: 0 }));
    bind("reverse", () => L.reverse());
    bind("reset", () => { st.layout = null; });
    bind("sel-all", () => L.forEach((x) => (x.selected = true)));
    bind("sel-odd", () => L.forEach((x) => (x.selected = x.src % 2 === 0)));
    bind("sel-even", () => L.forEach((x) => (x.selected = x.src % 2 === 1)));
    bind("apply-range", () => { const s = new Set(parseRanges($("#range").value, view.count)); L.forEach((x) => { if (s.has(x.src)) action === "remove" ? (x.removed = true) : (x.selected = true); }); });
    $("#zoom").oninput = (e) => { st.zoom = +e.target.value; grid.style.setProperty("--page-w", e.target.value + "px"); };

    const finalLayout = () => {
      if (action === "remove") return L.filter((x) => !x.removed);
      if (action === "extract") return L.filter((x) => x.selected);
      return L;
    };
    const upd = () => {
      const fl = finalLayout();
      const key = { remove: "pg.sum_rm", extract: "pg.sum_ex", organize: "pg.sum_org" }[action];
      const vars = action === "remove" ? { n: L.length - fl.length, m: fl.length } : action === "extract" ? { n: fl.length, m: L.length } : { n: fl.length };
      $("#summary").innerHTML = `<div class="summary">${t(key, vars)}<div class="local-note">${icon("shield", 14)} ${esc(t("ws.local"))}</div></div>`;
    };
    this.bindSidebar(() => {
      const fl = finalLayout();
      if (!fl.length) { toast(t(action === "extract" ? "pg.need_one" : "pg.not_empty"), "error"); return null; }
      return { files: [file], opts: { layout: fl.map((x) => (x.blank ? { blank: true } : { src: x.src, rot: x.rot })) } };
    }, null);
    upd();
    if (focusId) $(`.page-card[data-id="${focusId}"]`)?.focus();
  },
};
