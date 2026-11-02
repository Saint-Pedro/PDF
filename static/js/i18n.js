/* UI translations. English is the default; French via the EN/FR toggle. */
const I18N = {
  en: {
    "nav.themes": "Themes", "nav.lang_title": "Passer en français", "nav.dark": "Dark mode", "nav.light": "Light mode",
    "home.all": "All", "home.search": "Search a tool…", "home.popular": "Most popular", "home.none": "No tool matches.",
    "home.requires": "Requires {x}",
    "land.pick_pdf_multi": "Select PDF files", "land.pick_pdf": "Select a PDF file", "land.pick_multi": "Select files", "land.pick": "Select a file",
    "land.drop_multi": "or drop your files here", "land.drop": "or drop your file here", "land.formats": "Accepted formats: {x}",
    "land.missing": "<b>Missing engine:</b> this tool requires <b>{x}</b>. Install it and restart the app.",
    "drop.overlay": "Drop your files", "err.format": "Unsupported format: {x}", "err.notfound": "Tool not found.", "back": "Back",
    "ws.files": "{n} file(s)", "ws.reorder": "· drag to reorder", "ws.sort": "Sort A→Z", "ws.reverse": "Reverse", "ws.add": "Add", "ws.remove": "Remove",
    "ws.min_files": "Add at least {n} files.", "ws.pages": "{n} page(s)", "ws.locked": "Protected", "ws.choose": "Choose", "ws.none": "None",
    "pg.loading": "Loading pages…", "pg.unreadable": "Unable to read this PDF.", "pg.locked": "This PDF is protected: unlock it first.",
    "pg.rot_all": "Rotate all", "pg.blank": "Blank page", "pg.reverse": "Reverse order", "pg.reset": "Reset", "pg.keep_all": "Keep all",
    "pg.range_rm": "Pages: 2, 5-7", "pg.range_ex": "Pages: 1-3, 8", "pg.mark": "Mark", "pg.select": "Select", "pg.all": "All", "pg.odd": "Odd", "pg.even": "Even", "pg.none": "None",
    "pg.tip_org": "Drag pages to reorder them. Hover a page to rotate or delete it.", "pg.tip_rm": "Click the pages to remove.", "pg.tip_ex": "Click the pages to extract.",
    "pg.rot_l": "Rotate left", "pg.rot_r": "Rotate right", "pg.del": "Delete", "pg.blank_lbl": "Blank", "pg.blank_page": "blank",
    "pg.sum_rm": "<b>{a}</b> page(s) removed · {b} left", "pg.sum_ex": "<b>{a}</b> page(s) selected out of {b}", "pg.sum_org": "{a} page(s) in the final document",
    "pg.need_one": "Select at least one page.", "pg.not_empty": "The document cannot be empty.",
    "run.working": "{x} in progress…", "run.upload": "Uploading files", "run.processing": "Processing…", "run.error": "Something went wrong.", "run.offline": "Cannot reach the server.",
    "run.required": "The field “{x}” is required.",
    "res.ready_one": "Your file is ready!", "res.ready_many": "Your files are ready!", "res.zip": "{n} files (ZIP)", "res.download": "Download", "res.preview": "Preview",
    "res.again": "Start over", "res.continue": "Continue with this file…", "res.optimized": "This PDF was already optimized.",
    "ed.opening": "Opening document…", "ed.select": "Select", "ed.text": "Text", "ed.signature": "Signature", "ed.image": "Image", "ed.rect": "Hide", "ed.redact": "Area",
    "ed.items": "{n} element(s) added", "ed.need_item": "Add at least one element to the document.", "ed.your_text": "Your text", "ed.place": "Click on the page to place the element",
    "ed.tip_redact": "Draw areas to redact with the “Area” tool, and/or enter words below. Affected pages are converted to images: hidden text is truly removed.",
    "ed.tip_sign": "Create your signature, then click on the page to place it. Move it and resize it with the handle.",
    "ed.tip_edit": "Pick a tool on the left, then click on the page. Double-click a text to edit it.",
    "ed.p_text": "Text", "ed.p_size": "Size", "ed.p_color": "Color", "ed.p_font": "Font", "ed.p_bold": "Bold", "ed.p_shape": "Shape color",
    "ed.p_shape_tip": "Tip: a white rectangle visually hides an element (to truly remove it, use “Redact”).",
    "ed.p_redact": "Redaction area on page {n}.", "ed.p_image": "Image on page {n}. Resize it with the handle.",
    "ed.all_pages": "On every page", "ed.dup": "Duplicate", "ed.del": "Delete", "ed.copied": "Copied to {n} page(s)",
    "sig.title": "Your signature", "sig.recent": "Recent signatures", "sig.draw": "Draw", "sig.type": "Type", "sig.upload": "Upload",
    "sig.name": "Your name", "sig.upload_btn": "Choose an image (transparent PNG works best)", "sig.color": "Color", "sig.clear": "Clear",
    "sig.cancel": "Cancel", "sig.use": "Use", "sig.need_draw": "Draw your signature.", "sig.need_name": "Type your name.", "sig.sample": "Signature",
    "th.title": "Themes", "th.desc": "Pick a ready-made theme. Branding (name, logo, texts) is set in app/branding.json.",
    "th.default": "Default", "th.default_desc": "As defined in branding.json", "th.save": "Save", "th.cancel": "Cancel",
    "th.saved": "Theme saved ✓", "th.unsaved": "● Not saved", "th.clean": "No changes", "th.preview": "Live preview", "th.workspace": "Workspace",
    "th.view": "View site", "th.admin": "Admin password:", "th.bad_pw": "Incorrect admin password.", "th.save_err": "Could not save.", "th.discarded": "Unsaved theme changes discarded.",
    "th.sample_doc": "document-{n}.pdf", "th.sample_opt1": "Recommended", "th.sample_opt1d": "Good balance", "th.sample_opt2": "Extreme", "th.sample_opt2d": "Smallest size",
    "size.b": "B", "size.kb": "KB", "size.mb": "MB",
  },
  fr: {
    "nav.themes": "Thèmes", "nav.lang_title": "Switch to English", "nav.dark": "Mode sombre", "nav.light": "Mode clair",
    "home.all": "Tous", "home.search": "Rechercher un outil…", "home.popular": "Les plus utilisés", "home.none": "Aucun outil ne correspond.",
    "home.requires": "Requiert {x}",
    "land.pick_pdf_multi": "Sélectionner des fichiers PDF", "land.pick_pdf": "Sélectionner un fichier PDF", "land.pick_multi": "Sélectionner des fichiers", "land.pick": "Sélectionner un fichier",
    "land.drop_multi": "ou déposez vos fichiers ici", "land.drop": "ou déposez votre fichier ici", "land.formats": "Formats acceptés : {x}",
    "land.missing": "<b>Moteur manquant :</b> cet outil nécessite <b>{x}</b>. Installez-le puis redémarrez l'application.",
    "drop.overlay": "Déposez vos fichiers", "err.format": "Format non pris en charge : {x}", "err.notfound": "Outil introuvable.", "back": "Retour",
    "ws.files": "{n} fichier(s)", "ws.reorder": "· glissez pour réordonner", "ws.sort": "Trier A→Z", "ws.reverse": "Inverser", "ws.add": "Ajouter", "ws.remove": "Retirer",
    "ws.min_files": "Ajoutez au moins {n} fichiers.", "ws.pages": "{n} page(s)", "ws.locked": "Protégé", "ws.choose": "Choisir", "ws.none": "Aucune",
    "pg.loading": "Chargement des pages…", "pg.unreadable": "Impossible de lire ce PDF.", "pg.locked": "Ce PDF est protégé : déverrouillez-le d'abord.",
    "pg.rot_all": "Tout pivoter", "pg.blank": "Page blanche", "pg.reverse": "Inverser l'ordre", "pg.reset": "Réinitialiser", "pg.keep_all": "Tout garder",
    "pg.range_rm": "Pages : 2, 5-7", "pg.range_ex": "Pages : 1-3, 8", "pg.mark": "Marquer", "pg.select": "Sélectionner", "pg.all": "Tout", "pg.odd": "Impaires", "pg.even": "Paires", "pg.none": "Aucune",
    "pg.tip_org": "Glissez les pages pour les réordonner. Survolez une page pour la pivoter ou la supprimer.", "pg.tip_rm": "Cliquez sur les pages à supprimer.", "pg.tip_ex": "Cliquez sur les pages à extraire.",
    "pg.rot_l": "Pivoter à gauche", "pg.rot_r": "Pivoter à droite", "pg.del": "Supprimer", "pg.blank_lbl": "Blanche", "pg.blank_page": "vierge",
    "pg.sum_rm": "<b>{a}</b> page(s) supprimée(s) · {b} restante(s)", "pg.sum_ex": "<b>{a}</b> page(s) sélectionnée(s) sur {b}", "pg.sum_org": "{a} page(s) dans le document final",
    "pg.need_one": "Sélectionnez au moins une page.", "pg.not_empty": "Le document ne peut pas être vide.",
    "run.working": "{x} en cours…", "run.upload": "Envoi des fichiers", "run.processing": "Traitement…", "run.error": "Une erreur est survenue.", "run.offline": "Connexion au serveur impossible.",
    "run.required": "Le champ « {x} » est requis.",
    "res.ready_one": "Votre fichier est prêt !", "res.ready_many": "Vos fichiers sont prêts !", "res.zip": "{n} fichiers (ZIP)", "res.download": "Télécharger", "res.preview": "Aperçu",
    "res.again": "Recommencer", "res.continue": "Continuer avec ce fichier…", "res.optimized": "Ce PDF était déjà optimisé.",
    "ed.opening": "Ouverture du document…", "ed.select": "Sélection", "ed.text": "Texte", "ed.signature": "Signature", "ed.image": "Image", "ed.rect": "Masquer", "ed.redact": "Zone",
    "ed.items": "{n} élément(s) ajouté(s)", "ed.need_item": "Ajoutez au moins un élément sur le document.", "ed.your_text": "Votre texte", "ed.place": "Cliquez sur la page pour placer l'élément",
    "ed.tip_redact": "Dessinez des zones à caviarder avec l'outil « Zone », et/ou indiquez des mots ci-dessous. Les pages concernées seront converties en image : le texte masqué est réellement supprimé.",
    "ed.tip_sign": "Créez votre signature puis cliquez sur la page pour la placer. Déplacez-la et redimensionnez-la avec la poignée.",
    "ed.tip_edit": "Choisissez un outil à gauche puis cliquez sur la page. Double-cliquez sur un texte pour le modifier.",
    "ed.p_text": "Texte", "ed.p_size": "Taille", "ed.p_color": "Couleur", "ed.p_font": "Police", "ed.p_bold": "Gras", "ed.p_shape": "Couleur de la forme",
    "ed.p_shape_tip": "Astuce : un rectangle blanc masque visuellement un élément (pour une suppression réelle, utilisez « Caviarder »).",
    "ed.p_redact": "Zone de caviardage sur la page {n}.", "ed.p_image": "Image sur la page {n}. Redimensionnez avec la poignée.",
    "ed.all_pages": "Sur toutes les pages", "ed.dup": "Dupliquer", "ed.del": "Supprimer", "ed.copied": "Copié sur {n} page(s)",
    "sig.title": "Votre signature", "sig.recent": "Signatures récentes", "sig.draw": "Dessiner", "sig.type": "Taper", "sig.upload": "Importer",
    "sig.name": "Votre nom", "sig.upload_btn": "Choisir une image (PNG transparent idéal)", "sig.color": "Couleur", "sig.clear": "Effacer",
    "sig.cancel": "Annuler", "sig.use": "Utiliser", "sig.need_draw": "Dessinez votre signature.", "sig.need_name": "Tapez votre nom.", "sig.sample": "Signature",
    "th.title": "Thèmes", "th.desc": "Choisissez un thème prêt à l'emploi. L'identité (nom, logo, textes) se règle dans app/branding.json.",
    "th.default": "Par défaut", "th.default_desc": "Tel que défini dans branding.json", "th.save": "Enregistrer", "th.cancel": "Annuler",
    "th.saved": "Thème enregistré ✓", "th.unsaved": "● Non enregistré", "th.clean": "Aucune modification", "th.preview": "Aperçu en direct", "th.workspace": "Espace de travail",
    "th.view": "Voir le site", "th.admin": "Mot de passe administrateur :", "th.bad_pw": "Mot de passe administrateur incorrect.", "th.save_err": "Enregistrement impossible.", "th.discarded": "Modifications de thème non enregistrées abandonnées.",
    "th.sample_doc": "document-{n}.pdf", "th.sample_opt1": "Recommandée", "th.sample_opt1d": "Bon équilibre", "th.sample_opt2": "Extrême", "th.sample_opt2d": "Taille minimale",
    "size.b": "o", "size.kb": "Ko", "size.mb": "Mo",
  },
};

const Lang = {
  get() {
    try { const l = localStorage.getItem("lang"); if (l === "en" || l === "fr") return l; } catch {}
    return (window.__BRANDING__ && window.__BRANDING__.default_lang) || "en";
  },
  set(l) { try { localStorage.setItem("lang", l); } catch {} document.documentElement.lang = l; },
};
document.documentElement.lang = Lang.get();

/* t("key", {vars}) for UI strings; tx(value) for bilingual data ({en, fr} or plain string). */
function t(key, vars = {}) {
  const l = Lang.get();
  let s = (I18N[l] && I18N[l][key]) ?? I18N.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}
function tx(v) {
  if (v && typeof v === "object") return v[Lang.get()] ?? v.en ?? Object.values(v)[0];
  return v ?? "";
}
