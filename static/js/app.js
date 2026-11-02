/* ============================================================
   PDF Studio — cœur de l'interface (routeur, accueil, résultats)
   ============================================================ */
const App = {
  config: null,
  branding: window.__BRANDING__ || {},
  toolsById: {},
  homeFilter: { cat: "all", q: "" },
  carry: null, // fichier transmis d'un outil à l'autre
};

/* ---------- utilitaires ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function el(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }
function fmtSize(b) { if (b < 1024) return b + " o"; if (b < 1048576) return (b / 1024).toFixed(1) + " Ko"; return (b / 1048576).toFixed(1) + " Mo"; }
const extOf = (name) => (name.split(".").pop() || "").toLowerCase();
function toast(msg, type = "") {
  const t = el(`<div class="toast ${type}">${esc(msg)}</div>`);
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), type === "error" ? 6000 : 3200);
}
/* Sélecteur de fichiers (input attaché au DOM : requis par certains navigateurs) */
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
window.addEventListener("popstate", route);

function visibleTools() {
  const hidden = new Set(App.branding.hidden_tools || []);
  return App.config.tools.filter((t) => !hidden.has(t.id));
}
const toolColorStyle = (t) => `style="--tc:${t.color}"`;

/* ---------- mode clair / sombre côté visiteur ---------- */
function viewerMode() { try { return localStorage.getItem("viewer-mode"); } catch { return null; } }
function effectiveBranding(b = App.branding) {
  const vm = viewerMode();
  return vm ? { ...b, mode: vm } : b;
}
function applyBranding(b = App.branding) {
  Theme.apply(effectiveBranding(b));
  const fav = $("#favicon");
  if (fav) fav.href = b.favicon || b.logo || "/static/img/favicon.svg";
}

/* ---------- en-tête / pied ---------- */
function brandHTML(b = App.branding) {
  const logo = b.logo ? `<img src="${esc(b.logo)}" alt="">` : `<span class="brand-mark">${icon("file")}</span>`;
  return `${logo}${b.show_name !== false || !b.logo ? `<span>${esc(b.name)}</span>` : ""}`;
}
function renderHeader() {
  const b = App.branding;
  const cats = App.config.categories.map((c) => `<a href="/?cat=${c.id}" data-nav>${esc(c.label)}</a>`).join("");
  const dark = document.documentElement.dataset.mode === "dark";
  $("#topbar").innerHTML = `
    <a class="brand" href="/" data-nav>${brandHTML(b)}</a>
    <nav class="nav">${cats}</nav>
    <div class="top-actions">
      <button class="icon-btn" id="mode-btn" title="${dark ? "Mode clair" : "Mode sombre"}">${icon(dark ? "sun" : "moon", 18)}</button>
      <a class="btn sm" href="/personnaliser" data-nav title="Personnaliser l'application">${icon("palette", 16)}<span>Personnaliser</span></a>
    </div>`;
  $("#mode-btn").onclick = () => {
    const next = document.documentElement.dataset.mode === "dark" ? "light" : "dark";
    try { localStorage.setItem("viewer-mode", next); } catch {}
    applyBranding();
    renderHeader();
  };
  document.title = b.name || "PDF Studio";
}
function renderFooter() { $("#footer").textContent = App.branding.footer || ""; }

/* ---------- routeur ---------- */
function route() {
  const p = location.pathname;
  document.body.classList.remove("no-footer");
  if (p.startsWith("/outil/")) return Workspace.open(decodeURIComponent(p.slice(7)));
  if (p === "/personnaliser") return Customize.render();
  const cat = new URLSearchParams(location.search).get("cat");
  if (cat) App.homeFilter.cat = cat;
  renderHome();
}

/* ---------- accueil ---------- */
function toolCard(t) {
  const dis = !t.available;
  return `<a class="tool-card ${dis ? "disabled" : ""}" href="/outil/${t.id}" data-nav ${toolColorStyle(t)}>
      ${dis ? `<span class="badge">Requiert ${esc(t.missing)}</span>` : ""}
      <div class="tool-icon">${icon(t.icon, 26)}</div>
      <h3>${esc(t.title)}</h3>
      <p>${esc(t.desc)}</p>
    </a>`;
}
function renderHome() {
  const b = App.branding;
  const app = $("#app");
  const chips = [{ id: "all", label: "Tous" }, ...App.config.categories]
    .map((c) => `<button class="chip ${App.homeFilter.cat === c.id ? "active" : ""}" data-cat="${c.id}">${esc(c.label)}</button>`).join("");
  app.innerHTML = `
    <section class="hero">
      <h1>${esc(b.hero_title)}</h1>
      <p>${esc(b.hero_subtitle)}</p>
    </section>
    <div class="filters">${chips}
      <label class="search">${icon("search", 16)}<input id="tool-search" type="search" placeholder="Rechercher un outil…" value="${esc(App.homeFilter.q)}"></label>
    </div>
    <div class="tools-wrap" id="tools-wrap"></div>`;
  $$(".chip", app).forEach((c) => (c.onclick = () => {
    App.homeFilter.cat = c.dataset.cat;
    history.replaceState({}, "", c.dataset.cat === "all" ? "/" : `/?cat=${c.dataset.cat}`);
    renderHome();
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
  if (q) tools = tools.filter((t) => norm(t.title + " " + t.desc + " " + t.accept.join(" ")).includes(norm(q)));
  if (cat !== "all") tools = tools.filter((t) => t.cat === cat);
  if (!tools.length) { wrap.innerHTML = `<div class="empty">Aucun outil ne correspond.</div>`; return; }
  if (cat !== "all" || q) { wrap.innerHTML = `<div class="tool-grid" style="margin-top:.5rem">${tools.map(toolCard).join("")}</div>`; return; }
  const featured = (App.branding.featured_tools || []).map((id) => tools.find((t) => t.id === id)).filter(Boolean);
  let html = "";
  if (featured.length) html += `<h2 class="cat-title">Les plus utilisés</h2><div class="tool-grid">${featured.map(toolCard).join("")}</div>`;
  for (const c of App.config.categories) {
    const list = tools.filter((t) => t.cat === c.id);
    if (list.length) html += `<h2 class="cat-title">${esc(c.label)}</h2><div class="tool-grid">${list.map(toolCard).join("")}</div>`;
  }
  wrap.innerHTML = html;
}

/* ---------- formulaire d'options généré ---------- */
function renderOptions(tool, opts, container, onChange = () => {}) {
  container.innerHTML = "";
  const fields = [];
  for (const o of tool.options || []) {
    if (!(o.name in opts) && o.default !== undefined) opts[o.name] = o.default;
    const id = `opt-${o.name}`;
    let f;
    const label = `<label for="${id}">${esc(o.label)}</label>`;
    const hint = o.hint ? `<div class="hint">${esc(o.hint)}</div>` : "";
    switch (o.type) {
      case "checkbox":
        f = el(`<div class="field"><label class="check"><input type="checkbox" id="${id}" ${opts[o.name] ? "checked" : ""}> ${esc(o.label)}</label>${hint}</div>`);
        $("input", f).onchange = (e) => { opts[o.name] = e.target.checked; sync(); };
        break;
      case "select":
        f = el(`<div class="field">${label}<select class="input" id="${id}">${o.choices.map(([v, l]) => `<option value="${esc(v)}" ${String(opts[o.name]) === String(v) ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>${hint}</div>`);
        $("select", f).onchange = (e) => { opts[o.name] = e.target.value; sync(); };
        break;
      case "cards":
        f = el(`<div class="field"><span class="field-label">${esc(o.label)}</span><div class="opt-cards">${o.choices.map(([v, l, d]) => `<button type="button" class="opt-card ${opts[o.name] === v ? "active" : ""}" data-v="${esc(v)}"><span class="dot"></span><span><b>${esc(l)}</b><small>${esc(d || "")}</small></span></button>`).join("")}</div></div>`);
        $$(".opt-card", f).forEach((b) => (b.onclick = () => { opts[o.name] = b.dataset.v; $$(".opt-card", f).forEach((x) => x.classList.toggle("active", x === b)); sync(); }));
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
        f = el(`<div class="field">${label}<textarea class="input" id="${id}">${esc(opts[o.name] || "")}</textarea>${hint}</div>`);
        $("textarea", f).oninput = (e) => { opts[o.name] = e.target.value; sync(); };
        break;
      case "position": {
        const cells = ["top-left", "top-center", "top-right", "", "center", "", "bottom-left", "bottom-center", "bottom-right"];
        f = el(`<div class="field"><span class="field-label">${esc(o.label)}</span><div class="pos-grid">${cells.map((c) => `<button type="button" data-v="${c}" ${c ? "" : "disabled"} class="${opts[o.name] === c ? "active" : ""}" title="${c}"></button>`).join("")}</div></div>`);
        $$("button", f).forEach((b) => (b.onclick = () => { opts[o.name] = b.dataset.v; $$("button", f).forEach((x) => x.classList.toggle("active", x === b)); sync(); }));
        break;
      }
      default: {
        const type = o.type === "number" ? "number" : o.type === "password" ? "password" : "text";
        f = el(`<div class="field">${label}<input class="input" id="${id}" type="${type}" ${o.min !== undefined ? `min="${o.min}"` : ""} value="${esc(opts[o.name] ?? "")}" ${type === "password" ? 'autocomplete="new-password"' : ""}>${hint}</div>`);
        $("input", f).oninput = (e) => { opts[o.name] = type === "number" ? +e.target.value : e.target.value; sync(); };
      }
    }
    f.dataset.opt = o.name;
    fields.push([o, f]);
    container.appendChild(f);
  }
  function sync() {
    for (const [o, f] of fields) {
      if (!o.show_if) continue;
      const ok = Object.entries(o.show_if).every(([k, v]) => String(opts[k]) === String(v));
      f.classList.toggle("hidden", !ok);
    }
    onChange();
  }
  sync();
}

/* ---------- exécution d'un outil ---------- */
function validateOptions(tool, opts) {
  for (const o of tool.options || []) {
    if (o.required && !opts[o.name]) return `Le champ « ${o.label} » est requis.`;
  }
  return null;
}

function runTool(tool, files, opts, extraFile) {
  const app = $("#app");
  app.innerHTML = `<div class="processing"><div class="spinner"></div><h2>${esc(tool.title)} en cours…</h2><p class="muted" id="proc-step">Envoi des fichiers</p><div class="progress"><div id="proc-bar"></div></div></div>`;
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));
  fd.append("options", JSON.stringify(opts));
  if (extraFile) fd.append("extra", extraFile, extraFile.name);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/process/${tool.id}`);
  xhr.responseType = "blob";
  xhr.upload.onprogress = (e) => {
    if (!e.lengthComputable) return;
    const pct = (e.loaded / e.total) * 100;
    $("#proc-bar").style.width = pct * 0.6 + "%";
    if (pct >= 100) { $("#proc-step").textContent = "Traitement…"; $("#proc-bar").style.width = "75%"; }
  };
  xhr.onload = async () => {
    if (xhr.status !== 200) {
      let msg = "Une erreur est survenue.";
      try { msg = JSON.parse(await xhr.response.text()).detail || msg; } catch {}
      toast(msg, "error");
      Workspace.restore();
      return;
    }
    const cd = xhr.getResponseHeader("Content-Disposition") || "";
    let name = "resultat";
    const m = cd.match(/filename\*=utf-8''([^;]+)/i) || cd.match(/filename="?([^";]+)"?/i);
    if (m) name = decodeURIComponent(m[1]);
    renderResult(tool, xhr.response, name, {
      inSize: +xhr.getResponseHeader("X-Input-Size"), outSize: +xhr.getResponseHeader("X-Output-Size"),
      count: +xhr.getResponseHeader("X-File-Count"),
    });
  };
  xhr.onerror = () => { toast("Connexion au serveur impossible.", "error"); Workspace.restore(); };
  xhr.send(fd);
}

function download(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
}

function renderResult(tool, blob, name, info) {
  const app = $("#app");
  const isPdf = name.toLowerCase().endsWith(".pdf");
  const saved = tool.id === "compress" && info.inSize ? Math.round((1 - info.outSize / info.inSize) * 100) : null;
  const next = isPdf ? visibleTools().filter((t) => t.available && t.accept.includes("pdf") && t.id !== tool.id && t.cat !== "to_pdf") : [];
  const featured = App.branding.featured_tools || [];
  next.sort((a, b) => (featured.includes(b.id) ? 1 : 0) - (featured.includes(a.id) ? 1 : 0));
  app.innerHTML = `
    <div class="result">
      <div class="success-mark">${icon("check", 36)}</div>
      <h1>${info.count > 1 ? "Vos fichiers sont prêts !" : "Votre fichier est prêt !"}</h1>
      <p class="file-line">${esc(name)} · ${fmtSize(info.outSize || blob.size)}${info.count > 1 ? ` · ${info.count} fichiers (ZIP)` : ""}</p>
      ${saved !== null ? `<div class="saving"><span class="pct">${saved > 0 ? "−" + saved : "0"}%</span><span class="muted">${fmtSize(info.inSize)} → <b>${fmtSize(info.outSize)}</b>${saved <= 0 ? "<br>Ce PDF était déjà optimisé." : ""}</span></div>` : ""}
      <div class="actions">
        <button class="btn primary big" id="dl">${icon("download", 22)} Télécharger</button>
        ${isPdf ? `<a class="btn" id="view" target="_blank">${icon("eye", 18)} Aperçu</a>` : ""}
        <button class="btn ghost" id="again">${icon("undo", 18)} Recommencer</button>
      </div>
      ${next.length ? `<div class="continue"><h3>Continuer avec ce fichier…</h3><div class="list">${next.slice(0, 10).map((t) => `<button class="btn sm" data-t="${t.id}" ${toolColorStyle(t)}><span style="color:var(--tc)">${icon(t.icon, 16)}</span>${esc(t.title)}</button>`).join("")}</div></div>` : ""}
    </div>`;
  $("#dl").onclick = () => download(blob, name);
  if (isPdf) $("#view").href = URL.createObjectURL(blob);
  $("#again").onclick = () => nav(`/outil/${tool.id}`);
  $$(".continue [data-t]").forEach((b) => (b.onclick = () => {
    App.carry = [new File([blob], name, { type: "application/pdf" })];
    nav(`/outil/${b.dataset.t}`);
  }));
}

/* ---------- aperçus ---------- */
const thumbCache = new WeakMap();
async function pdfPreview(file, { width = 220, maxPages = 1, password = "" } = {}) {
  const key = `${width}-${maxPages}`;
  const cache = thumbCache.get(file) || {};
  if (cache[key]) return cache[key];
  const fd = new FormData();
  fd.append("file", file, file.name);
  fd.append("width", width);
  fd.append("max_pages", maxPages);
  if (password) fd.append("password", password);
  const r = await fetch("/api/preview", { method: "POST", body: fd });
  if (r.status === 423) return { locked: true, count: 0, pages: [] };
  if (!r.ok) throw new Error("Aperçu impossible");
  const data = await r.json();
  cache[key] = data;
  thumbCache.set(file, cache);
  return data;
}

/* ---------- démarrage ---------- */
async function boot() {
  applyBranding();
  App.config = await (await fetch("/api/config")).json();
  App.branding = App.config.branding;
  App.config.tools.forEach((t) => (App.toolsById[t.id] = t));
  applyBranding();
  renderHeader();
  renderFooter();
  route();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { applyBranding(); renderHeader(); });
}
document.addEventListener("DOMContentLoaded", boot);
