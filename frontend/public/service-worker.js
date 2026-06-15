const VERSION = 'v1';
const STATIC_CACHE = 'pif-svelte-static-' + VERSION;
const API_CACHE = 'pif-svelte-api-' + VERSION;

const APP_SHELL = [
  '/',
  '/manifest.json',
];

const CDN_HOSTS = [
  'fonts.googleapis.com',
  'fonts.gstatic.com',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) =>
      Promise.all(
        APP_SHELL.map((u) =>
          fetch(u, { credentials: 'same-origin' })
            .then((res) => (res && res.ok ? cache.put(u, res) : null))
            .catch(() => {})
        )
      )
    )
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((n) => n !== STATIC_CACHE && n !== API_CACHE)
          .map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
      .then(() => {
        self.clients.matchAll().then((clients) => {
          clients.forEach((c) => c.postMessage({ type: 'SW_UPDATED', version: VERSION }));
        });
      })
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;
  if (!url.protocol.startsWith('http')) return;

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request, API_CACHE, event));
    return;
  }

  if (url.pathname.startsWith('/assets/') ||
      url.pathname.endsWith('.js') ||
      url.pathname.endsWith('.css') ||
      url.pathname.endsWith('.woff2') ||
      url.pathname.endsWith('.woff')) {
    event.respondWith(cacheFirst(request, STATIC_CACHE, event));
    return;
  }

  if (CDN_HOSTS.includes(url.hostname)) {
    event.respondWith(cacheFirstCDN(request, STATIC_CACHE, event));
    return;
  }

  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirst(request, STATIC_CACHE, event));
    return;
  }

  event.respondWith(fetch(request).catch(() => caches.match(request)));
});

async function cacheFirst(request, cacheName, event) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const putP = cache.put(request, response.clone());
      if (event) event.waitUntil(putP.catch(() => {}));
    }
    return response;
  } catch (err) {
    if (request.mode === 'navigate') return cache.match('/');
    throw err;
  }
}

async function cacheFirstCDN(request, cacheName, event) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response && (response.ok || response.type === 'opaque')) {
      const putP = cache.put(request, response.clone());
      if (event) event.waitUntil(putP.catch(() => {}));
    }
    return response;
  } catch (err) {
    throw err;
  }
}

async function networkFirst(request, cacheName, event) {
  const cache = await caches.open(cacheName);

  try {
    const response = await fetch(request, { cache: 'no-cache' });
    if (response.ok) {
      const putP = cache.put(request, response.clone());
      if (event) event.waitUntil(putP.catch(() => {}));
    }
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;

    if (request.url.includes('/api/')) {
      return new Response(
        JSON.stringify({ error: 'Offline', message: 'Datele nu sunt disponibile offline' }),
        { status: 503, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (request.mode === 'navigate') {
      const shell = await cache.match('/');
      if (shell) return shell;
    }

    throw err;
  }
}

self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') self.skipWaiting();
  if (event.data === 'clearApiCache') caches.delete(API_CACHE);
});
