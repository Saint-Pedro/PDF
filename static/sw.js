/* Service worker: makes the app installable and loads the interface even
   without a network connection. API calls are never cached. */
const VERSION = new URL(self.location).searchParams.get("v") || "dev";
const CACHE = `pdfstudio-${VERSION}`;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(["/", "/static/css/app.css?v=" + VERSION])).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith("pdfstudio-") && k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  // Static files: cache first (they are versioned). Pages: network first, cache as fallback.
  if (url.pathname.startsWith("/static/")) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
      return res;
    })));
  } else {
    e.respondWith(fetch(e.request).then((res) => {
      if (res.ok && e.request.mode === "navigate") { const copy = res.clone(); caches.open(CACHE).then((c) => c.put("/", copy)); }
      return res;
    }).catch(() => caches.match(e.request).then((hit) => hit || caches.match("/"))));
  }
});
