// Public assets only. Authenticated HTML, API responses and writes are never cached.
const CACHE = "swan-public-bot-v1";
const ASSETS = ["/offline.html", "/icon-192.png", "/icon-512.png", "/fonts/inter-variable.woff2"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(Promise.all([
    caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("swan-") && key !== CACHE).map(key => caches.delete(key)))),
    self.clients.claim(),
  ]));
});
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(async () => (await caches.match("/offline.html")) || Response.error()));
    return;
  }
  if (ASSETS.includes(url.pathname) && !url.search) event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
