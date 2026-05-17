// PIF Mobile - Mobile SPA Logic
// IndexedDB for offline storage, sync when online

// ============================================================
// One-time SW cleanup (rulează o singură dată per device)
// ============================================================
(async () => {
    const swFixed = localStorage.getItem('sw_force_v5');
    if (!swFixed) {
        console.log('[Boot] One-time SW cleanup starting...');
        try {
            const regs = await navigator.serviceWorker.getRegistrations();
            for (const reg of regs) {
                console.log('[Boot] Unregistering SW:', reg.scope);
                await reg.unregister();
            }
            const keys = await caches.keys();
            for (const key of keys) {
                console.log('[Boot] Deleting cache:', key);
                await caches.delete(key);
            }
            localStorage.setItem('sw_force_v5', '1');
            if (regs.length > 0) {
                console.log('[Boot] SW was active — reloading');
                window.location.reload();
                // Nu returnăm — pagina se reîncarcă oricum
            } else {
                console.log('[Boot] No SW found — clean start');
            }
        } catch (e) {
            console.warn('[Boot] SW cleanup failed:', e.message || e);
        }
    }
})();

// ============================================================

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

function idbPut(database, storeName, obj) {
  return new Promise((resolve, reject) => {
    const tx = database.transaction(storeName, 'readwrite');
    const request = tx.objectStore(storeName).put(obj);
    request.onsuccess = () => resolve(request.result);
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

async function dbDelete(storeName, key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const request = store.delete(key);
    request.onsuccess = () => resolve();
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

function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;

    navigator.serviceWorker.register('/static/service-worker.js')
        .then(registration => {
            console.log('[App] SW registered');

            // Verifică update-uri la fiecare 60 min
            setInterval(() => registration.update(), 60 * 60 * 1000);

            // Când e un SW nou gata
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        // SW nou instalat, dar cel vechi încă controlează pagina
                        console.log('[App] New SW ready — activating');
                        newWorker.postMessage('SKIP_WAITING');
                    }
                });
            });
        })
        .catch(err => console.error('[App] SW registration failed:', err));

    // Când noul SW preia controlul → reload pentru a folosi noul cod
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
            refreshing = true;
            console.log('[App] New SW active — reloading');
            window.location.reload();
        }
    });
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
  
  if (q) {
    results = results.filter(p => p._search.includes(q));
    results.sort((a, b) => {
      const aCod = (a.cod || '').toLowerCase();
      const bCod = (b.cod || '').toLowerCase();
      if (aCod === q && bCod !== q) return -1;
      if (bCod === q && aCod !== q) return 1;
      if (aCod.startsWith(q) && !bCod.startsWith(q)) return -1;
      if (bCod.startsWith(q) && !aCod.startsWith(q)) return 1;
      return aCod.localeCompare(bCod);
    });
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

function getStatusLabel(status) {
  const labels = { 'in_lucru': 'În Lucru', 'finalizat': 'Finalizat', 'in_asteptare': 'În Așteptare' };
  return labels[status] || status;
}

async function showProjectDetail(projectId) {
  currentProject = projectsCache.find(p => p.id === projectId);
  if (!currentProject) return;

  const infoEl = document.getElementById('project-info');
  const p = currentProject;

  infoEl.innerHTML = `
    <div class="detail-section">
      <div class="detail-label">Proiect</div>
      <div class="detail-value" style="font-size:18px; font-weight:600;">${escapeHtml(p.nume || '-')}</div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="detail-section">
        <div class="detail-label">Client</div>
        <div class="detail-value">${escapeHtml(p.client || '-')}</div>
      </div>
      <div class="detail-section">
        <div class="detail-label">Producător</div>
        <div class="detail-value">${escapeHtml(p.producator || '-')}</div>
      </div>
      <div class="detail-section">
        <div class="detail-label">Echipament</div>
        <div class="detail-value">${escapeHtml(p.echipament_principal || '-')}</div>
      </div>
      <div class="detail-section">
        <div class="detail-label">Locație</div>
        <div class="detail-value">${escapeHtml(p.locatie || '-')}</div>
      </div>
      <div class="detail-section">
        <div class="detail-label">Status</div>
        <div class="detail-value"><span class="project-status status-${p.status || 'in_lucru'}">${getStatusLabel(p.status)}</span></div>
      </div>
      <div class="detail-section">
        <div class="detail-label">Tip</div>
        <div class="detail-value">${escapeHtml(p.tip || '-')}</div>
      </div>
      <div class="detail-section">
        <div class="detail-label">Deadline</div>
        <div class="detail-value">${p.deadline || '-'}</div>
      </div>
      <div class="detail-section">
        <div class="detail-label">Nr. Comandă</div>
        <div class="detail-value">${escapeHtml(p.nr_comanda || '-')}</div>
      </div>
    </div>

    <!-- Checklist PIF -->
    <div id="mobile-checklist" style="margin-top:16px;"></div>

    <!-- Timer -->
    <div id="mobile-timer" style="margin-top:16px;"></div>

    <!-- Echipamente -->
    <div id="mobile-equipment" style="margin-top:16px;"></div>
  `;

  // Încarcă sub-secțiunile
  loadMobileChecklist(projectId);
  loadMobileTimer(projectId);
  loadMobileEquipment(projectId);
  await loadProjectNotes(projectId);

  // Switch view
  document.querySelectorAll('.tab-view').forEach(v => v.classList.remove('active'));
  document.getElementById('project-detail').classList.add('active');

  // Update link to notes tab
  document.getElementById('all-notes-link').href = '#';
  document.getElementById('all-notes-link').addEventListener('click', (e) => {
    e.preventDefault();
    showTab('notes');
  }, { once: true });

  // Setup add note button
  document.getElementById('add-note-to-project').onclick = () => {
    openNoteModal(currentProject.id);
  };
}

// ============ M2: Checklist PIF pe mobil ============
async function loadMobileChecklist(projectId) {
  const el = document.getElementById('mobile-checklist');
  try {
    const items = await apiGet(`/api/proiecte/${projectId}/checklist`);
    if (!items || items.length === 0) { el.innerHTML = ''; return; }

    const completed = items.filter(i => i.completed).length;
    const total = items.length;
    const pct = Math.round((completed / total) * 100);

    el.innerHTML = `
      <div style="font-size:14px; font-weight:600; margin-bottom:8px; display:flex; align-items:center; gap:6px;"><i data-lucide="list-checks" style="color:var(--accent);"></i> Checklist PIF (${completed}/${total})</div>
      <div style="background:var(--border); border-radius:4px; height:6px; margin-bottom:12px;">
        <div style="background:var(--success); height:100%; border-radius:4px; width:${pct}%; transition:width 0.3s;"></div>
      </div>
      ${items.map(item => `
        <div style="display:flex; align-items:center; gap:10px; padding:10px; margin-bottom:4px; background:var(--surface); border-radius:8px; border:1px solid var(--border);">
          <input type="checkbox" ${item.completed ? 'checked' : ''}
            onchange="toggleChecklistItem('${item.id}', this.checked, '${projectId}')"
            style="width:20px; height:20px; accent-color:var(--success); flex-shrink:0;">
          <span style="font-size:13px; ${item.completed ? 'text-decoration:line-through; opacity:0.5;' : ''}">${escapeHtml(item.titlu)}</span>
        </div>
      `).join('')}
    `;
  } catch (e) { el.innerHTML = ''; }
}

async function toggleChecklistItem(itemId, checked, projectId) {
  try {
    await fetch(`/api/checklist/${itemId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ completed: checked ? 1 : 0 })
    });
    loadMobileChecklist(projectId);
  } catch (e) { console.error('Toggle checklist error:', e); }
}

// ============ M3: Timer pe mobil (vizualizare ore) ============
async function loadMobileTimer(projectId) {
  const el = document.getElementById('mobile-timer');
  try {
    const data = await apiGet(`/api/proiecte/${projectId}/timer`);
    if (!data) { el.innerHTML = ''; return; }

    const totalH = (data.total_secunde / 3600).toFixed(1);
    const sessions = data.sessions || [];

    el.innerHTML = `
      <div style="font-size:14px; font-weight:600; margin-bottom:8px;">⏱️ Timp lucrat: ${totalH}h</div>
      ${sessions.length > 0 ? `
        <div style="font-size:12px; color:var(--text-secondary);">
          ${sessions.slice(0, 5).map(s => {
            const h = ((s.durata_secunde || 0) / 3600).toFixed(1);
            const date = s.start_time ? s.start_time.substring(0, 10) : '-';
            return `<div style="padding:4px 0;">${date}: ${h}h</div>`;
          }).join('')}
          ${sessions.length > 5 ? `<div style="opacity:0.5;">+${sessions.length - 5} sesiuni</div>` : ''}
        </div>
      ` : '<div style="font-size:12px; color:var(--text-secondary);">Nicio sesiune înregistrată</div>'}
    `;
  } catch (e) { el.innerHTML = ''; }
}

// ============ M4: Echipamente pe mobil (vizualizare) ============
async function loadMobileEquipment(projectId) {
  const el = document.getElementById('mobile-equipment');
  try {
    const items = await apiGet(`/api/proiecte/${projectId}/echipamente`);
    if (!items || items.length === 0) { el.innerHTML = ''; return; }

    el.innerHTML = `
      <div style="font-size:14px; font-weight:600; margin-bottom:8px; display:flex; align-items:center; gap:6px;"><i data-lucide="wrench" style="color:var(--accent);"></i> Echipamente (${items.length})</div>
      ${items.map(eq => {
        let paramsCount = 0;
        try { paramsCount = Object.keys(JSON.parse(eq.params_json || '{}')).length; } catch {}
        return `
          <div style="background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:12px; margin-bottom:8px;">
            <div style="font-weight:600; font-size:14px;">${escapeHtml(eq.nume || '-')}</div>
            <div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
              ${escapeHtml(eq.producator || '-')} · ${escapeHtml(eq.model || '-')}
              ${eq.serial_number ? ' · S/N: ' + escapeHtml(eq.serial_number) : ''}
            </div>
            ${paramsCount > 0 ? `<div style="font-size:11px; color:var(--accent); margin-top:4px;">${paramsCount} parametri configurați</div>` : ''}
          </div>
        `;
      }).join('')}
    `;
  } catch (e) { el.innerHTML = ''; }
}

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

async function loadParameters() {
  const listEl = document.getElementById('params-list');
  listEl.innerHTML = '<div class="loading">Se încarcă...</div>';
  
  try {
    let allParams = await getCachedParams();
    const storedVersion = parseInt(localStorage.getItem('params_db_version') || '0');
    
    if (!allParams || allParams.length === 0 || storedVersion !== DB_VERSION) {
      if (_isOnline) {
        listEl.innerHTML = '<div class="loading">Se sincronizează...</div>';
        const ok = await syncParamsToLocal();
        if (ok) {
          allParams = await getCachedParams();
        }
      }
    }
    
    if (!allParams || allParams.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i data-lucide="wifi-off"></i></div>Fără conexiune. Conectează-te pentru a sincroniza parametrii.</div>';
      return;
    }
    
    // Populate family filter
    try {
      const families = [...new Set(allParams.map(p => p.familie))].sort();
      const select = document.getElementById('family-select');
      select.innerHTML = '<option value="all">Toate familiile</option>';
      families.forEach(f => { select.innerHTML += '<option value="'+f+'">'+f+'</option>'; });
    } catch(e) { console.error('family dropdown:', e); }
    
    // Render
    renderParameters(allParams);
    updateSyncStatus();
    
    // Search
    const searchEl = document.getElementById('param-search');
    const familyEl = document.getElementById('family-select');
    let timer;
    searchEl.oninput = function() {
      clearTimeout(timer);
      timer = setTimeout(async function() {
        const results = await searchParamsLocal(searchEl.value, familyEl.value);
        renderParameters(results);
      }, 200);
    };
    familyEl.onchange = async function() {
      const results = await searchParamsLocal(searchEl.value, familyEl.value);
      renderParameters(results);
    };
    
  } catch (e) {
    listEl.innerHTML = '<div class="empty-state">⚠️ Eroare: ' + (e.message || 'necunoscută') + '</div>';
  }
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
  if (param.explicatie && param.explicatie.trim().length > 0) {
    modal.querySelector('#mpm-explicatie').innerHTML = param.explicatie;
    explicatieRow.style.display = 'block';
  } else if (_isOnline && param.id) {
    // Fetch detail from server for full explicatie
    explicatieRow.style.display = 'block';
    modal.querySelector('#mpm-explicatie').textContent = 'Se încarcă...';
    apiGet('/api/parametri/' + param.id).then(detail => {
      if (detail && detail.explicatie) {
        modal.querySelector('#mpm-explicatie').innerHTML = detail.explicatie;
      } else {
        modal.querySelector('#mpm-explicatie').textContent = 'Nicio explicație disponibilă';
      }
    }).catch(() => {
      modal.querySelector('#mpm-explicatie').textContent = 'Eroare la încărcare';
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

// Helper: randare influențe din parametru sau fetch detalii
function renderInfluenteaza(param, modal, row) {
  if (!row) return;
  const div = modal.querySelector('#mpm-influenteaza');
  
  const tryRender = (influenteazaData) => {
    if (!influenteazaData || influenteazaData === '[]' || influenteazaData === 'null') {
      row.style.display = 'none';
      return;
    }
    let arr;
    try {
      arr = typeof influenteazaData === 'string' ? JSON.parse(influenteazaData) : influenteazaData;
    } catch { row.style.display = 'none'; return; }
    if (!Array.isArray(arr) || arr.length === 0) { row.style.display = 'none'; return; }
    div.innerHTML = arr.map(obj => {
      const pname = typeof obj === 'string' ? obj : (obj.parametru || '?');
      const efect = typeof obj === 'string' ? '' : (obj.efect || '');
      const tip = typeof obj === 'string' ? '' : (obj.tip || '');
      const tipTag = tip ? ` <span style="font-size:0.7em;opacity:0.6;">[${tip}]</span>` : '';
      const efectText = efect ? `<div style="font-size:0.8em;opacity:0.8;margin-top:1px;">${efect}</div>` : '';
      return `<div style="margin:4px 0;padding:6px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--success);">
        <span style="font-family:monospace;font-weight:bold;color:var(--success);">${pname}</span>${tipTag}
        ${efectText}
      </div>`;
    }).join('');
    row.style.display = 'block';
  };
  
  // Try param cache
  if (param.influenteaza) { tryRender(param.influenteaza); return; }
  
  // Fetch detail
  if (_isOnline && param.id) {
    apiGet('/api/parametri/' + param.id).then(detail => {
      if (detail && detail.influenteaza) tryRender(detail.influenteaza);
    }).catch(() => {});
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

async function loadDashboardHome() {
  try {
    const data = await apiGet('/api/dashboard/home');
    if (!data) return;

    // Stats cards
    document.getElementById('home-stats').innerHTML = `
      <div class="detail-section" style="text-align:center;">
        <div style="font-size:28px; font-weight:600; color:var(--accent);">${data.stats.active_projects}</div>
        <div class="detail-label">Proiecte active</div>
      </div>
      <div class="detail-section" style="text-align:center;">
        <div style="font-size:28px; font-weight:600; color:var(--accent);">${data.stats.weekly_hours}</div>
        <div class="detail-label">Ore (7 zile)</div>
      </div>
    `;

    // Active timer
    const timerEl = document.getElementById('home-active-timer');
    if (data.active_timer) {
      const start = new Date(data.active_timer.start_time);
      const elapsed = Math.floor((Date.now() - start.getTime()) / 1000);
      timerEl.innerHTML = `
        <div class="detail-section" style="border-left:3px solid var(--success);">
          <div style="font-size:12px; color:var(--success); font-weight:600;">⏱️ TIMER ACTIV</div>
          <div style="font-size:16px; margin-top:4px;">${escapeHtml(data.active_timer.project_name)}</div>
          <div style="font-size:20px; font-weight:600; color:var(--accent); margin-top:4px;" id="home-timer-display">${formatDuration(elapsed)}</div>
          <button onclick="stopTimerFromHome('${data.active_timer.project_id}')" class="modal-btn" style="margin-top:8px; background:var(--error);">⏹ Oprește timer</button>
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
        <div style="font-size:14px; font-weight:600; margin:16px 0 8px;">📅 Deadline-uri (7 zile)</div>
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
    case 'manuals': loadManuals(); break;
    case 'stats': loadMobileStats(); break;
    case 'clients': loadMobileClients(); break;
    case 'more': openMoreMenu(); break;
  }

  // FAB visibility
  const fab = document.getElementById('notes-fab');
  fab.classList.toggle('hidden', tab !== 'notes');
  const projectsFab = document.getElementById('projects-fab');
  if (projectsFab) projectsFab.classList.toggle('hidden', tab !== 'projects');
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

  infoEl.innerHTML = `
    <div style="margin-bottom:16px;">
      <div style="font-size:18px; font-weight:600;">${escapeHtml(p.nume || '-')}</div>
      <div style="margin-top:4px;">
        <span class="project-status status-${p.status || 'in_lucru'}">${getStatusLabel(p.status)}</span>
        <span style="font-size:12px; color:var(--text-secondary); margin-left:8px;">${escapeHtml(p.tip || 'PIF')}</span>
      </div>
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
      <div style="font-size:14px; font-weight:600; margin:16px 0 8px;">⏱️ Timer · ${totalH}h total</div>
      ${activeSession ? `
        <div class="detail-section" style="border-left:3px solid var(--success);">
          <div style="font-size:13px; color:var(--success);">Timer activ</div>
          <div id="mobile-timer-live" style="font-size:24px; font-weight:600; color:var(--accent); margin:8px 0;"></div>
          <button onclick="stopMobileTimer('${projectId}')" class="modal-btn" style="background:var(--error);">⏹ Oprește</button>
        </div>
      ` : `
        <button onclick="startMobileTimer('${projectId}')" class="modal-btn" style="margin-bottom:12px;">▶️ Pornește timer</button>
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

// 3.4 Checklist PIF
async function loadMobileChecklist(projectId) {
  const el = document.getElementById('mobile-checklist-section');
  try {
    const items = await apiGet(`/api/proiecte/${projectId}/checklist`);
    if (!items || items.length === 0) {
      el.innerHTML = `
        <div style="font-size:14px; font-weight:600; margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="list-checks" style="color:var(--accent);"></i> Checklist PIF</div>
        <div style="display:flex; gap:8px; margin-bottom:8px;">
          <input type="text" id="new-checklist-item" placeholder="Item nou..."
            style="flex:1;padding:10px;font-size:14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);">
          <button onclick="addMobileChecklistItem('${projectId}')" style="padding:10px 16px;background:var(--accent);color:var(--bg);border:none;border-radius:8px;font-weight:600;">+</button>
        </div>
      `;
      return;
    }

    const completed = items.filter(i => i.completed).length;
    const total = items.length;
    const pct = Math.round((completed / total) * 100);

    el.innerHTML = `
      <div style="font-size:14px; font-weight:600; margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="list-checks" style="color:var(--accent);"></i> Checklist PIF (${completed}/${total})</div>
      <div style="background:var(--border);border-radius:4px;height:6px;margin-bottom:12px;">
        <div style="background:var(--success);height:100%;border-radius:4px;width:${pct}%;transition:width 0.3s;"></div>
      </div>
      ${items.map(item => `
        <div style="display:flex;align-items:center;gap:10px;padding:10px;margin-bottom:4px;background:var(--surface);border-radius:8px;border:1px solid var(--border);">
          <input type="checkbox" ${item.completed ? 'checked' : ''}
            onchange="toggleMobileChecklist('${item.id}',this.checked,'${projectId}')"
            style="width:20px;height:20px;accent-color:var(--success);flex-shrink:0;">
          <span style="font-size:13px;flex:1;${item.completed ? 'text-decoration:line-through;opacity:0.5;' : ''}">${escapeHtml(item.titlu)}</span>
          <button onclick="deleteMobileChecklistItem('${item.id}','${projectId}')" style="background:none;border:none;color:var(--error);font-size:16px;cursor:pointer;padding:4px;">×</button>
        </div>
      `).join('')}
      <div style="display:flex;gap:8px;margin-top:8px;">
        <input type="text" id="new-checklist-item" placeholder="Item nou..."
          style="flex:1;padding:10px;font-size:14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);">
        <button onclick="addMobileChecklistItem('${projectId}')" style="padding:10px 16px;background:var(--accent);color:var(--bg);border:none;border-radius:8px;font-weight:600;">+</button>
      </div>
    `;
  } catch (e) { el.innerHTML = ''; }
}

async function toggleMobileChecklist(itemId, checked, projectId) {
  await apiPut(`/api/checklist/${itemId}`, { completed: checked ? 1 : 0 });
  loadMobileChecklist(projectId);
}

async function addMobileChecklistItem(projectId) {
  const input = document.getElementById('new-checklist-item');
  const titlu = input.value.trim();
  if (!titlu) return;
  await apiPost(`/api/proiecte/${projectId}/checklist`, { titlu, ordine: 999 });
  input.value = '';
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

    el.innerHTML = `
      <div style="font-size:14px;font-weight:600;margin:16px 0 8px;">📌 Todo List</div>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input type="text" id="new-project-task" placeholder="Task nou..."
          style="flex:1;padding:10px;font-size:14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);">
        <button onclick="addMobileProjectTask('${projectId}')" style="padding:10px 16px;background:var(--accent);color:var(--bg);border:none;border-radius:8px;font-weight:600;">+</button>
      </div>
      ${tasks.map(t => `
        <div style="display:flex;align-items:center;gap:10px;padding:10px;margin-bottom:4px;background:var(--surface);border-radius:8px;border:1px solid var(--border);">
          <input type="checkbox" ${t.status === 'done' ? 'checked' : ''}
            onchange="toggleMobileProjectTask('${t.id}',this.checked,'${projectId}')"
            style="width:20px;height:20px;accent-color:var(--accent);flex-shrink:0;">
          <span style="font-size:13px;flex:1;${t.status === 'done' ? 'text-decoration:line-through;opacity:0.5;' : ''}">${escapeHtml(t.titlu)}</span>
          <span style="font-size:10px;padding:2px 6px;border-radius:4px;background:var(--border);color:var(--text-secondary);">${t.prioritate || 'normal'}</span>
          <button onclick="deleteMobileProjectTask('${t.id}','${projectId}')" style="background:none;border:none;color:var(--error);font-size:16px;cursor:pointer;padding:4px;">×</button>
        </div>
      `).join('')}
    `;
  } catch (e) { el.innerHTML = ''; }
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

    el.innerHTML = `
      <div style="font-size:14px;font-weight:600;margin:16px 0 8px;">📎 Atașamente</div>
      <label style="display:block;padding:12px;text-align:center;background:var(--surface);border:2px dashed var(--border);border-radius:8px;cursor:pointer;margin-bottom:12px;color:var(--text-secondary);">
        <i data-lucide="paperclip"></i> Adaugă fișier
        <input type="file" id="mobile-file-upload" onchange="uploadMobileFile('${projectId}')" style="display:none;">
      </label>
      ${(attachments || []).map(a => {
        const iconName = {'PDF':'file-text','IMG':'image','DOC':'file-text','XLS':'file-spreadsheet','EMAIL':'mail','ZIP':'archive'}[a.tip_fisier] || 'file';
        const size = formatFileSize(a.dimensiune);
        return `
          <div style="display:flex;align-items:center;gap:10px;padding:10px;margin-bottom:4px;background:var(--surface);border-radius:8px;border:1px solid var(--border);">
            <span style="color:var(--accent);display:inline-flex;align-items:center;"><i data-lucide="${iconName}"></i></span>
            <div style="flex:1;min-width:0;">
              <div style="font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(a.nume_fisier)}</div>
              <div style="font-size:11px;color:var(--text-secondary);">${size}</div>
            </div>
            <a href="/api/atasamente/${a.id}/download" target="_blank" aria-label="Descarcă" style="color:var(--accent);text-decoration:none;padding:8px;display:inline-flex;align-items:center;"><i data-lucide="download"></i></a>
            <button onclick="deleteMobileAttachment('${a.id}','${projectId}')" aria-label="Șterge" style="background:none;border:none;color:var(--danger);cursor:pointer;padding:6px;display:inline-flex;align-items:center;"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></button>
          </div>
        `;
      }).join('')}
    `;
  } catch (e) { el.innerHTML = ''; }
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
          <div class="detail-section" style="margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;align-items:start;gap:8px;">
              <div style="flex:1;min-width:0;">
                <div style="font-weight:600;font-size:14px;">${escapeHtml(eq.nume || '-')}</div>
                <div style="font-size:12px;color:var(--text-secondary);">${escapeHtml(eq.producator || '')} · ${escapeHtml(eq.model || '')}</div>
                ${eq.serial_number ? `<div style="font-size:11px;color:var(--text-secondary);">S/N: ${escapeHtml(eq.serial_number)}</div>` : ''}
              </div>
              <div style="display:flex;gap:4px;flex-shrink:0;">
                <button onclick='editMobileEquipment(${eqJson}, "${projectId}")' aria-label="Editează" style="background:none;border:none;color:var(--text-secondary);cursor:pointer;padding:6px;display:inline-flex;align-items:center;justify-content:center;"><i data-lucide="pencil" style="width:16px;height:16px;"></i></button>
                <button onclick="deleteMobileEquipment('${eq.id}','${projectId}')" aria-label="Șterge" style="background:none;border:none;color:var(--danger);cursor:pointer;padding:6px;display:inline-flex;align-items:center;justify-content:center;"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></button>
              </div>
            </div>
            ${paramEntries.length > 0 ? `
              <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);">
                <div style="font-size:11px;color:var(--accent);margin-bottom:4px;">${paramEntries.length} parametri</div>
                ${paramEntries.slice(0, 10).map(([k, v]) => `
                  <div style="display:flex;justify-content:space-between;font-size:12px;padding:2px 0;">
                    <span style="color:var(--accent);font-family:monospace;">${escapeHtml(k)}</span>
                    <span>${escapeHtml(v)}</span>
                  </div>
                `).join('')}
                ${paramEntries.length > 10 ? `<div style="font-size:11px;opacity:0.5;">+${paramEntries.length - 10} mai mult</div>` : ''}
              </div>
            ` : ''}
          </div>
        `;
      }).join('')}
    `;
  } catch (e) { el.innerHTML = ''; }
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
    <textarea id="eq-params" placeholder="Parametri (un par=val pe linie)&#10;p0304 = 400&#10;p0305 = 5.6" style="width:100%;min-height:100px;padding:12px;font-size:14px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);resize:vertical;font-family:'JetBrains Mono',monospace;margin-bottom:8px;">${escapeHtml(paramsText)}</textarea>
    <button onclick="saveMobileEquipment('${projectId}', ${isEdit ? `'${eq.id}'` : 'null'})" class="modal-btn">${isEdit ? 'Salvează' : 'Creează'}</button>
  `;

  modal._originalContent = originalContent;
  modal.classList.add('active');
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

// 3.9 Observations
async function loadMobileObservations(project) {
  const el = document.getElementById('mobile-observations-section');
  if (!project.observatii && !project.observatii?.trim()) { el.innerHTML = ''; return; }

  el.innerHTML = `
    <div style="font-size:14px;font-weight:600;margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="message-square-text" style="color:var(--accent);"></i> Observații tehnice</div>
    <textarea id="obs-textarea" style="width:100%;min-height:80px;padding:10px;font-size:14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);resize:vertical;font-family:inherit;">${escapeHtml(project.observatii || '')}</textarea>
    <button onclick="saveMobileObservations()" class="modal-btn" style="margin-top:4px;">Salvează</button>
  `;
}

async function saveMobileObservations() {
  if (!currentProject) return;
  const text = document.getElementById('obs-textarea').value;
  await apiPut(`/api/proiecte/${currentProject.id}`, { observatii: text });
  if ('vibrate' in navigator) navigator.vibrate(30);
}

// 3.10 Service fields
async function loadMobileServiceFields(project) {
  const el = document.getElementById('mobile-service-section');
  if (project.tip !== 'Service') { el.innerHTML = ''; return; }

  el.innerHTML = `
    <div style="font-size:14px;font-weight:600;margin:16px 0 8px; display:flex; align-items:center; gap:6px;"><i data-lucide="clipboard-list" style="color:var(--accent);"></i> Fișă intervenție</div>
    <div class="detail-section" style="border-left:3px solid var(--error);margin-bottom:8px;">
      <div style="font-size:12px;color:var(--danger);font-weight:600;margin-bottom:4px; display:flex; align-items:center; gap:4px;"><i data-lucide="alert-circle" style="width:12px;height:12px;"></i> Constatări</div>
      <textarea id="service-before" style="width:100%;min-height:60px;padding:8px;font-size:13px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);resize:vertical;font-family:inherit;">${escapeHtml(project.service_before || '')}</textarea>
    </div>
    <div class="detail-section" style="border-left:3px solid var(--success);">
      <div style="font-size:12px;color:var(--success);font-weight:600;margin-bottom:4px; display:flex; align-items:center; gap:4px;"><i data-lucide="circle-check" style="width:12px;height:12px;"></i> Acțiuni</div>
      <textarea id="service-after" style="width:100%;min-height:60px;padding:8px;font-size:13px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);resize:vertical;font-family:inherit;">${escapeHtml(project.service_after || '')}</textarea>
    </div>
    <button onclick="saveMobileServiceFields()" class="modal-btn" style="margin-top:4px;">Salvează</button>
  `;
}

async function saveMobileServiceFields() {
  if (!currentProject) return;
  await apiPut(`/api/proiecte/${currentProject.id}`, {
    service_before: document.getElementById('service-before').value,
    service_after: document.getElementById('service-after').value
  });
  if ('vibrate' in navigator) navigator.vibrate(30);
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

    listEl.innerHTML = filtered.map(t => `
      <div class="note-item" style="display:flex;align-items:center;gap:10px;padding:12px;">
        <input type="checkbox" ${t.status === 'done' ? 'checked' : ''}
          onchange="toggleMobileTask('${t.id}', this.checked)"
          style="width:22px;height:22px;cursor:pointer;accent-color:var(--accent);flex-shrink:0;">
        <div style="flex:1;min-width:0;" onclick="editMobileTask('${t.id}')">
          <div style="font-size:14px;${t.status === 'done' ? 'text-decoration:line-through;opacity:0.5;' : ''}">${escapeHtml(t.titlu)}</div>
          <div style="font-size:11px;color:var(--text-secondary);margin-top:2px;">
            ${t.categorie || ''}${t.data_scadenta ? ' · 📅 ' + t.data_scadenta : ''}
          </div>
        </div>
        <span style="font-size:10px;padding:2px 6px;border-radius:4px;background:${t.prioritate==='Urgent'?'rgba(239,68,68,0.2)':'var(--border)'};color:${t.prioritate==='Urgent'?'var(--error)':'var(--text-secondary)'};">${t.prioritate || 'Normal'}</span>
        <button onclick="deleteMobileGlobalTask('${t.id}')" style="background:none;border:none;color:var(--error);font-size:14px;cursor:pointer;padding:4px;">×</button>
      </div>
    `).join('');
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

// ============ Utility ============

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Human-readable file size: 512 B, 12.4 KB, 4.7 MB, 1.2 GB
function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return '';
  const n = Number(bytes);
  if (!isFinite(n) || n < 0) return '';
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' KB';
  if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + ' MB';
  return (n / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

function debounce(fn, ms) {
  let timer; return function(...args) { clearTimeout(timer); timer = setTimeout(() => fn.apply(this, args), ms); };
}

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
  
  // Theme toggle (mobile)
  const themeToggleMobile = document.getElementById('theme-toggle-mobile');
  if (themeToggleMobile) {
    const currentTheme = localStorage.getItem('theme') || 'dark';
    themeToggleMobile.textContent = currentTheme === 'dark' ? '🌙' : '☀️';
    themeToggleMobile.addEventListener('click', () => {
      const html = document.documentElement;
      const current = html.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      themeToggleMobile.textContent = next === 'dark' ? '🌙' : '☀️';
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
  
  // Quick search handler
  const quickSearch = document.getElementById('quick-search');
  if (quickSearch) {
    let qsTimer;
    quickSearch.addEventListener('focus', () => showTab('params'));
    quickSearch.addEventListener('input', () => {
      clearTimeout(qsTimer);
      qsTimer = setTimeout(async () => {
        const results = await searchParamsLocal(quickSearch.value, 'all');
        renderParameters(results);
      }, 200);
    });
  }
  
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
  
  // FAB for notes
  document.getElementById('notes-fab').addEventListener('click', () => {
    openNoteModal();
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

    // 1. Trimite mesaj la SW să-și golească cache-urile
    if (navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage('CLEAR_CACHE');
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

    // 4. Reload fără cache
    window.location.reload(true);
  });
});
