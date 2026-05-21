// PIF Dashboard Service Worker
// Cache-first strategy for app shell, network-first for API calls

const CACHE_NAME = 'pif-dashboard-v19';
const STATIC_CACHE = 'pif-static-v19';
const API_CACHE = 'pif-api-v19';

// App shell files to cache on install
const APP_SHELL = [
  '/',
  '/static/app.js',
  '/static/manifest.json'
];

// API endpoints that should be cached
const CACHEABLE_API = [
  '/api/proiecte',
  '/api/stats',
  '/api/global-tasks'
];

// Install event - cache app shell
self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Caching app shell');
        return cache.addAll(APP_SHELL);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== STATIC_CACHE && name !== API_CACHE)
            .map((name) => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch event - handle requests
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
    // Return offline page if available
    return cache.match('/');
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
    const response = await fetch(request);
    return response;
  } catch (error) {
    console.log('[SW] Network request failed:', error);
    throw error;
  }
}

// Listen for messages from the main thread
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
  
  if (event.data === 'clearApiCache') {
    caches.delete(API_CACHE).then(() => {
      console.log('[SW] API cache cleared');
    });
  }
});
