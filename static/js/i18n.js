/* Translations: static/locales/<lang>.json
   - "ui":   interface strings, by key (plural forms: {one, other})
   - "data": tool texts, keyed by their English source text
   Language = user's choice > browser language > branding default. */
const SUPPORTED_LANGS = ["en", "fr", "es", "de", "it"];
const LANG_NAMES = { en: "English", fr: "Français", es: "Español", de: "Deutsch", it: "Italiano" };
const LOCALES = {};

const Lang = {
  detect() {
    const b = window.__BRANDING__ || {};
    const allowed = (b.languages || SUPPORTED_LANGS).filter((l) => SUPPORTED_LANGS.includes(l));
    try { const l = localStorage.getItem("lang"); if (allowed.includes(l)) return l; } catch {}
    if (!b.default_lang || b.default_lang === "auto") {
      for (const nl of navigator.languages || [navigator.language || "en"]) {
        const code = (nl || "").slice(0, 2).toLowerCase();
        if (allowed.includes(code)) return code;
      }
      return allowed.includes("en") ? "en" : allowed[0];
    }
    return allowed.includes(b.default_lang) ? b.default_lang : allowed[0];
  },
  current: null,
  get() { return this.current || (this.current = this.detect()); },
  async load(l) {
    for (const code of new Set(["en", l])) {
      if (LOCALES[code]) continue;
      try { LOCALES[code] = await (await fetch(`/static/locales/${code}.json`)).json(); }
      catch { LOCALES[code] = { ui: {}, data: {} }; }
    }
  },
  async set(l) {
    await this.load(l);
    this.current = l;
    try { localStorage.setItem("lang", l); } catch {}
    document.documentElement.lang = l;
  },
};
document.documentElement.lang = Lang.get();

/* t("key", {vars}) for UI strings. A var named n selects the plural form. */
function t(key, vars = {}) {
  const l = Lang.get();
  let s = LOCALES[l]?.ui?.[key] ?? LOCALES.en?.ui?.[key] ?? key;
  if (s && typeof s === "object") {
    let form = "other";
    try { form = new Intl.PluralRules(l).select(Number(vars.n ?? 0)); } catch {}
    s = s[form] ?? s.other ?? s.one;
  }
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

/* tx(value): tool texts (English source string) or branding texts ({en, fr, …}). */
function tx(v) {
  const l = Lang.get();
  if (v && typeof v === "object") return v[l] ?? v.en ?? Object.values(v)[0];
  if (typeof v === "string") return LOCALES[l]?.data?.[v] ?? v;
  return v ?? "";
}
