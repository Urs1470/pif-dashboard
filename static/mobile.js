// PIF Mobile - Mobile SPA Logic
// IndexedDB for offline storage, sync when online

const DB_NAME = 'pif_mobile_db';
const DB_VERSION = 7;

let db = null;
let currentTab = 'projects';
let currentProject = null;
let projectsCache = [];
let allNotes = [];

// ============ IndexedDB — Wrapper corect (v3, fără anti-pattern) ============

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onupgradeneeded = (event) => {
      const database = event.target.result;
      if (!database.objectStoreNames.contains('notes')) {
        const ns = database.createObjectStore('notes', { keyPath: 'local_id' });
        ns.createIndex('synced', 'synced', { unique: false });
        ns.createIndex('project_id', 'project_id', { unique: false });
      }
      if (!database.objectStoreNames.contains('projects_cache')) {
        database.createObjectStore('projects_cache', { keyPath: 'id' });
      }
      if (!database.objectStoreNames.contains('sync_queue')) {
        database.createObjectStore('sync_queue', { keyPath: 'id' });
      }
      if (!database.objectStoreNames.contains('params_cache')) {
        const ps = database.createObjectStore('params_cache', { keyPath: 'id' });
        ps.createIndex('familie', 'familie', { unique: false });
      }
      console.log('[IDB] Upgrade to v' + DB_VERSION + ' complete');
    };
    
    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };
    request.onerror = () => reject(request.error);
    request.onblocked = () => {
      console.warn('[IDB] Blocked — close other tabs');
      reject(new Error('IDB blocked'));
    };
  });
}

// Wrapper IDB generic (proper Promise, fără async executor)
function idbGetAll(database, storeName) {
  return new Promise((resolve, reject) => {
    if (!database.objectStoreNames.contains(storeName)) return resolve([]);
    const tx = database.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).getAll();
    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => reject(request.error);
  });
}

function idbClear(database, storeName) {
  return new Promise((resolve, reject) => {
    if (!database.objectStoreNames.contains(storeName)) return resolve();
    const tx = database.transaction(storeName, 'readwrite');
    const request = tx.objectStore(storeName).clear();
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function dbGet(storeName, key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const store = tx.objectStore(storeName);
    const request = store.get(key);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function dbGetAll(storeName) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const store = tx.objectStore(storeName);
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function dbPut(storeName, data) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const request = store.put(data);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function dbClear(storeName) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const request = store.clear();
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

// ============ Auth ============

async function login(pin, rememberMe = false) {
  try {
    const res = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin })
    });
    if (res.ok) {
      sessionStorage.setItem('pif_auth', '1');
      if (rememberMe) {
        const hash = await crypto.subtle.digest(
          'SHA-256',
          new TextEncoder().encode(pin)
        );
        const hashHex = Array.from(new Uint8Array(hash))
          .map(b => b.toString(16).padStart(2, '0')).join('');
        localStorage.setItem('pin_hash', hashHex);
        localStorage.setItem('remember_me', 'true');
      }
      return true;
    }
    return false;
  } catch (e) {
    console.error('Login error:', e);
    return false;
  }
}

function isAuthenticated() {
  return sessionStorage.getItem('pif_auth') === '1';
}

// ============ API Helpers ============

async function apiGet(url) {
  const res = await fetch(url, { credentials: 'include' });
  
  if (res.status === 401) {
    sessionStorage.removeItem('pif_auth');
    showLogin();
    return null;
  }
  
  // Detectează redirect la login (HTML în loc de JSON)
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    console.error('[API] Expected JSON but got:', contentType, 'for', url);
    console.error('[API] Status:', res.status);
    // Probabil redirect la login — refresh auth
    if (!isAuthenticated()) {
      console.warn('[API] Not authenticated, showing login');
      showLogin();
      return null;
    }
    console.warn('[API] Auth OK but got non-JSON — server may require re-login');
    return null;
  }
  
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiPost(url, data) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data)
  });
  if (res.status === 401) {
    sessionStorage.removeItem('pif_auth');
    showLogin();
    return null;
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiPut(url, data) {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data)
  });
  if (res.status === 401) { sessionStorage.removeItem('pif_auth'); showLogin(); return null; }
  const ct = res.headers.get('content-type') || '';
  if (!ct.includes('application/json')) return null;
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiDelete(url) {
  const res = await fetch(url, { method: 'DELETE', credentials: 'include' });
  if (res.status === 401) { sessionStorage.removeItem('pif_auth'); showLogin(); return null; }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ============ Online/Offline Status ============

// navigator.onLine e unreliable pe Android Chrome – verificare reală cu fetch
let _isOnline = true;
let _onlineCheckPending = false;
let _onlineRetryCount = 0;

async function updateOnlineStatus() {
  const statusEl = document.getElementById('sync-status');
  if (!statusEl) {
    console.warn('[Online] sync-status element not found');
    return;
  }

  if (_onlineCheckPending) return;
  _onlineCheckPending = true;

  let online = false;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const resp = await fetch('/api/healthz', {
      signal: controller.signal,
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' }
    });
    clearTimeout(timeout);

    if (resp.ok) {
      // Verifică că e REALMENTE healthcheck, nu redirect la login
      const contentType = resp.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        online = true;
        console.log('[Online] ✅ Healthcheck OK (JSON)');
      } else {
        // Probabil redirect la login page
        console.warn('[Online] ⚠️ Got 200 but content-type:', contentType);
        console.warn('[Online] Probabil redirect la login — healthz nu e exclus din auth');
        online = true; // Suntem online (am primit răspuns), doar auth e problema
      }
    } else {
      console.warn('[Online] Healthcheck status:', resp.status);
    }
  } catch (err) {
    console.warn('[Online] ❌ Fetch failed:', err.name, err.message);
    // Fallback la navigator.onLine
    online = navigator.onLine;
    console.log('[Online] Fallback navigator.onLine:', online);
  }

  _isOnline = online;
  _onlineRetryCount = online ? 0 : _onlineRetryCount + 1;

  statusEl.innerHTML = online
    ? '<i data-lucide="circle-check" style="width:12px;height:12px;color:var(--success);"></i> online'
    : '<i data-lucide="circle-x" style="width:12px;height:12px;color:var(--danger);"></i> offline';
  statusEl.className = online ? 'online' : 'offline';
  _onlineCheckPending = false;
}

// Fallback: evenimentele browserului declanșează reverificare
window.addEventListener('online', () => {
  updateOnlineStatus();
  syncNotes();
});

window.addEventListener('offline', () => {
  updateOnlineStatus();
});

// Verificare periodică la fiecare 30s (mobile — conexiunea fluctuează)
setInterval(updateOnlineStatus, 30000);

// ============ Service Worker Registration ============

// Set to true only when the user taps "Reincarca" in the update banner.
let _swUpdateAccepted = false;

function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;

    // Reload the page only after the user has accepted an update — never on
    // its own (a background SW activation must not reload the page).
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (_swUpdateAccepted) window.location.reload();
    });

    // Root-scope registration (same as desktop) so the worker actually
    // controls the /m page — '/static/service-worker.js' would scope to /static/.
    navigator.serviceWorker.register('/service-worker.js')
        .then(registration => {
            console.log('[App] SW registered');
            setInterval(() => registration.update(), 60 * 60 * 1000);

            if (registration.waiting && navigator.serviceWorker.controller) {
                promptMobileSWUpdate(registration.waiting);
            }
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                if (!newWorker) return;
                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        promptMobileSWUpdate(newWorker);
                    }
                });
            });
        })
        .catch(err => console.error('[App] SW registration failed:', err));
}

// Non-blocking update banner — the page reloads ONLY when the user taps it.
function promptMobileSWUpdate(worker) {
    if (document.getElementById('sw-update-banner')) return;
    const b = document.createElement('div');
    b.id = 'sw-update-banner';
    b.style.cssText = 'position:fixed;left:12px;right:12px;bottom:76px;z-index:5000;' +
        'display:flex;align-items:center;gap:10px;padding:10px 12px;' +
        'background:var(--bg-elev3);border:1px solid var(--border);border-radius:12px;' +
        'box-shadow:0 8px 32px rgba(0,0,0,0.4);';
    b.innerHTML = '<span style="flex:1;font-size:13px;color:var(--text);">Versiune noua disponibila</span>' +
        '<button id="sw-update-apply" style="background:var(--accent);color:var(--bg);border:none;' +
        'border-radius:8px;padding:8px 14px;font-size:13px;font-weight:600;">Reincarca</button>' +
        '<button id="sw-update-dismiss" aria-label="Inchide" style="background:none;border:none;' +
        'color:var(--text-secondary);font-size:20px;line-height:1;padding:0 4px;">&times;</button>';
    document.body.appendChild(b);
    document.getElementById('sw-update-apply').addEventListener('click', () => {
        _swUpdateAccepted = true;
        worker.postMessage('skipWaiting');
        b.remove();
    });
    document.getElementById('sw-update-dismiss').addEventListener('click', () => b.remove());
}

// ============ Sync Logic ============

async function syncNotes() {
  if (!_isOnline || !isAuthenticated()) return;
  
  try {
    // Get unsynced notes from IndexedDB
    const unsyncedNotes = await dbGetAll('notes');
    const pendingNotes = unsyncedNotes.filter(n => !n.synced);
    
    if (pendingNotes.length === 0) return;
    
    // Get last sync time
    const lastSync = localStorage.getItem('last_sync') || null;
    
    // Call sync API
    const syncData = {
      notes: pendingNotes.map(n => ({
        local_id: n.local_id,
        project_id: n.project_id,
        content: n.content,
        updated_at: n.updated_at
      })),
      last_sync: lastSync
    };
    
    const result = await apiPost('/api/sync/notes', syncData);
    
    if (result === null) return;
    
    // Mark synced notes as synced
    for (const note of result.saved) {
      const localNote = pendingNotes.find(n => n.local_id === note.local_id);
      if (localNote) {
        localNote.synced = true;
        localNote.server_id = note.id;
        await dbPut('notes', localNote);
      }
    }
    
    // Add server notes to local DB
    for (const serverNote of result.server_notes) {
      const existsLocally = await dbGet('notes', serverNote.id);
      if (!existsLocally) {
        await dbPut('notes', {
          local_id: serverNote.id,
          project_id: serverNote.proiect_id,
          content: serverNote.continut,
          created_at: serverNote.created_at,
          updated_at: serverNote.updated_at,
          synced: true,
          server_id: serverNote.id
        });
      }
    }
    
    // Update last sync time
    localStorage.setItem('last_sync', new Date().toISOString());
    
    // Refresh notes view if on notes tab
    if (currentTab === 'notes') {
      loadNotes();
    }
  } catch (e) {
    console.error('Sync error:', e);
  }
}

// ============ Params Sync (IndexedDB cache — v3 proper) ============

async function syncParamsToLocal() {
    const statusEl = document.getElementById('params-sync-status') || document.getElementById('sync-status');
    console.log('[Sync] === START syncParamsToLocal ===');
    
    try {
        if (statusEl) statusEl.innerHTML = '<i data-lucide="refresh-cw" style="width:12px;height:12px;"></i> Sincronizare parametri...';
        
        // Pas 1: Fetch bulk
        console.log('[Sync] Fetching /api/parametri/bulk ...');
        const response = await apiGet('/api/parametri/bulk');
        console.log('[Sync] Response type:', typeof response);
        console.log('[Sync] Is array:', Array.isArray(response));
        console.log('[Sync] Length:', response?.length);
        
        if (!response) {
            console.error('[Sync] ❌ Response is null/undefined');
            if (statusEl) statusEl.textContent = '❌ Sync eșuat — răspuns gol';
            return false;
        }
        
        if (!Array.isArray(response)) {
            console.error('[Sync] ❌ Response is NOT array:', JSON.stringify(response).substring(0, 200));
            if (statusEl) statusEl.textContent = '❌ Sync eșuat — format invalid';
            return false;
        }
        
        if (response.length === 0) {
            console.error('[Sync] ❌ Response is empty array');
            if (statusEl) statusEl.textContent = '❌ Sync eșuat — 0 parametri';
            return false;
        }
        
        // Log primul parametru pentru verificare structură
        console.log('[Sync] First param sample:', JSON.stringify(response[0]));
        
        // Pas 2: Open DB
        console.log('[Sync] Opening IndexedDB...');
        const database = await openDB();
        console.log('[Sync] DB opened, stores:', Array.from(database.objectStoreNames));
        
        if (!database.objectStoreNames.contains('params_cache')) {
            console.error('[Sync] ❌ Store params_cache MISSING!');
            if (statusEl) statusEl.textContent = '❌ Sync eșuat — DB store lipsă';
            return false;
        }
        
        // Pas 3: Clear
        console.log('[Sync] Clearing params_cache...');
        await idbClear(database, 'params_cache');
        console.log('[Sync] Clear done');
        
        // Pas 4: Batch insert
        console.log('[Sync] Inserting', response.length, 'params...');
        let insertCount = 0;
        await new Promise((resolve, reject) => {
            const tx = database.transaction('params_cache', 'readwrite');
            const store = tx.objectStore('params_cache');
            
            for (const param of response) {
                store.put({
                    id: param.id,
                    cod: param.parametru,
                    familie: param.familie,
                    descriere: param.descriere_scurta || '',
                    descriere_full: '',                                         // nu mai stocăm dump-ul PDF
                    valoare_default_str: param.valoare_default_str,
                    unitate: param.unitate,
                    min: param.min,
                    max: param.max,
                    acces: param.acces,
                    tip_date: param.tip_date,
                    _search: (param.parametru + ' ' + (param.descriere_scurta || '')).toLowerCase()
                });
                insertCount++;
            }
            
            tx.oncomplete = () => {
                console.log('[Sync] ✅ TX complete,', insertCount, 'params inserted');
                resolve();
            };
            tx.onerror = (e) => {
                console.error('[Sync] ❌ TX error:', tx.error);
                reject(tx.error);
            };
            tx.onabort = (e) => {
                console.error('[Sync] ❌ TX aborted:', tx.error);
                reject(tx.error || new Error('TX aborted'));
            };
        });
        
        // Pas 5: Save metadata
        const count = response.length;
        localStorage.setItem('params_last_sync', Date.now().toString());
        localStorage.setItem('params_count', count.toString());
        localStorage.setItem('params_db_version', DB_VERSION.toString());
        
        console.log('[Sync] ✅ SUCCESS:', count, 'parametri cached');
        if (statusEl) statusEl.innerHTML = '<i data-lucide="circle-check" style="width:12px;height:12px;color:var(--success);"></i> ' + count.toLocaleString() + ' parametri · synced';
        
        updateSyncStatus();
        populateFamilyDropdown();
        
        return true;
        
    } catch (err) {
        console.error('[Sync] ❌ CAUGHT ERROR:', err.name, err.message, err.stack);
        if (statusEl) statusEl.textContent = '❌ Sync eșuat — ' + (err.message || 'eroare');
        return false;
    }
}

function updateSyncStatus() {
  const el = document.getElementById('params-sync-status');
  if (!el) return;
  const count = localStorage.getItem('params_count');
  const lastSync = localStorage.getItem('params_last_sync');
  if (!count || count === '0') {
    el.innerHTML = '<i data-lucide="circle" style="width:12px;height:12px;color:var(--danger);"></i> Cache gol — tap pentru sync';
  } else {
    const ago = lastSync ? timeSince(parseInt(lastSync)) : 'necunoscut';
    el.innerHTML = '<i data-lucide="circle-check" style="width:12px;height:12px;color:var(--success);"></i> ' + parseInt(count).toLocaleString() + ' parametri · ' + ago;
  }
}

function timeSince(timestamp) {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return 'acum';
  if (seconds < 3600) return Math.floor(seconds / 60) + ' min';
  if (seconds < 86400) return Math.floor(seconds / 3600) + ' ore';
  return Math.floor(seconds / 86400) + ' zile';
}

// Render KaTeX math inside a container. Delimiters: $...$ inline, $$...$$ display.
const _katexOptions = {
  delimiters: [
    { left: '$$', right: '$$', display: true },
    { left: '$',  right: '$',  display: false },
    { left: '\\(', right: '\\)', display: false },
    { left: '\\[', right: '\\]', display: true },
  ],
  throwOnError: false,
  errorColor: 'var(--danger)',
};
function renderMathIn(el) {
  if (!el) return;
  if (typeof window.renderMathInElement !== 'function') {
    setTimeout(() => {
      if (typeof window.renderMathInElement === 'function') {
        try { window.renderMathInElement(el, _katexOptions); } catch (e) {}
      }
    }, 200);
    return;
  }
  try { window.renderMathInElement(el, _katexOptions); } catch (e) {}
}

async function getCachedParams() {
  try {
    const database = await openDB();
    return await idbGetAll(database, 'params_cache');
  } catch (e) {
    console.error('[Cache] Error:', e);
    return [];
  }
}

// Fallback: search API
async function searchParamsAPI(query) {
  if (!query || query.length < 2) return [];
  if (!_isOnline) return [];
  try {
    const response = await apiGet('/api/parametri/search?q=' + encodeURIComponent(query));
    if (!response) return [];
    const data = response.params || response;
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

function filterParams(allParams, query, familyFilter) {
  const q = (query || '').toLowerCase().trim();
  let results = allParams;

  if (familyFilter && familyFilter !== 'all') {
    results = results.filter(p => p.familie === familyFilter);
  }

  // Natural ASC sort by code is the default. Use { numeric: true } so
  // "01.2" comes before "01.10" instead of after.
  const natural = (a, b) => {
    const aCod = (a.cod || a.parametru || '').toLowerCase();
    const bCod = (b.cod || b.parametru || '').toLowerCase();
    return aCod.localeCompare(bCod, 'ro', { numeric: true, sensitivity: 'base' });
  };

  if (q) {
    results = results.filter(p => p._search.includes(q));
    // Search results: exact match first, then prefix matches, then natural.
    results.sort((a, b) => {
      const aCod = (a.cod || '').toLowerCase();
      const bCod = (b.cod || '').toLowerCase();
      if (aCod === q && bCod !== q) return -1;
      if (bCod === q && aCod !== q) return 1;
      if (aCod.startsWith(q) && !bCod.startsWith(q)) return -1;
      if (bCod.startsWith(q) && !aCod.startsWith(q)) return 1;
      return natural(a, b);
    });
  } else {
    results = results.slice().sort(natural);
  }

  return results.slice(0, 50);
}

async function searchParamsLocal(query, familyFilter) {
  try {
    const allParams = await getCachedParams();
    if (!allParams || allParams.length === 0) {
      return await searchParamsAPI(query);
    }
    return filterParams(allParams, query, familyFilter);
  } catch (e) {
    console.error('[Search] Error:', e);
    return await searchParamsAPI(query);
  }
}

async function populateFamilyDropdown(allParamsParam) {
  try {
    let params = allParamsParam || await getCachedParams();
    if (!params || !Array.isArray(params) || params.length === 0) return;
    const families = [...new Set(params.map(p => p.familie))].sort();
    const select = document.getElementById('family-select');
    if (!select) return;
    select.innerHTML = '<option value="all">Toate familiile</option>';
    families.forEach(f => {
      select.innerHTML += '<option value="' + f + '">' + f + '</option>';
    });
  } catch (e) {
    console.error('[Dropdown] Error:', e);
  }
}

// ============ Load Data ============

let mobileProjectFilter = 'active'; // 'active' sau 'archive'

async function loadProjects() {
  const listEl = document.getElementById('projects-list');
  listEl.innerHTML = '<div class="loading">Se încarcă...</div>';
  
  try {
    if (_isOnline) {
      const projects = await apiGet('/api/proiecte');
      if (projects === null) return;
      projectsCache = projects;
      await dbClear('projects_cache');
      for (const p of projects) {
        p.cached_at = new Date().toISOString();
        await dbPut('projects_cache', p);
      }
    } else {
      projectsCache = await dbGetAll('projects_cache');
    }
    
    renderProjects(projectsCache);
  } catch (e) {
    console.error('Load projects error:', e);
    projectsCache = await dbGetAll('projects_cache');
    if (projectsCache.length > 0) renderProjects(projectsCache);
    else listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="folder-open"></i></div>Nu există proiecte</div>';
  }
}

function renderProjects(projects) {
  const listEl = document.getElementById('projects-list');
  if (!projects || projects.length === 0) {
    listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="folder-open"></i></div>Nu există proiecte</div>';
    return;
  }
  
  const active = projects.filter(p => p.status !== 'finalizat' && p.status !== 'anulat');
  const archived = projects.filter(p => p.status === 'finalizat' || p.status === 'anulat');
  const isArchive = mobileProjectFilter === 'archive';
  const displayList = isArchive ? archived : active;
  
  let html = `
    <div style="display:flex;gap:6px;margin-bottom:12px;">
      <button class="gt-filter ${!isArchive ? 'active' : ''}" onclick="switchProjectFilter('active')">
        Activ (${active.length})
      </button>
      <button class="gt-filter ${isArchive ? 'active' : ''}" onclick="switchProjectFilter('archive')">
        <i data-lucide="archive" style="width:14px;height:14px;vertical-align:-2px;"></i> Arhivă (${archived.length})
      </button>
    </div>
  `;
  
  if (displayList.length === 0) {
    html += `<div class="empty-state"><div class="empty-state-icon"><i data-lucide="${isArchive ? 'archive' : 'folder-open'}"></i></div>${isArchive ? 'Niciun proiect finalizat' : 'Niciun proiect activ'}</div>`;
  } else {
    html += displayList.map(p => `
      <div class="project-card" data-id="${p.id}">
        <div class="project-name">${escapeHtml(p.nume || 'Fără nume')}</div>
        <div class="project-client">${escapeHtml(p.client || '-')}</div>
        <span class="project-status status-${p.status || 'in_lucru'}">${getStatusLabel(p.status || 'in_lucru')}</span>
      </div>
    `).join('');
  }
  
  listEl.innerHTML = html;
  
  listEl.querySelectorAll('.project-card').forEach(card => {
    card.addEventListener('click', () => showProjectDetail(card.dataset.id));
  });
}

function switchProjectFilter(filter) {
  mobileProjectFilter = filter;
  renderProjects(projectsCache);
}

// getStatusLabel -> moved to shared core.js

// (Audit Faza 6) FAZA 2 mobile project-detail functions removed here — they were
// dead code, fully superseded by the FAZA 3 versions defined further below
// (showProjectDetail / loadMobileChecklist / loadMobileTimer / loadMobileEquipment).

async function loadProjectNotes(projectId) {
  const notesEl = document.getElementById('project-notes');
  notesEl.innerHTML = '<div class="loading">Se încarcă notițele...</div>';
  
  try {
    // Try to get notes from server
    let projectNotes = [];
    if (_isOnline) {
      const serverNotes = await apiGet(`/api/proiecte/${projectId}/jurnal`);
      if (serverNotes) {
        projectNotes = serverNotes.map(n => ({
          local_id: n.id,
          project_id: n.proiect_id,
          content: n.continut,
          created_at: n.created_at,
          updated_at: n.data,
          synced: true
        }));
      }
    }
    
    // Also get from local DB
    const localNotes = await dbGetAll('notes');
    const localProjectNotes = localNotes.filter(n => n.project_id === projectId);
    
    // Merge
    const allProjectNotes = [...projectNotes];
    for (const ln of localProjectNotes) {
      if (!allProjectNotes.find(p => p.local_id === ln.local_id)) {
        allProjectNotes.push(ln);
      }
    }
    
    // Sort by date
    allProjectNotes.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    
    if (allProjectNotes.length === 0) {
      notesEl.innerHTML = '<div class="empty-state">Nu există notițe pentru acest proiect</div>';
      return;
    }
    
    notesEl.innerHTML = allProjectNotes.map(n => `
      <div class="note-item" data-id="${n.local_id}">
        <div class="note-preview">${escapeHtml(n.content.substring(0, 100))}${n.content.length > 100 ? '...' : ''}</div>
        <div class="note-full">${escapeHtml(n.content)}</div>
        <div class="note-date">${formatDate(n.updated_at)}</div>
      </div>
    `).join('');
    
    // Add click handlers for expand
    notesEl.querySelectorAll('.note-item').forEach(item => {
      item.addEventListener('click', () => {
        item.classList.toggle('expanded');
      });
    });
  } catch (e) {
    console.error('Load project notes error:', e);
    notesEl.innerHTML = '<div class="empty-state">Eroare la încărcarea notițelor</div>';
  }
}

async function loadNotes() {
  const listEl = document.getElementById('notes-list');
  listEl.innerHTML = '<div class="loading">Se încarcă...</div>';
  try {
    let notes = [];
    if (_isOnline) {
      const serverNotes = await apiGet('/api/jurnal/all');
      if (serverNotes) {
        notes = serverNotes.map(n => ({
          local_id: n.id,
          project_id: n.proiect_id,
          project_name: n.project_name,
          content: n.continut,
          updated_at: n.data,
          synced: true
        }));
      }
    }
    // Merge cu note locale nesincronizate
    const localNotes = await dbGetAll('notes');
    for (const ln of localNotes) {
      if (!ln.synced && !notes.find(n => n.local_id === ln.local_id)) {
        const project = projectsCache.find(p => p.id === ln.project_id);
        notes.push({ ...ln, project_name: project ? project.nume : null });
      }
    }
    allNotes = notes;
    notes.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    if (notes.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="notebook"></i></div>Nu există notițe</div>';
      return;
    }
    listEl.innerHTML = notes.map(n => `
      <div class="note-item" data-id="${n.local_id}">
        ${n.project_name ? `<div class="note-project">${escapeHtml(n.project_name)}</div>` : ''}
        <div class="note-preview">${escapeHtml(n.content.substring(0, 100))}${n.content.length > 100 ? '...' : ''}</div>
        <div class="note-full">${escapeHtml(n.content)}</div>
        <div class="note-date">${formatDate(n.updated_at)}</div>
      </div>
    `).join('');
    listEl.querySelectorAll('.note-item').forEach(item => {
      item.addEventListener('click', () => item.classList.toggle('expanded'));
    });
  } catch (e) {
    console.error('Load notes error:', e);
    listEl.innerHTML = '<div class="empty-state">Eroare la încărcarea notițelor</div>';
  }
}

// ============ Parametri tab: producer→family drill-down (parity with desktop) ============

const PARAM_PRODUCATORI_MOBILE = {
  'ABB':     { icon: 'cpu', families: ['ACS580', 'ACS880'],                                                 label: 'ABB' },
  'Siemens': { icon: 'cpu', families: ['SINAMICS_G120', 'SINAMICS_G130_G150', 'SINAMICS_S120_S150'],        label: 'Siemens' },
  'Danfoss': { icon: 'cpu', families: ['Danfoss_VLT_FC302'],                                                label: 'Danfoss' },
  'Lenze':   { icon: 'cpu', families: ['Lenze_i550', 'Lenze_i950'],                                         label: 'Lenze' },
};
let _mobileParamSelectedProducator = null;
let _mobileParamSelectedFamilie = null;
let _mobileParamFamilieCounts = {};
let _mobileParamsAll = null;  // cached for filtering

async function loadParameters() {
  try {
    let allParams = await getCachedParams();
    const storedVersion = parseInt(localStorage.getItem('params_db_version') || '0');

    if (!allParams || allParams.length === 0 || storedVersion !== DB_VERSION) {
      if (_isOnline) {
        const listEl = document.getElementById('params-list');
        if (listEl) listEl.innerHTML = '<div class="loading">Se sincronizează...</div>';
        const ok = await syncParamsToLocal();
        if (ok) allParams = await getCachedParams();
      }
    }

    const stepProducator = document.getElementById('mobile-param-step-producator');
    const stepList       = document.getElementById('mobile-param-step-list');
    const gridEl         = document.getElementById('mobile-param-producator-grid');

    if (!allParams || allParams.length === 0) {
      if (stepProducator) stepProducator.style.display = 'none';
      if (stepList) stepList.style.display = 'block';
      const listEl = document.getElementById('params-list');
      if (listEl) listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="wifi-off"></i></div>Fără conexiune. Conectează-te pentru a sincroniza parametrii.</div>';
      if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
      return;
    }

    _mobileParamsAll = allParams;

    // Family counts: { 'ACS580': 1337, ... }
    _mobileParamFamilieCounts = {};
    for (const p of allParams) {
      const f = p.familie;
      if (!f) continue;
      _mobileParamFamilieCounts[f] = (_mobileParamFamilieCounts[f] || 0) + 1;
    }

    // Keep hidden select in sync so any legacy code reading it still works
    try {
      const select = document.getElementById('family-select');
      if (select) {
        const families = Object.keys(_mobileParamFamilieCounts).sort();
        select.innerHTML = '<option value="all">Toate familiile</option>';
        families.forEach(f => { select.innerHTML += '<option value="'+f+'">'+f+'</option>'; });
      }
    } catch (e) {}

    // Show step 1 by default; if a producer was already selected this session, keep it
    if (_mobileParamSelectedProducator) {
      mobileParamSelectProducator(_mobileParamSelectedProducator);
    } else {
      if (stepProducator) stepProducator.style.display = 'block';
      if (stepList) stepList.style.display = 'none';
      renderMobileProducatorPicker();
    }

    updateSyncStatus();

    // Wire search input once
    const searchEl = document.getElementById('param-search');
    if (searchEl && !searchEl._wired) {
      let timer;
      searchEl.oninput = function() {
        clearTimeout(timer);
        timer = setTimeout(async function() {
          const familieFilter = _mobileParamSelectedFamilie || 'all';
          const results = await searchParamsLocal(searchEl.value, familieFilter);
          renderParameters(results);
        }, 200);
      };
      searchEl._wired = true;
    }
  } catch (e) {
    const listEl = document.getElementById('params-list');
    if (listEl) listEl.innerHTML = '<div class="empty-state"><i data-lucide="alert-triangle" style="color:var(--warning);"></i> Eroare: ' + (e.message || 'necunoscută') + '</div>';
    if (window.lucide) try { window.lucide.createIcons(); } catch (_e) {}
  }
}

function renderMobileProducatorPicker() {
  const grid = document.getElementById('mobile-param-producator-grid');
  if (!grid) return;
  grid.innerHTML = Object.entries(PARAM_PRODUCATORI_MOBILE).map(([key, info]) => {
    const total = info.families.reduce((s, f) => s + (_mobileParamFamilieCounts[f] || 0), 0);
    const familiesLabel = info.families.map(f => f.replace(/^(SINAMICS_|Lenze_|Danfoss_VLT_)/, '')).join(' · ');
    return `
      <button class="mppc-card" onclick="mobileParamSelectProducator('${key}')">
        <i data-lucide="${info.icon}"></i>
        <div class="mppc-name">${info.label}</div>
        <div class="mppc-meta">${total.toLocaleString('ro-RO')} parametri</div>
        <div class="mppc-families">${familiesLabel}</div>
      </button>
    `;
  }).join('');
  if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

function mobileParamSelectProducator(producator) {
  const info = PARAM_PRODUCATORI_MOBILE[producator];
  if (!info) return;
  _mobileParamSelectedProducator = producator;

  const stepProducator = document.getElementById('mobile-param-step-producator');
  const stepList       = document.getElementById('mobile-param-step-list');
  if (stepProducator) stepProducator.style.display = 'none';
  if (stepList) stepList.style.display = 'block';

  const breadcrumb = document.getElementById('mobile-param-breadcrumb');
  if (breadcrumb) breadcrumb.textContent = info.label;

  // Mini-tabs per family
  const tabsEl = document.getElementById('mobile-param-mini-tabs');
  if (tabsEl) {
    tabsEl.innerHTML = info.families.map(f => {
      const count = _mobileParamFamilieCounts[f] || 0;
      const label = f.replace(/^(SINAMICS_|Lenze_|Danfoss_VLT_)/, '');
      return `<button class="mpmt" data-familie="${f}" onclick="mobileParamSelectFamilie('${f}')">${label}<span class="count">${count.toLocaleString('ro-RO')}</span></button>`;
    }).join('');
  }

  // Auto-select first family
  if (info.families.length > 0) mobileParamSelectFamilie(info.families[0]);
}

async function mobileParamSelectFamilie(familie) {
  _mobileParamSelectedFamilie = familie;
  // Update active mini-tab
  document.querySelectorAll('.mpmt').forEach(t => {
    t.classList.toggle('active', t.dataset.familie === familie);
  });
  // Sync hidden select for legacy code paths
  const hidden = document.getElementById('family-select');
  if (hidden) hidden.value = familie;
  // Filter params for this family using the existing search helper
  const searchEl = document.getElementById('param-search');
  const q = searchEl ? searchEl.value : '';
  const results = await searchParamsLocal(q, familie);
  renderParameters(results);
}

function mobileParamBackToProducator() {
  _mobileParamSelectedProducator = null;
  _mobileParamSelectedFamilie = null;
  const stepProducator = document.getElementById('mobile-param-step-producator');
  const stepList       = document.getElementById('mobile-param-step-list');
  if (stepList) stepList.style.display = 'none';
  if (stepProducator) stepProducator.style.display = 'block';
  // Clear search input so next entry to a family starts fresh
  const searchEl = document.getElementById('param-search');
  if (searchEl) searchEl.value = '';
  renderMobileProducatorPicker();
}

function renderParameters(params) {
  const listEl = document.getElementById('params-list');

  if (!Array.isArray(params) || params.length === 0) {
    listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="sliders-horizontal"></i></div>Nu există parametri</div>';
    return;
  }

  // Store params globally for safe access via onclick
  window._mobileParams = params;

  listEl.innerHTML = params.map((p, i) => {
    const desc = p.descriere_scurta || '-';
    const shortDesc = desc.length > 80 ? desc.substring(0, 80) + '…' : desc;
    return `
    <div class="param-item" data-code="${escapeHtml(p.cod || p.parametru || '')}"
         onclick="openMobileParamModal(window._mobileParams[${i}])">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div class="param-code">${escapeHtml(p.cod || p.parametru || '-')}</div>
        <div style="font-size:11px; color:var(--text-secondary); font-family:'Courier New',monospace;">${escapeHtml(p.familie || '')}</div>
      </div>
      <div class="param-default">${escapeHtml(shortDesc)}</div>
    </div>
    `;
  }).join('');
}

function extractParamName(descriere) {
  if (!descriere) return '-';
  const words = descriere.trim().split(/\s+/);
  let nameEnd = Math.min(words.length, 4);
  for (let i = 2; i < Math.min(words.length, 6); i++) {
    if (/^(Scaled|Received|Selects|Specifies|Sets|Defines|Controls|Enables|Disables|Shows|Indicates|Returns|Contains|Used|When|If|The|A|An)$/i.test(words[i])) {
      nameEnd = i; break;
    }
  }
  return words.slice(0, nameEnd).join(' ');
}

// Copy current param code to clipboard, show transient feedback in the modal.
async function copyMobileParamCode() {
  const codeEl = document.getElementById('mpm-code');
  const labelEl = document.getElementById('mpm-copy-label');
  if (!codeEl) return;
  const code = (codeEl.textContent || '').trim();
  if (!code || code === '-') return;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(code);
    } else {
      // Fallback: temporary textarea
      const ta = document.createElement('textarea');
      ta.value = code;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    if ('vibrate' in navigator) navigator.vibrate(20);
    if (labelEl) {
      const prev = labelEl.textContent;
      labelEl.textContent = 'Copiat';
      setTimeout(() => { if (labelEl) labelEl.textContent = prev; }, 1200);
    }
  } catch (e) {
    console.error('Copy failed:', e);
  }
}

function openMobileParamModal(param) {
  const modal = document.getElementById('param-modal-mobile');
  if (!modal) return;

  const cod = param.cod || param.parametru;
  modal.querySelector('#mpm-code').textContent = cod || '-';
  modal.querySelector('#mpm-familie').textContent = param.familie || '';
  modal.querySelector('#mpm-name').textContent = extractParamName(param.descriere || param.cod || '');
  
  // Descriere — afișează versiunea curătată sau scurtă
  const descriereScurta = param.descriere || '-';
  modal.querySelector('#mpm-descriere').textContent = descriereScurta;
  
  modal.querySelector('#mpm-acces').textContent = param.acces || '-';
  modal.querySelector('#mpm-tip').textContent = param.tip_date || '-';
  modal.querySelector('#mpm-default').textContent = param.valoare_default_str || param.valoare_default || '-';
  modal.querySelector('#mpm-unitate').textContent = param.unitate || '-';
  modal.querySelector('#mpm-min').textContent = param.min != null ? param.min : '-';
  modal.querySelector('#mpm-max').textContent = param.max != null ? param.max : '-';
  
  // Explicație — din cache (dacă există) sau fetch
  const explicatieRow = modal.querySelector('#mpm-explicatie-row');
  const explicatieEl = modal.querySelector('#mpm-explicatie');
  if (param.explicatie && param.explicatie.trim().length > 0) {
    explicatieEl.innerHTML = param.explicatie;
    renderMathIn(explicatieEl);
    explicatieRow.style.display = 'block';
  } else if (_isOnline && param.id) {
    // Fetch detail from server for full explicatie
    explicatieRow.style.display = 'block';
    explicatieEl.textContent = 'Se încarcă...';
    apiGet('/api/parametri/' + param.id).then(detail => {
      if (detail && detail.explicatie) {
        explicatieEl.innerHTML = detail.explicatie;
        renderMathIn(explicatieEl);
      } else {
        explicatieEl.textContent = 'Nicio explicație disponibilă';
      }
    }).catch(() => {
      explicatieEl.textContent = 'Eroare la încărcare';
    });
  } else {
    explicatieRow.style.display = 'none';
  }
  
  // Interconexiuni — ascunse (Ion vrea doar explicație + influențe, 10 Mai 2026)
  const interconRow = modal.querySelector('#mpm-interconex-row');
  interconRow.style.display = 'none';
  
  // Influențe — din cache (dacă există) sau fetch
  const influenteRow = modal.querySelector('#mpm-influenteaza-row');
  renderInfluenteaza(param, modal, influenteRow);
  
  modal.classList.add('active');
}

// Parse influenteaza into [{code, efect, tip}]
function _mobParseInflu(data) {
  if (!data || data === '[]' || data === 'null') return [];
  if (Array.isArray(data)) {
    return data.map(o => typeof o === 'string'
      ? { code: o, efect: '', tip: '' }
      : { code: o.parametru || '?', efect: o.efect || '', tip: o.tip || '' });
  }
  if (typeof data !== 'string') return [];
  const t = data.trim();
  if (!t) return [];
  if (t.startsWith('[')) {
    try { return _mobParseInflu(JSON.parse(t)); } catch {}
  }
  return t.split(/[\s,]+/).filter(Boolean).map(c => ({ code: c, efect: '', tip: '' }));
}

function _mobChip(entry, color) {
  const code = entry.code || entry.parametru || '?';
  const tipTag = entry.tip ? ` <span style="font-size:0.7em;opacity:0.6;">[${entry.tip}]</span>` : '';
  const labelText = entry.descriere_scurta ? ` <span style="font-size:0.8em;opacity:0.75;">${entry.descriere_scurta}</span>` : '';
  const efectText = entry.efect ? `<div style="font-size:0.8em;opacity:0.8;margin-top:1px;">${entry.efect}</div>` : '';
  return `<div style="margin:4px 0;padding:6px 10px;background:var(--bg);border-radius:6px;border-left:3px solid ${color};">
    <span style="font-family:'JetBrains Mono', monospace;font-weight:600;color:${color};">${code}</span>${tipTag}${labelText}
    ${efectText}
  </div>`;
}

function _mobEnsureRow(rowId, divId, label, iconName, color, anchorId) {
  const modal = document.getElementById('param-modal-mobile') || document.getElementById('param-modal');
  if (!modal) return null;
  let row = document.getElementById(rowId);
  if (!row) {
    row = document.createElement('div');
    row.id = rowId;
    row.style.cssText = `display:none;margin-top:8px;padding:12px;background:rgba(116,212,165,0.06);border:1px solid ${color};border-radius:6px;`;
    row.innerHTML = `<strong style="display:flex;align-items:center;gap:6px;"><i data-lucide="${iconName}" style="width:15px;height:15px;"></i> ${label}</strong><div id="${divId}" style="margin-top:6px;font-size:0.9em;"></div>`;
    const anchor = anchorId ? document.getElementById(anchorId) : null;
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(row, anchor);
    else modal.appendChild(row);
  }
  return row;
}

// Helper: randare influențe (bidirectional) din parametru
function renderInfluenteaza(param, modal, row) {
  // Existing #mpm-influenteaza-row is the "influențează" panel (X →)
  const div = modal && modal.querySelector('#mpm-influenteaza');
  const tryRender = (data, panel, divEl, color) => {
    const entries = _mobParseInflu(data);
    if (!entries.length || !divEl || !panel) { if (panel) panel.style.display = 'none'; return; }
    divEl.innerHTML = entries.map(e => _mobChip(e, color)).join('');
    panel.style.display = 'block';
  };

  // Bidirectional row created dynamically (←)
  const reverseRow = _mobEnsureRow(
    'mpm-influentat-de-row', 'mpm-influentat-de',
    'Influențat de', 'arrow-left', 'var(--violet)',
    'mpm-influenteaza-row'
  );
  const reverseDiv = document.getElementById('mpm-influentat-de');

  const applyDetail = (detail) => {
    tryRender(detail.influenteaza, row, div, 'var(--success)');
    if (Array.isArray(detail.influentat_de) && detail.influentat_de.length) {
      const entries = detail.influentat_de.map(o => ({
        code: o.parametru,
        descriere_scurta: o.descriere_scurta || '',
      }));
      if (reverseDiv && reverseRow) {
        reverseDiv.innerHTML = entries.map(e => _mobChip(e, 'var(--violet)')).join('');
        reverseRow.style.display = 'block';
      }
    } else if (reverseRow) {
      reverseRow.style.display = 'none';
    }
    if (window.lucide && lucide.createIcons) try { lucide.createIcons(); } catch {}
  };

  // Try param cache first; fetch only if we don't have influentat_de (computed reverse)
  if (param.influentat_de !== undefined) {
    applyDetail(param);
    return;
  }
  if (_isOnline && param.id) {
    apiGet('/api/parametri/' + param.id).then(detail => {
      if (detail) applyDetail(detail);
    }).catch(() => {});
  } else if (param.influenteaza) {
    tryRender(param.influenteaza, row, div, 'var(--success)');
  }
}

// ============ Notes Modal ============

function openNoteModal(projectId = null) {
  const modal = document.getElementById('note-modal');
  const textarea = document.getElementById('note-content');
  const select = document.getElementById('note-project-select');
  
  textarea.value = '';
  
  // Populate project dropdown
  select.innerHTML = '<option value="">Proiect (opțional)</option>';
  for (const p of projectsCache) {
    const selected = projectId && p.id === projectId ? 'selected' : '';
    select.innerHTML += `<option value="${p.id}" ${selected}>${escapeHtml(p.nume)}</option>`;
  }
  
  modal.classList.add('active');
  textarea.focus();
}

function closeNoteModal() {
  document.getElementById('note-modal').classList.remove('active');
}

async function saveNote() {
  const content = document.getElementById('note-content').value.trim();
  const projectId = document.getElementById('note-project-select').value || null;
  if (!content) return;

  const now = new Date().toISOString();
  const localId = 'local_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

  const note = {
    local_id: localId, project_id: projectId,
    content: content, created_at: now, updated_at: now, synced: false
  };

  // Salvează local întotdeauna
  await dbPut('notes', note);

  // Dacă online ȘI are proiect, trimite direct la server
  if (_isOnline && projectId) {
    try {
      const result = await apiPost(`/api/proiecte/${projectId}/jurnal`, {
        continut: content, data: now.substring(0, 10)
      });
      if (result && result.id) {
        note.synced = true;
        note.server_id = result.id;
        await dbPut('notes', note);
      }
    } catch (e) { console.warn('[Note] Server save failed, will retry:', e); }
  }

  closeNoteModal();
  if (currentProject && currentProject.id === projectId) loadProjectNotes(projectId);
  else if (currentTab === 'notes') loadNotes();
}

// ============ Dashboard Home (FAZA 2) ============

// Greeting helpers — port from desktop app.js for mobile parity.
function _greetingMobile() {
  const h = new Date().getHours();
  if (h < 5) return 'Noapte bună';
  if (h < 12) return 'Bună dimineața';
  if (h < 18) return 'Bună ziua';
  return 'Bună seara';
}
function _fmtDateMobile(d = new Date()) {
  const zile = ['Duminică', 'Luni', 'Marți', 'Miercuri', 'Joi', 'Vineri', 'Sâmbătă'];
  const luni = ['ianuarie', 'februarie', 'martie', 'aprilie', 'mai', 'iunie', 'iulie',
                'august', 'septembrie', 'octombrie', 'noiembrie', 'decembrie'];
  return `${zile[d.getDay()]}, ${d.getDate()} ${luni[d.getMonth()]} ${d.getFullYear()}`;
}

async function loadDashboardHome() {
  try {
    const data = await apiGet('/api/dashboard/home');
    if (!data) return;
    const s = data.stats || data;  // tolerate both shapes

    // Greeting
    const greetEl = document.getElementById('home-greeting');
    if (greetEl) {
      greetEl.innerHTML = `
        <div style="font-size:20px; font-weight:600; color:var(--text);">${_greetingMobile()}, Ion</div>
        <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">${_fmtDateMobile()}</div>
      `;
    }

    // 4 stats color-coded, same scheme as desktop:
    //   total projects (violet), active projects (accent),
    //   weekly hours (success) + delta, urgent tasks (danger)
    const delta = (s.weekly_delta != null)
      ? (s.weekly_delta >= 0 ? `+${s.weekly_delta}h` : `${s.weekly_delta}h`)
      : '';
    document.getElementById('home-stats').innerHTML = `
      <div class="detail-section" style="text-align:center; padding:12px;">
        <div style="font-size:24px; font-weight:600; color:var(--violet); font-family:'JetBrains Mono',monospace;">${s.total_projects ?? 0}</div>
        <div class="detail-label">Total proiecte</div>
      </div>
      <div class="detail-section" style="text-align:center; padding:12px;">
        <div style="font-size:24px; font-weight:600; color:var(--accent); font-family:'JetBrains Mono',monospace;">${s.active_projects ?? 0}</div>
        <div class="detail-label">Active</div>
      </div>
      <div class="detail-section" style="text-align:center; padding:12px;">
        <div style="font-size:24px; font-weight:600; color:var(--success); font-family:'JetBrains Mono',monospace;">${s.weekly_hours ?? 0}</div>
        <div class="detail-label">Ore (7 zile)${delta ? ` <span style="color:var(--text-dim);">${delta}</span>` : ''}</div>
      </div>
      <div class="detail-section" style="text-align:center; padding:12px;">
        <div style="font-size:24px; font-weight:600; color:var(--danger); font-family:'JetBrains Mono',monospace;">${s.urgent_count ?? 0}</div>
        <div class="detail-label">Taskuri urgente</div>
      </div>
    `;

    // Active timer
    const timerEl = document.getElementById('home-active-timer');
    if (data.active_timer) {
      const start = new Date(data.active_timer.start_time);
      const elapsed = Math.floor((Date.now() - start.getTime()) / 1000);
      timerEl.innerHTML = `
        <div class="detail-section" style="border-left:3px solid var(--success);">
          <div style="font-size:12px; color:var(--success); font-weight:600; display:flex; align-items:center; gap:4px;"><i data-lucide="timer" style="width:14px;height:14px;"></i> TIMER ACTIV</div>
          <div style="font-size:16px; margin-top:4px;">${escapeHtml(data.active_timer.project_name)}</div>
          <div style="font-size:20px; font-weight:600; color:var(--accent); margin-top:4px;" id="home-timer-display">${formatDuration(elapsed)}</div>
          <button onclick="stopTimerFromHome('${data.active_timer.project_id}')" class="modal-btn" style="margin-top:8px; background:var(--danger); display:flex; align-items:center; justify-content:center; gap:6px;"><i data-lucide="square"></i> Oprește timer</button>
        </div>
      `;
      // Live counter
      if (window._homeTimerInterval) clearInterval(window._homeTimerInterval);
      window._homeTimerInterval = setInterval(() => {
        const el = document.getElementById('home-timer-display');
        if (!el) { clearInterval(window._homeTimerInterval); return; }
        const now = Math.floor((Date.now() - start.getTime()) / 1000);
        el.textContent = formatDuration(now);
      }, 1000);
    } else {
      timerEl.innerHTML = '';
    }

    // Urgent tasks
    const urgentEl = document.getElementById('home-urgent-tasks');
    if (data.urgent_tasks && data.urgent_tasks.length > 0) {
      urgentEl.innerHTML = `
        <div style="font-size:14px; font-weight:600; margin-bottom:8px; display:flex; align-items:center; gap:6px;"><i data-lucide="alert-circle" style="color:var(--danger);"></i> Task-uri urgente</div>
        ${data.urgent_tasks.map(t => `
          <div class="note-item" style="border-left:3px solid var(--error); padding:12px;">
            <div style="font-size:14px;">${escapeHtml(t.titlu)}</div>
          </div>
        `).join('')}
      `;
    } else { urgentEl.innerHTML = ''; }

    // Upcoming deadlines
    const deadlineEl = document.getElementById('home-deadlines');
    if (data.upcoming_deadlines && data.upcoming_deadlines.length > 0) {
      deadlineEl.innerHTML = `
        <div style="font-size:14px; font-weight:600; margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="calendar-clock" style="color:var(--warning);"></i> Deadline-uri (7 zile)</div>
        ${data.upcoming_deadlines.map(t => `
          <div class="note-item" style="padding:12px;">
            <div style="font-size:14px;">${escapeHtml(t.titlu)}</div>
            <div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">${t.data_scadenta}</div>
          </div>
        `).join('')}
      `;
    } else { deadlineEl.innerHTML = ''; }

    // Recent journal
    const journalEl = document.getElementById('home-recent-journal');
    if (data.recent_journal && data.recent_journal.length > 0) {
      journalEl.innerHTML = `
        <div style="font-size:14px; font-weight:600; margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="notebook-pen" style="color:var(--accent);"></i> Jurnal recent</div>
        ${data.recent_journal.map(j => `
          <div class="note-item" style="padding:12px;">
            <div class="note-project">${escapeHtml(j.project_name)}</div>
            <div style="font-size:13px;">${escapeHtml((j.continut || '').substring(0, 120))}</div>
            <div class="note-date">${j.created_at ? j.created_at.substring(0, 10) : ''}</div>
          </div>
        `).join('')}
      `;
    } else { journalEl.innerHTML = ''; }

  } catch (e) { console.error('Dashboard home error:', e); }
}

async function stopTimerFromHome(projectId) {
  try {
    await apiPost(`/api/proiecte/${projectId}/timer/stop`, {});
    if ('vibrate' in navigator) navigator.vibrate(50);
    loadDashboardHome();
  } catch (e) { console.error('Stop timer error:', e); }
}

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h.toString().padStart(2,'0')}:${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
}

// ============ Navigation ============

function showTab(tab) {
  currentTab = tab;

  // Close more menu if open
  closeMoreMenu();

  // Update nav (only for main 5 tabs)
  document.querySelectorAll('.nav-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tab);
  });

  // Hide all tab views
  document.querySelectorAll('.tab-view').forEach(v => v.classList.remove('active'));

  // Reset project detail
  if (tab !== 'project-detail') currentProject = null;

  const tabEl = document.getElementById('tab-' + tab);
  if (tabEl) tabEl.classList.add('active');

  // Load data for tab
  switch(tab) {
    case 'home': loadDashboardHome(); break;
    case 'projects': loadProjects(); break;
    case 'tasks': loadMobileTasks(); break;
    case 'params': loadParameters(); break;
    case 'notes': loadNotes(); break;
    case 'obsidian': loadObsidianMobile(); break;
    case 'manuals': loadManuals(); break;
    case 'stats': loadMobileStats(); break;
    case 'clients': loadMobileClients(); break;
    case 'more': openMoreMenu(); break;
  }

}

function openMoreMenu() {
  document.getElementById('more-menu').classList.add('active');
}
function closeMoreMenu() {
  document.getElementById('more-menu').classList.remove('active');
}

function removeBoot() {
  const bootStyle = document.getElementById('boot-screen');
  if (bootStyle) bootStyle.remove();
}

function showLogin() {
  removeBoot();
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('app').style.display = 'none';
  document.getElementById('hermes-fab')?.classList.remove('ready');
  document.getElementById('hermes-panel')?.classList.remove('active');
}

// ============ FAZA 3: Project Detail (10 sections) ============

async function showProjectDetail(projectId) {
  let project;
  if (_isOnline) {
    project = await apiGet(`/api/proiecte/${projectId}`);
  }
  if (!project) {
    project = projectsCache.find(p => p.id === projectId);
  }
  if (!project) return;

  currentProject = project;

  const p = project;
  const infoEl = document.getElementById('project-info');

  // BEGIN: PV (owned by spawned-pv session)
  const isServiceProj = (p.tip === 'Service');
  const isPifProj = (p.tip === 'PIF');
  let pvButtonHtml = '';
  if (isServiceProj || isPifProj) {
    const callExpr = isServiceProj
      ? `if(window.openPvServiceModal) openPvServiceModal('${p.id}')`
      : `if(window.openPvPifModal) openPvPifModal('${p.id}')`;
    const tone = isPifProj
      ? 'background:var(--violet-soft, rgba(139,135,255,0.12)); color:var(--violet, #8b87ff); border-color:rgba(139,135,255,0.25);'
      : 'background:var(--accent-soft); color:var(--accent); border-color:var(--accent-ring);';
    pvButtonHtml = `
      <div style="margin-top:12px;">
        <button onclick="${callExpr}"
                style="display:inline-flex; align-items:center; gap:6px; padding:8px 14px;
                       ${tone}
                       border-width:1px; border-style:solid; border-radius:8px;
                       font-size:13px; font-weight:600; cursor:pointer; font-family:inherit;">
          <i data-lucide="file-output" style="width:14px; height:14px;"></i> Generează PV
        </button>
      </div>`;
  }
  // END: PV
  infoEl.innerHTML = `
    <div style="margin-bottom:16px;">
      <div style="font-size:18px; font-weight:600;">${escapeHtml(p.nume || '-')}</div>
      <div style="margin-top:4px;">
        <span class="project-status status-${p.status || 'in_lucru'}">${getStatusLabel(p.status)}</span>
        <span style="font-size:12px; color:var(--text-secondary); margin-left:8px;">${escapeHtml(p.tip || 'PIF')}</span>
      </div>
      ${pvButtonHtml}
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
      ${infoField('Client', p.client)}
      ${infoField('Producător', p.producator)}
      ${infoField('Echipament', p.echipament_principal)}
      ${infoField('Locație', p.locatie)}
      ${infoField('Deadline', p.deadline)}
      ${infoField('Data start', p.data_incepere)}
      ${infoField('Nr. Comandă', p.nr_comanda)}
      ${infoField('Nr. Contract', p.nr_contract)}
      ${infoField('PM', p.pm)}
      ${infoField('Cod proiect', p.cod_proiect)}
    </div>
  `;

  // Încarcă toate secțiunile (paralel)
  Promise.all([
    loadMobileTimer(projectId),
    loadMobileChecklist(projectId),
    loadMobileProjectTasks(projectId),
    loadMobileJournal(projectId),
    loadMobileAttachments(projectId),
    loadMobileEquipment(projectId),
    loadMobileObservations(p),
    loadMobileServiceFields(p),
  ]);

  // Switch view
  document.querySelectorAll('.tab-view').forEach(v => v.classList.remove('active'));
  document.getElementById('project-detail').classList.add('active');
}

function infoField(label, value) {
  if (!value) return '';
  return `<div style="padding:8px; background:var(--surface); border:1px solid var(--border); border-radius:8px;">
    <div class="detail-label">${label}</div>
    <div style="font-size:14px;">${escapeHtml(value)}</div>
  </div>`;
}

// 3.3 Timer
async function loadMobileTimer(projectId) {
  const el = document.getElementById('mobile-timer-section');
  try {
    const data = await apiGet(`/api/proiecte/${projectId}/timer`);
    if (!data) { el.innerHTML = ''; return; }

    const totalH = (data.total_secunde / 3600).toFixed(1);
    const sessions = data.sessions || [];
    const activeSession = sessions.find(s => !s.stop_time);

    el.innerHTML = `
      <div style="font-size:14px; font-weight:600; margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="timer" style="color:var(--accent);"></i> Timer · ${totalH}h total</div>
      ${activeSession ? `
        <div class="detail-section" style="border-left:3px solid var(--success);">
          <div style="font-size:13px; color:var(--success);">Timer activ</div>
          <div id="mobile-timer-live" style="font-size:24px; font-weight:600; color:var(--accent); margin:8px 0;"></div>
          <button onclick="stopMobileTimer('${projectId}')" class="modal-btn" style="background:var(--danger);display:flex;align-items:center;justify-content:center;gap:6px;"><i data-lucide="square"></i> Oprește</button>
        </div>
      ` : `
        <button onclick="startMobileTimer('${projectId}')" class="modal-btn" style="margin-bottom:12px;display:flex;align-items:center;justify-content:center;gap:6px;"><i data-lucide="play"></i> Pornește timer</button>
      `}
      ${sessions.filter(s => s.stop_time).slice(0, 5).map(s => `
        <div style="display:flex; justify-content:space-between; padding:8px 12px; font-size:12px; color:var(--text-secondary); border-bottom:1px solid var(--border);">
          <span>${(s.start_time || '').substring(0, 16).replace('T', ' ')}</span>
          <span>${((s.durata_secunde || 0) / 3600).toFixed(1)}h</span>
          <button onclick="deleteMobileTimerSession('${s.id}','${projectId}')" style="background:none;border:none;color:var(--error);font-size:14px;cursor:pointer;">×</button>
        </div>
      `).join('')}
    `;

    if (activeSession) {
      const start = new Date(activeSession.start_time).getTime();
      if (window._mobileTimerInterval) clearInterval(window._mobileTimerInterval);
      window._mobileTimerInterval = setInterval(() => {
        const el = document.getElementById('mobile-timer-live');
        if (!el) { clearInterval(window._mobileTimerInterval); return; }
        el.textContent = formatDuration(Math.floor((Date.now() - start) / 1000));
      }, 1000);
    }
  } catch (e) { el.innerHTML = ''; }
}

async function startMobileTimer(projectId) {
  await apiPost(`/api/proiecte/${projectId}/timer/start`, {});
  if ('vibrate' in navigator) navigator.vibrate(30);
  loadMobileTimer(projectId);
}

async function stopMobileTimer(projectId) {
  await apiPost(`/api/proiecte/${projectId}/timer/stop`, {});
  if ('vibrate' in navigator) navigator.vibrate(50);
  if (window._mobileTimerInterval) clearInterval(window._mobileTimerInterval);
  loadMobileTimer(projectId);
}

async function deleteMobileTimerSession(sessionId, projectId) {
  if (!confirm('Șterge sesiunea?')) return;
  await apiDelete(`/api/timer/${sessionId}`);
  loadMobileTimer(projectId);
}

// 3.4 Checklist PIF cu categorii dinamice (parity cu desktop)
function _mobileChecklistCollapsedKey(projectId) { return `pif-mobile:checklist-collapsed:${projectId}`; }
function _getMobileChecklistCollapsed(projectId) {
  try { return new Set(JSON.parse(localStorage.getItem(_mobileChecklistCollapsedKey(projectId)) || '[]')); }
  catch { return new Set(); }
}
function _setMobileChecklistCollapsed(projectId, set) {
  try { localStorage.setItem(_mobileChecklistCollapsedKey(projectId), JSON.stringify([...set])); } catch {}
}

function toggleMobileChecklistCat(catKey, projectId) {
  const collapsed = _getMobileChecklistCollapsed(projectId);
  if (collapsed.has(catKey)) collapsed.delete(catKey);
  else collapsed.add(catKey);
  _setMobileChecklistCollapsed(projectId, collapsed);
  const el = document.querySelector(`.mob-checklist-cat[data-cat-key="${catKey}"]`);
  if (el) el.classList.toggle('collapsed');
}

async function loadMobileChecklist(projectId) {
  const el = document.getElementById('mobile-checklist-section');
  if (!el) return;
  try {
    const [items, categorii] = await Promise.all([
      apiGet(`/api/proiecte/${projectId}/checklist`),
      apiGet(`/api/proiecte/${projectId}/checklist-categorii`).catch(() => [])
    ]);

    const total = (items || []).length;
    const done = (items || []).filter(i => i.completed).length;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const collapsed = _getMobileChecklistCollapsed(projectId);

    const byCat = new Map();
    for (const it of (items || [])) {
      const key = it.categorie_id != null ? String(it.categorie_id) : '0';
      if (!byCat.has(key)) byCat.set(key, []);
      byCat.get(key).push(it);
    }
    const orderedCats = [...(categorii || [])].sort((a, b) => (a.ordine ?? 0) - (b.ordine ?? 0));
    const uncategorized = byCat.get('0') || [];

    const renderCatBlock = (cat, its, isUncategorized = false) => {
      const catKey = String(cat.id);
      const isCollapsed = collapsed.has(catKey);
      const catDone = its.filter(i => i.completed).length;
      const progressTxt = its.length > 0 ? `${catDone}/${its.length}` : '0/0';
      const isFullDone = its.length > 0 && catDone === its.length;
      const actions = isUncategorized ? '' : `
        <div class="mob-cat-actions">
          <button onclick="event.stopPropagation(); renameMobileChecklistCat(${cat.id}, '${projectId}')" aria-label="Redenumește"><i data-lucide="pencil"></i></button>
          <button onclick="event.stopPropagation(); deleteMobileChecklistCat(${cat.id}, '${escapeHtml(cat.nume).replace(/'/g, "\\'")}', '${projectId}')" aria-label="Șterge"><i data-lucide="trash-2"></i></button>
        </div>`;
      const rows = its.map(it => `
        <div class="mob-checklist-item ${it.completed ? 'done' : ''}">
          <input type="checkbox" ${it.completed ? 'checked' : ''}
            onchange="toggleMobileChecklist('${it.id}',this.checked,'${projectId}')">
          <span class="mob-ci-text">${escapeHtml(it.titlu || '')}</span>
          <button onclick="deleteMobileChecklistItem('${it.id}','${projectId}')" class="mob-ci-del" aria-label="Șterge"><i data-lucide="trash-2"></i></button>
        </div>
      `).join('') || `<div class="mob-cat-empty">Niciun item.</div>`;
      const addRow = `
        <div class="mob-cat-addrow">
          <input type="text" placeholder="${isUncategorized ? 'Item fără categorie...' : 'Item nou...'}"
                 onkeydown="if(event.key==='Enter') addMobileChecklistItem('${projectId}', ${isUncategorized ? 'null' : cat.id})">
          <button onclick="addMobileChecklistItem('${projectId}', ${isUncategorized ? 'null' : cat.id})"><i data-lucide="plus"></i></button>
        </div>`;
      return `
        <div class="mob-checklist-cat ${isCollapsed ? 'collapsed' : ''} ${isUncategorized ? 'uncategorized' : ''}" data-cat-key="${catKey}">
          <div class="mob-cat-head" onclick="toggleMobileChecklistCat('${catKey}', '${projectId}')">
            <i data-lucide="chevron-down" class="mob-cat-chevron"></i>
            <span class="mob-cat-name">${escapeHtml(cat.nume)}</span>
            <span class="mob-cat-progress ${isFullDone ? 'done' : ''}">${progressTxt}</span>
            ${actions}
          </div>
          <div class="mob-cat-body">
            ${rows}
            ${addRow}
          </div>
        </div>`;
    };

    el.innerHTML = `
      <div style="font-size:14px; font-weight:600; margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="list-checks" style="color:var(--accent);"></i> Checklist PIF (${done}/${total})</div>
      <div style="background:var(--border);border-radius:4px;height:6px;margin-bottom:12px;">
        <div style="background:linear-gradient(90deg, var(--accent), var(--success));height:100%;border-radius:4px;width:${pct}%;transition:width 0.3s;"></div>
      </div>
      <div style="display:flex; justify-content:flex-end; margin-bottom:8px;">
        <button onclick="addMobileChecklistCat('${projectId}')" class="mob-add-cat-btn"><i data-lucide="folder-plus"></i> Categorie</button>
      </div>
      ${orderedCats.map(c => renderCatBlock(c, byCat.get(String(c.id)) || [])).join('')}
      ${renderCatBlock({ id: 0, nume: 'Fără categorie' }, uncategorized, true)}
    `;
  } catch (e) { el.innerHTML = ''; console.error('loadMobileChecklist failed:', e); }
}

async function addMobileChecklistCat(projectId) {
  const nume = prompt('Numele categoriei:');
  if (!nume || !nume.trim()) return;
  try {
    await apiPost(`/api/proiecte/${projectId}/checklist-categorii`, { nume: nume.trim() });
    if ('vibrate' in navigator) navigator.vibrate(20);
    loadMobileChecklist(projectId);
  } catch (e) { alert('Eroare la creare'); }
}

async function renameMobileChecklistCat(catId, projectId) {
  const current = document.querySelector(`.mob-checklist-cat[data-cat-key="${catId}"] .mob-cat-name`)?.textContent || '';
  const newName = prompt('Noul nume:', current);
  if (!newName || !newName.trim() || newName.trim() === current) return;
  try {
    await apiPut(`/api/checklist-categorii/${catId}`, { nume: newName.trim() });
    loadMobileChecklist(projectId);
  } catch (e) { alert('Eroare'); }
}

async function deleteMobileChecklistCat(catId, catName, projectId) {
  if (!confirm(`Ștergi categoria "${catName}"? Items-urile vor fi mutate la "Fără categorie".`)) return;
  try {
    await apiDelete(`/api/checklist-categorii/${catId}?move=1`);
    if ('vibrate' in navigator) navigator.vibrate(20);
    loadMobileChecklist(projectId);
  } catch (e) { alert('Eroare'); }
}

async function toggleMobileChecklist(itemId, checked, projectId) {
  await apiPut(`/api/checklist/${itemId}`, { completed: checked ? 1 : 0 });
  loadMobileChecklist(projectId);
}

async function addMobileChecklistItem(projectId, categorieId = null) {
  const catKey = categorieId == null ? '0' : String(categorieId);
  const root = document.querySelector(`.mob-checklist-cat[data-cat-key="${catKey}"] .mob-cat-addrow input`);
  const titlu = (root?.value || '').trim();
  if (!titlu) return;
  await apiPost(`/api/proiecte/${projectId}/checklist`, { titlu, ordine: 999, categorie_id: categorieId });
  if (root) root.value = '';
  loadMobileChecklist(projectId);
}

async function deleteMobileChecklistItem(itemId, projectId) {
  await apiDelete(`/api/checklist/${itemId}`);
  loadMobileChecklist(projectId);
}

// 3.5 Project Tasks
async function loadMobileProjectTasks(projectId) {
  const el = document.getElementById('mobile-tasks-section');
  try {
    const tasks = await apiGet(`/api/proiecte/${projectId}/tasks`);
    if (!tasks) { el.innerHTML = ''; return; }

    // Separate active vs finalised — Ion wants them grouped, not mixed.
    const active = tasks.filter(t => t.status !== 'done');
    const done = tasks.filter(t => t.status === 'done');
    done.sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || ''));

    const renderRow = (t) => {
      const prioRaw = t.prioritate || 'Normal';
      const prioCap = prioRaw.charAt(0).toUpperCase() + prioRaw.slice(1).toLowerCase();
      const statusClass = t.status || 'to_do';
      const statusLabel = ({ to_do: 'To Do', in_lucru: 'În Lucru', done: 'Finalizat' })[statusClass] || statusClass;
      return `
        <div class="mobile-task-row">
          <input type="checkbox" ${t.status === 'done' ? 'checked' : ''} class="mobile-task-check"
            onchange="toggleMobileProjectTask('${t.id}',this.checked,'${projectId}')">
          <div class="mobile-task-body">
            <div class="mobile-task-title ${t.status === 'done' ? 'done' : ''}">${escapeHtml(t.titlu)}</div>
            ${t.data_scadenta ? `<div class="mobile-task-meta"><i data-lucide="calendar" style="width:11px;height:11px;vertical-align:-2px;"></i> ${t.data_scadenta}</div>` : ''}
          </div>
          <span class="todo-priority cyclable ${prioRaw.toLowerCase()}" onclick="event.stopPropagation(); cycleMobileTodoPriority('${t.id}', '${prioCap}', '${projectId}')">${prioCap}</span>
          <span class="todo-status cyclable ${statusClass}" onclick="event.stopPropagation(); cycleMobileTodoStatus('${t.id}', '${statusClass}', '${projectId}')">${statusLabel}</span>
          <button onclick="deleteMobileProjectTask('${t.id}','${projectId}')" class="mobile-task-del" aria-label="Șterge"><i data-lucide="trash-2"></i></button>
        </div>`;
    };

    let listHtml = active.map(renderRow).join('');
    if (done.length > 0) {
      listHtml += `<div class="mobile-tasks-divider"><span>Finalizate (${done.length})</span></div>`;
      listHtml += done.map(renderRow).join('');
    }

    el.innerHTML = `
      <div style="font-size:14px;font-weight:600;margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="list-todo" style="color:var(--accent);"></i> Todo List</div>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input type="text" id="new-project-task" placeholder="Task nou..."
          style="flex:1;padding:10px;font-size:14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);">
        <button onclick="addMobileProjectTask('${projectId}')" style="padding:10px 16px;background:var(--accent);color:var(--bg);border:none;border-radius:8px;font-weight:600;">+</button>
      </div>
      ${listHtml}
    `;
  } catch (e) { el.innerHTML = ''; }
}

async function cycleMobileTodoPriority(taskId, current, projectId) {
  const idx = _MOBILE_PRIO_CYCLE.indexOf(current || 'Normal');
  const next = _MOBILE_PRIO_CYCLE[(idx + 1) % _MOBILE_PRIO_CYCLE.length];
  try {
    await apiPut(`/api/tasks/${taskId}`, { prioritate: next.toLowerCase() });
    if ('vibrate' in navigator) navigator.vibrate(15);
    loadMobileProjectTasks(projectId);
  } catch (e) {}
}

async function cycleMobileTodoStatus(taskId, current, projectId) {
  const idx = _MOBILE_STATUS_CYCLE.indexOf(current || 'to_do');
  const next = _MOBILE_STATUS_CYCLE[(idx + 1) % _MOBILE_STATUS_CYCLE.length];
  try {
    await apiPut(`/api/tasks/${taskId}`, { status: next });
    if ('vibrate' in navigator) navigator.vibrate(15);
    loadMobileProjectTasks(projectId);
  } catch (e) {}
}

async function addMobileProjectTask(projectId) {
  const input = document.getElementById('new-project-task');
  const titlu = input.value.trim();
  if (!titlu) return;
  await apiPost(`/api/proiecte/${projectId}/tasks`, { titlu, prioritate: 'normal' });
  input.value = '';
  loadMobileProjectTasks(projectId);
}

async function toggleMobileProjectTask(taskId, checked, projectId) {
  await apiPut(`/api/tasks/${taskId}`, { status: checked ? 'done' : 'to_do' });
  loadMobileProjectTasks(projectId);
}

async function deleteMobileProjectTask(taskId, projectId) {
  await apiDelete(`/api/tasks/${taskId}`);
  loadMobileProjectTasks(projectId);
}

// 3.6 Journal
async function loadMobileJournal(projectId) {
  const el = document.getElementById('mobile-journal-section');
  try {
    const entries = await apiGet(`/api/proiecte/${projectId}/jurnal`);

    el.innerHTML = `
      <div style="font-size:14px;font-weight:600;margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="notebook-pen" style="color:var(--accent);"></i> Jurnal de lucru</div>
      <div style="margin-bottom:12px;">
        <textarea id="new-journal-entry" placeholder="Adaugă intrare..."
          style="width:100%;min-height:60px;padding:10px;font-size:14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);resize:vertical;font-family:inherit;"></textarea>
        <button onclick="addMobileJournalEntry('${projectId}')" class="modal-btn" style="margin-top:4px;">Salvează</button>
      </div>
      ${(entries || []).map(j => `
        <div class="note-item" style="padding:12px;">
          <div style="display:flex;justify-content:space-between;align-items:start;">
            <div class="note-date">${j.data || ''}</div>
            <button onclick="deleteMobileJournalEntry('${j.id}','${projectId}')" style="background:none;border:none;color:var(--error);font-size:14px;cursor:pointer;">×</button>
          </div>
          <div style="font-size:13px;margin-top:4px;white-space:pre-wrap;">${escapeHtml(j.continut || '')}</div>
        </div>
      `).join('')}
    `;
  } catch (e) { el.innerHTML = ''; }
}

async function addMobileJournalEntry(projectId) {
  const textarea = document.getElementById('new-journal-entry');
  const continut = textarea.value.trim();
  if (!continut) return;
  await apiPost(`/api/proiecte/${projectId}/jurnal`, {
    continut, data: new Date().toISOString().substring(0, 10)
  });
  textarea.value = '';
  if ('vibrate' in navigator) navigator.vibrate(30);
  loadMobileJournal(projectId);
}

async function deleteMobileJournalEntry(entryId, projectId) {
  if (!confirm('Șterge intrarea?')) return;
  await apiDelete(`/api/jurnal/${entryId}`);
  loadMobileJournal(projectId);
}

// 3.7 Attachments
async function loadMobileAttachments(projectId) {
  const el = document.getElementById('mobile-attachments-section');
  try {
    const attachments = await apiGet(`/api/proiecte/${projectId}/atasamente`);
    const count = (attachments || []).length;

    const downloadAllBar = (count >= 2)
      ? `<button onclick="downloadAllMobileAttachments('${projectId}')" class="modal-btn" style="margin-bottom:8px; background:var(--bg-elev2); color:var(--text); display:flex; align-items:center; justify-content:center; gap:6px; font-size:13px; padding:8px 12px;"><i data-lucide="download-cloud"></i> Descarcă tot (${count})</button>`
      : '';

    el.innerHTML = `
      <div style="font-size:14px;font-weight:600;margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="paperclip" style="color:var(--accent);"></i> Atașamente</div>
      <label style="display:block;padding:12px;text-align:center;background:var(--surface);border:2px dashed var(--border);border-radius:8px;cursor:pointer;margin-bottom:12px;color:var(--text-secondary);">
        <i data-lucide="paperclip"></i> Adaugă fișier
        <input type="file" id="mobile-file-upload" onchange="uploadMobileFile('${projectId}')" style="display:none;">
      </label>
      ${downloadAllBar}
      ${(attachments || []).map(a => {
        const iconName = {'PDF':'file-text','IMG':'image','DOC':'file-text','XLS':'file-spreadsheet','EMAIL':'mail','ZIP':'archive'}[a.tip_fisier] || 'file';
        const size = formatFileSize(a.dimensiune);
        return `
          <div style="display:flex;align-items:center;gap:8px;padding:10px;margin-bottom:4px;background:var(--surface);border-radius:8px;border:1px solid var(--border);">
            <span style="color:var(--accent);display:inline-flex;align-items:center;flex-shrink:0;"><i data-lucide="${iconName}"></i></span>
            <div style="flex:1;min-width:0;">
              <div style="font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(a.nume_fisier)}</div>
              <div style="font-size:11px;color:var(--text-secondary);">${size}</div>
            </div>
            <a href="/api/atasamente/${a.id}/download" target="_blank" aria-label="Descarcă" style="width:32px;height:32px;flex-shrink:0;border-radius:6px;color:var(--accent);text-decoration:none;display:inline-flex;align-items:center;justify-content:center;"><i data-lucide="download" style="width:16px;height:16px;"></i></a>
            <button onclick="deleteMobileAttachment('${a.id}','${projectId}')" aria-label="Șterge" style="width:32px;height:32px;flex-shrink:0;border-radius:6px;background:none;border:none;color:var(--danger);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></button>
          </div>
        `;
      }).join('')}
    `;
  } catch (e) { el.innerHTML = ''; }
}

// Sequential downloads on mobile, same pattern as desktop.
async function downloadAllMobileAttachments(projectId) {
  try {
    const attachments = await apiGet(`/api/proiecte/${projectId}/atasamente`);
    if (!attachments || !attachments.length) return;
    for (let i = 0; i < attachments.length; i++) {
      const a = document.createElement('a');
      a.href = `/api/atasamente/${attachments[i].id}/download`;
      a.download = attachments[i].nume_fisier || '';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      await new Promise(r => setTimeout(r, 250));
    }
    if ('vibrate' in navigator) navigator.vibrate(30);
  } catch (e) { console.error('downloadAllMobileAttachments failed:', e); }
}

async function uploadMobileFile(projectId) {
  const input = document.getElementById('mobile-file-upload');
  if (!input.files[0]) return;
  const formData = new FormData();
  formData.append('file', input.files[0]);
  try {
    const res = await fetch(`/api/proiecte/${projectId}/atasamente`, {
      method: 'POST', credentials: 'include', body: formData
    });
    if (res.ok) {
      if ('vibrate' in navigator) navigator.vibrate(30);
      loadMobileAttachments(projectId);
    }
  } catch (e) { console.error('Upload error:', e); }
  input.value = '';
}

async function deleteMobileAttachment(attachmentId, projectId) {
  if (!confirm('Șterge atașamentul?')) return;
  await apiDelete(`/api/atasamente/${attachmentId}`);
  loadMobileAttachments(projectId);
}

// 3.8 Equipment
async function loadMobileEquipment(projectId) {
  const el = document.getElementById('mobile-equipment-section');
  try {
    const items = await apiGet(`/api/proiecte/${projectId}/echipamente`);

    el.innerHTML = `
      <div style="font-size:14px;font-weight:600;margin:16px 0 8px;display:flex;align-items:center;gap:6px;"><i data-lucide="wrench" style="color:var(--accent);"></i> Echipamente</div>
      <button onclick="showMobileEquipmentForm('${projectId}')" class="modal-btn" style="margin-bottom:12px;display:flex;align-items:center;justify-content:center;gap:6px;"><i data-lucide="plus"></i> Adaugă echipament</button>
      ${(items || []).map(eq => {
        let params = {};
        try { params = JSON.parse(eq.params_json || '{}'); } catch {}
        const paramEntries = Object.entries(params);
        const eqJson = JSON.stringify(eq).replace(/"/g, '&quot;');
        return `
          <div class="detail-section eq-card" data-eq-id="${escapeHtml(eq.id)}" style="margin-bottom:8px; cursor:pointer;" onclick="toggleMobileEquipmentCard(this, event)">
            <div style="display:flex;justify-content:space-between;align-items:start;gap:8px;">
              <div style="flex:1;min-width:0;">
                <div style="font-weight:600;font-size:14px;">${escapeHtml(eq.nume || '-')}</div>
                <div style="font-size:12px;color:var(--text-secondary);">${escapeHtml(eq.producator || '')} · ${escapeHtml(eq.model || '')}</div>
                ${eq.serial_number ? `<div style="font-size:11px;color:var(--text-secondary);">S/N: ${escapeHtml(eq.serial_number)}</div>` : ''}
                ${paramEntries.length > 0 ? `<div style="font-size:11px;color:var(--accent);margin-top:3px;display:inline-flex;align-items:center;gap:3px;"><i data-lucide="sliders-horizontal" style="width:11px;height:11px;"></i> ${paramEntries.length} parametri</div>` : ''}
              </div>
              <div style="display:flex;gap:4px;flex-shrink:0;align-items:center;" onclick="event.stopPropagation()">
                <button onclick='event.stopPropagation(); editMobileEquipment(${eqJson}, "${projectId}")' aria-label="Editează" style="background:none;border:none;color:var(--text-secondary);cursor:pointer;padding:6px;display:inline-flex;align-items:center;justify-content:center;"><i data-lucide="pencil" style="width:16px;height:16px;"></i></button>
                <button onclick="event.stopPropagation(); deleteMobileEquipment('${eq.id}','${projectId}')" aria-label="Șterge" style="background:none;border:none;color:var(--danger);cursor:pointer;padding:6px;display:inline-flex;align-items:center;justify-content:center;"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></button>
                ${paramEntries.length > 0 ? `<i data-lucide="chevron-down" class="eq-chevron" style="width:16px;height:16px;color:var(--text-dim);transition:transform 0.15s;"></i>` : ''}
              </div>
            </div>
            ${paramEntries.length > 0 ? `
              <div class="eq-expanded" style="display:none; margin-top:8px;padding-top:8px;border-top:1px solid var(--border);">
                ${paramEntries.map(([k, v]) => `
                  <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;padding:4px 0;border-bottom:1px solid var(--line-soft);gap:8px;">
                    <span style="color:var(--accent);font-family:'JetBrains Mono',monospace;font-weight:600;flex-shrink:0;">${escapeHtml(k)}</span>
                    <span style="font-family:'JetBrains Mono',monospace;text-align:right;word-break:break-word;">${escapeHtml(v)}</span>
                  </div>
                `).join('')}
              </div>
            ` : ''}
          </div>
        `;
      }).join('')}
    `;
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
  } catch (e) { el.innerHTML = ''; }
}

function toggleMobileEquipmentCard(card, ev) {
  const expanded = card.querySelector('.eq-expanded');
  const chevron = card.querySelector('.eq-chevron');
  if (!expanded) return;
  const isOpen = expanded.style.display !== 'none';
  expanded.style.display = isOpen ? 'none' : 'block';
  if (chevron) chevron.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
}

function editMobileEquipment(eq, projectId) {
  // Pre-fill modal with existing equipment data
  showMobileEquipmentForm(projectId, eq);
}

function showMobileEquipmentForm(projectId, eq = null) {
  const modal = document.getElementById('note-modal');
  const content = modal.querySelector('.modal-content');
  const originalContent = content.innerHTML;
  const isEdit = !!eq;

  // Build params text from eq.params_json if editing
  let paramsText = '';
  if (isEdit) {
    try {
      const obj = typeof eq.params_json === 'string' ? JSON.parse(eq.params_json || '{}') : (eq.params_json || {});
      paramsText = Object.entries(obj).map(([k, v]) => `${k} = ${v}`).join('\n');
    } catch {}
  }

  const producator = isEdit ? (eq.producator || 'Altul') : 'ABB';
  const producatori = ['ABB', 'Siemens', 'Danfoss', 'Lenze', 'Altul'];

  content.innerHTML = `
    <div class="modal-header">
      <span class="modal-title">${isEdit ? 'Editează echipament' : 'Echipament nou'}</span>
      <button class="modal-close" onclick="restoreAndCloseModal()">×</button>
    </div>
    <input type="text" id="eq-nume" placeholder="Nume echipament" value="${escapeHtml(isEdit ? (eq.nume || '') : '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
    <select id="eq-producator" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      ${producatori.map(p => `<option value="${p}" ${p === producator ? 'selected' : ''}>${p}</option>`).join('')}
    </select>
    <input type="text" id="eq-model" placeholder="Model" value="${escapeHtml(isEdit ? (eq.model || '') : '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
    <input type="text" id="eq-serial" placeholder="Serial Number" value="${escapeHtml(isEdit ? (eq.serial_number || '') : '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
    <button type="button" onclick="triggerMobileImportParams()" class="modal-btn" style="background:var(--bg-elev2); color:var(--text); padding:10px 12px; font-size:13px; display:inline-flex; align-items:center; gap:6px; margin-bottom:8px; width:100%; justify-content:center;"><i data-lucide="file-up"></i> Import parametri din fișier</button>
    <input type="file" id="mobile-import-file" accept=".txt,.pdf,.csv,.dcparamsbak" style="display:none;" onchange="onMobileImportFileSelected(event)">
    <textarea id="eq-params" placeholder="Parametri (un par=val pe linie)&#10;p0304 = 400&#10;p0305 = 5.6" style="width:100%;min-height:100px;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);resize:vertical;font-family:'JetBrains Mono',monospace;margin-bottom:8px;">${escapeHtml(paramsText)}</textarea>
    <button onclick="saveMobileEquipment('${projectId}', ${isEdit ? `'${eq.id}'` : 'null'})" class="modal-btn">${isEdit ? 'Salvează' : 'Creează'}</button>
  `;

  modal._originalContent = originalContent;
  modal.classList.add('active');
  if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

async function saveMobileEquipment(projectId, eqId) {
  const data = {
    nume: document.getElementById('eq-nume').value.trim(),
    producator: document.getElementById('eq-producator').value,
    model: document.getElementById('eq-model').value.trim(),
    serial_number: document.getElementById('eq-serial').value.trim(),
    params_text: document.getElementById('eq-params').value
  };
  if (!data.nume) { alert('Numele e obligatoriu'); return; }

  if (eqId && eqId !== 'null') {
    await apiPut(`/api/echipamente/${eqId}`, data);
  } else {
    await apiPost(`/api/proiecte/${projectId}/echipamente`, data);
  }

  restoreAndCloseModal();
  loadMobileEquipment(projectId);
}

async function deleteMobileEquipment(eqId, projectId) {
  if (!confirm('Șterge echipamentul?')) return;
  await apiDelete(`/api/echipamente/${eqId}`);
  loadMobileEquipment(projectId);
}

// ============ IMPORT PARAMETRI DIN EXPORT PRODUCATOR (mobile) ============

let _mobileImportPreview = null;

function triggerMobileImportParams() {
  const producator = document.getElementById('eq-producator')?.value || '';
  if (!producator || producator === 'Altul') {
    alert('Selectează mai întâi un producător (Danfoss, ABB, Siemens, Lenze)');
    return;
  }
  const input = document.getElementById('mobile-import-file');
  if (input) {
    input.value = '';
    input.click();
  }
}

async function onMobileImportFileSelected(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const producator = document.getElementById('eq-producator')?.value || '';
  const model = document.getElementById('eq-model')?.value || '';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('producator', producator);
  formData.append('model', model);

  try {
    const res = await fetch('/api/import-params/preview', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || 'Eroare la parsare');
      return;
    }
    _mobileImportPreview = data;
    showMobileImportModal(data);
  } catch (e) {
    console.error('Mobile import preview failed:', e);
    alert('Eroare la parsare fișier');
  }
}

function showMobileImportModal(data) {
  const modal = document.getElementById('mobile-import-modal');
  const body = document.getElementById('mobile-import-body');
  if (!modal || !body) return;

  const params = data.params || [];
  const rows = params.map((p, idx) => {
    const denumire = p.descriere_db || p.name || '';
    const conflictBadge = p.conflict
      ? `<span style="color:var(--warning); font-size:11px; margin-left:4px;"><i data-lucide="alert-triangle" style="width:11px;height:11px;vertical-align:-1px;"></i> conflict</span>`
      : '';
    const valueRow = p.conflict
      ? `<select class="mimp-value-select" data-idx="${idx}" style="margin-top:4px; padding:6px 8px; background:var(--bg); border:1px solid var(--border); border-radius:6px; color:var(--text); font-family:'JetBrains Mono',monospace; font-size:12px; width:100%;">
            ${Object.entries(p.per_setup).map(([s, v]) => `<option value="${escapeHtml(v)}"${v === p.value ? ' selected' : ''}>S${escapeHtml(s)}: ${escapeHtml(v)}</option>`).join('')}
         </select>`
      : `<span style="font-family:'JetBrains Mono',monospace; color:var(--text);">${escapeHtml(p.value)}</span>`;

    return `
      <label data-idx="${idx}" style="display:flex; gap:10px; align-items:flex-start; padding:10px 8px; border-bottom:1px solid var(--line-soft); cursor:pointer;">
        <input type="checkbox" class="mimp-check" data-idx="${idx}" checked style="margin-top:3px; width:18px; height:18px; accent-color:var(--accent);">
        <div style="flex:1; min-width:0;">
          <div style="display:flex; align-items:baseline; gap:6px; flex-wrap:wrap;">
            <span style="font-family:'JetBrains Mono',monospace; color:var(--accent); font-weight:600;">${escapeHtml(p.db_id)}</span>
            <span style="font-size:12px; color:var(--text-secondary);">${escapeHtml(denumire)}</span>
            ${conflictBadge}
          </div>
          <div style="margin-top:4px;">${valueRow}</div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">default: ${escapeHtml(p.default || '-')}</div>
        </div>
      </label>`;
  }).join('');

  body.innerHTML = `
    <div style="margin-bottom:10px; padding:8px 10px; background:var(--bg); border:1px solid var(--border); border-radius:8px; font-size:12px; color:var(--text-secondary);">
      <div><strong>${escapeHtml(data.producator_detected || '')}</strong> · familie <span style="font-family:'JetBrains Mono',monospace;">${escapeHtml(data.familie || '-')}</span></div>
      <div style="margin-top:4px;">${data.count} parametri${data.conflicts ? ` · <span style="color:var(--warning);">${data.conflicts} conflicte</span>` : ''}</div>
    </div>
    <div style="display:flex; gap:6px; margin-bottom:8px;">
      <button onclick="toggleAllMobileImport(true)" class="modal-btn" style="background:var(--bg-elev2); color:var(--text); padding:6px 10px; font-size:12px; flex:1;">Toate</button>
      <button onclick="toggleAllMobileImport(false)" class="modal-btn" style="background:var(--bg-elev2); color:var(--text); padding:6px 10px; font-size:12px; flex:1;">Niciunul</button>
    </div>
    <div>${rows || '<div style="text-align:center; padding:20px; color:var(--text-secondary);">Niciun parametru găsit.</div>'}</div>
  `;

  modal.classList.add('active');
  if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

function toggleAllMobileImport(checked) {
  document.querySelectorAll('.mimp-check').forEach(cb => cb.checked = checked);
}

function applyMobileImportedParams() {
  if (!_mobileImportPreview) return;
  const params = _mobileImportPreview.params || [];
  const ta = document.getElementById('eq-params');
  if (!ta) { closeMobileImportModal(); return; }

  const existing = {};
  ta.value.split('\n').forEach(line => {
    const idx = line.indexOf('=');
    if (idx > 0) {
      const k = line.slice(0, idx).trim();
      const v = line.slice(idx + 1).trim();
      if (k) existing[k] = v;
    }
  });

  let added = 0, overridden = 0;
  document.querySelectorAll('.mimp-check').forEach(cb => {
    if (!cb.checked) return;
    const idx = parseInt(cb.dataset.idx, 10);
    const p = params[idx];
    if (!p) return;
    let value = p.value;
    const sel = document.querySelector(`.mimp-value-select[data-idx="${idx}"]`);
    if (sel) value = sel.value;
    if (Object.prototype.hasOwnProperty.call(existing, p.db_id)) overridden++;
    else added++;
    existing[p.db_id] = String(value);
  });

  ta.value = Object.entries(existing).map(([k, v]) => `${k} = ${v}`).join('\n');
  closeMobileImportModal();
  const msg = overridden
    ? `Import: +${added} adăugați, ${overridden} suprascriși`
    : `Import: +${added} parametri`;
  if ('vibrate' in navigator) navigator.vibrate(30);
  // Toast minimal
  const toast = document.createElement('div');
  toast.textContent = msg;
  toast.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:var(--bg-elev3);border:1px solid var(--accent);color:var(--text);padding:10px 16px;border-radius:8px;z-index:200;font-size:13px;';
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2500);
}

function closeMobileImportModal() {
  const modal = document.getElementById('mobile-import-modal');
  if (modal) modal.classList.remove('active');
  _mobileImportPreview = null;
}

// Long-text editor on mobile: preview card -> modal with toolbar.
// Backing values live on `currentProject` until the user saves through the modal.
function _renderLongTextPreviewMobile(value, placeholder) {
  const text = (value || '').trim();
  if (!text) {
    return `<div class="mlt-preview is-empty">${escapeHtml(placeholder)}</div>`;
  }
  // Truncate visually via CSS (-webkit-line-clamp). Pre-wrap preserves new lines.
  return `<div class="mlt-preview">${escapeHtml(text)}</div>`;
}

// 3.9 Observations
async function loadMobileObservations(project) {
  const el = document.getElementById('mobile-observations-section');
  if (project.tip !== 'PIF') { el.innerHTML = ''; return; }

  const preview = _renderLongTextPreviewMobile(project.observatii, 'Click pentru a adăuga observații tehnice — listă acțiuni, măsurători, decizii...');

  el.innerHTML = `
    <div style="font-size:14px;font-weight:600;margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="message-square-text" style="color:var(--accent);"></i> Observații tehnice</div>
    <div onclick="openMobileLongTextEditor('observatii', 'Observații tehnice', 'message-square-text')">
      ${preview}
    </div>
    <div class="mlt-hint"><i data-lucide="mouse-pointer-click"></i> Click pentru editare</div>
  `;
}

// 3.10 Service fields
async function loadMobileServiceFields(project) {
  const el = document.getElementById('mobile-service-section');
  if (project.tip !== 'Service') { el.innerHTML = ''; return; }

  const beforePreview = _renderLongTextPreviewMobile(project.service_before, 'Click pentru constatări — simptome, cod eroare, comportament echipament...');
  const afterPreview = _renderLongTextPreviewMobile(project.service_after, 'Click pentru acțiuni efectuate și rezultat final...');

  el.innerHTML = `
    <div style="font-size:14px;font-weight:600;margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="clipboard-list" style="color:var(--accent);"></i> Fișă intervenție</div>
    <div class="detail-section" style="border-left:3px solid var(--danger);margin-bottom:8px;padding:10px;">
      <div style="font-size:12px;color:var(--danger);font-weight:600;margin-bottom:6px; display:flex; align-items:center; gap:4px;"><i data-lucide="alert-circle" style="width:12px;height:12px;"></i> Constatări</div>
      <div onclick="openMobileLongTextEditor('service_before', 'Constatări înainte de intervenție', 'alert-circle')">
        ${beforePreview}
      </div>
      <div class="mlt-hint"><i data-lucide="mouse-pointer-click"></i> Click pentru editare</div>
    </div>
    <div class="detail-section" style="border-left:3px solid var(--success);padding:10px;">
      <div style="font-size:12px;color:var(--success);font-weight:600;margin-bottom:6px; display:flex; align-items:center; gap:4px;"><i data-lucide="circle-check" style="width:12px;height:12px;"></i> Acțiuni</div>
      <div onclick="openMobileLongTextEditor('service_after', 'Acțiuni și rezultat', 'circle-check')">
        ${afterPreview}
      </div>
      <div class="mlt-hint"><i data-lucide="mouse-pointer-click"></i> Click pentru editare</div>
    </div>
  `;
}

// ============ Long-text editor (mobile) ============
let _mltActiveField = null;

function openMobileLongTextEditor(fieldName, title, iconName) {
  if (!currentProject) return;
  _mltActiveField = fieldName;

  const value = currentProject[fieldName] || '';
  const modal = document.getElementById('mobile-long-text-modal');
  if (!modal) {
    console.error('mobile-long-text-modal not in DOM');
    return;
  }
  document.getElementById('mlt-title-text').textContent = title;
  const iconEl = document.getElementById('mlt-title-icon');
  if (iconEl && iconName) iconEl.setAttribute('data-lucide', iconName);

  const ta = document.getElementById('mlt-textarea');
  ta.value = value;
  _mltUpdateCounter();
  ta.oninput = _mltUpdateCounter;

  modal.classList.add('active');
  if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
  setTimeout(() => ta.focus(), 50);
}

function closeMobileLongTextEditor() {
  const modal = document.getElementById('mobile-long-text-modal');
  if (modal) modal.classList.remove('active');
  _mltActiveField = null;
}

async function saveMobileLongText() {
  if (!_mltActiveField || !currentProject) { closeMobileLongTextEditor(); return; }
  const ta = document.getElementById('mlt-textarea');
  const value = ta.value;
  try {
    await apiPut(`/api/proiecte/${currentProject.id}`, { [_mltActiveField]: value });
    currentProject[_mltActiveField] = value;
    if ('vibrate' in navigator) navigator.vibrate(30);
    closeMobileLongTextEditor();
    // Re-render the matching section so the preview reflects the new value.
    if (_mltActiveField === 'observatii') loadMobileObservations(currentProject);
    else if (_mltActiveField === 'service_before' || _mltActiveField === 'service_after') loadMobileServiceFields(currentProject);
  } catch (e) {
    console.error('Save long text failed:', e);
    alert('Eroare la salvare');
  }
}

async function copyMobileLongText() {
  const ta = document.getElementById('mlt-textarea');
  if (!ta) return;
  const text = ta.value || '';
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      ta.select(); document.execCommand('copy'); ta.setSelectionRange(0, 0);
    }
    if ('vibrate' in navigator) navigator.vibrate(20);
    const btn = document.getElementById('mlt-copy-label');
    if (btn) { const prev = btn.textContent; btn.textContent = 'Copiat'; setTimeout(() => { btn.textContent = prev; }, 1200); }
  } catch (e) { console.error('Copy failed:', e); }
}

function _mltUpdateCounter() {
  const ta = document.getElementById('mlt-textarea');
  const c = document.getElementById('mlt-counter');
  if (ta && c) c.textContent = (ta.value || '').length + ' caractere';
}

function mltWrap(open, close) {
  const ta = document.getElementById('mlt-textarea');
  if (!ta) return;
  const s = ta.selectionStart, e = ta.selectionEnd;
  const sel = ta.value.substring(s, e);
  const repl = open + (sel || 'text') + close;
  ta.setRangeText(repl, s, e, 'select');
  if (!sel) ta.setSelectionRange(s + open.length, s + open.length + 'text'.length);
  ta.focus();
  _mltUpdateCounter();
}
function mltPrefixLines(prefix) {
  const ta = document.getElementById('mlt-textarea');
  if (!ta) return;
  const s = ta.selectionStart, e = ta.selectionEnd;
  const before = ta.value.substring(0, s);
  const sel = ta.value.substring(s, e) || '\n';
  const after = ta.value.substring(e);
  const prefixed = sel.split('\n').map(l => prefix + l).join('\n');
  ta.value = before + prefixed + after;
  ta.setSelectionRange(s, s + prefixed.length);
  ta.focus();
  _mltUpdateCounter();
}
function mltInsertDate() {
  const ta = document.getElementById('mlt-textarea');
  if (!ta) return;
  const txt = new Date().toLocaleDateString('ro-RO', { day:'2-digit', month:'2-digit', year:'numeric' }) + ' ';
  ta.setRangeText(txt, ta.selectionStart, ta.selectionEnd, 'end');
  ta.focus();
  _mltUpdateCounter();
}

// Click-to-cycle priority / status on mobile tasks. Mirrors the desktop helpers.
// Status cycle skips 'done' — checkbox owns the finalised state.
const _MOBILE_PRIO_CYCLE = ['Normal', 'Minor', 'Urgent'];
const _MOBILE_STATUS_CYCLE = ['to_do', 'in_lucru'];

async function cycleMobileGtPriority(taskId, current) {
  const idx = _MOBILE_PRIO_CYCLE.indexOf(current || 'Normal');
  const next = _MOBILE_PRIO_CYCLE[(idx + 1) % _MOBILE_PRIO_CYCLE.length];
  try {
    await apiPut(`/api/global-tasks/${taskId}`, { prioritate: next });
    if ('vibrate' in navigator) navigator.vibrate(15);
    loadMobileTasks();
  } catch (e) {}
}

async function cycleMobileGtStatus(taskId, current) {
  const idx = _MOBILE_STATUS_CYCLE.indexOf(current || 'to_do');
  const next = _MOBILE_STATUS_CYCLE[(idx + 1) % _MOBILE_STATUS_CYCLE.length];
  try {
    await apiPut(`/api/global-tasks/${taskId}`, { status: next });
    if ('vibrate' in navigator) navigator.vibrate(15);
    loadMobileTasks();
  } catch (e) {}
}

// 3.11 Project CRUD
async function deleteMobileProject() {
  if (!currentProject) return;
  if (!confirm(`Șterge proiectul "${currentProject.nume}"? Toate datele asociate vor fi pierdute.`)) return;
  await apiDelete(`/api/proiecte/${currentProject.id}`);
  currentProject = null;
  showTab('projects');
}

function editMobileProject() {
  if (!currentProject) return;
  openProjectFormModal(currentProject);
}

function openProjectFormModal(project = null) {
  const modal = document.getElementById('note-modal');
  const content = modal.querySelector('.modal-content');
  modal._originalContent = content.innerHTML;

  const isEdit = !!project;
  const p = project || {};

  content.innerHTML = `
    <div class="modal-header">
      <span class="modal-title">${isEdit ? 'Editează proiect' : 'Proiect nou'}</span>
      <button class="modal-close" onclick="restoreAndCloseModal()">×</button>
    </div>
    <div style="max-height:60vh;overflow-y:auto;">
      <input id="pf-nume" placeholder="Nume proiect *" value="${escapeHtml(p.nume || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="pf-client" placeholder="Client" value="${escapeHtml(p.client || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <select id="pf-tip" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
        <option value="PIF" ${p.tip==='PIF'?'selected':''}>PIF</option>
        <option value="Service" ${p.tip==='Service'?'selected':''}>Service</option>
      </select>
      <select id="pf-producator" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
        <option value="ABB" ${p.producator==='ABB'?'selected':''}>ABB</option>
        <option value="Siemens" ${p.producator==='Siemens'?'selected':''}>Siemens</option>
        <option value="Danfoss" ${p.producator==='Danfoss'?'selected':''}>Danfoss</option>
        <option value="Lenze" ${p.producator==='Lenze'?'selected':''}>Lenze</option>
        <option value="Altul" ${p.producator==='Altul'||!p.producator?'selected':''}>Altul</option>
      </select>
      <input id="pf-echipament" placeholder="Echipament principal" value="${escapeHtml(p.echipament_principal || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="pf-locatie" placeholder="Locație" value="${escapeHtml(p.locatie || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <select id="pf-status" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
        <option value="in_lucru" ${p.status==='in_lucru'||!p.status?'selected':''}>În Lucru</option>
        <option value="in_asteptare" ${p.status==='in_asteptare'?'selected':''}>În Așteptare</option>
        <option value="finalizat" ${p.status==='finalizat'?'selected':''}>Finalizat</option>
      </select>
      <input id="pf-deadline" type="date" value="${p.deadline || ''}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="pf-nr-comanda" placeholder="Nr. comandă" value="${escapeHtml(p.nr_comanda || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="pf-nr-contract" placeholder="Nr. contract" value="${escapeHtml(p.nr_contract || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="pf-pm" placeholder="Project Manager" value="${escapeHtml(p.pm || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
    </div>
    <button onclick="saveProjectFromModal('${isEdit ? p.id : ''}')" class="modal-btn">${isEdit ? 'Salvează' : 'Creează'}</button>
  `;

  modal.classList.add('active');
}

function restoreAndCloseModal() {
  const modal = document.getElementById('note-modal');
  if (modal._originalContent) {
    modal.querySelector('.modal-content').innerHTML = modal._originalContent;
  }
  modal.classList.remove('active');
}

async function saveProjectFromModal(existingId) {
  const data = {
    nume: document.getElementById('pf-nume').value.trim(),
    client: document.getElementById('pf-client').value.trim(),
    tip: document.getElementById('pf-tip').value,
    producator: document.getElementById('pf-producator').value,
    echipament_principal: document.getElementById('pf-echipament').value.trim(),
    locatie: document.getElementById('pf-locatie').value.trim(),
    status: document.getElementById('pf-status').value,
    deadline: document.getElementById('pf-deadline').value,
    nr_comanda: document.getElementById('pf-nr-comanda').value.trim(),
    nr_contract: document.getElementById('pf-nr-contract').value.trim(),
    pm: document.getElementById('pf-pm').value.trim(),
  };

  if (!data.nume) { alert('Numele proiectului e obligatoriu'); return; }

  if (existingId) {
    await apiPut(`/api/proiecte/${existingId}`, data);
    restoreAndCloseModal();
    showProjectDetail(existingId);
  } else {
    const result = await apiPost('/api/proiecte', data);
    restoreAndCloseModal();
    if (result && result.id) showProjectDetail(result.id);
    else showTab('projects');
  }
}

async function exportMobileProjectPDF() {
  if (!currentProject) return;
  window.open(`/api/export/pdf?project_id=${currentProject.id}`, '_blank');
}

function showApp() {
  removeBoot();
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display = 'flex';
  document.getElementById('hermes-fab')?.classList.add('ready');
  showTab('home');

  // Background params sync (non-blocking)
  (async () => {
    const lastSync = parseInt(localStorage.getItem('params_last_sync') || '0');
    const hoursSinceSync = (Date.now() - lastSync) / (1000 * 60 * 60);
    const storedVersion = parseInt(localStorage.getItem('params_db_version') || '0');
    if (hoursSinceSync > 24 || !localStorage.getItem('params_count') || storedVersion !== DB_VERSION) {
      console.log('[Init] Sync needed (' + hoursSinceSync.toFixed(1) + 'h, DBv' + storedVersion + '→v' + DB_VERSION + ')');
      await syncParamsToLocal();
    }
  })();
}

// ============ Mobile Tasks (FAZA 4 - Complete CRUD + filters) ============

let mobileTaskFilter = 'all';

async function loadMobileTasks() {
  const listEl = document.getElementById('mobile-tasks-list');
  listEl.innerHTML = '<div class="loading">Se încarcă...</div>';
  try {
    const url = mobileTaskFilter === 'archive'
      ? '/api/global-tasks?arhiva=true'
      : '/api/global-tasks';
    const tasks = await apiGet(url);
    if (!tasks) return;

    let filtered = tasks;
    if (mobileTaskFilter !== 'all' && mobileTaskFilter !== 'archive') {
      filtered = tasks.filter(t => t.prioritate === mobileTaskFilter);
    }

    const priorityOrder = { 'Urgent': 0, 'Normal': 1, 'Minor': 2 };
    filtered.sort((a, b) => (priorityOrder[a.prioritate] ?? 1) - (priorityOrder[b.prioritate] ?? 1));

    if (filtered.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="check-square"></i></div>Niciun task</div>';
      return;
    }

    listEl.innerHTML = filtered.map(t => {
      const prio = t.prioritate || 'Normal';
      const prioClass = prio.toLowerCase();
      const statusClass = t.status || 'to_do';
      const statusLabel = ({ to_do: 'To Do', in_lucru: 'În Lucru', done: 'Finalizat' })[statusClass] || statusClass;
      return `
      <div class="mobile-task-row">
        <input type="checkbox" ${t.status === 'done' ? 'checked' : ''}
          onchange="toggleMobileTask('${t.id}', this.checked)" class="mobile-task-check">
        <div class="mobile-task-body" onclick="editMobileTask('${t.id}')">
          <div class="mobile-task-title ${t.status === 'done' ? 'done' : ''}">${escapeHtml(t.titlu)}</div>
          ${(t.categorie || t.data_scadenta) ? `<div class="mobile-task-meta">
            ${t.categorie ? escapeHtml(t.categorie) : ''}${t.data_scadenta ? ' · <i data-lucide="calendar" style="width:11px;height:11px;vertical-align:-2px;"></i> ' + t.data_scadenta : ''}
          </div>` : ''}
        </div>
        <span class="todo-priority cyclable ${prioClass}" onclick="event.stopPropagation(); cycleMobileGtPriority('${t.id}', '${prio}')">${prio}</span>
        <span class="todo-status cyclable ${statusClass}" onclick="event.stopPropagation(); cycleMobileGtStatus('${t.id}', '${statusClass}')">${statusLabel}</span>
        <button onclick="event.stopPropagation(); deleteMobileGlobalTask('${t.id}')" class="mobile-task-del" aria-label="Șterge"><i data-lucide="trash-2"></i></button>
      </div>`;
    }).join('');
  } catch (e) {
    listEl.innerHTML = '<div class="empty-state">Eroare la încărcarea taskurilor</div>';
  }
}

function filterMobileTasks(filter) {
  mobileTaskFilter = filter;
  document.querySelectorAll('.gt-filter').forEach(b => {
    b.classList.toggle('active', b.dataset.filter === filter);
  });
  loadMobileTasks();
}

async function quickAddMobileTask() {
  const input = document.getElementById('quick-task-mobile');
  const titlu = input.value.trim();
  if (!titlu) return;
  await apiPost('/api/global-tasks', { titlu, prioritate: 'Normal', status: 'to_do' });
  input.value = '';
  if ('vibrate' in navigator) navigator.vibrate(30);
  loadMobileTasks();
}

async function deleteMobileGlobalTask(taskId) {
  if (!confirm('Șterge taskul?')) return;
  await apiDelete(`/api/global-tasks/${taskId}`);
  loadMobileTasks();
}

function editMobileTask(taskId) {
  apiGet(`/api/global-tasks/${taskId}`).then(task => {
    if (!task) return;
    const modal = document.getElementById('note-modal');
    const content = modal.querySelector('.modal-content');
    modal._originalContent = content.innerHTML;

    content.innerHTML = `
      <div class="modal-header">
        <span class="modal-title">Editează task</span>
        <button class="modal-close" onclick="restoreAndCloseModal()">×</button>
      </div>
      <input id="et-titlu" value="${escapeHtml(task.titlu || '')}" placeholder="Titlu"
        style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <textarea id="et-descriere" placeholder="Descriere (opțional)"
        style="width:100%;min-height:60px;padding:10px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);resize:vertical;font-family:inherit;margin-bottom:8px;">${escapeHtml(task.descriere || '')}</textarea>
      <select id="et-prioritate" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
        <option value="Urgent" ${task.prioritate==='Urgent'?'selected':''}>Urgent</option>
        <option value="Normal" ${task.prioritate==='Normal'?'selected':''}>Normal</option>
        <option value="Minor" ${task.prioritate==='Minor'?'selected':''}>Minor</option>
      </select>
      <input id="et-categorie" value="${escapeHtml(task.categorie || '')}" placeholder="Categorie"
        style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="et-scadenta" type="date" value="${task.data_scadenta || ''}"
        style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <button onclick="saveMobileTaskEdit('${task.id}')" class="modal-btn">Salvează</button>
    `;

    modal.classList.add('active');
  });
}

async function saveMobileTaskEdit(taskId) {
  await apiPut(`/api/global-tasks/${taskId}`, {
    titlu: document.getElementById('et-titlu').value.trim(),
    descriere: document.getElementById('et-descriere').value.trim(),
    prioritate: document.getElementById('et-prioritate').value,
    categorie: document.getElementById('et-categorie').value.trim(),
    data_scadenta: document.getElementById('et-scadenta').value,
  });
  restoreAndCloseModal();
  loadMobileTasks();
}

async function toggleMobileTask(taskId, checked) {
  try {
    await apiPut(`/api/global-tasks/${taskId}`, { status: checked ? 'done' : 'to_do', data_finalizare: checked ? new Date().toISOString() : '' });
    loadMobileTasks();
  } catch (e) { console.error('Toggle task error:', e); }
}

// ============ Manuals ============

async function loadManuals() {
  const listEl = document.getElementById('manuals-list');
  listEl.innerHTML = '<div class="loading">Se încarcă...</div>';
  try {
    const data = await apiGet('/api/manuals');
    if (!data || !data.manuals || data.manuals.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="book-open"></i></div>Niciun manual disponibil</div>';
      return;
    }
    listEl.innerHTML = data.manuals.map(m => `
      <div class="note-item" style="cursor:pointer;" onclick="window.open('${m.url}', '_blank')">
        <div style="margin-right:12px;color:var(--accent);display:inline-flex;align-items:center;"><i data-lucide="file-text"></i></div>
        <div style="flex:1;">
          <div style="font-family:'Courier New',monospace; font-size:14px; font-weight:600;">${escapeHtml(m.name)}</div>
          <div style="font-size:11px; color:var(--text-secondary); margin-top:2px;">${m.size_kb} KB</div>
        </div>
        <span style="color:var(--accent); font-size:18px;">↗</span>
      </div>
    `).join('');
  } catch (e) {
    console.error('Load manuals error:', e);
    listEl.innerHTML = '<div class="empty-state">Eroare la încărcarea manualelor</div>';
  }
}

// ============ FAZA 5: Clients CRUD ============

async function loadMobileClients() {
  const listEl = document.getElementById('clients-list');
  listEl.innerHTML = '<div class="loading">Se încarcă...</div>';
  try {
    const search = document.getElementById('client-search')?.value || '';
    const url = search ? `/api/clienti?search=${encodeURIComponent(search)}` : '/api/clienti';
    const clients = await apiGet(url);
    if (!clients || clients.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="users"></i></div>Niciun client</div>';
      return;
    }
    listEl.innerHTML = clients.map(c => `
      <div class="note-item" style="padding:12px;" onclick="editMobileClient('${c.id}')">
        <div style="font-size:14px;font-weight:600;">${escapeHtml(c.nume)}</div>
        <div style="font-size:12px;color:var(--text-secondary);margin-top:2px;">
          ${c.telefon ? '📞 ' + escapeHtml(c.telefon) : ''}
          ${c.email ? ' · ✉️ ' + escapeHtml(c.email) : ''}
        </div>
        ${c.contact_principal ? `<div style="font-size:11px;color:var(--text-secondary);">Contact: ${escapeHtml(c.contact_principal)}</div>` : ''}
      </div>
    `).join('');
  } catch (e) { listEl.innerHTML = '<div class="empty-state">Eroare</div>'; }
}

function openClientModal(clientId = null) {
  const modal = document.getElementById('note-modal');
  const content = modal.querySelector('.modal-content');
  modal._originalContent = content.innerHTML;

  const load = clientId ? apiGet(`/api/clienti/${clientId}`) : Promise.resolve({});
  load.then(c => {
    c = c || {};
    content.innerHTML = `
      <div class="modal-header">
        <span class="modal-title">${clientId ? 'Editează client' : 'Client nou'}</span>
        <button class="modal-close" onclick="restoreAndCloseModal()">×</button>
      </div>
      <input id="cl-nume" placeholder="Nume *" value="${escapeHtml(c.nume || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="cl-telefon" placeholder="Telefon" value="${escapeHtml(c.telefon || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="cl-email" placeholder="Email" value="${escapeHtml(c.email || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="cl-contact" placeholder="Contact principal" value="${escapeHtml(c.contact_principal || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <input id="cl-adresa" placeholder="Adresă" value="${escapeHtml(c.adresa || '')}" style="width:100%;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);margin-bottom:8px;">
      <textarea id="cl-note" placeholder="Note" style="width:100%;min-height:60px;padding:10px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);resize:vertical;font-family:inherit;margin-bottom:8px;">${escapeHtml(c.note || '')}</textarea>
      ${clientId ? `<button onclick="deleteMobileClient('${clientId}')" style="width:100%;padding:12px;background:var(--error);color:white;border:none;border-radius:8px;margin-bottom:8px;font-size:14px;cursor:pointer;">Șterge client</button>` : ''}
      <button onclick="saveMobileClient('${clientId || ''}')" class="modal-btn">Salvează</button>
    `;
    modal.classList.add('active');
  });
}

function editMobileClient(clientId) { openClientModal(clientId); }

async function saveMobileClient(existingId) {
  const data = {
    nume: document.getElementById('cl-nume').value.trim(),
    telefon: document.getElementById('cl-telefon').value.trim(),
    email: document.getElementById('cl-email').value.trim(),
    contact_principal: document.getElementById('cl-contact').value.trim(),
    adresa: document.getElementById('cl-adresa').value.trim(),
    note: document.getElementById('cl-note').value.trim(),
  };
  if (!data.nume) { alert('Numele e obligatoriu'); return; }
  if (existingId) await apiPut(`/api/clienti/${existingId}`, data);
  else await apiPost('/api/clienti', data);
  restoreAndCloseModal();
  loadMobileClients();
}

async function deleteMobileClient(clientId) {
  if (!confirm('Șterge clientul?')) return;
  await apiDelete(`/api/clienti/${clientId}`);
  restoreAndCloseModal();
  loadMobileClients();
}

// ============ FAZA 6: Statistics + Export ============

async function loadMobileStats() {
  const el = document.getElementById('stats-content');
  el.innerHTML = '<div class="loading">Se încarcă...</div>';
  try {
    const data = await apiGet('/api/stats/extended');
    if (!data) return;

    el.innerHTML = `
      <div style="font-size:16px;font-weight:600;margin-bottom:16px; display:flex; align-items:center; gap:6px;"><i data-lucide="bar-chart-3" style="color:var(--accent);"></i> Statistici</div>

      <div style="font-size:14px;font-weight:600;margin:12px 0 8px;">Proiecte după status</div>
      ${(data.by_status || []).map(s => `
        <div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--surface);border-radius:6px;margin-bottom:4px;">
          <span>${getStatusLabel(s.status)}</span>
          <span style="font-weight:600;color:var(--accent);">${s.count}</span>
        </div>
      `).join('')}

      <div style="font-size:14px;font-weight:600;margin:16px 0 8px;">Proiecte după producător</div>
      ${(data.by_manufacturer || []).map(m => `
        <div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--surface);border-radius:6px;margin-bottom:4px;">
          <span>${escapeHtml(m.producator || 'Altul')}</span>
          <span style="font-weight:600;color:var(--accent);">${m.count}</span>
        </div>
      `).join('')}

      <div style="font-size:14px;font-weight:600;margin:16px 0 8px;">Ore totale facturabile</div>
      <div class="detail-section" style="text-align:center;">
        <div style="font-size:28px;font-weight:600;color:var(--accent);">${data.total_billable_hours || 0}</div>
        <div class="detail-label">ore</div>
      </div>

      ${(data.hours_per_project || []).length > 0 ? `
        <div style="font-size:14px;font-weight:600;margin:16px 0 8px;">Top proiecte (ore)</div>
        ${data.hours_per_project.slice(0, 10).map(p => `
          <div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--surface);border-radius:6px;margin-bottom:4px;">
            <span style="font-size:13px;">${escapeHtml(p.nume)}</span>
            <span style="font-weight:600;color:var(--accent);">${p.hours}h</span>
          </div>
        `).join('')}
      ` : ''}
    `;
  } catch (e) { el.innerHTML = '<div class="empty-state">Eroare la încărcarea statisticilor</div>'; }
}

async function mobileBackupJSON() {
  try {
    const data = await apiGet('/api/backup');
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pif_backup_${new Date().toISOString().substring(0,10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) { console.error('Backup error:', e); }
}

// ============ Hermes Assistant (mobile) ============

let _hermesMessages = [];
let _hermesBusy = false;
// Write-tools: after the assistant uses one, refresh whatever tab is open.
const _HERMES_WRITE_TOOLS = ['create_proiect', 'create_task', 'add_checklist_item', 'add_jurnal', 'update_task_status'];

function openHermes() {
  const panel = document.getElementById('hermes-panel');
  if (!panel) return;
  panel.classList.add('active');
  renderHermesMessages();
  setTimeout(() => document.getElementById('hermes-input')?.focus(), 150);
}

function closeHermes() {
  const panel = document.getElementById('hermes-panel');
  if (panel) panel.classList.remove('active');
}

function clearHermesChat() {
  _hermesMessages = [];
  renderHermesMessages();
}

// Minimal, safe inline markdown: bold, italic, inline code, line breaks.
// Everything is escaped first — no raw HTML is ever injected.
function hermesRenderText(src) {
  let s = escapeHtml(String(src || ''));
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  s = s.replace(/\n/g, '<br>');
  return s;
}

function renderHermesMessages() {
  const box = document.getElementById('hermes-messages');
  if (!box) return;
  if (!_hermesMessages.length) {
    box.innerHTML = '<div class="hermes-welcome">'
      + '<i data-lucide="sparkles"></i>'
      + '<p>Salut, Ion. Sunt Hermes.<br>Pot cauta parametri, notite si proiecte — si pot crea proiecte, taskuri, checklist-uri si intrari de jurnal. Spune-mi ce ai nevoie.</p>'
      + '</div>';
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
    return;
  }
  box.innerHTML = _hermesMessages.map(m => {
    if (m.role === 'user') return '<div class="hermes-msg user">' + escapeHtml(m.content) + '</div>';
    if (m.role === 'typing') return '<div class="hermes-typing">Hermes scrie...</div>';
    if (m.role === 'tools') return '<div class="hermes-tools"><i data-lucide="settings-2"></i> ' + escapeHtml(m.content) + '</div>';
    if (m.role === 'error') return '<div class="hermes-msg error">' + hermesRenderText(m.content) + '</div>';
    return '<div class="hermes-msg bot">' + hermesRenderText(m.content) + '</div>';
  }).join('');
  box.scrollTop = box.scrollHeight;
  if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

async function sendHermesMessage() {
  if (_hermesBusy) return;
  const input = document.getElementById('hermes-input');
  if (!input) return;
  const text = (input.value || '').trim();
  if (!text) return;
  input.value = '';
  input.style.height = 'auto';

  _hermesMessages.push({ role: 'user', content: text });
  _hermesMessages.push({ role: 'typing', content: '' });
  renderHermesMessages();
  _hermesBusy = true;
  const sendBtn = document.getElementById('hermes-send');
  if (sendBtn) sendBtn.disabled = true;

  // Backend expects { messages: [{role, content}] } with plain-text turns.
  const payload = _hermesMessages
    .filter(m => m.role === 'user' || m.role === 'assistant')
    .map(m => ({ role: m.role, content: m.content }));

  try {
    const res = await fetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ messages: payload })
    });
    let data = {};
    try { data = await res.json(); } catch (e) { data = {}; }
    _hermesMessages = _hermesMessages.filter(m => m.role !== 'typing');
    if (data && data.error) {
      _hermesMessages.push({ role: 'error', content: data.error });
    } else if (!res.ok) {
      _hermesMessages.push({ role: 'error', content: 'Eroare server (' + res.status + ').' });
    } else {
      if (Array.isArray(data.tool_log) && data.tool_log.length) {
        _hermesMessages.push({ role: 'tools', content: 'A folosit: ' + data.tool_log.map(t => t.tool).join(', ') });
      }
      _hermesMessages.push({ role: 'assistant', content: data.reply || '(raspuns gol)' });
      if (Array.isArray(data.tool_log) && data.tool_log.some(t => _HERMES_WRITE_TOOLS.includes(t.tool))) {
        _hermesRefreshContext();
      }
    }
  } catch (e) {
    _hermesMessages = _hermesMessages.filter(m => m.role !== 'typing');
    _hermesMessages.push({ role: 'error', content: 'Eroare de retea. Verifica conexiunea.' });
  }
  _hermesBusy = false;
  if (sendBtn) sendBtn.disabled = false;
  renderHermesMessages();
}

// After the assistant changes data, refresh whatever tab the user is on.
function _hermesRefreshContext() {
  try {
    if (currentProject && typeof showProjectDetail === 'function') {
      showProjectDetail(currentProject.id);
    } else if (currentTab === 'projects' && typeof loadProjects === 'function') {
      loadProjects();
    } else if (currentTab === 'tasks' && typeof loadMobileTasks === 'function') {
      loadMobileTasks();
    } else if (currentTab === 'home' && typeof loadDashboardHome === 'function') {
      loadDashboardHome();
    }
  } catch (e) { /* refresh is best-effort */ }
}

function initHermes() {
  // Auto-grow the input textarea.
  const ta = document.getElementById('hermes-input');
  if (ta) {
    ta.addEventListener('input', () => {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    });
  }
}

// ============ Utility ============

// escapeHtml, formatFileSize, debounce -> moved to shared core.js

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ro-RO', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return dateStr;
  }
}

// ============ Event Listeners ============

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Auth check FIRST (cel mai rapid path)
  const hasSession = isAuthenticated();
  const hasRemember = localStorage.getItem('remember_me') === 'true' && localStorage.getItem('pin_hash');
  
  if (hasSession) {
    // Session activă — arată app IMEDIAT, fără await-uri
    removeBoot();
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app').style.display = 'flex';
  }
  
  // 2. Init DB (non-blocking dacă session e deja activă)
  await openDB();
  
  // 3. Register SW (nu blochează)
  registerServiceWorker();
  
  // 4. Online status (nu blochează)
  updateOnlineStatus();
  
  // 5. Debug panel: 5 tap-uri rapide pe header → info
  let _debugTaps = 0;
  let _debugTimer = null;
  document.getElementById('header')?.addEventListener('click', () => {
    _debugTaps++;
    clearTimeout(_debugTimer);
    _debugTimer = setTimeout(() => { _debugTaps = 0; }, 1000);
    if (_debugTaps >= 5) {
      _debugTaps = 0;
      const info = [
        'SW: ' + (navigator.serviceWorker.controller ? 'active' : 'none'),
        'Online: ' + _isOnline,
        'navigator.onLine: ' + navigator.onLine,
        'Last sync: ' + (localStorage.getItem('params_last_sync') || 'never'),
        'Params: ' + (localStorage.getItem('params_count') || '0'),
        'SW forced: ' + (localStorage.getItem('sw_force_v5') || 'no'),
        'Origin: ' + window.location.origin,
        'IDB version: 5'
      ];
      alert(info.join('\n'));
    }
  });
  
  // Theme toggle (mobile) — Lucide moon/sun icons.
  const themeToggleMobile = document.getElementById('theme-toggle-mobile');
  if (themeToggleMobile) {
    const setThemeIcon = (t) => {
      themeToggleMobile.innerHTML = '<i data-lucide="' + (t === 'light' ? 'sun' : 'moon') + '"></i>';
      if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
    };
    const currentTheme = localStorage.getItem('theme') || 'dark';
    setThemeIcon(currentTheme);
    themeToggleMobile.addEventListener('click', () => {
      const html = document.documentElement;
      const current = html.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      setThemeIcon(next);
    });
  }
  
  // 6. Final auth resolution
  if (hasSession) {
    // Deja afișat app-ul — acum doar încarcă datele
    showApp();
  } else if (hasRemember) {
    // Auto-login cu hash — abia ACUM facem fetch
    try {
      const resp = await fetch('/login-hash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin_hash: localStorage.getItem('pin_hash') })
      });
      if (resp.ok) {
        sessionStorage.setItem('pif_auth', '1');
        showApp();
      } else {
        showLogin();
      }
    } catch (e) {
      showLogin();
    }
  } else {
    showLogin();
  }
  
  // Login button
  document.getElementById('login-btn').addEventListener('click', async () => {
    const pin = document.getElementById('pin-input').value;
    const rememberMe = document.getElementById('remember-me')?.checked || false;
    const success = await login(pin, rememberMe);
    if (success) {
      if ('vibrate' in navigator) navigator.vibrate(30);
      document.getElementById('login-error').style.display = 'none';
      showApp();
    } else {
      document.getElementById('login-error').style.display = 'block';
    }
  });
  
  // PIN input enter key
  document.getElementById('pin-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      document.getElementById('login-btn').click();
    }
  });
  
  // Bottom navigation
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      showTab(tab.dataset.tab);
    });
  });
  
  // Back button
  document.getElementById('back-to-projects').addEventListener('click', () => {
    currentProject = null;
    showTab('projects');
  });
  
  // Note modal
  document.getElementById('close-note-modal').addEventListener('click', closeNoteModal);
  document.getElementById('save-note').addEventListener('click', saveNote);

  // Close modal on backdrop click
  document.getElementById('note-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
      closeNoteModal();
    }
  });

  // Client search debounce
  document.getElementById('client-search')?.addEventListener('input', debounce(() => loadMobileClients(), 300));

  // Hermes assistant
  initHermes();

  // Param modal
  document.getElementById('close-param-modal').addEventListener('click', () => {
    document.getElementById('param-modal-mobile').classList.remove('active');
  });
  document.getElementById('param-modal-mobile').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
      e.currentTarget.classList.remove('active');
    }
  });

  // Force Refresh button
  document.getElementById('force-refresh')?.addEventListener('click', async () => {
    if (!confirm('Reîncarcă aplicația? (cache-ul va fi șters)')) return;

    // 1. Trimite mesaj la SW să-și golească cache-ul de API
    if (navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage('clearApiCache');
    }

    // 2. Unregister SW complet
    const registrations = await navigator.serviceWorker.getRegistrations();
    for (const reg of registrations) {
      await reg.unregister();
    }

    // 3. Șterge toate cache-urile din CacheStorage
    const keys = await caches.keys();
    for (const key of keys) {
      await caches.delete(key);
    }

    // 4. Reload (argumentul boolean e ignorat de browsere moderne)
    window.location.reload();
  });
});

// ============ OBSIDIAN NOTES (mobile) ============
// Drill-down browser for the read-only Obsidian vault. Mirrors the desktop
// "Notițe" tab but as a single-column flow: tree/search -> note. Backend:
//   GET /api/obsidian/notes   -> { notes: [{path,title,folder,mtime,size}], error? }
//   GET /api/obsidian/note?path=<rel> -> { path, title, content } | { error }
//   GET /api/obsidian/search?q=<q>    -> { results: [{path,title,folder,snippet,hits,score}], query }

let _obsNotes = [];                 // flat list from /notes (cached for the session)
let _obsLoaded = false;             // tree fetched at least once this session
let _obsSearchTimer = null;
let _obsCollapsed = (function () {
  try { return new Set(JSON.parse(localStorage.getItem('pif:m:obs:collapsed') || '[]')); }
  catch (e) { return new Set(); }
})();
function _obsSaveCollapsed() {
  try { localStorage.setItem('pif:m:obs:collapsed', JSON.stringify([..._obsCollapsed])); } catch (e) {}
}

// Attribute-safe escaping for values placed inside data-* attributes.
function _obsAttr(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// --- Lightweight Markdown renderer (ported from desktop app.js) ---
// Obsidian callout type -> [css class, default Romanian title].
function _obsCalloutMeta(type) {
  const map = {
    note: ['note', 'Notă'], info: ['note', 'Info'], abstract: ['note', 'Rezumat'],
    summary: ['note', 'Rezumat'], tldr: ['note', 'TL;DR'], todo: ['note', 'De făcut'],
    tip: ['tip', 'Tip'], hint: ['tip', 'Tip'], important: ['tip', 'Important'],
    success: ['success', 'Succes'], check: ['success', 'OK'], done: ['success', 'Gata'],
    question: ['question', 'Întrebare'], help: ['question', 'Ajutor'], faq: ['question', 'FAQ'],
    warning: ['warning', 'Atenție'], caution: ['warning', 'Atenție'], attention: ['warning', 'Atenție'],
    failure: ['danger', 'Eșec'], fail: ['danger', 'Eșec'], missing: ['danger', 'Lipsă'],
    danger: ['danger', 'Pericol'], error: ['danger', 'Eroare'], bug: ['danger', 'Bug'],
    example: ['example', 'Exemplu'], quote: ['quote', 'Citat'], cite: ['quote', 'Citat'],
  };
  const t = (type || '').toLowerCase();
  return map[t] || ['note', type ? (type.charAt(0).toUpperCase() + type.slice(1)) : 'Notă'];
}

// Inline-level Markdown. Input is escaped FIRST so note content can never
// inject HTML (no XSS from the vault).
function _obsMdInline(text) {
  let s = escapeHtml(text);
  // Protect inline code spans from further substitution.
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (m, c) => { codes.push(c); return ' IC' + (codes.length - 1) + ' '; });
  // Images, then links. URLs come from already-escaped text.
  s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g, '<img alt="$1" src="$2">');
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)[^)]*\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Obsidian wikilinks [[Note]] / [[Note|alias]] (also embeds ![[...]]).
  s = s.replace(/!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, target, alias) =>
    `<span class="md-wikilink" data-wikilink="${_obsAttr(target.trim())}">${(alias || target).trim()}</span>`);
  // Bold, italic, strikethrough, ==highlight==.
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  s = s.replace(/~~([^~]+)~~/g, '<del>$1</del>');
  s = s.replace(/==([^=]+)==/g, '<mark>$1</mark>');
  // Tags #tag.
  s = s.replace(/(^|\s)#([a-zA-Z][\w/\-]*)/g, '$1<span class="md-tag">#$2</span>');
  // Restore inline code (re-escaped — codes[] holds raw text).
  s = s.replace(/ IC(\d+) /g, (m, i) => '<code>' + escapeHtml(codes[+i]) + '</code>');
  return s;
}

function renderObsMarkdown(src) {
  let text = String(src || '').replace(/\r\n/g, '\n');
  // Strip leading YAML frontmatter and Obsidian %% comments %%.
  text = text.replace(/^---\n[\s\S]*?\n---\n?/, '');
  text = text.replace(/%%[\s\S]*?%%/g, '');
  const lines = text.split('\n');
  const out = [];
  let i = 0, inCode = false, codeBuf = [];
  const listStack = [];
  const closeLists = () => { while (listStack.length) out.push('</' + listStack.pop() + '>'); };

  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^```(.*)$/);
    if (fence) {
      if (inCode) { out.push('<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>'); inCode = false; codeBuf = []; }
      else { closeLists(); inCode = true; }
      i++; continue;
    }
    if (inCode) { codeBuf.push(line); i++; continue; }
    if (line.trim() === '') { closeLists(); i++; continue; }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { closeLists(); const lvl = Math.min(h[1].length, 3); out.push(`<h${lvl}>${_obsMdInline(h[2])}</h${lvl}>`); i++; continue; }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) { closeLists(); out.push('<hr>'); i++; continue; }

    if (/^>\s?/.test(line)) {
      closeLists();
      const quote = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) { quote.push(lines[i].replace(/^>\s?/, '')); i++; }
      // Obsidian callout: first line is [!type] optional-title.
      const cm = quote[0] && quote[0].match(/^\[!(\w+)\][+-]?\s*(.*)$/);
      if (cm) {
        const meta = _obsCalloutMeta(cm[1]);
        const ctitle = cm[2].trim() || meta[1];
        const body = quote.slice(1).join('\n').trim();
        out.push(`<div class="md-callout md-callout-${meta[0]}">`
          + `<div class="md-callout-title">${_obsMdInline(ctitle)}</div>`
          + (body ? `<div class="md-callout-body">${renderObsMarkdown(body)}</div>` : '')
          + '</div>');
      } else {
        out.push('<blockquote>' + renderObsMarkdown(quote.join('\n')) + '</blockquote>');
      }
      continue;
    }

    // Table: header row with pipes + separator row of dashes.
    if (line.includes('|') && i + 1 < lines.length &&
        /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('-')) {
      closeLists();
      const cells = r => r.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim());
      const head = cells(line);
      i += 2;
      let tbl = '<table><thead><tr>' + head.map(c => `<th>${_obsMdInline(c)}</th>`).join('') + '</tr></thead><tbody>';
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        tbl += '<tr>' + cells(lines[i]).map(c => `<td>${_obsMdInline(c)}</td>`).join('') + '</tr>';
        i++;
      }
      out.push(tbl + '</tbody></table>');
      continue;
    }

    const ul = line.match(/^(\s*)[-*+]\s+(.*)$/);
    const ol = line.match(/^(\s*)\d+\.\s+(.*)$/);
    if (ul || ol) {
      const type = ul ? 'ul' : 'ol';
      if (listStack[listStack.length - 1] !== type) { closeLists(); out.push('<' + type + '>'); listStack.push(type); }
      const content = ul ? ul[2] : ol[2];
      const task = content.match(/^\[([ xX])\]\s+(.*)$/);
      if (task) out.push(`<li><input type="checkbox" disabled ${task[1] !== ' ' ? 'checked' : ''}> ${_obsMdInline(task[2])}</li>`);
      else out.push('<li>' + _obsMdInline(content) + '</li>');
      i++; continue;
    }

    closeLists();
    const para = [line]; i++;
    while (i < lines.length && lines[i].trim() !== '' &&
           !/^(#{1,6}\s|```|>\s?|\s*[-*+]\s|\s*\d+\.\s)/.test(lines[i]) &&
           !/^(-{3,}|\*{3,}|_{3,})$/.test(lines[i].trim())) {
      para.push(lines[i]); i++;
    }
    out.push('<p>' + _obsMdInline(para.join('\n')).replace(/\n/g, '<br>') + '</p>');
  }
  closeLists();
  if (inCode) out.push('<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>');
  return out.join('\n');
}

// --- Data ---
async function _obsApi(path) {
  // apiGet handles 401/redirects; returns null when not authenticated.
  return apiGet('/api/obsidian' + path);
}

async function loadObsidianMobile() {
  // Always reset to the tree view when entering the tab.
  obsBackToTree();
  if (_obsLoaded) { renderObsTree(); return; }  // session cache — instant re-open
  const listEl = document.getElementById('obs-list');
  const metaEl = document.getElementById('obs-meta');
  if (!listEl) return;
  listEl.innerHTML = '<div class="loading">Se încarcă...</div>';
  if (metaEl) metaEl.textContent = '';
  try {
    const data = await _obsApi('/notes');
    if (!data) { listEl.innerHTML = '<div class="obs-empty">Sesiune expirată.</div>'; return; }
    if (data.error) {
      _obsNotes = [];
      listEl.innerHTML = '<div class="obs-empty"><i data-lucide="folder-x"></i>'
        + '<div>Vault Obsidian neconfigurat.<br>Setează-l din varianta desktop → Administrativ.</div></div>';
      if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
      return;
    }
    _obsNotes = data.notes || [];
    _obsLoaded = true;
    renderObsTree();
  } catch (e) {
    console.error('loadObsidianMobile failed:', e);
    listEl.innerHTML = '<div class="obs-empty">Eroare la încărcarea notițelor.</div>';
  }
}

// --- Folder tree ---
function _obsBuildTree(notes) {
  const root = { folders: {}, notes: [] };
  for (const n of notes) {
    const parts = n.path.split('/');
    parts.pop(); // drop the filename
    let node = root;
    for (const p of parts) {
      if (!node.folders[p]) node.folders[p] = { folders: {}, notes: [] };
      node = node.folders[p];
    }
    node.notes.push(n);
  }
  return root;
}
function _obsCountNotes(node) {
  let c = node.notes.length;
  for (const k in node.folders) c += _obsCountNotes(node.folders[k]);
  return c;
}
function _obsRenderNode(node, depth, prefix) {
  let html = '';
  Object.keys(node.folders).sort((a, b) => a.localeCompare(b, 'ro')).forEach(fname => {
    const full = prefix ? prefix + '/' + fname : fname;
    const collapsed = _obsCollapsed.has(full);
    const child = node.folders[fname];
    html += `<div class="obs-folder-row" data-folder="${_obsAttr(full)}" style="padding-left:${4 + depth * 14}px">
      <i data-lucide="chevron-${collapsed ? 'right' : 'down'}" class="obs-chevron"></i>
      <i data-lucide="folder" class="obs-folder-icon"></i>
      <span class="obs-folder-name">${escapeHtml(fname)}</span>
      <span class="obs-folder-count">${_obsCountNotes(child)}</span>
    </div>`;
    if (!collapsed) html += _obsRenderNode(child, depth + 1, full);
  });
  node.notes.slice()
    .sort((a, b) => a.title.toLowerCase().localeCompare(b.title.toLowerCase(), 'ro'))
    .forEach(n => {
      html += `<div class="obs-note-row" data-path="${_obsAttr(n.path)}" style="padding-left:${8 + depth * 14}px">
        <i data-lucide="file-text" class="obs-note-icon"></i>
        <span class="obs-note-name">${escapeHtml(n.title)}</span>
      </div>`;
    });
  return html;
}
function renderObsTree() {
  const listEl = document.getElementById('obs-list');
  const metaEl = document.getElementById('obs-meta');
  if (!listEl) return;
  if (metaEl) metaEl.textContent = _obsNotes.length + ' notițe';
  if (!_obsNotes.length) {
    listEl.innerHTML = '<div class="obs-empty">Nicio notiță.</div>';
    return;
  }
  listEl.innerHTML = _obsRenderNode(_obsBuildTree(_obsNotes), 0, '');
  if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

// --- Search ---
function onObsSearchInput() {
  clearTimeout(_obsSearchTimer);
  _obsSearchTimer = setTimeout(() => {
    const el = document.getElementById('obs-search');
    doObsSearch((el && el.value || '').trim());
  }, 280);
}
function _obsHighlight(snippet, query) {
  let s = escapeHtml(snippet);
  if (query) {
    const q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    try { s = s.replace(new RegExp('(' + q + ')', 'gi'), '<mark>$1</mark>'); } catch (e) {}
  }
  return s;
}
async function doObsSearch(q) {
  const listEl = document.getElementById('obs-list');
  const metaEl = document.getElementById('obs-meta');
  if (!listEl) return;
  if (!q) { renderObsTree(); return; }  // empty box -> back to tree
  try {
    const data = await _obsApi('/search?q=' + encodeURIComponent(q));
    if (!data) return;
    const results = data.results || [];
    if (metaEl) metaEl.textContent = results.length + ' rezultate';
    if (!results.length) {
      listEl.innerHTML = '<div class="obs-empty">Niciun rezultat.</div>';
      return;
    }
    listEl.innerHTML = results.map(n => `
      <div class="obs-result" data-path="${_obsAttr(n.path)}">
        <div class="obs-result-title">${escapeHtml(n.title)}</div>
        ${n.folder ? `<div class="obs-result-folder">${escapeHtml(n.folder)}</div>` : ''}
        ${n.snippet ? `<div class="obs-result-snippet">${_obsHighlight(n.snippet, q)}</div>` : ''}
      </div>`).join('');
  } catch (e) {
    console.error('Obsidian mobile search failed:', e);
    listEl.innerHTML = '<div class="obs-empty">Eroare la căutare.</div>';
  }
}

// --- Single-note view (drill-down) ---
function obsBackToTree() {
  const browse = document.getElementById('obs-browse');
  const note = document.getElementById('obs-note');
  if (browse) browse.style.display = '';
  if (note) note.style.display = 'none';
}
async function openObsNote(path) {
  const browse = document.getElementById('obs-browse');
  const noteEl = document.getElementById('obs-note');
  const titleEl = document.getElementById('obs-note-title');
  const pathEl = document.getElementById('obs-note-path');
  const bodyEl = document.getElementById('obs-note-body');
  if (!noteEl || !bodyEl) return;
  if (browse) browse.style.display = 'none';
  noteEl.style.display = '';
  if (titleEl) titleEl.textContent = '';
  if (pathEl) pathEl.textContent = '';
  bodyEl.innerHTML = '<div class="loading">Se încarcă...</div>';
  window.scrollTo(0, 0);
  try {
    const data = await _obsApi('/note?path=' + encodeURIComponent(path));
    if (!data) { bodyEl.innerHTML = '<div class="obs-empty">Sesiune expirată.</div>'; return; }
    if (data.error) {
      bodyEl.innerHTML = '<div class="obs-empty"><i data-lucide="file-x"></i><div>'
        + escapeHtml(data.error) + '</div></div>';
      if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
      return;
    }
    if (titleEl) titleEl.textContent = data.title || '';
    if (pathEl) pathEl.textContent = data.path || '';
    bodyEl.innerHTML = renderObsMarkdown(data.content);
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
  } catch (e) {
    console.error('openObsNote failed:', e);
    bodyEl.innerHTML = '<div class="obs-empty">Eroare la încărcarea notiței.</div>';
  }
}

// Delegated taps inside the Obsidian tab: folder rows, note rows, wikilinks.
document.addEventListener('click', function (e) {
  const tab = document.getElementById('tab-obsidian');
  if (!tab || !tab.contains(e.target)) return;
  const folderRow = e.target.closest && e.target.closest('.obs-folder-row');
  if (folderRow) {
    const f = folderRow.getAttribute('data-folder');
    if (_obsCollapsed.has(f)) _obsCollapsed.delete(f);
    else _obsCollapsed.add(f);
    _obsSaveCollapsed();
    renderObsTree();
    return;
  }
  const noteRow = e.target.closest && e.target.closest('.obs-note-row, .obs-result');
  if (noteRow) { openObsNote(noteRow.getAttribute('data-path')); return; }
  const wl = e.target.closest && e.target.closest('.md-wikilink');
  if (wl) {
    const target = (wl.getAttribute('data-wikilink') || '').toLowerCase();
    const note = _obsNotes.find(n => n.title.toLowerCase() === target)
      || _obsNotes.find(n => n.path.toLowerCase().endsWith('/' + target + '.md'))
      || _obsNotes.find(n => n.path.toLowerCase() === target + '.md');
    if (note) openObsNote(note.path);
    else alert('Nota „' + (wl.getAttribute('data-wikilink') || '') + '" nu a fost găsită.');
  }
});

// ============ GLOBAL SEARCH (mobile) ============
// Near-full-screen search overlay, mirrors the desktop command palette.
// Backend: GET /api/search?q=<query> -> { results: [...], query, count }
// Each result: { type, id, title, subtitle, snippet, proiect_id?, path?, familie?, cod? }

let _gsResults = [];
let _gsTimer = null;

// type -> { label, icon } for grouped rendering (mirror of desktop _GS_META).
const _GS_META = {
  proiect:     { label: 'Proiecte', icon: 'folder-kanban' },
  observatie:  { label: 'Observații', icon: 'file-text' },
  task:        { label: 'Taskuri', icon: 'check-square' },
  global_task: { label: 'Taskuri zilnice', icon: 'calendar-check' },
  checklist:   { label: 'Checklist', icon: 'list-checks' },
  jurnal:      { label: 'Jurnal', icon: 'notebook-pen' },
  echipament:  { label: 'Echipamente', icon: 'cpu' },
  client:      { label: 'Clienți', icon: 'users' },
  parametru:   { label: 'Parametri', icon: 'sliders-horizontal' },
  obsidian:    { label: 'Notițe', icon: 'book-open' },
};
const _GS_ORDER = ['proiect', 'observatie', 'task', 'global_task', 'checklist',
                   'jurnal', 'echipament', 'client', 'parametru', 'obsidian'];

function openGlobalSearch() {
  const ov = document.getElementById('global-search');
  if (!ov) return;
  ov.classList.add('active');
  const inp = document.getElementById('gs-input');
  if (inp) { inp.value = ''; }
  _gsResults = [];
  renderGlobalSearch();
  setTimeout(() => { if (inp) inp.focus(); }, 60);
}

function closeGlobalSearch() {
  const ov = document.getElementById('global-search');
  if (ov) ov.classList.remove('active');
  clearTimeout(_gsTimer);
}

function onGlobalSearchInput() {
  clearTimeout(_gsTimer);
  _gsTimer = setTimeout(doGlobalSearch, 250);
}

async function doGlobalSearch() {
  const inp = document.getElementById('gs-input');
  const q = ((inp && inp.value) || '').trim();
  if (q.length < 2) { _gsResults = []; renderGlobalSearch(); return; }
  try {
    const data = await apiGet('/api/search?q=' + encodeURIComponent(q));
    if (!data) return;  // apiGet handles 401 / non-JSON
    const raw = data.results || [];
    // Order by group so the on-screen layout is stable.
    _gsResults = [];
    for (const t of _GS_ORDER) for (const r of raw) if (r.type === t) _gsResults.push(r);
    renderGlobalSearch();
  } catch (e) {
    console.error('Global search failed:', e);
    const box = document.getElementById('gs-results');
    if (box) box.innerHTML = '<div class="gs-state"><i data-lucide="wifi-off"></i>'
      + '<div>Căutarea a eșuat. Verifică conexiunea.</div></div>';
    if (window.lucide) try { window.lucide.createIcons(); } catch (e2) {}
  }
}

// Safe term highlighting: escape FIRST, then wrap matches in <mark>.
function _gsHighlight(text, q) {
  let s = escapeHtml(text || '');
  if (q) {
    const esc = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    try { s = s.replace(new RegExp('(' + esc + ')', 'gi'), '<mark>$1</mark>'); } catch (e) {}
  }
  return s;
}

function renderGlobalSearch() {
  const box = document.getElementById('gs-results');
  if (!box) return;
  const inp = document.getElementById('gs-input');
  const q = ((inp && inp.value) || '').trim();
  if (q.length < 2) {
    box.innerHTML = '<div class="gs-state"><i data-lucide="search"></i>'
      + '<div>Scrie cel puțin 2 caractere ca să cauți.</div></div>';
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
    return;
  }
  if (!_gsResults.length) {
    box.innerHTML = '<div class="gs-state"><i data-lucide="search-x"></i>'
      + '<div>Niciun rezultat pentru „' + escapeHtml(q) + '".</div></div>';
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
    return;
  }
  let html = '';
  let lastType = null;
  _gsResults.forEach((r, idx) => {
    if (r.type !== lastType) {
      html += '<div class="gs-group-label">' + escapeHtml((_GS_META[r.type] || {}).label || r.type) + '</div>';
      lastType = r.type;
    }
    const meta = _GS_META[r.type] || { icon: 'circle' };
    html += '<div class="gs-item" data-idx="' + idx + '">'
      + '<div class="gs-item-icon"><i data-lucide="' + meta.icon + '"></i></div>'
      + '<div class="gs-item-body">'
      + '<div class="gs-item-title">' + _gsHighlight(r.title, q) + '</div>'
      + (r.subtitle ? '<div class="gs-item-sub">' + escapeHtml(r.subtitle) + '</div>' : '')
      + (r.snippet ? '<div class="gs-item-snippet">' + _gsHighlight(r.snippet, q) + '</div>' : '')
      + '</div></div>';
  });
  box.innerHTML = html;
  if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

// Small toast — there is no shared toast helper in mobile.js, so build one.
function _gsToast(msg) {
  const toast = document.createElement('div');
  toast.textContent = msg;
  toast.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);'
    + 'background:var(--bg-elev3);border:1px solid var(--accent);color:var(--text);'
    + 'padding:10px 16px;border-radius:8px;z-index:300;font-size:13px;max-width:80%;text-align:center;';
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2500);
}

// Open the mobile parameter modal from a search hit. The search result only
// carries id/familie/cod, so fetch the full record first (modal shows '-' for
// any missing field otherwise).
async function _gsOpenParam(r) {
  if (!r.id) { _gsToast('Parametru indisponibil.'); return; }
  try {
    const detail = await apiGet('/api/parametri/' + encodeURIComponent(r.id));
    if (detail && !detail.error) {
      openMobileParamModal(detail);
    } else {
      openMobileParamModal({ id: r.id, cod: r.cod, familie: r.familie });
    }
  } catch (e) {
    console.error('open param failed:', e);
    openMobileParamModal({ id: r.id, cod: r.cod, familie: r.familie });
  }
}

// Tap a result: close the overlay, then navigate to the item.
function activateSearchResult(r) {
  closeGlobalSearch();
  if (!r) return;
  switch (r.type) {
    case 'proiect':
    case 'task':
    case 'observatie':
    case 'checklist':
    case 'jurnal':
    case 'echipament':
      // All of these live inside a project — open the parent project detail.
      if (r.proiect_id) showProjectDetail(r.proiect_id);
      else _gsToast('Proiectul asociat nu a fost găsit.');
      break;
    case 'global_task':
      showTab('tasks');
      break;
    case 'parametru':
      showTab('params');
      _gsOpenParam(r);
      break;
    case 'client':
      showTab('clients');
      break;
    case 'obsidian':
      // openObsNote toggles views inside #tab-obsidian, so show that tab first.
      showTab('obsidian');
      if (r.path) setTimeout(() => openObsNote(r.path), 300);
      break;
    default:
      _gsToast('Nu există o destinație pentru acest rezultat.');
  }
}

// Wire the overlay. mobile.js loads at the end of <body>, so the DOM elements
// already exist; still guard every getElementById.
(function () {
  function wireGlobalSearch() {
    const btn = document.getElementById('global-search-btn');
    if (btn) btn.addEventListener('click', openGlobalSearch);

    const closeBtn = document.getElementById('gs-close');
    if (closeBtn) closeBtn.addEventListener('click', closeGlobalSearch);

    const inp = document.getElementById('gs-input');
    if (inp) {
      inp.addEventListener('input', onGlobalSearchInput);
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeGlobalSearch();
      });
    }

    const box = document.getElementById('gs-results');
    if (box) box.addEventListener('click', function (e) {
      const item = e.target.closest && e.target.closest('.gs-item');
      if (item) activateSearchResult(_gsResults[+item.getAttribute('data-idx')]);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireGlobalSearch);
  } else {
    wireGlobalSearch();
  }
})();
