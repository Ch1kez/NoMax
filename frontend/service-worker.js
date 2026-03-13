const CACHE_NAME = "nomax-static-v3";
const APP_SHELL = ["/", "/index.html", "/manifest.json", "/favicon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() =>
      caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  // Для API и WS не кэшируем ответы, только network
  const reqUrl = new URL(event.request.url);
  const isApi = ["/auth", "/relationships", "/calls", "/me", "/ws"].some((p) =>
    reqUrl.pathname.startsWith(p)
  );
  if (isApi) {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(event.request);
    if (cached) return cached;
    try {
      const networkResp = await fetch(event.request);
      if (event.request.method === "GET" && networkResp && networkResp.status === 200) {
        const cache = await caches.open(CACHE_NAME);
        cache.put(event.request, networkResp.clone());
      }
      return networkResp;
    } catch (_e) {
      // Не падаем с Load failed, даже если сеть недоступна
      if (cached) return cached;
      return new Response("Offline", { status: 503, statusText: "Offline" });
    }
  })());
});

