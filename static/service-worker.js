// PIF Dashboard Service Worker
// Cache-first for the app shell, network-first for API calls.
//
// Update model: a newly installed worker STAYS in the "waiting" state until the
// user explicitly accepts the update in-app (see initPWA / _promptSWUpdate in
// app.js). The worker never reloads the page on its own — this is what used to
// cause the "page flashes as if it reloads" while working.
//
// Single VERSION constant — bump it on every frontend deploy so old caches are
// dropped on activate.

const VERSION = 'v27';
const STATIC_CACHE = 'pif-static-' + VERSION;
const API_CACHE = 'pif-api-' + VERSION;

// App shell files to cache on install
const APP_SHELL = [
  '/',
  '/static/app.js',
  '/static/manifest.json'
];

// Install — cache the app shell. No skipWaiting(): the new worker waits until
// the user accepts the update.
self.addEventListener('install', (event) => {
  console.log('[SW] Installing', VERSION);
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(APP_SHELL))
  );
});

// Activate — clean up old caches, then take control of open pages.
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating', VERSION);
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== API_CACHE)
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      ))
      .then(() => self.clients.claim())
  );
});

// Fetch — handle requests
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip chrome-extension and other non-http requests
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // API requests: network-first with cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstWithCache(request, API_CACHE));
    return;
  }

  // Static assets (JS, CSS, fonts): cache-first
  if (url.pathname.startsWith('/static/') ||
      url.pathname.endsWith('.js') ||
      url.pathname.endsWith('.css') ||
      url.pathname.endsWith('.woff2') ||
      url.pathname.endsWith('.woff')) {
    event.respondWith(cacheFirstWithNetwork(request, STATIC_CACHE));
    return;
  }

  // HTML pages: network-first (to get fresh content)
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstWithCache(request, STATIC_CACHE));
    return;
  }

  // Default: network-first
  event.respondWith(networkFirstWithNetwork(request));
});

// Cache-first strategy with network fallback
async function cacheFirstWithNetwork(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.log('[SW] Network request failed:', error);
    // Only fall back to the app shell for actual page navigations —
    // never return HTML where JS/CSS was expected.
    if (request.mode === 'navigate') {
      return cache.match('/');
    }
    throw error;
  }
}

// Network-first strategy with cache fallback
async function networkFirstWithCache(request, cacheName) {
  const cache = await caches.open(cacheName);

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.log('[SW] Network failed, trying cache:', request.url);
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    // For API requests, return a JSON error response
    if (request.url.includes('/api/')) {
      return new Response(
        JSON.stringify({ error: 'Offline', message: 'Datele nu sunt disponibile offline' }),
        {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }
    throw error;
  }
}

// Network-first with no cache fallback (for page navigation)
async function networkFirstWithNetwork(request) {
  try {
    return await fetch(request);
  } catch (error) {
    console.log('[SW] Network request failed:', error);
    throw error;
  }
}

// Listen for messages from the main thread
self.addEventListener('message', (event) => {
  // Sent by app.js only after the user accepts the update banner.
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }

  if (event.data === 'clearApiCache') {
    caches.delete(API_CACHE).then(() => {
      console.log('[SW] API cache cleared');
    });
  }
});
