/* Service Worker - 缓存 app shell，API 始终走网络保证实时 */
const CACHE = "rhythm-v1";
const SHELL = [
  "/",
  "/index.html",
  "/manifest.json",
  "/apple-touch-icon.png",
  "/vendor/echarts.min.js",
  "/vendor/leaflet.js",
  "/vendor/leaflet-heat.js",
  "/vendor/leaflet.css"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL))
      .catch(() => {})
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  // 数据接口始终走网络，页面壳走缓存优先
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    e.respondWith(fetch(e.request));
    return;
  }
  e.respondWith(
    caches.match(e.request).then((hit) => {
      if (hit) return hit;
      return fetch(e.request).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return res;
      }).catch(() => caches.match("/"));
    })
  );
});
