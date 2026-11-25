// The root is a static, public sign-in shell. Private data lives in account-scoped IndexedDB.
// Never cache authenticated API responses, tokens or writes here.
const CACHE = "swan-public-bot-v2";
const ASSETS = ["/", "/offline.html", "/icon-192.png", "/icon-512.png", "/fonts/inter-variable.woff2"];
self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(ASSETS);
    const shell = await cache.match("/");
    const html = shell ? await shell.text() : "";
    // Cache the shell's entry scripts/styles before promising offline reloads.
    const chunks = [...new Set(html.match(/\/_next\/static\/[^"'<>\s\\]+\.(?:js|css)/g) || [])];
    await cache.addAll(chunks);
  })());
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
  if (event.request.mode === "navigate" && url.pathname === "/" && !url.search) {
    event.respondWith(fetch(event.request).then(async response => {
      if (response.ok) { const cache = await caches.open(CACHE); await cache.put("/", response.clone()); }
      return response;
    }).catch(async () => (await caches.match("/")) || (await caches.match("/offline.html")) || Response.error()));
    return;
  }
  if (url.pathname.startsWith("/_next/static/") && !url.search) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(async response => {
      if (response.ok) { const cache = await caches.open(CACHE); await cache.put(event.request, response.clone()); }
      return response;
    })));
    return;
  }
  if (ASSETS.includes(url.pathname) && !url.search) event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
