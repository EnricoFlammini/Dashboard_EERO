/**
 * Service Worker for eero Dashboard PWA (v1.6.0)
 * Provides offline shell caching and fast background sync
 */

const CACHE_NAME = 'eero-dashboard-v1.6.0';
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
  '/static/locales/it.json',
  '/static/locales/en.json',
  '/static/manifest.json'
];

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
