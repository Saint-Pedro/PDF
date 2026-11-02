/* ============================================================
   Personnalisation : identité, couleurs, typo, style, outils
   ============================================================ */
const Customize = {
  draft: null,
  dirty: false,
  palTab: "colors",

  render() {
    this.draft = structuredClone(App.branding);
    this.dirty = false;
    const sec = (id, ic, title, body, open = false) =>
      `<details class="cz-sec" data-sec="${id}" ${open ? "open" : ""}><summary>${icon(ic, 18)}${title}</summary><div class="cz-body">${body}</div></details>`;
    $("#app").innerHTML = `
      <div class="cz">
        <aside class="cz-panel">
          <div class="cz-head"><h1>Personnaliser</h1><p>Les changements s'affichent en direct. Enregistrez pour les appliquer à tous.</p></div>
          <div class="cz-scroll">
            ${sec("presets", "sparkles", "Thèmes prêts à l'emploi", `<div class="presets" id="presets"></div><div class="hint muted" style="font-size:.8rem">Un thème change couleurs, typo et style, mais garde votre nom et votre logo.</div>`, true)}
            ${sec("identity", "tag", "Identité", this.identityHTML())}
            ${sec("colors", "palette", "Couleurs", this.colorsHTML())}
            ${sec("type", "type", "Typographie", this.typeHTML())}
            ${sec("style", "layout", "Style & mise en page", this.styleHTML())}
            ${sec("tools", "grid", "Outils affichés", `<div class="hint muted" style="font-size:.8rem">Décochez pour masquer un outil, ★ pour le mettre dans « Les plus utilisés ».</div><div class="tool-toggles" id="tool-toggles"></div>`)}
            ${sec("advanced", "code", "Avancé", this.advancedHTML())}
          </div>
          <div class="cz-foot"><span class="dirty" id="dirty">Aucune modification</span><button class="btn" id="cz-cancel">Annuler</button><button class="btn primary" id="cz-save">${icon("check", 16)} Enregistrer</button></div>
        </aside>
        <section class="cz-preview"><div class="label"><span>Aperçu en direct</span><a href="/" data-nav class="btn sm ghost">Voir le site ${icon("arrow-right", 14)}</a></div><div class="frame" id="pv"></div>
          <div class="label" style="margin-top:2rem"><span>Espace de travail</span></div><div class="frame" id="pv2"></div></section>
      </div>`;
    this.bind();
    this.refresh(false);
  },

  /* ---------------- gabarits ---------------- */
  identityHTML() {
    return `
      <div class="field"><label>Nom de l'application</label><input class="input" data-k="name"></div>
      <div class="field"><label>Slogan (onglet du navigateur)</label><input class="input" data-k="tagline"></div>
      <div class="field"><label>Titre d'accueil</label><input class="input" data-k="hero_title"></div>
      <div class="field"><label>Sous-titre d'accueil</label><textarea class="input" data-k="hero_subtitle" style="min-height:70px"></textarea></div>
      <div class="field"><label>Pied de page</label><input class="input" data-k="footer"></div>
      <div class="field"><span class="field-label">Logo</span>
        <div class="logo-drop" id="logo-drop"><div id="logo-prev"></div><div><b>Importer un logo</b><div class="muted" style="font-size:.8rem">SVG, PNG, WEBP… Les couleurs seront détectées.</div></div></div>
        <div style="display:flex;gap:.8rem;align-items:center;flex-wrap:wrap"><label class="check"><input type="checkbox" data-k="show_name" data-type="bool"> Afficher le nom à côté</label>
        <button class="btn sm ghost" id="logo-rm">${icon("trash", 14)} Retirer</button></div>
        <div class="field"><label>Hauteur du logo</label><div class="range-row"><input type="range" min="20" max="64" data-k="logo_height" data-type="num"><output data-out="logo_height"></output></div></div>
      </div>
      <div class="field"><span class="field-label">Favicon</span>
        <div style="display:flex;gap:.5rem;align-items:center"><img id="fav-prev" style="width:28px;height:28px;border-radius:6px;object-fit:contain;background:var(--surface-2)"><button class="btn sm" id="fav-up">${icon("upload", 14)} Importer</button><button class="btn sm ghost" id="fav-rm">Utiliser le logo</button></div>
      </div>`;
  },
  colorsHTML() {
    const keys = [["primary", "Principale"], ["on_primary", "Texte sur principale"], ["bg", "Fond"], ["surface", "Surfaces (cartes)"], ["text", "Texte"], ["muted", "Texte secondaire"], ["border", "Bordures"]];
    return `
      <div class="field"><span class="field-label">Mode d'affichage par défaut</span><div class="seg" data-seg="mode"><button data-v="light">Clair</button><button data-v="dark">Sombre</button><button data-v="auto">Auto (système)</button></div></div>
      <div class="field"><span class="field-label">Générer depuis une couleur</span>
        <div style="display:flex;gap:.5rem"><div class="color-field" style="flex:1"><input type="color" id="gen-color"><input type="text" id="gen-hex"></div><button class="btn" id="gen-go">${icon("sparkles", 16)} Générer</button></div>
        <div class="hint muted" style="font-size:.78rem">Crée automatiquement une palette claire et sombre harmonieuse.</div></div>
      <div class="field hidden" id="logo-colors"><span class="field-label">Couleurs de votre logo</span><div class="swatches" id="logo-swatches"></div></div>
      <div class="field"><div class="tabs" style="margin:0"><button data-pal="colors" class="active">Palette claire</button><button data-pal="dark">Palette sombre</button></div></div>
      <div id="pal-fields" style="display:grid;gap:.6rem">${keys.map(([k, l]) => `<div class="field"><label style="font-weight:500;font-size:.85rem">${l}</label><div class="color-field"><input type="color" data-ck="${k}"><input type="text" data-ckt="${k}"></div></div>`).join("")}</div>
      <div id="contrast" style="display:grid;gap:.3rem"></div>`;
  },
  typeHTML() {
    const opts = Object.entries(Theme.FONT_STACKS).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join("");
    return `
      <div class="field"><label>Police du texte</label><select class="input" data-k="font.body">${opts}</select></div>
      <div class="field"><label>Police des titres</label><select class="input" data-k="font.heading">${opts}</select></div>
      <div class="field"><span class="field-label">Importer une police (WOFF2, TTF, OTF)</span>
        <div style="display:flex;gap:.5rem;align-items:center"><button class="btn sm" id="font-up">${icon("upload", 14)} Choisir un fichier</button><span class="muted" id="font-name" style="font-size:.85rem"></span></div>
        <div class="hint muted" style="font-size:.78rem">Fonctionne hors ligne. Sélectionnez ensuite « Police importée ».</div></div>
      <div class="field"><label>Google Fonts (nécessite Internet)</label><input class="input" data-k="font.google" placeholder="ex. Poppins, Inter, Playfair Display"></div>
      <div class="font-sample" id="font-sample"><div style="font-family:var(--font-heading);font-weight:800">Titre Aa Éé 123</div><div style="font-family:var(--font-body);font-size:1rem">Le texte courant de votre application.</div></div>`;
  },
  styleHTML() {
    const seg = (k, label, choices) => `<div class="field"><span class="field-label">${label}</span><div class="seg" data-seg="${k}">${choices.map(([v, l]) => `<button data-v="${v}">${l}</button>`).join("")}</div></div>`;
    return `
      <div class="field"><label>Arrondi des angles</label><div class="range-row"><input type="range" min="0" max="28" data-k="radius" data-type="num"><output data-out="radius"></output></div></div>
      ${seg("density", "Densité", [["compact", "Compacte"], ["comfortable", "Normale"], ["spacious", "Aérée"]])}
      ${seg("card_style", "Cartes d'outils", [["elevated", "Ombre"], ["outline", "Contour"], ["flat", "À plat"], ["glass", "Verre"], ["brutal", "Brutal"]])}
      ${seg("icon_style", "Icônes", [["tinted", "Teintées"], ["solid", "Pleines"], ["outline", "Contour"], ["mono", "Monochrome"]])}
      ${seg("header_style", "En-tête", [["surface", "Blanc"], ["primary", "Couleur"], ["glass", "Verre"], ["transparent", "Transparent"]])}
      ${seg("hero_style", "Bandeau d'accueil", [["plain", "Simple"], ["gradient", "Dégradé"], ["pattern", "Motif"], ["banner", "Bannière"]])}
      <label class="check"><input type="checkbox" data-k="tool_colors" data-type="bool"> Une couleur par outil (sinon couleur principale)</label>
      <label class="check"><input type="checkbox" data-k="show_descriptions" data-type="bool"> Afficher les descriptions des outils</label>`;
  },
  advancedHTML() {
    return `
      <div class="field"><label>CSS personnalisé</label><textarea class="input" data-k="custom_css" style="font-family:ui-monospace,monospace;font-size:.8rem;min-height:120px" placeholder=".tool-card h3 { letter-spacing: .02em; }"></textarea></div>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap">
        <button class="btn sm" id="exp">${icon("download", 14)} Exporter le thème</button>
        <button class="btn sm" id="imp">${icon("upload", 14)} Importer un thème</button>
        <button class="btn sm ghost" id="reset">${icon("undo", 14)} Réinitialiser tout</button>
      </div>
      <div class="hint muted" style="font-size:.78rem">Variables CSS disponibles : --primary, --bg, --surface, --text, --muted, --border, --radius, --font-body, --font-heading.</div>`;
  },

  /* ---------------- liaisons ---------------- */
  get(path) { return path.split(".").reduce((o, k) => o?.[k], this.draft); },
  set(path, v) {
    const ks = path.split("."); let o = this.draft;
    ks.slice(0, -1).forEach((k) => (o = o[k] = o[k] || {}));
    o[ks.at(-1)] = v;
    this.change();
  },
  change() { this.dirty = true; this.draft.preset = this.draft.preset || null; this.refresh(); },

  bind() {
    const root = $(".cz");
    // champs simples
    $$("[data-k]", root).forEach((inp) => {
      const k = inp.dataset.k, type = inp.dataset.type;
      const ev = inp.type === "checkbox" || inp.tagName === "SELECT" ? "onchange" : "oninput";
      inp[ev] = () => this.set(k, type === "bool" ? inp.checked : type === "num" ? +inp.value : inp.value);
    });
    $$("[data-seg]", root).forEach((s) => $$("button", s).forEach((b) => (b.onclick = () => this.set(s.dataset.seg, b.dataset.v))));
    // presets
    $("#presets").innerHTML = Object.entries(Theme.PRESETS).map(([id, p]) => `
      <button class="preset" data-p="${id}"><div class="sw">${[p.colors.primary, p.colors.bg, p.colors.text, p.dark.bg, p.dark.primary].map((c) => `<span style="background:${c}"></span>`).join("")}</div><b>${p.label}</b><small>${p.desc}</small></button>`).join("");
    $$(".preset", root).forEach((b) => (b.onclick = () => {
      const p = structuredClone(Theme.PRESETS[b.dataset.p]);
      delete p.label; delete p.desc;
      Object.assign(this.draft, p, { font: { ...this.draft.font, ...p.font }, preset: b.dataset.p });
      this.dirty = true; this.refresh();
    }));
    // palette
    $$("[data-pal]", root).forEach((b) => (b.onclick = () => { this.palTab = b.dataset.pal; $$("[data-pal]").forEach((x) => x.classList.toggle("active", x === b)); this.refresh(false); }));
    $$("[data-ck]", root).forEach((inp) => (inp.oninput = () => { this.draft[this.palTab][inp.dataset.ck] = inp.value; this.draft.preset = null; this.change(); }));
    $$("[data-ckt]", root).forEach((inp) => (inp.onchange = () => {
      const v = inp.value.trim(); if (!/^#?[0-9a-f]{3}([0-9a-f]{3})?$/i.test(v)) return toast("Couleur invalide (ex. #e5322d)", "error");
      this.draft[this.palTab][inp.dataset.ckt] = v.startsWith("#") ? v : "#" + v; this.draft.preset = null; this.change();
    }));
    const gc = $("#gen-color"), gh = $("#gen-hex");
    gc.value = this.draft.colors.primary; gh.value = this.draft.colors.primary;
    gc.oninput = () => (gh.value = gc.value);
    gh.onchange = () => { if (/^#[0-9a-f]{6}$/i.test(gh.value)) gc.value = gh.value; };
    $("#gen-go").onclick = () => this.generate(gc.value);
    // logo / favicon / police
    $("#logo-drop").onclick = () => this.upload("logo", "image/*,.svg", async (url) => { this.draft.logo = url; this.change(); this.detectLogoColors(true); });
    $("#logo-rm").onclick = () => { this.draft.logo = null; $("#logo-colors").classList.add("hidden"); this.change(); };
    $("#fav-up").onclick = () => this.upload("favicon", "image/*,.ico,.svg", (url) => { this.draft.favicon = url; this.change(); });
    $("#fav-rm").onclick = () => { this.draft.favicon = null; this.change(); };
    $("#font-up").onclick = () => this.upload("font", ".woff2,.woff,.ttf,.otf", (url, name) => {
      this.draft.font = { ...this.draft.font, custom_url: url, custom_name: name.replace(/[^\w -]/g, "") || "MaPolice", body: "custom", heading: "custom" };
      this.change(); this.fillInputs();
    });
    // avancé
    $("#exp").onclick = () => download(new Blob([JSON.stringify(this.draft, null, 2)], { type: "application/json" }), `theme-${(this.draft.name || "pdf").toLowerCase().replace(/\W+/g, "-")}.json`);
    $("#imp").onclick = () => {
      chooseFiles(".json,application/json", false, async ([f]) => {
        try { const d = JSON.parse(await f.text()); this.draft = { ...this.draft, ...d }; this.change(); this.fillInputs(); toast("Thème importé"); }
        catch { toast("Fichier de thème invalide.", "error"); }
      });
    };
    $("#reset").onclick = () => { if (!confirm("Revenir à l'apparence d'origine ?")) return; this.draft = structuredClone(App.config.defaults); this.change(); this.fillInputs(); };
    $("#cz-cancel").onclick = () => { this.draft = structuredClone(App.branding); this.dirty = false; this.fillInputs(); this.refresh(false); };
    $("#cz-save").onclick = () => this.save();
    this.fillInputs();
    if (this.draft.logo) this.detectLogoColors(false);
  },

  fillInputs() {
    const root = $(".cz");
    $$("[data-k]", root).forEach((inp) => {
      const v = this.get(inp.dataset.k);
      if (inp.type === "checkbox") inp.checked = v !== false;
      else inp.value = v ?? "";
    });
    $("#font-name").textContent = this.draft.font?.custom_name ? `Importée : ${this.draft.font.custom_name}` : "";
  },

  /* ---------------- actions ---------------- */
  generate(hex) {
    const { colors, dark } = Theme.derivePalette(hex);
    this.draft.colors = colors; this.draft.dark = dark; this.draft.preset = null;
    this.change();
    toast("Palette générée");
  },

  adminHeaders() {
    const h = {};
    if (App.config.admin_protected) {
      let pw = sessionStorage.getItem("admin-pw");
      if (!pw) { pw = prompt("Mot de passe administrateur :"); if (!pw) return null; sessionStorage.setItem("admin-pw", pw); }
      h["X-Admin-Password"] = pw;
    }
    return h;
  },

  upload(kind, accept, done) {
    chooseFiles(accept, false, async ([f]) => {
      const headers = this.adminHeaders(); if (!headers) return;
      const fd = new FormData(); fd.append("kind", kind); fd.append("file", f);
      const r = await fetch("/api/branding/asset", { method: "POST", body: fd, headers });
      if (r.status === 401) { sessionStorage.removeItem("admin-pw"); return toast("Mot de passe administrateur incorrect.", "error"); }
      if (!r.ok) return toast((await r.json()).detail || "Import impossible", "error");
      const d = await r.json();
      done(d.url, d.name);
    });
  },

  detectLogoColors(suggest) {
    const img = new Image();
    img.onload = () => {
      let cols = [];
      try { cols = Theme.dominantColors(img, 6); } catch {}
      if (!cols.length) return;
      $("#logo-colors").classList.remove("hidden");
      $("#logo-swatches").innerHTML = cols.map((c) => `<button title="${c} — générer une palette" style="background:${c}" data-c="${c}"></button>`).join("");
      $$("#logo-swatches button").forEach((b) => (b.onclick = () => { $("#gen-color").value = b.dataset.c; $("#gen-hex").value = b.dataset.c; this.generate(b.dataset.c); }));
      if (suggest) toast("Couleurs du logo détectées : cliquez sur une pastille (section Couleurs) pour générer la palette.");
    };
    img.src = this.draft.logo;
  },

  async save() {
    const headers = this.adminHeaders(); if (!headers) return;
    const r = await fetch("/api/branding", { method: "PUT", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(this.draft) });
    if (r.status === 401) { sessionStorage.removeItem("admin-pw"); return toast("Mot de passe administrateur incorrect.", "error"); }
    if (!r.ok) return toast("Enregistrement impossible.", "error");
    App.branding = await r.json();
    App.config.branding = App.branding;
    this.draft = structuredClone(App.branding);
    this.dirty = false;
    try { localStorage.removeItem("viewer-mode"); } catch {}
    this.refresh(false);
    toast("Apparence enregistrée ✓");
  },

  /* ---------------- rendu en direct ---------------- */
  refresh(markDirty = true) {
    const d = this.draft;
    Theme.apply(d);
    // en-tête réel + favicon
    const saved = App.branding; App.branding = d; renderHeader(); renderFooter(); App.branding = saved;
    $("#favicon").href = d.favicon || d.logo || "/static/img/favicon.svg";
    document.title = `${d.name}${d.tagline ? " — " + d.tagline : ""}`;
    // contrôles
    $$("[data-seg]").forEach((s) => $$("button", s).forEach((b) => b.classList.toggle("active", String(this.get(s.dataset.seg)) === b.dataset.v)));
    $$(".preset").forEach((b) => b.classList.toggle("active", b.dataset.p === d.preset));
    $$("[data-out]").forEach((o) => (o.textContent = this.get(o.dataset.out)));
    const pal = d[this.palTab];
    $$("[data-ck]").forEach((i) => (i.value = pal[i.dataset.ck] || "#000000"));
    $$("[data-ckt]").forEach((i) => { if (document.activeElement !== i) i.value = pal[i.dataset.ckt] || ""; });
    $("#logo-prev").innerHTML = d.logo ? `<img src="${esc(d.logo)}" alt="">` : `<div class="ph">${icon("image", 22)}</div>`;
    $("#fav-prev").src = d.favicon || d.logo || "/static/img/favicon.svg";
    const ct = (a, b, label) => { const r = Theme.contrast(a, b); const ok = r >= 4.5; return `<div class="contrast-note">${label} : <span class="${ok ? "ok" : r >= 3 ? "" : "bad"}">${r.toFixed(1)}:1 ${ok ? "✓ lisible" : r >= 3 ? "· limite" : "✗ peu lisible"}</span></div>`; };
    $("#contrast").innerHTML = ct(pal.on_primary, pal.primary, "Bouton principal") + ct(pal.text, pal.bg, "Texte sur fond") + ct(pal.muted, pal.surface, "Texte secondaire");
    // liste des outils
    const hidden = new Set(d.hidden_tools || []), feat = new Set(d.featured_tools || []);
    $("#tool-toggles").innerHTML = App.config.categories.map((c) => `<div class="muted" style="font-size:.72rem;font-weight:700;text-transform:uppercase;margin:.4rem .3rem .1rem">${esc(c.label)}</div>` +
      App.config.tools.filter((t) => t.cat === c.id).map((t) => `<label class="tool-toggle"><input type="checkbox" data-t="${t.id}" ${hidden.has(t.id) ? "" : "checked"}><span class="name">${esc(t.title)}</span><button type="button" class="star-btn ${feat.has(t.id) ? "on" : ""}" data-star="${t.id}">${icon("star", 16)}</button></label>`).join("")).join("");
    $$("#tool-toggles [data-t]").forEach((c) => (c.onchange = () => {
      const s = new Set(this.draft.hidden_tools || []); c.checked ? s.delete(c.dataset.t) : s.add(c.dataset.t);
      this.draft.hidden_tools = [...s]; this.dirty = true; this.refresh();
    }));
    $$("#tool-toggles [data-star]").forEach((b) => (b.onclick = (e) => {
      e.preventDefault();
      const arr = [...(this.draft.featured_tools || [])]; const i = arr.indexOf(b.dataset.star);
      i >= 0 ? arr.splice(i, 1) : arr.push(b.dataset.star);
      this.draft.featured_tools = arr; this.dirty = true; this.refresh();
    }));
    const dl = $("#dirty"); dl.textContent = this.dirty ? "● Non enregistré" : "Aucune modification"; dl.classList.toggle("on", this.dirty);
    this.preview();
  },

  preview() {
    const d = this.draft;
    const hidden = new Set(d.hidden_tools || []);
    const tools = App.config.tools.filter((t) => !hidden.has(t.id));
    const feat = (d.featured_tools || []).map((id) => tools.find((t) => t.id === id)).filter(Boolean);
    const list = (feat.length ? feat : tools).slice(0, 6);
    const saved = App.branding; App.branding = d;
    $("#pv").innerHTML = `
      <header class="topbar"><span class="brand">${brandHTML(d)}</span><nav class="nav">${App.config.categories.slice(0, 4).map((c) => `<a>${esc(c.label)}</a>`).join("")}</nav>
        <div class="top-actions"><span class="icon-btn">${icon("moon", 16)}</span></div></header>
      <section class="hero" style="padding:2.2rem 1.5rem 1.4rem"><h1 style="font-size:2rem">${esc(d.hero_title)}</h1><p style="font-size:1rem">${esc(d.hero_subtitle)}</p></section>
      <div class="filters"><button class="chip active">Tous</button>${App.config.categories.slice(0, 3).map((c) => `<button class="chip">${esc(c.label)}</button>`).join("")}</div>
      <div class="tools-wrap" style="padding-bottom:2rem"><div class="tool-grid">${list.map(toolCard).join("")}</div></div>`;
    App.branding = saved;
    $("#pv2").innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 280px;min-height:280px">
        <div style="padding:1.5rem;display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-start">
          ${[1, 2].map((n) => `<div class="file-card" style="width:140px"><span class="order-badge">${n}</span><div class="thumb" style="height:150px"><span class="ext">${icon("file", 30)}PDF</span></div><div class="name">document-${n}.pdf</div><div class="meta">1,2 Mo</div></div>`).join("")}
        </div>
        <aside class="sidebar" style="position:static;height:auto">
          <div class="sidebar-head"><h2 style="font-size:1.2rem">Compresser PDF</h2></div>
          <div class="sidebar-body"><div class="opt-cards"><button class="opt-card active"><span class="dot"></span><span><b>Recommandée</b><small>Bon équilibre</small></span></button><button class="opt-card"><span class="dot"></span><span><b>Extrême</b><small>Taille minimale</small></span></button></div></div>
          <div class="sidebar-foot"><button class="btn primary block">Compresser PDF ${icon("arrow-right", 18)}</button></div>
        </aside>
      </div>`;
    $$("#pv a, #pv2 a").forEach((a) => a.removeAttribute("data-nav"));
    $$("#pv .tool-card").forEach((a) => { a.removeAttribute("href"); });
  },
};

/* Quitter la page de personnalisation sans enregistrer : on restaure. */
const _route = route;
route = function () {
  if (location.pathname !== "/personnaliser" && Customize.draft) {
    if (Customize.dirty) toast("Modifications de thème non enregistrées abandonnées.");
    Customize.draft = null; Customize.dirty = false;
    applyBranding(); renderHeader(); renderFooter();
    document.title = App.branding.name;
  }
  _route();
};
window.removeEventListener("popstate", _route);
window.addEventListener("popstate", () => route());
