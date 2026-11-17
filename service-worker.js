const SHELL_CACHE = "weather-shell-v1";
const DATA_CACHE = "weather-data-v1";
const SHELL = [
  "./index.html", "./browse.html", "./trends.html",
  "./css/styles.css", "./js/common.js", "./js/today.js", "./js/browse.js",
  "./js/trends.js", "./js/charts.js", "./manifest.webmanifest",
  "./assets/icon.svg", "./assets/icon-192.png", "./assets/icon-512.png",
];
const DATA_PATHS = new Set([
  new URL("./data/status.json", self.registration.scope).pathname,
  new URL("./data/history.csv", self.registration.scope).pathname,
]);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith("weather-") && ![SHELL_CACHE, DATA_CACHE].includes(key)).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (DATA_PATHS.has(url.pathname)) {
    event.respondWith((async () => {
      const cache = await caches.open(DATA_CACHE);
      try {
        const response = await fetch(request);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        await cache.put(request, response.clone());
        return response;
      } catch {
        return await cache.match(request) || new Response("Data is not available yet.", { status: 503 });
      }
    })());
    return;
  }
  event.respondWith((async () => {
    const cache = await caches.open(SHELL_CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;
    try {
      const response = await fetch(request);
      if (response.ok) await cache.put(request, response.clone());
      return response;
    } catch {
      if (request.mode === "navigate") return await cache.match("./index.html") || Response.error();
      return Response.error();
    }
  })());
});
