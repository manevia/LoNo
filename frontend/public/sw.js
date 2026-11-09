/* LoNo service worker: fast repeat visits and an offline screen.
   - Website files with a content hash in the name (/static/...): cache-first, they never change.
   - Page loads: network-first, falling back to the cached app shell, then to offline.html.
   - Images: stale-while-revalidate with a size cap.
   - /api and media streams: never cached here (personal data; video is too large). */
const VERSION = "lono-v1";
const SHELL = `${VERSION}-shell`;
const STATIC = `${VERSION}-static`;
const IMAGES = `${VERSION}-images`;
const MAX_IMAGES = 150;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL).then((c) => c.addAll(["/", "/offline.html", "/manifest.webmanifest", "/icons/icon-192.png"]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function trim(cacheName, max) {
  const c = await caches.open(cacheName);
  const keys = await c.keys();
  for (let i = 0; i < keys.length - max; i++) await c.delete(keys[i]);
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === self.location.origin && (url.pathname.startsWith("/api/") || url.pathname === "/sw.js")) return;
  if (req.headers.has("range")) return; // media streaming

  // Page navigations: network first so new releases show immediately.
  if (req.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const res = await fetch(req);
        if (res.ok) (await caches.open(SHELL)).put("/", res.clone());
        return res;
      } catch {
        return (await caches.match("/", { cacheName: SHELL })) || (await caches.match("/offline.html"));
      }
    })());
    return;
  }

  // Hashed website files: cache-first.
  if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
    event.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) caches.open(STATIC).then((c) => c.put(req, res.clone()));
      return res;
    })));
    return;
  }

  // Images (ours and thumbnails from image hosts): stale-while-revalidate.
  if (req.destination === "image") {
    event.respondWith((async () => {
      const cache = await caches.open(IMAGES);
      const hit = await cache.match(req);
      const refresh = fetch(req).then((res) => {
        if (res.ok || res.type === "opaque") { cache.put(req, res.clone()); trim(IMAGES, MAX_IMAGES); }
        return res;
      }).catch(() => hit);
      return hit || refresh;
    })());
  }
});
