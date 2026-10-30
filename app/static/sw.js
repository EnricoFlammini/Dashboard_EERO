/**
 * Service Worker for eero Dashboard PWA (v1.6.2)
 * Provides offline shell caching and fast background sync
 */

const CACHE_NAME = 'eero-dashboard-v1.6.2';
const STATIC_ASSETS = [
  '/',
  '/dashboard',
  '/static/css/styles.css',
  '/static/css/fonts.css',
  '/static/vendor/tailwind.min.js',
  '/static/vendor/alpine.min.js',
  '/static/vendor/chart.umd.min.js',
  '/static/vendor/lucide.min.js',
  '/static/js/app.js',
  '/static/manifest.json'
];
// Locale files (/static/locales/<lang>.json) are not listed here on purpose: the
// language set comes from the server (SUPPORTED_LANGUAGES), and the network-first
// branch of the fetch handler below caches each locale the first time the page
// requests it, so the offline fallback covers every language the viewer has used.

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('SW: pre-caching non-critical failure', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Bypass service worker cache for API requests and live telemetry
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Network-first for HTML documents to ensure freshness, falling back to cache
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/dashboard') || caches.match('/'))
    );
    return;
  }

  // Network-first for locale files so a release never pairs new markup with
  // stale translations; the cached copy is only used offline.
  if (url.pathname.startsWith('/static/locales/')) {
    event.respondWith(
      fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(url.pathname, responseToCache);
          });
        }
        return networkResponse;
      }).catch(() => caches.match(url.pathname))
    );
    return;
  }

  // Stale-while-revalidate for static assets
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      }).catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});
