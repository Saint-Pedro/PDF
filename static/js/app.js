/* ============================================================
   PDF Studio — UI core (router, home, jobs, results)
   ============================================================ */
const App = {
  config: null,
  branding: window.__BRANDING__ || {},
  toolsById: {},
  homeFilter: { cat: "all", q: "" },
  carry: null, // file handed from one tool to the next
  installPrompt: null,
};

/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function el(html) { const tp = document.createElement("template"); tp.innerHTML = html.trim(); return tp.content.firstElementChild; }
function fmtSize(b) {
  if (b < 1024) return `${b} ${t("size.b")}`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} ${t("size.kb")}`;
  return `${(b / 1048576).toFixed(1)} ${t("size.mb")}`;
}
const extOf = (name) => (name.split(".").pop() || "").toLowerCase();
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
function toast(msg, type = "") {
  const n = el(`<div class="toast ${type}" role="${type === "error" ? "alert" : "status"}">${esc(msg)}</div>`);
  $("#toasts").appendChild(n);
  setTimeout(() => n.remove(), type === "error" ? 6000 : 3200);
}
/* Screen-reader announcement */
function announce(msg) {
  const live = $("#sr-live");
  if (!live) return;
  live.textContent = "";
  setTimeout(() => (live.textContent = msg), 30);
}
const typingTarget = (e) => e.target.isContentEditable || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);
/* File picker (input attached to the DOM: required by some browsers) */
function chooseFiles(accept, multiple, cb) {
  const inp = el(`<input type="file" class="sr" ${multiple ? "multiple" : ""} accept="${accept}">`);
  document.body.appendChild(inp);
  inp.onchange = () => { const f = [...inp.files]; inp.remove(); if (f.length) cb(f); };
  inp.click();
}
function nav(path) { history.pushState({}, "", path); route(); window.scrollTo(0, 0); }
document.addEventListener("click", (e) => {
  const a = e.target.closest("a[data-nav]");
  if (a && !e.metaKey && !e.ctrlKey) { e.preventDefault(); nav(a.getAttribute("href")); }
});
window.addEventListener("popstate", () => route());

/* Undo / redo history of JSON-serialisable state */
class History {
  constructor(get, set, onChange = () => {}) { this.get = get; this.set = set; this.onChange = onChange; this.past = []; this.future = []; }
  push() { this.past.push(JSON.stringify(this.get())); if (this.past.length > 100) this.past.shift(); this.future = []; this.onChange(); }
  undo() { if (!this.past.length) return; this.future.push(JSON.stringify(this.get())); this.set(JSON.parse(this.past.pop())); this.onChange(); }
  redo() { if (!this.future.length) return; this.past.push(JSON.stringify(this.get())); this.set(JSON.parse(this.future.pop())); this.onChange(); }
  get canUndo() { return this.past.length > 0; }
  get canRedo() { return this.future.length > 0; }
}
let activeHistory = null; // the History bound to the current view (Ctrl+Z / Ctrl+Y)
document.addEventListener("keydown", (e) => {
  if (!activeHistory || typingTarget(e) || !(e.ctrlKey || e.metaKey)) return;
  const k = e.key.toLowerCase();
  if (k === "z" && !e.shiftKey) { e.preventDefault(); activeHistory.undo(); }
  else if ((k === "z" && e.shiftKey) || k === "y") { e.preventDefault(); activeHistory.redo(); }
});
function historyButtons() {
  return `<span class="hist"><button class="icon-btn sm" id="undo-btn" title="${esc(t("undo"))} (Ctrl+Z)" aria-label="${esc(t("undo"))}">${icon("undo", 16)}</button>
    <button class="icon-btn sm" id="redo-btn" title="${esc(t("redo"))} (Ctrl+Y)" aria-label="${esc(t("redo"))}">${icon("redo", 16)}</button></span>`;
}
function bindHistoryButtons(h) {
  const sync = () => { const u = $("#undo-btn"), r = $("#redo-btn"); if (u) u.disabled = !h.canUndo; if (r) r.disabled = !h.canRedo; };
  if ($("#undo-btn")) $("#undo-btn").onclick = () => h.undo();
  if ($("#redo-btn")) $("#redo-btn").onclick = () => h.redo();
  sync();
  return sync;
}

/* FLIP animation for re-ordered cards: flip("file-grid", () => rerender()) */
function flip(containerId, render) {
  const c = $("#" + containerId);
  const before = new Map(c ? $$("[data-id]", c).map((n) => [n.dataset.id, n.getBoundingClientRect()]) : []);
  render();
  const c2 = $("#" + containerId);
  if (!c2 || reducedMotion()) return;
  for (const n of $$("[data-id]", c2)) {
    const b = before.get(n.dataset.id);
    if (!b) continue;
    const a = n.getBoundingClientRect();
    const dx = b.left - a.left, dy = b.top - a.top;
    if (!dx && !dy) continue;
    n.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], { duration: 220, easing: "cubic-bezier(.2,.7,.2,1)" });
  }
}

function visibleTools() {
  const hidden = new Set(App.branding.hidden_tools || []);
  return App.config.tools.filter((tl) => !hidden.has(tl.id));
}
const toolColorStyle = (tl) => `style="--tc:${tl.color}"`;
function toolIcon(tl, size = 26) {
  return `<div class="tool-icon" aria-hidden="true">${icon(tl.icon, size)}${tl.badge ? `<span class="tool-badge">${esc(tl.badge)}</span>` : ""}</div>`;
}
function mascot(cls = "", alt = "") {
  return `<img class="mascot ${cls}" src="${esc(App.branding.mascot || "/static/img/mascot.png")}" alt="${esc(alt)}" ${alt ? "" : 'aria-hidden="true"'} width="96" height="96">`;
}

/* ---------- light / dark (per viewer) ---------- */
function viewerMode() { try { return localStorage.getItem("viewer-mode"); } catch { return null; } }
function applyBranding(b = App.branding) {
  Theme.apply(b, viewerMode());
  const fav = $("#favicon");
  if (fav) fav.href = b.favicon || b.logo || "/static/img/favicon.svg";
  document.title = `${b.name}${b.tagline ? " — " + tx(b.tagline) : ""}`;
}

/* ---------- header / footer ---------- */
function brandHTML(b = App.branding) {
  const logo = b.logo ? `<img src="${esc(b.logo)}" alt="">` : `<span class="brand-mark">${icon("file")}</span>`;
  return `${logo}${b.show_name !== false || !b.logo ? `<span>${esc(b.name)}</span>` : ""}`;
}
function renderHeader() {
  const cats = App.config.categories.map((c) => `<a href="/?cat=${c.id}" data-nav>${esc(tx(c.label))}</a>`).join("");
  const dark = document.documentElement.dataset.mode === "dark";
  const langs = (App.branding.languages || SUPPORTED_LANGS).filter((l) => SUPPORTED_LANGS.includes(l));
  const cur = Lang.get();
  $("#topbar").innerHTML = `
    <a class="skip-link" href="#app">${esc(t("nav.skip"))}</a>
    <a class="brand" href="/" data-nav aria-label="${esc(App.branding.name)}">${brandHTML()}</a>
    <nav class="nav" aria-label="${esc(t("home.all"))}">${cats}</nav>
    <div class="top-actions">
      ${App.installPrompt ? `<button class="btn sm" id="install-btn">${icon("download", 16)}<span>${esc(t("pwa.install"))}</span></button>` : ""}
      ${langs.length > 1 ? `<div class="lang-menu">
        <button class="lang-btn" id="lang-btn" aria-haspopup="menu" aria-expanded="false" aria-label="${esc(t("nav.language"))}: ${esc(LANG_NAMES[cur])}">${icon("globe", 16)}<span>${cur.toUpperCase()}</span></button>
        <div class="lang-list hidden" role="menu">${langs.map((l) => `<button role="menuitemradio" aria-checked="${l === cur}" data-lang="${l}" lang="${l}">${esc(LANG_NAMES[l])}</button>`).join("")}</div>
      </div>` : ""}
      <button class="icon-btn" id="mode-btn" aria-label="${esc(t(dark ? "nav.light" : "nav.dark"))}" title="${esc(t(dark ? "nav.light" : "nav.dark"))}">${icon(dark ? "sun" : "moon", 18)}</button>
      <a class="btn sm" href="/themes" data-nav>${icon("palette", 16)}<span>${esc(t("nav.themes"))}</span></a>
    </div>`;
  $("#mode-btn").onclick = () => {
    const next = document.documentElement.dataset.mode === "dark" ? "light" : "dark";
    try { localStorage.setItem("viewer-mode", next); } catch {}
    applyBranding(Customize.draft || App.branding);
    renderHeader();
    $("#mode-btn").focus();
  };
  const lb = $("#lang-btn");
  if (lb) {
    const list = $(".lang-list");
    const close = () => { list.classList.add("hidden"); lb.setAttribute("aria-expanded", "false"); };
    lb.onclick = (e) => {
      e.stopPropagation();
      const open = list.classList.toggle("hidden") === false;
      lb.setAttribute("aria-expanded", String(open));
      if (open) list.querySelector('[aria-checked="true"]')?.focus();
    };
    list.onkeydown = (e) => {
      const items = $$("button", list), i = items.indexOf(document.activeElement);
      if (e.key === "Escape") { close(); lb.focus(); }
      if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length].focus(); }
      if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
    };
    document.addEventListener("click", close, { once: true });
    $$("[data-lang]", list).forEach((b) => (b.onclick = async () => {
      await Lang.set(b.dataset.lang);
      applyBranding(Customize.draft || App.branding);
      renderHeader(); renderFooter();
      rerenderView();
      $("#lang-btn")?.focus();
    }));
  }
  const ib = $("#install-btn");
  if (ib) ib.onclick = async () => { App.installPrompt.prompt(); await App.installPrompt.userChoice; App.installPrompt = null; renderHeader(); };
}
function renderFooter(storage = null) {
  const v = App.config.version;
  $("#footer").innerHTML = `<span>${esc(tx(App.branding.footer))}</span>
    <span class="sep">·</span><button class="link-btn" id="whats-new">v${esc(v)} — ${esc(t("about.whats_new"))}</button>
    ${storage !== null ? `<span class="sep">·</span><span class="storage">${icon("shield", 14)} ${esc(t("about.storage", { n: storage }))}</span>` : ""}`;
  $("#whats-new").onclick = showChangelog;
}
async function refreshStorage() {
  try { const s = await (await fetch("/api/storage")).json(); renderFooter(s.stored_files); return s.stored_files; } catch { return null; }
}

/* ---------- modal ---------- */
function openModal(title, bodyHTML, { wide = false } = {}) {
  const prev = document.activeElement;
  const m = el(`<div class="modal-back" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal ${wide ? "wide" : ""}">
    <div class="modal-head"><h3>${esc(title)}</h3><button class="icon-btn" data-x aria-label="${esc(t("about.close"))}">${icon("x", 16)}</button></div>
    <div class="modal-body">${bodyHTML}</div></div></div>`);
  document.body.appendChild(m);
  const close = () => { m.remove(); prev?.focus?.(); };
  $$("[data-x]", m).forEach((b) => (b.onclick = close));
  m.onclick = (e) => { if (e.target === m) close(); };
  m.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
    if (e.key === "Tab") { // focus trap
      const f = $$("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])", m).filter((x) => !x.disabled && x.offsetParent);
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
  });
  setTimeout(() => ($("input, textarea, canvas", m) || $("[data-x]", m)).focus(), 30);
  return { el: m, close };
}
async function showChangelog() {
  let md = "";
  try { md = await (await fetch("/api/changelog")).text(); } catch {}
  const html = esc(md)
    .replace(/^## (.*)$/gm, "<h4>$1</h4>").replace(/^# .*$/gm, "")
    .replace(/^- (.*)$/gm, "<li>$1</li>").replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n{2,}/g, "<br>");
  openModal(t("about.whats_new"), `<div class="changelog">${html}</div>`, { wide: true });
}

/* Re-render the current view after a language change, keeping work in progress. */
function rerenderView() {
  const p = location.pathname;
  if (p.startsWith("/tool/") && Workspace.state) return Workspace.restore();
  if (p === "/themes" && Customize.draft) return Customize.render(true);
  route();
}

/* ---------- router ---------- */
function route() {
  const p = location.pathname;
  activeHistory = null;
  if (p !== "/themes" && Customize.draft) Customize.leave();
  if (p.startsWith("/tool/")) return Workspace.open(decodeURIComponent(p.slice(6)));
  if (p === "/themes") return Customize.render();
  if (p !== "/") return renderNotFound();
  const cat = new URLSearchParams(location.search).get("cat");
  if (cat) App.homeFilter.cat = cat;
  renderHome();
}
function renderNotFound(msg = t("err.notfound")) {
  $("#app").innerHTML = `<div class="empty-state">${mascot("tilt")}<p>${esc(msg)}</p><a class="btn primary" href="/" data-nav>${esc(t("back"))}</a></div>`;
}

/* ---------- home ---------- */
function toolCard(tl, i = 0) {
  const dis = !tl.available;
  return `<a class="tool-card ${dis ? "disabled" : ""}" href="/tool/${tl.id}" data-nav ${toolColorStyle(tl).replace('"', `"--i:${i};`)}>
      ${dis ? `<span class="badge">${esc(t("home.requires", { x: tl.missing }))}</span>` : ""}
      ${toolIcon(tl)}
      <h3>${esc(tx(tl.title))}</h3>
      <p>${esc(tx(tl.desc))}</p>
    </a>`;
}
function renderHome() {
  const b = App.branding;
  const chips = [{ id: "all", label: t("home.all") }, ...App.config.categories]
    .map((c) => `<button class="chip ${App.homeFilter.cat === c.id ? "active" : ""}" aria-pressed="${App.homeFilter.cat === c.id}" data-cat="${c.id}">${esc(tx(c.label))}</button>`).join("");
  $("#app").innerHTML = `
    <section class="hero">
      <h1>${esc(tx(b.hero_title))}</h1>
      <p>${esc(tx(b.hero_subtitle))}</p>
    </section>
    <div class="filters" role="toolbar">${chips}
      <label class="search">${icon("search", 16)}<span class="sr">${esc(t("home.search"))}</span><input id="tool-search" type="search" placeholder="${esc(t("home.search"))}" value="${esc(App.homeFilter.q)}"></label>
    </div>
    <div class="tools-wrap" id="tools-wrap"></div>`;
  $$(".chip").forEach((c) => (c.onclick = () => {
    App.homeFilter.cat = c.dataset.cat;
    history.replaceState({}, "", c.dataset.cat === "all" ? "/" : `/?cat=${c.dataset.cat}`);
    renderHome();
    $(`.chip[data-cat="${c.dataset.cat}"]`)?.focus();
  }));
  const s = $("#tool-search");
  s.oninput = () => { App.homeFilter.q = s.value; renderToolGrid(); };
  renderToolGrid();
}
function renderToolGrid() {
  const wrap = $("#tools-wrap");
  const { cat, q } = App.homeFilter;
  const norm = (x) => x.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  let tools = visibleTools();
  if (q) tools = tools.filter((tl) => norm([tl.title, tx(tl.title), tl.desc, tx(tl.desc), ...tl.accept].join(" ")).includes(norm(q)));
  if (cat !== "all") tools = tools.filter((tl) => tl.cat === cat);
  if (!tools.length) { wrap.innerHTML = `<div class="empty-state small">${mascot()}<p>${esc(t("home.none"))}</p></div>`; return; }
  let i = 0;
  const grid = (list) => `<div class="tool-grid">${list.map((tl) => toolCard(tl, i++)).join("")}</div>`;
  if (cat !== "all" || q) { wrap.innerHTML = `<div style="margin-top:.5rem">${grid(tools)}</div>`; return; }
  const featured = (App.branding.featured_tools || []).map((id) => tools.find((tl) => tl.id === id)).filter(Boolean);
  let html = "";
  if (featured.length) html += `<h2 class="cat-title">${esc(t("home.popular"))}</h2>${grid(featured)}`;
  for (const c of App.config.categories) {
    const list = tools.filter((tl) => tl.cat === c.id);
    if (list.length) html += `<h2 class="cat-title">${esc(tx(c.label))}</h2>${grid(list)}`;
  }
  wrap.innerHTML = html;
}

/* ---------- generated options form ---------- */
function renderOptions(tool, opts, container, onChange = () => {}) {
  container.innerHTML = "";
  const fields = [];
  for (const o of tool.options || []) {
    if (tool.mode === "url" && o.name === "url") continue; // asked on the landing page
    if (!(o.name in opts) && o.default !== undefined) opts[o.name] = o.default;
    const id = `opt-${o.name}`;
    const lbl = esc(tx(o.label));
    let f;
    const label = `<label for="${id}">${lbl}</label>`;
    const hint = o.hint ? `<div class="hint" id="${id}-hint">${esc(tx(o.hint))}</div>` : "";
    const desc = o.hint ? `aria-describedby="${id}-hint"` : "";
    switch (o.type) {
      case "checkbox":
        f = el(`<div class="field"><label class="check"><input type="checkbox" id="${id}" ${opts[o.name] ? "checked" : ""}> ${lbl}</label>${hint}</div>`);
        $("input", f).onchange = (e) => { opts[o.name] = e.target.checked; sync(); };
        break;
      case "select":
        f = el(`<div class="field">${label}<select class="input" id="${id}" ${desc}>${o.choices.map(([v, l]) => `<option value="${esc(v)}" ${String(opts[o.name]) === String(v) ? "selected" : ""}>${esc(tx(l))}</option>`).join("")}</select>${hint}</div>`);
        $("select", f).onchange = (e) => { opts[o.name] = e.target.value; sync(); };
        break;
      case "cards":
        f = el(`<div class="field" role="radiogroup" aria-label="${lbl}"><span class="field-label">${lbl}</span><div class="opt-cards">${o.choices.map(([v, l, d]) => `<button type="button" role="radio" aria-checked="${opts[o.name] === v}" class="opt-card ${opts[o.name] === v ? "active" : ""}" data-v="${esc(v)}"><span class="dot"></span><span><b>${esc(tx(l))}</b><small>${esc(tx(d))}</small></span></button>`).join("")}</div></div>`);
        $$(".opt-card", f).forEach((b) => (b.onclick = () => {
          opts[o.name] = b.dataset.v;
          $$(".opt-card", f).forEach((x) => { x.classList.toggle("active", x === b); x.setAttribute("aria-checked", String(x === b)); });
          sync();
        }));
        break;
      case "range":
        f = el(`<div class="field">${label}<div class="range-row"><input type="range" id="${id}" min="${o.min}" max="${o.max}" value="${opts[o.name]}"><output>${opts[o.name]}</output></div></div>`);
        $("input", f).oninput = (e) => { opts[o.name] = +e.target.value; $("output", f).textContent = e.target.value; sync(); };
        break;
      case "color":
        f = el(`<div class="field">${label}<input type="color" class="input" id="${id}" value="${esc(opts[o.name] || "#000000")}"></div>`);
        $("input", f).oninput = (e) => { opts[o.name] = e.target.value; sync(); };
        break;
      case "textarea":
        f = el(`<div class="field">${label}<textarea class="input" id="${id}" ${desc}>${esc(opts[o.name] || "")}</textarea>${hint}</div>`);
        $("textarea", f).oninput = (e) => { opts[o.name] = e.target.value; sync(); };
        break;
      case "position": {
        const cells = ["top-left", "top-center", "top-right", "", "center", "", "bottom-left", "bottom-center", "bottom-right"];
        f = el(`<div class="field"><span class="field-label">${lbl}</span><div class="pos-grid" role="radiogroup" aria-label="${lbl}">${cells.map((c) => `<button type="button" role="radio" aria-checked="${opts[o.name] === c}" aria-label="${c}" data-v="${c}" ${c ? "" : "disabled"} class="${opts[o.name] === c ? "active" : ""}"></button>`).join("")}</div></div>`);
        $$("button", f).forEach((b) => (b.onclick = () => {
          opts[o.name] = b.dataset.v;
          $$("button", f).forEach((x) => { x.classList.toggle("active", x === b); x.setAttribute("aria-checked", String(x === b)); });
          sync();
        }));
        break;
      }
      default: {
        const type = o.type === "number" ? "number" : o.type === "password" ? "password" : o.type === "url" ? "url" : "text";
        f = el(`<div class="field">${label}<input class="input" id="${id}" type="${type}" ${desc} ${o.required ? "required" : ""} ${o.min !== undefined ? `min="${o.min}"` : ""} value="${esc(opts[o.name] ?? "")}" ${type === "password" ? 'autocomplete="new-password"' : ""}>${hint}</div>`);
        $("input", f).oninput = (e) => { opts[o.name] = type === "number" ? +e.target.value : e.target.value; sync(); };
      }
    }
    fields.push([o, f]);
    container.appendChild(f);
  }
  function sync() {
    for (const [o, f] of fields) {
      if (!o.show_if) continue;
      const ok = Object.entries(o.show_if).every(([k, v]) => (Array.isArray(v) ? v.map(String) : [String(v)]).includes(String(opts[k])));
      f.classList.toggle("hidden", !ok);
    }
    onChange();
  }
  sync();
}

/* ---------- running a tool ---------- */
function validateOptions(tool, opts) {
  for (const o of tool.options || []) if (o.required && !opts[o.name]) return t("run.required", { x: tx(o.label) });
  return null;
}

function processingView(tool) {
  $("#app").innerHTML = `
    <div class="processing" aria-busy="true">
      <div class="mascot-spin">${mascot()}</div>
      <h2>${esc(t("run.working", { x: tx(tool.title) }))}</h2>
      <p class="muted" id="proc-step" aria-live="polite">${esc(t("run.upload"))}</p>
      <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" id="proc-pb"><div id="proc-bar"></div></div>
      <button class="btn ghost" id="proc-cancel">${icon("x", 16)} ${esc(t("run.cancel"))}</button>
    </div>`;
  return {
    set(pct, step) {
      const bar = $("#proc-bar");
      if (!bar) return;
      bar.style.width = Math.max(2, Math.min(100, pct)) + "%";
      $("#proc-pb").setAttribute("aria-valuenow", String(Math.round(pct)));
      if (step) $("#proc-step").textContent = step;
    },
    onCancel(fn) { $("#proc-cancel").onclick = fn; },
  };
}

async function runTool(tool, files, opts, extraFile) {
  const view = processingView(tool);
  let cancelled = false;
  // 1) in the browser when possible
  if (ClientOps.supports(tool, files, opts)) {
    view.set(30, t("run.processing"));
    view.onCancel(() => { cancelled = true; Workspace.restore(); });
    try {
      const res = await ClientOps.run(tool, files, opts);
      if (cancelled) return;
      view.set(100);
      const inSize = files.reduce((s, f) => s + f.size, 0);
      return renderResult(tool, res.blob, res.name, { inSize, outSize: res.blob.size, count: 1, local: true });
    } catch { /* encrypted or unusual PDF: let the server handle it */ }
    if (cancelled) return;
  }
  // 2) server job: upload, queue, progress, download, deletion check
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));
  fd.append("options", JSON.stringify(opts));
  if (extraFile) fd.append("extra", extraFile, extraFile.name);
  const xhr = new XMLHttpRequest();
  let jobId = null, timer = null;
  view.onCancel(async () => {
    cancelled = true;
    xhr.abort();
    clearTimeout(timer);
    if (jobId) await fetch(`/api/jobs/${jobId}`, { method: "DELETE" }).catch(() => {});
    toast(t("run.cancelled"));
    Workspace.restore();
  });
  const fail = (msg) => { if (cancelled) return; toast(msg || t("run.error"), "error"); Workspace.restore(); };
  xhr.open("POST", `/api/jobs/${tool.id}`);
  xhr.setRequestHeader("X-Lang", Lang.get());
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) view.set((e.loaded / e.total) * 25, t("run.upload")); };
  xhr.onerror = () => fail(t("run.offline"));
  xhr.onload = () => {
    let data = {};
    try { data = JSON.parse(xhr.responseText); } catch {}
    if (xhr.status !== 200) return fail(data.detail);
    jobId = data.id;
    poll();
  };
  xhr.send(fd);

  async function poll() {
    if (cancelled) return;
    let j;
    try { j = await (await fetch(`/api/jobs/${jobId}`, { headers: { "X-Lang": Lang.get() } })).json(); }
    catch { return fail(t("run.offline")); }
    if (j.status === "queued") view.set(25, j.position > 1 ? t("run.queued", { n: j.position - 1 }) : t("run.processing"));
    else if (j.status === "running") view.set(25 + j.progress * 68, j.label && t("prog." + j.label) !== "prog." + j.label ? t("prog." + j.label) : t("run.processing"));
    else if (j.status === "done") return download(j);
    else if (j.status === "error") return fail(j.error || j.detail);
    else if (j.detail) return fail(j.detail);
    timer = setTimeout(poll, j.status === "queued" ? 700 : 350);
  }
  async function download(j) {
    view.set(94, t("run.downloading"));
    const r = await fetch(`/api/jobs/${jobId}/result`);
    if (!r.ok) return fail();
    const blob = await r.blob();
    if (cancelled) return;
    view.set(100);
    const stored = await refreshStorage(); // the server deleted the files right after sending them
    renderResult(tool, blob, j.result.name, { inSize: j.result.in_size, outSize: j.result.size, count: j.result.count, files: j.result.files, stored });
  }
}

function downloadBlob(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
}

/* ---------- result: preview + download ---------- */
function sizeLine(info) {
  if (!info.inSize || !info.outSize) return "";
  const pct = Math.round((1 - info.outSize / info.inSize) * 100);
  const cls = pct > 0 ? "good" : pct < 0 ? "bad" : "";
  const label = pct > 0 ? t("res.smaller", { p: pct }) : pct < 0 ? t("res.bigger", { p: -pct }) : t("res.same");
  return `<div class="size-compare ${cls}"><span>${fmtSize(info.inSize)}</span>${icon("arrow-right", 16)}<b>${fmtSize(info.outSize)}</b><span class="pill">${esc(label)}</span></div>`;
}

function renderResult(tool, blob, name, info) {
  const ext = extOf(name);
  const isPdf = ext === "pdf";
  const next = isPdf ? visibleTools().filter((tl) => tl.available && tl.accept.includes("pdf") && tl.id !== tool.id && tl.cat !== "to_pdf") : [];
  const featured = App.branding.featured_tools || [];
  next.sort((a, b) => (featured.includes(b.id) ? 1 : 0) - (featured.includes(a.id) ? 1 : 0));
  const privacy = info.local
    ? `<div class="privacy ok">${icon("shield", 16)} ${esc(t("res.local"))}</div>`
    : `<div class="privacy ok" title="${esc(t("res.deleted_tip", { n: info.stored ?? 0 }))}">${icon("shield", 16)} ${esc(t("res.deleted"))}<small>${esc(t("res.deleted_tip", { n: info.stored ?? 0 }))}</small></div>`;
  $("#app").innerHTML = `
    <div class="result-layout">
      <section class="result-preview" aria-label="${esc(t("res.preview"))}"><div id="preview" class="preview-pane skeleton-box"></div></section>
      <section class="result-side">
        <div class="result-mascot">${mascot()}<span class="check">${icon("check", 18)}</span></div>
        <h1>${esc(t(info.count > 1 ? "res.ready_many" : "res.ready_one"))}</h1>
        <p class="file-line">${esc(name)}${info.count > 1 ? ` · ${esc(t("res.zip", { n: info.count }))}` : ""}</p>
        ${sizeLine(info)}
        ${tool.id === "compress" && info.outSize >= info.inSize ? `<p class="muted">${esc(t("res.optimized"))}</p>` : ""}
        <div class="actions">
          <button class="btn primary big" id="dl">${icon("download", 22)} ${esc(t("res.download"))}</button>
          <button class="btn ghost" id="again">${icon("undo", 18)} ${esc(t("res.again"))}</button>
        </div>
        ${privacy}
        ${next.length ? `<div class="continue"><h3>${esc(t("res.continue"))}</h3><div class="list">${next.slice(0, 10).map((tl) => `<button class="btn sm" data-t="${tl.id}" ${toolColorStyle(tl)}><span style="color:var(--tc)">${icon(tl.icon, 16)}</span>${esc(tx(tl.title))}</button>`).join("")}</div></div>` : ""}
      </section>
    </div>`;
  $("#dl").onclick = () => downloadBlob(blob, name);
  $("#dl").focus();
  $("#again").onclick = () => nav(`/tool/${tool.id}`);
  $$(".continue [data-t]").forEach((b) => (b.onclick = () => {
    App.carry = [new File([blob], name, { type: "application/pdf" })];
    nav(`/tool/${b.dataset.t}`);
  }));
  announce(t(info.count > 1 ? "res.ready_many" : "res.ready_one"));
  renderPreview(blob, name, info);
}

async function renderPreview(blob, name, info) {
  const box = $("#preview");
  const ext = extOf(name);
  const done = () => box.classList.remove("skeleton-box");
  if (ext === "pdf") {
    try {
      const view = await PDFView.open(blob);
      box.innerHTML = "";
      for (let i = 0; i < view.count; i++) {
        const s = view.size(i);
        const pg = el(`<figure class="pv-page skeleton" style="aspect-ratio:${s.w}/${s.h}"><img alt="${esc(t("pg.page", { n: i + 1 }))}"><figcaption>${i + 1} / ${view.count}</figcaption></figure>`);
        box.appendChild(pg);
        LazyThumbs.watch($("img", pg), () => view.thumb(i, 700));
      }
    } catch {
      box.innerHTML = `<div class="no-preview">${icon("file", 48)}<p>${esc(t("res.no_preview"))}</p></div>`;
    }
  } else if (["jpg", "jpeg", "png", "webp"].includes(ext)) {
    box.innerHTML = `<img class="pv-image" src="${URL.createObjectURL(blob)}" alt="">`;
  } else if (ext === "txt") {
    const txt = (await blob.slice(0, 20000).text());
    box.innerHTML = `<pre class="pv-text">${esc(txt)}${blob.size > 20000 ? "\n…" : ""}</pre>`;
  } else if (ext === "zip" && info.files) {
    box.innerHTML = `<div class="pv-zip"><h3>${icon("archive", 18)} ${esc(t("res.zip_content"))}</h3><ul>${info.files.map((f) => `<li>${icon("file", 14)} ${esc(f)}</li>`).join("")}</ul></div>`;
  } else {
    box.innerHTML = `<div class="no-preview">${icon(ext === "docx" ? "word" : ext === "xlsx" ? "excel" : ext === "pptx" ? "ppt" : "file", 56)}<p>${esc(name)}</p><p class="muted">${esc(t("res.no_preview"))}</p></div>`;
  }
  done();
}

/* ---------- boot ---------- */
async function boot() {
  applyBranding();
  const [config] = await Promise.all([fetch("/api/config").then((r) => r.json()), Lang.load(Lang.get())]);
  App.config = config;
  App.branding = config.branding;
  config.tools.forEach((tl) => (App.toolsById[tl.id] = tl));
  applyBranding();
  renderHeader();
  renderFooter();
  route();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { applyBranding(Customize.draft || App.branding); renderHeader(); });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register(`/sw.js?v=${config.version}`).catch(() => {});
}
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); App.installPrompt = e; if (App.config) renderHeader(); });
document.addEventListener("DOMContentLoaded", boot);
