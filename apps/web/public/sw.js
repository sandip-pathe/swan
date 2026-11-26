// The root is a static, public sign-in shell. Private data lives in account-scoped IndexedDB.
// Never cache authenticated API responses, tokens or writes here.
const CACHE = "swan-public-bot-v8";
const ASSETS = ["/offline.html", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png",
  "/fonts/inter-variable.woff2", "/fonts/plex-sans-0.woff2", "/fonts/plex-sans-1.woff2",
  "/fonts/plex-sans-2.woff2", "/fonts/plex-sans-3.woff2", "/fonts/plex-mono-0.woff2"];
async function saveShell(cache, response) {
  if (!response.ok || !response.headers.get("content-type")?.includes("text/html")) throw new Error("Shell unavailable");
  const html = await response.clone().text();
  const chunks = [...new Set(html.match(/\/_next\/static\/[^"'<>\s\\]+\.(?:js|css)/g) || [])];
  if (!chunks.length) throw new Error("Shell assets unavailable");
  // Commit the shell only after every referenced entry script/style is available.
  await Promise.all(chunks.map(async path => {
    if (!(await cache.match(path))) await cache.add(path);
  }));
  await cache.put("/", response.clone());
}
self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(ASSETS);
    await saveShell(cache, await fetch("/", { cache: "reload" }));
    await self.skipWaiting();
  })());
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
  if (event.request.mode === "navigate" && url.pathname === "/") {
    // Open the downloaded UI immediately; refresh a complete shell in the background.
    const refresh = (async () => {
      const response = await fetch(event.request, { signal: AbortSignal.timeout(5000) });
      const cache = await caches.open(CACHE);
      await saveShell(cache, response);
      return response;
    })().catch(() => undefined);
    event.waitUntil(refresh.then(() => undefined));
    event.respondWith((async () => (await caches.match("/")) || await refresh ||
      (await caches.match("/offline.html")) || Response.error())());
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
self.addEventListener("push", event => {
  event.waitUntil((async () => {
    let value;
    try { value = event.data.json(); } catch { return; }
    const age = Date.now() - Date.parse(value.published_at);
    if (!Number.isFinite(age) || age < -30000 || age > 60000) return;
    await self.registration.showNotification("SWAN idea updated", {
      body: "Open Insights for fresh conditions and source times.", icon: "/icon-192.png",
      tag: "swan-idea-" + String(value.idea_id).slice(0, 64), data: { url: "/#insights" },
    });
  })());
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of windows) {
      if (new URL(client.url).origin === self.location.origin) {
        await client.navigate("/#insights"); await client.focus(); return;
      }
    }
    await self.clients.openWindow("/#insights");
  })());
});
