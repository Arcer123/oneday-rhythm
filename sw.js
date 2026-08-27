/* Service Worker - 让"远程同步更新"生效
 *
 * 关键改动：页面壳（HTML / 导航请求）改成「网络优先」：
 *   每次打开都先拉服务器最新版，拉不到才用本地缓存（离线兜底）。
 *   这样你改完服务器上的 index.html 后，用户手机下一次打开就自动更新，
 *   无需重新打包、无需重装。
 *
 * 静态资源（js/css/图片）用「缓存优先 + 后台刷新」，兼顾速度和更新。
 * API 请求（/api/*）和跨域请求始终走网络。
 */
const CACHE = "rhythm-v4";
const SHELL = [
  "/",
  "/index.html",
  "/manifest.json",
  "/icon-192.png",
  "/icon-512.png",
  "/apple-touch-icon.png",
  "/hz_density.json",
  "/events.json",
  "/vendor/echarts.min.js",
  "/vendor/leaflet.js",
  "/vendor/leaflet-heat.js",
  "/vendor/leaflet.css"
];

self.addEventListener("install", (e) => {
  // 逐项缓存：某项失败（如某个资源暂不可用）不拖垮整个 shell，
  // 其余资源仍能离线缓存，避免历史上 addAll 一失败就全盘不缓存。
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await Promise.allSettled(SHELL.map((u) => cache.add(u)));
    await self.skipWaiting();
  })());
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

  // 跨域 & 数据接口：永远走网络，保证实时
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    // 失败返回 504：底图瓦片会触发 tileerror（从而正常走多源兜底），
    // 接口请求则由页面自身的 catch 处理；同时避免 SW 里出现未处理拒绝。
    e.respondWith(fetch(e.request).catch(() => new Response("", { status: 504, statusText: "offline" })));
    return;
  }

  // 页面导航（HTML 壳）：网络优先，离线才回退缓存
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          // 只缓存“成功”的 HTML，避免把 500 等错误页缓存进离线壳
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copy));
          }
          return res;
        })
        .catch(() => caches.match(e.request).then((hit) => hit || caches.match("/")))
    );
    return;
  }

  // 静态资源：缓存优先，同时后台拉新版本替换
  e.respondWith(
    caches.match(e.request).then((hit) => {
      const update = fetch(e.request).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return res;
      }).catch(() => hit);
      return hit || update;
    })
  );
});
