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

const VERSION = 'v98';
const STATIC_CACHE = 'pif-static-' + VERSION;
const API_CACHE = 'pif-api-' + VERSION;

// App shell to cache on install. The legacy vanilla-JS app and the /m mobile
// twin were removed; the Svelte SPA shell is served at '/'.
//
// '/calc' is the standalone public calculator (app.py: calc_public). It is the
// page most likely to be opened with no signal — on site, in a hall — so it is
// part of the shell, not something you have to visit first to get cached.
// '/' is @login_required: for a logged-out visitor its fetch returns a login
// redirect, which precacheShell skips quietly (per-item, never aborts install).
const APP_SHELL = [
  '/',
  '/calc'
];

// Same-origin files the shell needs but does not reference as /assets/ or
// /static/ (those are discovered by parsing the HTML — see precacheShell).
const EXTRA_SHELL = [
  '/favicon.svg',
  '/manifest.json'
];

// Cross-origin CDN hosts whose assets we cache-first at runtime. Fonts are now
// self-hosted (static/fonts/), so only the jsDelivr fallback (KaTeX) remains.
const CDN_HOSTS = [
  'cdn.jsdelivr.net'
];

// Cache one shell page AND the build assets it references.
//
// Vite emits content-hashed bundles (/assets/calc-KANpVbZQ.js …) whose names
// change on every build, so they cannot be listed here. They are referenced
// only from the built HTML — so parse the HTML we just fetched and cache what
// it points at. Without this the shell HTML was cached but its JS was not, and
// the PWA could not start offline at all.
async function precacheShell(cache, url) {
  let res;
  try {
    res = await fetch(url, { credentials: 'same-origin' });
  } catch (_) {
    return;
  }
  if (!res || !res.ok) return;   // '/' when logged out → login redirect: skip quietly

  let html = '';
  try {
    html = await res.clone().text();
  } catch (_) {
    /* keep going — worst case we cache the page without its assets */
  }
  await cache.put(url, res).catch(() => {});

  const refs = new Set();
  for (const m of html.matchAll(/(?:src|href)="(\/(?:assets|static)\/[^"]+)"/g)) {
    refs.add(m[1]);
  }
  await Promise.all([...refs].map((u) =>
    fetch(u, { credentials: 'same-origin' })
      .then((r) => (r && r.ok ? cache.put(u, r) : null))
      .catch(() => {})
  ));
}

// Install — cache the app shell. No skipWaiting(): the new worker waits until
// the user accepts the update.
self.addEventListener('install', (event) => {
  console.log('[SW] Installing', VERSION);
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => Promise.all([
      // Per-item, each with its own catch: one missing or redirected page must
      // not abort the whole install the way cache.addAll() would.
      ...APP_SHELL.map((u) => precacheShell(cache, u)),
      ...EXTRA_SHELL.map((u) =>
        fetch(u, { credentials: 'same-origin' })
          .then((r) => (r && r.ok ? cache.put(u, r) : null))
          .catch(() => {})
      )
    ]))
  );
  // No skipWaiting() — let the new SW wait until all tabs close, avoiding
  // mismatches between cached HTML and new JS/CSS assets.
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
      .then(() => {
        // Notify all open clients that a new SW has activated and they should
        // show the update banner. This works even when the old page's app.js
        // didn't properly register updatefound (the root cause of the bug).
        self.clients.matchAll().then(clients => {
          clients.forEach(client => {
            client.postMessage({ type: 'SW_UPDATED', version: VERSION });
          });
        });
      })
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
    event.respondWith(networkFirstWithCache(request, API_CACHE, event));
    return;
  }

  // Vite build output: cache-first. Everything under /assets/ is a build
  // artifact with a content hash in its name (app.py: dist_assets), so it is
  // immutable and safe to serve from cache forever — a new build produces new
  // filenames, and the old ones are dropped with the old cache on activate.
  //
  // GOTCHA that made the PWA useless offline before v98: the built HTML points
  // at /assets/…, NOT /static/dist/… . The rule below only matched /static/,
  // so the app's own JS and CSS were never cached and every offline start died
  // on the first module import.
  if (url.origin === self.location.origin && url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirstWithNetwork(request, STATIC_CACHE, event));
    return;
  }

  // Static assets (JS, CSS, fonts): cache-first — require both path prefix AND
  // file extension so we don't accidentally cache-first random app routes that
  // happen to end with one of these extensions.
  if (url.pathname.startsWith('/static/') &&
      (url.pathname.endsWith('.js') ||
       url.pathname.endsWith('.css') ||
       url.pathname.endsWith('.woff2') ||
       url.pathname.endsWith('.woff'))) {
    event.respondWith(cacheFirstWithNetwork(request, STATIC_CACHE, event));
    return;
  }

  // CDN assets (Google Fonts, KaTeX): cache-first so the PWA renders correctly
  // offline. These are cross-origin; responses may be opaque, so we cache them
  // regardless of `response.ok` (opaque responses report status 0).
  if (CDN_HOSTS.includes(url.hostname)) {
    event.respondWith(cacheFirstCDN(request, STATIC_CACHE, event));
    return;
  }

  // HTML pages: network-first (to get fresh content)
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstWithCache(request, STATIC_CACHE, event));
    return;
  }

  // Default: network-first
  event.respondWith(networkFirstWithNetwork(request));
});

// Cache-first strategy with network fallback.
// `event` is optional; when provided, cache.put calls are wrapped in
// event.waitUntil so they survive the SW thread potentially terminating
// before the background write finishes.
async function cacheFirstWithNetwork(request, cacheName, event) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      const clone = response.clone();
      const putPromise = cache.put(request, clone);
      if (event && typeof event.waitUntil === 'function') {
        event.waitUntil(putPromise.catch(() => {}));
      }
    }
    return response;
  } catch (error) {
    console.log('[SW] Network request failed:', error);
    // Only fall back to the app shell for actual page navigations —
    // never return HTML where JS/CSS was expected. Prefer the shell for THIS
    // page (a /calc navigation must not be answered with the dashboard shell,
    // which would then redirect a logged-out colleague to the login page).
    if (request.mode === 'navigate') {
      return (await cache.match(new URL(request.url).pathname)) || (await cache.match('/'));
    }
    throw error;
  }
}

// Cache-first for cross-origin CDN assets (fonts, KaTeX). Unlike the same-origin
// helper, this caches opaque responses too (status 0) so offline rendering works.
async function cacheFirstCDN(request, cacheName, event) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) {
    return cached;
  }
  try {
    const response = await fetch(request);
    // Cache 2xx and opaque (status 0) responses; skip explicit error statuses.
    if (response && (response.ok || response.type === 'opaque')) {
      const clone = response.clone();
      const putPromise = cache.put(request, clone);
      if (event && typeof event.waitUntil === 'function') {
        event.waitUntil(putPromise.catch(() => {}));
      }
    }
    return response;
  } catch (error) {
    console.log('[SW] CDN request failed:', error);
    throw error;
  }
}

// Network-first strategy with cache fallback.
// `event` is optional; when provided, cache.put calls are wrapped in
// event.waitUntil so they complete even if the page navigates away before
// the background write finishes.
async function networkFirstWithCache(request, cacheName, event) {
  const cache = await caches.open(cacheName);

  try {
    // cache:'no-cache' forces revalidation with the origin — plain fetch()
    // would happily return the browser's heuristically-cached copy, making
    // "network-first" serve a stale HTML shell after deploys.
    const response = await fetch(request, { cache: 'no-cache' });
    if (response.ok) {
      const clone = response.clone();
      const putPromise = cache.put(request, clone);
      if (event && typeof event.waitUntil === 'function') {
        event.waitUntil(putPromise.catch(() => {}));
      }
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
