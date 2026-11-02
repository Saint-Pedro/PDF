/* Moteur de thème : transforme la configuration de marque en variables CSS.
   Chargé dans <head> pour éviter tout « flash » de thème. */
(function () {
  const FONT_STACKS = {
    system: { label: "Système (par défaut)", stack: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' },
    humanist: { label: "Humaniste", stack: 'Seravek, "Gill Sans Nova", Ubuntu, Calibri, "DejaVu Sans", source-sans-pro, sans-serif' },
    geometric: { label: "Géométrique", stack: 'Avenir, Montserrat, Corbel, "URW Gothic", source-sans-pro, sans-serif' },
    rounded: { label: "Arrondie", stack: 'ui-rounded, "Hiragino Maru Gothic ProN", Quicksand, Comfortaa, Manjari, "Arial Rounded MT", "Arial Rounded MT Bold", Calibri, source-sans-pro, sans-serif' },
    industrial: { label: "Industrielle (condensée)", stack: 'Bahnschrift, "DIN Alternate", "Franklin Gothic Medium", "Nimbus Sans Narrow", sans-serif-condensed, sans-serif' },
    serif: { label: "Serif classique", stack: 'Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif' },
    didone: { label: "Didone (élégante)", stack: 'Didot, "Bodoni MT", "Noto Serif Display", "URW Palladio L", P052, Sylfaen, serif' },
    mono: { label: "Monospace", stack: 'ui-monospace, "Cascadia Code", "Source Code Pro", Menlo, Consolas, "DejaVu Sans Mono", monospace' },
    custom: { label: "Police importée", stack: null },
    google: { label: "Google Fonts (en ligne)", stack: null },
  };

  const PRESETS = {
    classique: { label: "Classique", desc: "Rouge vif, net et familier",
      colors: { primary: "#e5322d", on_primary: "#ffffff", bg: "#f5f5fa", surface: "#ffffff", text: "#24252f", muted: "#6c6f80", border: "#e6e6ee" },
      dark: { primary: "#ff5a52", on_primary: "#ffffff", bg: "#121318", surface: "#1c1d25", text: "#ececf2", muted: "#9a9cad", border: "#2c2d39" },
      font: { body: "system", heading: "system" }, radius: 14, card_style: "elevated", icon_style: "tinted", header_style: "surface", hero_style: "plain", tool_colors: true, mode: "light" },
    ocean: { label: "Océan", desc: "Bleu apaisant, formes douces",
      colors: { primary: "#0b84d8", on_primary: "#ffffff", bg: "#f1f7fc", surface: "#ffffff", text: "#0f2537", muted: "#5d7489", border: "#dce8f2" },
      dark: { primary: "#38a9f5", on_primary: "#06263d", bg: "#0b1622", surface: "#122232", text: "#e6f1fa", muted: "#8aa3b8", border: "#1f3346" },
      font: { body: "rounded", heading: "rounded" }, radius: 20, card_style: "elevated", icon_style: "tinted", header_style: "glass", hero_style: "gradient", tool_colors: false, mode: "light" },
    foret: { label: "Forêt", desc: "Vert profond et titres serif",
      colors: { primary: "#1f7a4d", on_primary: "#ffffff", bg: "#f4f6f1", surface: "#ffffff", text: "#1d2a22", muted: "#647266", border: "#dfe5da" },
      dark: { primary: "#47b07a", on_primary: "#0b2416", bg: "#101511", surface: "#18201a", text: "#e7efe8", muted: "#93a596", border: "#26322a" },
      font: { body: "humanist", heading: "serif" }, radius: 10, card_style: "outline", icon_style: "outline", header_style: "surface", hero_style: "pattern", tool_colors: false, mode: "light" },
    minuit: { label: "Minuit", desc: "Sombre, violet, effet verre",
      colors: { primary: "#7c5cff", on_primary: "#ffffff", bg: "#f6f5ff", surface: "#ffffff", text: "#211d3a", muted: "#6d6890", border: "#e5e2f7" },
      dark: { primary: "#9b84ff", on_primary: "#140d33", bg: "#0d0b1a", surface: "#17142b", text: "#ece9ff", muted: "#9d97c4", border: "#2a2547" },
      font: { body: "geometric", heading: "geometric" }, radius: 18, card_style: "glass", icon_style: "solid", header_style: "glass", hero_style: "gradient", tool_colors: true, mode: "dark" },
    brutal: { label: "Brutaliste", desc: "Contrasté, bordures épaisses",
      colors: { primary: "#111111", on_primary: "#fff35c", bg: "#fff9db", surface: "#ffffff", text: "#111111", muted: "#3d3d3d", border: "#111111" },
      dark: { primary: "#fff35c", on_primary: "#111111", bg: "#111111", surface: "#1b1b1b", text: "#fafafa", muted: "#c9c9c9", border: "#fafafa" },
      font: { body: "mono", heading: "industrial" }, radius: 0, card_style: "brutal", icon_style: "solid", header_style: "surface", hero_style: "plain", tool_colors: true, mode: "light" },
    pastel: { label: "Pastel", desc: "Rose tendre, très arrondi",
      colors: { primary: "#e0569b", on_primary: "#ffffff", bg: "#fff6fa", surface: "#ffffff", text: "#3a2531", muted: "#8a6b7b", border: "#f6dfe9" },
      dark: { primary: "#f27bb5", on_primary: "#33091d", bg: "#1a1116", surface: "#24171e", text: "#f8e9f0", muted: "#bb98aa", border: "#3a2630" },
      font: { body: "rounded", heading: "rounded" }, radius: 24, card_style: "flat", icon_style: "tinted", header_style: "surface", hero_style: "gradient", tool_colors: true, mode: "light" },
    corporate: { label: "Corporate", desc: "Bleu marine, sobre, monochrome",
      colors: { primary: "#1e3a8a", on_primary: "#ffffff", bg: "#f4f6fa", surface: "#ffffff", text: "#111827", muted: "#5b6475", border: "#dfe3ea" },
      dark: { primary: "#6c8cf0", on_primary: "#0a1433", bg: "#0c111c", surface: "#141b2a", text: "#e7ebf3", muted: "#929cb0", border: "#232c3e" },
      font: { body: "system", heading: "industrial" }, radius: 6, card_style: "outline", icon_style: "mono", header_style: "primary", hero_style: "banner", tool_colors: false, mode: "light" },
    terre: { label: "Terre cuite", desc: "Chaleureux, éditorial",
      colors: { primary: "#c2502a", on_primary: "#ffffff", bg: "#faf5ef", surface: "#fffdfa", text: "#2f2118", muted: "#7d6a5c", border: "#eee2d6" },
      dark: { primary: "#e57a52", on_primary: "#2b0f04", bg: "#17110d", surface: "#211913", text: "#f4ebe3", muted: "#b39f90", border: "#352920" },
      font: { body: "humanist", heading: "didone" }, radius: 12, card_style: "flat", icon_style: "tinted", header_style: "transparent", hero_style: "plain", tool_colors: false, mode: "light" },
  };

  /* ---------- outils couleur ---------- */
  function hexToRgb(h) {
    h = (h || "#000").replace("#", "");
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    const n = parseInt(h.slice(0, 6), 16) || 0;
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const rgbToHex = (r, g, b) => "#" + [r, g, b].map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h = 0, s = 0; const l = (max + min) / 2;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
      h /= 6;
    }
    return [h * 360, s * 100, l * 100];
  }
  function hslToHex(h, s, l) {
    s /= 100; l /= 100;
    const k = (n) => (n + h / 30) % 12, a = s * Math.min(l, 1 - l);
    const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return rgbToHex(f(0) * 255, f(8) * 255, f(4) * 255);
  }
  function luminance(hex) {
    const [r, g, b] = hexToRgb(hex).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  function contrast(a, b) {
    const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  }
  const bestOn = (bg) => (contrast(bg, "#ffffff") >= contrast(bg, "#111111") ? "#ffffff" : "#111111");
  function mix(a, b, t) {
    const A = hexToRgb(a), B = hexToRgb(b);
    return rgbToHex(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t);
  }
  const alpha = (hex, a) => { const [r, g, b] = hexToRgb(hex); return `rgba(${r},${g},${b},${a})`; };

  /* Génère une palette complète et harmonieuse à partir d'une couleur. */
  function derivePalette(primary) {
    const [h, s] = rgbToHsl(...hexToRgb(primary));
    const ts = Math.min(s, 30);
    const light = {
      primary, on_primary: bestOn(primary),
      bg: hslToHex(h, Math.min(ts, 25), 97), surface: "#ffffff",
      text: hslToHex(h, Math.min(ts, 20), 15), muted: hslToHex(h, Math.min(ts, 12), 45),
      border: hslToHex(h, Math.min(ts, 22), 90),
    };
    const [, , l] = rgbToHsl(...hexToRgb(primary));
    const dprimary = l < 55 ? hslToHex(h, Math.min(s + 5, 95), 64) : primary;
    const dark = {
      primary: dprimary, on_primary: bestOn(dprimary),
      bg: hslToHex(h, Math.min(ts, 22), 7), surface: hslToHex(h, Math.min(ts, 20), 11),
      text: hslToHex(h, Math.min(ts, 18), 93), muted: hslToHex(h, Math.min(ts, 12), 64),
      border: hslToHex(h, Math.min(ts, 18), 19),
    };
    return { colors: light, dark };
  }

  /* Couleur dominante (la plus saturée et fréquente) d'une image. */
  function dominantColors(img, count = 5) {
    const c = document.createElement("canvas");
    const S = 64; c.width = S; c.height = S;
    const ctx = c.getContext("2d");
    ctx.drawImage(img, 0, 0, S, S);
    const data = ctx.getImageData(0, 0, S, S).data;
    const buckets = {};
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] < 128) continue;
      const [r, g, b] = [data[i], data[i + 1], data[i + 2]];
      const [hh, ss, ll] = rgbToHsl(r, g, b);
      if (ll > 94 || ll < 6) continue;
      const key = [Math.round(hh / 15), Math.round(ss / 25), Math.round(ll / 20)].join(",");
      const bk = (buckets[key] = buckets[key] || { n: 0, r: 0, g: 0, b: 0, s: ss });
      bk.n++; bk.r += r; bk.g += g; bk.b += b;
    }
    return Object.values(buckets)
      .map((b) => ({ hex: rgbToHex(b.r / b.n, b.g / b.n, b.b / b.n), score: b.n * (0.35 + b.s / 100) }))
      .sort((a, b) => b.score - a.score).slice(0, count).map((b) => b.hex);
  }

  /* ---------- application du thème ---------- */
  function resolveMode(b) {
    if (b.mode === "auto") return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    return b.mode === "dark" ? "dark" : "light";
  }

  function fontStack(key, b) {
    const f = b.font || {};
    if (key === "custom" && f.custom_name) return `"${f.custom_name}", ${FONT_STACKS.system.stack}`;
    if (key === "google" && f.google) return `"${f.google}", ${FONT_STACKS.system.stack}`;
    return (FONT_STACKS[key] || FONT_STACKS.system).stack || FONT_STACKS.system.stack;
  }

  function apply(b) {
    const root = document.documentElement;
    const mode = resolveMode(b);
    const c = mode === "dark" ? b.dark : b.colors;
    const isDark = mode === "dark";
    const vars = {
      "--primary": c.primary, "--on-primary": c.on_primary || bestOn(c.primary),
      "--primary-soft": alpha(c.primary, isDark ? 0.18 : 0.1),
      "--primary-hover": mix(c.primary, isDark ? "#ffffff" : "#000000", 0.12),
      "--bg": c.bg, "--surface": c.surface, "--surface-2": mix(c.surface, c.text, isDark ? 0.06 : 0.035),
      "--text": c.text, "--muted": c.muted, "--border": c.border,
      "--shadow-color": isDark ? "0,0,0" : hexToRgb(c.text).join(","),
      "--radius": (b.radius ?? 14) + "px",
      "--radius-sm": Math.max(0, Math.round((b.radius ?? 14) * 0.6)) + "px",
      "--font-body": fontStack(b.font?.body, b),
      "--font-heading": fontStack(b.font?.heading, b),
      "--logo-h": (b.logo_height || 34) + "px",
    };
    for (const [k, v] of Object.entries(vars)) root.style.setProperty(k, v);
    const ds = root.dataset;
    ds.mode = mode; ds.density = b.density || "comfortable"; ds.card = b.card_style || "elevated";
    ds.icon = b.icon_style || "tinted"; ds.header = b.header_style || "surface"; ds.hero = b.hero_style || "plain";
    ds.toolColors = b.tool_colors === false ? "off" : "on"; ds.desc = b.show_descriptions === false ? "off" : "on";
    root.style.colorScheme = mode;

    // Polices importées / Google Fonts
    let st = document.getElementById("brand-fonts");
    if (!st) { st = document.createElement("style"); st.id = "brand-fonts"; document.head.appendChild(st); }
    let css = "";
    if (b.font?.custom_url && b.font?.custom_name) css += `@font-face{font-family:"${b.font.custom_name}";src:url("${b.font.custom_url}");font-display:swap;font-weight:100 900;}`;
    st.textContent = css + (b.custom_css || "");
    const gid = "brand-google-font";
    const usesGoogle = b.font?.google && (b.font.body === "google" || b.font.heading === "google");
    let link = document.getElementById(gid);
    if (usesGoogle) {
      const href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(b.font.google).replace(/%20/g, "+")}:wght@400;500;600;700;800&display=swap`;
      if (!link) { link = document.createElement("link"); link.id = gid; link.rel = "stylesheet"; document.head.appendChild(link); }
      if (link.href !== href) link.href = href;
    } else if (link) link.remove();

    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = c.primary;
  }

  window.Theme = { apply, derivePalette, dominantColors, contrast, bestOn, mix, FONT_STACKS, PRESETS, hexToRgb };
  if (window.__BRANDING__) apply(window.__BRANDING__);
})();
