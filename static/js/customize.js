/* ============================================================
   Themes page: pick a ready-made theme (branding is hard-coded
   in app/branding.json)
   ============================================================ */
const Customize = {
  draft: null,
  dirty: false,

  render(keep = false) {
    if (!keep || !this.draft) { this.draft = structuredClone(App.branding); this.dirty = false; }
    const presets = [["", { label: t("th.default"), desc: t("th.default_desc"), colors: App.branding.colors, dark: App.branding.dark }], ...Object.entries(Theme.PRESETS)];
    $("#app").innerHTML = `
      <div class="cz">
        <aside class="cz-panel">
          <div class="cz-head"><h1>${esc(t("th.title"))}</h1><p>${esc(t("th.desc"))}</p></div>
          <div class="cz-scroll"><div class="cz-body" style="padding-top:1.4rem">
            <div class="presets">${presets.map(([id, p]) => `
              <button class="preset" data-p="${id}"><div class="sw">${[p.colors.primary, p.colors.bg, p.colors.text, p.dark.bg, p.dark.primary].map((c) => `<span style="background:${c}"></span>`).join("")}</div>
              <b>${esc(tx(p.label))}</b><small>${esc(tx(p.desc))}</small></button>`).join("")}</div>
          </div></div>
          <div class="cz-foot"><span class="dirty" id="dirty"></span><button class="btn" id="cz-cancel">${esc(t("th.cancel"))}</button><button class="btn primary" id="cz-save">${icon("check", 16)} ${esc(t("th.save"))}</button></div>
        </aside>
        <section class="cz-preview">
          <div class="label"><span>${esc(t("th.preview"))}</span><a href="/" data-nav class="btn sm ghost">${esc(t("th.view"))} ${icon("arrow-right", 14)}</a></div>
          <div class="frame" id="pv"></div>
          <div class="label" style="margin-top:2rem"><span>${esc(t("th.workspace"))}</span></div>
          <div class="frame" id="pv2"></div>
        </section>
      </div>`;
    $$(".preset").forEach((b) => (b.onclick = () => {
      this.draft.preset = b.dataset.p || null;
      this.dirty = (this.draft.preset || null) !== (App.branding.preset || null);
      this.refresh();
    }));
    $("#cz-cancel").onclick = () => { this.draft = structuredClone(App.branding); this.dirty = false; this.refresh(); };
    $("#cz-save").onclick = () => this.save();
    this.refresh();
  },

  adminHeaders() {
    const h = { "Content-Type": "application/json", "X-Lang": Lang.get() };
    if (App.config.admin_protected) {
      let pw = sessionStorage.getItem("admin-pw");
      if (!pw) { pw = prompt(t("th.admin")); if (!pw) return null; sessionStorage.setItem("admin-pw", pw); }
      h["X-Admin-Password"] = pw;
    }
    return h;
  },

  async save() {
    const headers = this.adminHeaders(); if (!headers) return;
    const r = await fetch("/api/theme", { method: "PUT", headers, body: JSON.stringify({ preset: this.draft.preset || null }) });
    if (r.status === 401) { sessionStorage.removeItem("admin-pw"); return toast(t("th.bad_pw"), "error"); }
    if (!r.ok) return toast(t("th.save_err"), "error");
    App.branding = await r.json();
    App.config.branding = App.branding;
    this.draft = structuredClone(App.branding);
    this.dirty = false;
    try { localStorage.removeItem("viewer-mode"); } catch {}
    this.refresh();
    toast(t("th.saved"));
  },

  leave() {
    if (this.dirty) toast(t("th.discarded"));
    this.draft = null; this.dirty = false;
    applyBranding(); renderHeader();
  },

  refresh() {
    applyBranding(this.draft);
    renderHeader();
    $$(".preset").forEach((b) => b.classList.toggle("active", (b.dataset.p || null) === (this.draft.preset || null)));
    const dl = $("#dirty"); dl.textContent = t(this.dirty ? "th.unsaved" : "th.clean"); dl.classList.toggle("on", this.dirty);
    this.preview();
  },

  preview() {
    const d = this.draft;
    const hidden = new Set(d.hidden_tools || []);
    const tools = App.config.tools.filter((tl) => !hidden.has(tl.id));
    const feat = (d.featured_tools || []).map((id) => tools.find((tl) => tl.id === id)).filter(Boolean);
    const list = (feat.length ? feat : tools).slice(0, 6);
    const cats = App.config.categories;
    $("#pv").innerHTML = `
      <header class="topbar"><span class="brand">${brandHTML(d)}</span><nav class="nav">${cats.slice(0, 4).map((c) => `<a>${esc(tx(c.label))}</a>`).join("")}</nav>
        <div class="top-actions"><span class="icon-btn">${icon("moon", 16)}</span></div></header>
      <section class="hero" style="padding:2.2rem 1.5rem 1.4rem"><h1 style="font-size:2rem">${esc(tx(d.hero_title))}</h1><p style="font-size:1rem">${esc(tx(d.hero_subtitle))}</p></section>
      <div class="filters"><button class="chip active">${esc(t("home.all"))}</button>${cats.slice(0, 3).map((c) => `<button class="chip">${esc(tx(c.label))}</button>`).join("")}</div>
      <div class="tools-wrap" style="padding-bottom:2rem"><div class="tool-grid">${list.map(toolCard).join("")}</div></div>`;
    const comp = App.toolsById.compress;
    $("#pv2").innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 280px;min-height:280px">
        <div style="padding:1.5rem;display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-start">
          ${[1, 2].map((n) => `<div class="file-card" style="width:140px"><span class="order-badge">${n}</span><div class="thumb" style="height:150px"><span class="ext">${icon("file", 30)}PDF</span></div><div class="name">${esc(t("th.sample_doc", { n }))}</div><div class="meta">${fmtSize(1258291)}</div></div>`).join("")}
        </div>
        <aside class="sidebar" style="position:static;height:auto">
          <div class="sidebar-head"><h2 style="font-size:1.2rem">${esc(tx(comp.title))}</h2></div>
          <div class="sidebar-body"><div class="opt-cards"><button class="opt-card active"><span class="dot"></span><span><b>${esc(t("th.sample_opt1"))}</b><small>${esc(t("th.sample_opt1d"))}</small></span></button><button class="opt-card"><span class="dot"></span><span><b>${esc(t("th.sample_opt2"))}</b><small>${esc(t("th.sample_opt2d"))}</small></span></button></div></div>
          <div class="sidebar-foot"><button class="btn primary block">${esc(tx(comp.title))} ${icon("arrow-right", 18)}</button></div>
        </aside>
      </div>`;
    $$("#pv a, #pv2 a").forEach((a) => { a.removeAttribute("data-nav"); a.removeAttribute("href"); });
  },
};
