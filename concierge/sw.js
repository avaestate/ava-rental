/* AVA Concierge — service worker
   Precaches the app shell + local imagery so the installed app opens instantly
   and keeps working on flaky island connections. Bump CACHE_VERSION on every
   release that changes index.html or the assets below. */
var CACHE_VERSION = "ava-concierge-v2";
var RUNTIME = CACHE_VERSION + "-runtime";

var PRECACHE = [
  "./",
  "./index.html",
  "./manifest.json",
  "./assets/icon-512.png",
  "./assets/icon-maskable-512.png",
  "./img/bikes_hero.jpg",
  "./img/taxi.jpg",
  "./img/speedboat.jpg",
  "./img/jetski.jpg",
  "./img/massage.jpg",
  "./img/tickets.jpg",
  "./img/nanny.jpg",
  "./img/excursions.jpg",
  "./img/grocery.jpg",
  "./img/laundry.jpg",
  "./img/yoga.jpg"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE_VERSION).then(function (cache) {
      // add one by one so a single missing file never blocks installation
      return Promise.all(PRECACHE.map(function (url) {
        return cache.add(url).catch(function () {});
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        if (k !== CACHE_VERSION && k !== RUNTIME) return caches.delete(k);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);

  // Never intercept WhatsApp / external navigations
  if (req.mode === "navigate" && url.origin !== self.location.origin) return;

  // App shell: network first, fall back to the cached index.html when offline
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE_VERSION).then(function (c) { c.put("./index.html", copy); });
        return res;
      }).catch(function () {
        return caches.match("./index.html");
      })
    );
    return;
  }

  // Everything else (local images, fonts, icon fonts, remote photos):
  // stale-while-revalidate — serve from cache instantly, refresh in the background
  e.respondWith(
    caches.match(req).then(function (cached) {
      var network = fetch(req).then(function (res) {
        if (res && (res.status === 200 || res.type === "opaque")) {
          var copy = res.clone();
          caches.open(RUNTIME).then(function (c) { c.put(req, copy); });
        }
        return res;
      }).catch(function () { return cached; });
      return cached || network;
    })
  );
});
