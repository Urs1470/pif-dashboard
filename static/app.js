const API_BASE = '/api';

// Toast system - moved to top to avoid TDZ
const toastQueue = [];
const MAX_TOASTS = 3;

let currentProjectId = null;
let confirmCallback = null;
let parametriData = [];
let currentParam = null;
let sortCol = null;
let sortDir = 0;
let archiveVisible = false;
let gtFilters = { status: '', prioritate: '', categorie: '', search: '' };
let parametriFamilii = [];
let parametriPage = 1;
let parametriTotal = 0;
let parametriLimit = 50;

const NAV_ICONS = {
    acasa: `<svg width="16" height="16" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <rect x="2" y="10" width="7" height="8" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <rect x="11" y="6" width="7" height="12" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <polyline points="1,11 10,3 19,11" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="miter"/>
    </svg>`,

    taskuri: `<svg width="16" height="16" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <rect x="2" y="3" width="16" height="3" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <rect x="2" y="9" width="10" height="3" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <rect x="2" y="15" width="7" height="3" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <polyline points="13,13 16,16 19,11" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="miter"/>
    </svg>`,

    proiecte: `<svg width="16" height="16" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="2" width="14" height="16" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="6" y1="7" x2="14" y2="7" stroke="currentColor" stroke-width="1.5"/>
        <line x1="6" y1="11" x2="14" y2="11" stroke="currentColor" stroke-width="1"/>
        <line x1="6" y1="15" x2="10" y2="15" stroke="currentColor" stroke-width="1"/>
        <rect x="7" y="0" width="6" height="4" fill="var(--bg)" stroke="currentColor" stroke-width="1.5"/>
    </svg>`,

    parametri: `<svg width="16" height="16" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <rect x="2" y="2" width="16" height="12" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="5" y1="7" x2="15" y2="7" stroke="currentColor" stroke-width="1"/>
        <line x1="5" y1="10" x2="12" y2="10" stroke="currentColor" stroke-width="1"/>
        <line x1="10" y1="14" x2="10" y2="17" stroke="currentColor" stroke-width="1.5"/>
        <line x1="6" y1="17" x2="14" y2="17" stroke="currentColor" stroke-width="1.5"/>
    </svg>`
};

// ============ API HELPERS ============

// ─── Tiny request cache with stale-while-revalidate ───
// - First call: fetches, stores result
// - Subsequent calls within TTL: returns cached instantly, kicks off background refresh
// - Mutations (POST/PUT/DELETE) invalidate by URL prefix match (see _invalidateCache)
const _apiCache = new Map();   // url -> { data, ts }
const _apiInflight = new Map(); // url -> Promise (dedupe parallel requests)
const _API_CACHE_TTL = 60_000;  // 60s — stale entries still served, then refreshed

function _cacheKey(url) { return url; }

function _invalidateCache(url) {
    // Invalidate cached GETs related to the mutated resource.
    // Direct match on the URL root (e.g. /proiecte -> /proiecte, /proiecte/123, /proiecte/123/jurnal),
    // PLUS any nested resource of the same type (e.g. DELETE /jurnal/abc invalidates /proiecte/{any}/jurnal),
    // PLUS aggregate endpoints (/stats, /dashboard/*) that summarize over everything.
    const path = url.split('?')[0];
    const seg = path.split('/')[1] || '';
    const root = '/' + seg;                             // '/jurnal'
    for (const k of _apiCache.keys()) {
        if (
            // resource-specific: only when we actually have a segment, so an
            // empty root ('/') can never wipe the whole cache
            (seg && (k.startsWith(root) || k.includes(root))) ||
            k.startsWith('/dashboard') ||               // dashboards depend on most resources
            k.startsWith('/stats')                      // stat counters re-aggregate from every mutation
        ) _apiCache.delete(k);
    }
}

async function _doFetch(url) {
    const res = await fetch(API_BASE + url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiGet(url, { fresh = false } = {}) {
    const key = _cacheKey(url);
    const cached = _apiCache.get(key);
    const now = Date.now();

    if (!fresh && cached) {
        // Serve cached, refresh in background if stale-ish (>15s old)
        if (now - cached.ts > 15_000 && !_apiInflight.has(key)) {
            const p = _doFetch(url).then(data => {
                _apiCache.set(key, { data, ts: Date.now() });
                _apiInflight.delete(key);
                return data;
            }).catch(() => _apiInflight.delete(key));
            _apiInflight.set(key, p);
        }
        return cached.data;
    }

    // Dedupe parallel callers for same URL
    if (_apiInflight.has(key)) return _apiInflight.get(key);

    const p = _doFetch(url).then(data => {
        _apiCache.set(key, { data, ts: Date.now() });
        _apiInflight.delete(key);
        return data;
    }).catch(e => { _apiInflight.delete(key); throw e; });
    _apiInflight.set(key, p);
    return p;
}

// Prefetch helper for adjacent tabs (fire and forget)
function apiPrefetch(url) { apiGet(url).catch(() => {}); }

// ═══════ Custom Select dropdowns (replace native popup on dark theme) ═══════
// Enhances <select class="cs-enhance">…</select>. Hides the real select,
// builds a button + popup menu styled with our palette. Two-way sync:
//  - clicking an option sets select.value and dispatches a `change` event
//  - external changes to select.value can be propagated via select.dispatchEvent(new Event('change'))
function enhanceSelect(select) {
    if (!select || select.dataset.csInit === '1') return;
    select.dataset.csInit = '1';
    select.style.display = 'none';

    const wrap = document.createElement('div');
    wrap.className = 'cs';
    if (select.id) wrap.id = 'cs-' + select.id;

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'cs-trigger';
    trigger.innerHTML = `<span class="cs-trigger-label"></span>` +
        `<svg class="cs-trigger-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>`;

    const menu = document.createElement('div');
    menu.className = 'cs-menu';

    const labelEl = trigger.querySelector('.cs-trigger-label');

    const syncFromSelect = () => {
        menu.innerHTML = '';
        for (const opt of select.options) {
            const item = document.createElement('div');
            item.className = 'cs-option' + (opt.value === select.value ? ' selected' : '');
            item.textContent = opt.textContent;
            item.dataset.value = opt.value;
            item.addEventListener('click', () => {
                select.value = opt.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                close();
            });
            menu.appendChild(item);
        }
        const selOpt = select.options[select.selectedIndex];
        labelEl.textContent = selOpt ? selOpt.textContent : '';
        // Mirror selected value on the wrapper for value-aware CSS (e.g. priority color)
        wrap.setAttribute('data-value', select.value);
    };

    // The menu is portaled to <body> (see below) so no ancestor's overflow
    // can clip it. Position it to the trigger in viewport space on open.
    const positionMenu = () => {
        const r = trigger.getBoundingClientRect();
        menu.style.minWidth = r.width + 'px';
        menu.style.left = r.left + 'px';
        const menuH = menu.offsetHeight || 0;
        const spaceBelow = window.innerHeight - r.bottom;
        if (spaceBelow < menuH + 8 && r.top > spaceBelow) {
            menu.style.top = Math.max(8, r.top - menuH - 4) + 'px';   // open upward
        } else {
            menu.style.top = (r.bottom + 4) + 'px';
        }
    };
    // Scroll closes the menu (a fixed menu would otherwise detach from the
    // trigger) — but ignore scrolls inside the menu's own option list.
    const onScroll = (e) => { if (e.target !== menu) close(); };
    const open = () => {
        wrap.classList.add('open');
        menu.classList.add('open');
        positionMenu();
        document.addEventListener('mousedown', onDocClick, true);
        window.addEventListener('scroll', onScroll, true);
        window.addEventListener('resize', close);
    };
    const close = () => {
        wrap.classList.remove('open');
        menu.classList.remove('open');
        document.removeEventListener('mousedown', onDocClick, true);
        window.removeEventListener('scroll', onScroll, true);
        window.removeEventListener('resize', close);
    };
    const onDocClick = (e) => {
        if (!wrap.contains(e.target) && !menu.contains(e.target)) close();
    };

    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        wrap.classList.contains('open') ? close() : open();
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });

    // Watch external changes to select (e.g., filter reset)
    select.addEventListener('change', syncFromSelect);
    // Watch attribute/option changes
    new MutationObserver(syncFromSelect).observe(select, { childList: true, attributes: true, attributeFilter: ['value'] });

    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(trigger);
    wrap.appendChild(select);
    document.body.appendChild(menu);   // portaled out — positioned by positionMenu()
    syncFromSelect();
}

function enhanceAllSelects() {
    document.querySelectorAll('select.cs-enhance:not([data-cs-init])').forEach(enhanceSelect);
}

async function apiPost(url, data) {
    const res = await fetch(API_BASE + url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    _invalidateCache(url);
    return res.json();
}

async function apiPut(url, data) {
    const res = await fetch(API_BASE + url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    _invalidateCache(url);
    return res.json();
}

async function apiDelete(url) {
    const res = await fetch(API_BASE + url, { method: 'DELETE' });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    _invalidateCache(url);
    return res.json();
}

async function apiUpload(url, formData) {
    const res = await fetch(API_BASE + url, {
        method: 'POST',
        body: formData
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    _invalidateCache(url);
    return res.json();
}

// ============ THEME MANAGEMENT ============

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
}

function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    // Suppress transitions during the swap so the palette changes instantly
    // instead of smearing across every element.
    html.classList.add('theme-switching');
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    requestAnimationFrame(() => requestAnimationFrame(() => {
        html.classList.remove('theme-switching');
    }));
}

function setTheme(theme) {
    const html = document.documentElement;
    html.setAttribute('data-theme', theme);

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.innerHTML = `<i data-lucide="${theme === 'dark' ? 'sun' : 'moon'}"></i>`;
        themeToggle.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    }
}

// ============ FLATPICKR ============

function initFlatpickr(selector, options = {}) {
    if (typeof flatpickr !== 'function') { console.warn('flatpickr not loaded'); return null; }
    const defaults = { locale: 'ro', dateFormat: 'Y-m-d', allowInput: true, disableMobile: false, ...options };
    return flatpickr(selector, defaults);
}

function initAllDatePickers() {
    // Reflect prio select value on the element for color theming
    document.querySelectorAll('.prio-select').forEach(sel => {
        const sync = () => sel.setAttribute('data-value', sel.value);
        sync();
        sel.addEventListener('change', sync);
    });

    enhanceAllSelects();

    if (document.getElementById('quick-scadenta')) initFlatpickr('#quick-scadenta');
    if (document.getElementById('p-data-start')) initFlatpickr('#p-data-start');
    if (document.getElementById('p-data-est')) initFlatpickr('#p-data-est');
    if (document.getElementById('jurnal-data')) initFlatpickr('#jurnal-data');
    if (document.getElementById('filter-date-from')) initFlatpickr('#filter-date-from');
    if (document.getElementById('filter-date-to')) initFlatpickr('#filter-date-to');
}

// ============ INITIALIZATION ============

// Render all data-lucide icons currently in the DOM. Safe to call multiple times.
// Guarded with a re-entry flag so the MutationObserver below doesn't loop on
// the SVGs Lucide itself inserts (which still carry the data-lucide attribute).
let _iconsRendering = false;
function refreshIcons() {
    if (_iconsRendering) return;
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        _iconsRendering = true;
        try {
            window.lucide.createIcons();
            // Mark decorative SVGs as aria-hidden — screen readers can skip them.
            document.querySelectorAll('svg.lucide:not([aria-hidden])').forEach(s => {
                s.setAttribute('aria-hidden', 'true');
            });
        } catch (e) { /* noop */ }
        // release on next tick so the resulting mutations don't re-enter
        setTimeout(() => { _iconsRendering = false; }, 0);
    }
}

let _iconRefreshTimer = null;
function scheduleIconRefresh() {
    if (_iconsRendering || _iconRefreshTimer) return;
    _iconRefreshTimer = setTimeout(() => { _iconRefreshTimer = null; refreshIcons(); }, 30);
}

// Render KaTeX math inside a container (e.g. parameter explicatie modal).
// Delimiters: $...$ inline, $$...$$ display. No-op until the auto-render
// helper has loaded from CDN. Safe to call repeatedly.
function renderMathIn(el) {
    if (!el) return;
    if (typeof window.renderMathInElement !== 'function') {
        // Library still loading — try once it does
        const onReady = () => { try { window.renderMathInElement(el, _katexOptions); } catch (e) {} };
        setTimeout(() => {
            if (typeof window.renderMathInElement === 'function') onReady();
            else setTimeout(onReady, 300);
        }, 100);
        return;
    }
    try {
        window.renderMathInElement(el, _katexOptions);
    } catch (e) {
        console.warn('KaTeX render failed:', e);
    }
}
// _katexOptions lives in core.js (shared with the mobile shell).

// Check if a node tree contains an UN-RENDERED <i data-lucide="...">
// (we only need to refresh when raw placeholders appear, not when Lucide's own
// SVGs get inserted — those also carry data-lucide but are already rendered)
function _hasUnrenderedLucide(node) {
    if (node.nodeType !== 1) return false;
    if (node.tagName === 'I' && node.hasAttribute('data-lucide')) return true;
    return node.querySelector?.('i[data-lucide]') != null;
}

document.addEventListener('DOMContentLoaded', () => {
    refreshIcons();
    const obs = new MutationObserver(muts => {
        if (_iconsRendering) return;
        for (const m of muts) {
            for (const n of m.addedNodes) {
                if (_hasUnrenderedLucide(n)) {
                    scheduleIconRefresh();
                    return;
                }
            }
        }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    initApp();
});

// Accessibility: ARIA roles for the tab navigation, keyboard arrow-nav,
// accessible names for icon-only controls, and a focus trap for modals.
function initA11y() {
    const tablist = document.querySelector('.main-tabs');
    if (tablist) {
        tablist.setAttribute('role', 'tablist');
        tablist.setAttribute('aria-label', 'Navigare principala');
        const tabs = [...tablist.querySelectorAll('.main-tab')];
        tabs.forEach(tab => {
            const name = tab.getAttribute('data-tab');
            tab.setAttribute('role', 'tab');
            if (name) {
                tab.id = 'maintab-' + name;
                tab.setAttribute('aria-controls', 'tab-' + name);
            }
            const on = tab.classList.contains('active');
            tab.setAttribute('aria-selected', on ? 'true' : 'false');
            tab.setAttribute('tabindex', on ? '0' : '-1');
        });
        document.querySelectorAll('.tab-content').forEach(panel => {
            const name = (panel.id || '').replace('tab-', '');
            panel.setAttribute('role', 'tabpanel');
            if (document.getElementById('maintab-' + name)) {
                panel.setAttribute('aria-labelledby', 'maintab-' + name);
            }
        });
        // Left/Right/Home/End move between tabs (WAI-ARIA tabs pattern).
        tablist.addEventListener('keydown', e => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
            e.preventDefault();
            const cur = tabs.findIndex(t => t.getAttribute('aria-selected') === 'true');
            let next = cur < 0 ? 0 : cur;
            if (e.key === 'ArrowRight') next = (cur + 1) % tabs.length;
            else if (e.key === 'ArrowLeft') next = (cur - 1 + tabs.length) % tabs.length;
            else if (e.key === 'Home') next = 0;
            else if (e.key === 'End') next = tabs.length - 1;
            const t = tabs[next];
            if (t) { t.click(); t.focus(); }
        });
    }

    // Promote title -> aria-label on icon-only controls that lack a name.
    document.querySelectorAll('button[title]:not([aria-label]), a[title]:not([aria-label])').forEach(el => {
        if (!(el.textContent || '').trim()) el.setAttribute('aria-label', el.getAttribute('title'));
    });

    // Focus trap: keep Tab within the top-most visible modal overlay.
    document.addEventListener('keydown', e => {
        if (e.key !== 'Tab') return;
        const open = [...document.querySelectorAll('.modal-overlay')].filter(
            m => m.offsetParent !== null && getComputedStyle(m).display !== 'none'
        );
        if (!open.length) return;
        const modal = open[open.length - 1];
        const f = [...modal.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
            .filter(el => el.offsetParent !== null);
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });

    // Apply ARIA dialog semantics to all modal overlays (one-time setup).
    document.querySelectorAll('.modal-overlay').forEach(m => {
        if (!m.getAttribute('role')) {
            m.setAttribute('role', 'dialog');
            m.setAttribute('aria-modal', 'true');
        }
    });
}

async function initApp() {
    initTheme();
    initA11y();
    switchTab('acasa');

    // Warm cache for other tabs in the background — after Home renders
    setTimeout(() => {
        apiPrefetch('/proiecte');
        apiPrefetch('/global-tasks');
        apiPrefetch('/parametri');
        apiPrefetch('/clienti');
        apiPrefetch('/parametri/familii');
    }, 800);

    // Setup filter listeners with debounce
    const debouncedLoad = debounce(loadProjects, 300);
    document.getElementById('filter-status').addEventListener('change', debouncedLoad);
    document.getElementById('filter-type').addEventListener('change', debouncedLoad);
    document.getElementById('filter-producator').addEventListener('change', debouncedLoad);
    document.getElementById('filter-date-from').addEventListener('change', debouncedLoad);
    document.getElementById('filter-date-to').addEventListener('change', debouncedLoad);
    document.getElementById('search-proiecte').addEventListener('input', debouncedLoad);

    // Setup project type selector
    document.querySelectorAll('.project-type-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.project-type-btn').forEach(b => b.classList.remove('selected'));
            this.classList.add('selected');
            const radio = this.querySelector('input[type="radio"]');
            radio.checked = true;
        });
    });

    // Set today's date for jurnal (element may not exist after journal form was removed)
    const jurnalDataEl = document.getElementById('jurnal-data');
    if (jurnalDataEl) jurnalDataEl.value = new Date().toISOString().split('T')[0];

    // Global tasks filters
    const debouncedGtLoad = debounce(() => loadGlobalTasks(), 300);
    document.getElementById('gt-filter-status').addEventListener('change', () => { gtFilters.status = document.getElementById('gt-filter-status').value; debouncedGtLoad(); });
    document.getElementById('gt-filter-prioritate').addEventListener('change', () => { gtFilters.prioritate = document.getElementById('gt-filter-prioritate').value; debouncedGtLoad(); });
    document.getElementById('gt-filter-categorie').addEventListener('change', () => { gtFilters.categorie = document.getElementById('gt-filter-categorie').value; debouncedGtLoad(); });
    document.getElementById('gt-search').addEventListener('input', () => { gtFilters.search = document.getElementById('gt-search').value; debouncedGtLoad(); });

    // Project tasks filters
    const debouncedPT = debounce(loadProjectTasks, 300);
    document.getElementById('pt-filter-status')?.addEventListener('change', debouncedPT);
    document.getElementById('pt-filter-prioritate')?.addEventListener('change', debouncedPT);

    initSortableHeaders();

    // Project form modal event handlers
    document.getElementById('new-project-form').addEventListener('click', function(e) {
        if (e.target === this) hideNewProjectForm();
    });

    // Setup keyboard shortcuts
    setupKeyboardShortcuts();

    initAllDatePickers();
}

// ============ KEYBOARD SHORTCUTS ============

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Don't trigger shortcuts when typing in inputs/textareas (except Escape).
        // isContentEditable covers the WYSIWYG notes editor — a <div>, so the old
        // tagName-only check let 'n' fire the New-project shortcut mid-typing.
        const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)
            || e.target.isContentEditable;

        // Escape - close modal or go back
        if (e.key === 'Escape') {
            const modal = document.querySelector('.modal-overlay.active');
            if (modal) {
                if (modal.id === 'new-project-form') hideNewProjectForm();
                else if (modal.id === 'confirm-modal') closeConfirmModal();
                else if (modal.id === 'preview-modal') closePreview();
                else if (modal.id === 'keyboard-help-overlay') hideKeyboardHelp();
                else if (modal.id === 'param-detail-modal') closeParamModal();
                else if (modal.id === 'task-edit-modal') closeTaskEditModal();
                else if (modal.id === 'manuals-modal') closeManualsModal();
            }
            closeParamModal();
            if (currentProjectId) {
                showProjectList();
            }
            return;
        }

        // If in input, only handle / for search focus
        if (isInput) {
            if (e.key === '/') {
                e.preventDefault();
                document.getElementById('search-proiecte')?.focus();
            }
            return;
        }

        // ? - Show keyboard help
        if (e.key === '?') {
            e.preventDefault();
            showKeyboardHelp();
            return;
        }

        // N - New project
        if (e.key === 'n' || e.key === 'N') {
            e.preventDefault();
            showNewProjectForm();
            return;
        }

        // / - Focus search
        if (e.key === '/') {
            e.preventDefault();
            document.getElementById('search-proiecte')?.focus();
            return;
        }

        // 1-5 - Switch tabs
        if (e.key === '1') { switchTab('acasa'); return; }
        if (e.key === '2') { switchTab('taskuri'); return; }
        if (e.key === '3') { switchTab('proiecte'); return; }
        if (e.key === '4') { switchTab('parametri'); return; }
        if (e.key === '5') { switchTab('admin'); return; }

        // Ctrl+S - Save (if modal is open)
        if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            const modal = document.getElementById('new-project-form');
            if (modal && modal.classList.contains('active')) {
                document.getElementById('project-form')?.requestSubmit();
            }
            return;
        }
    });
}

function showKeyboardHelp() {
    document.getElementById('keyboard-help-overlay')?.classList.add('active');
}

function hideKeyboardHelp() {
    document.getElementById('keyboard-help-overlay')?.classList.remove('active');
}

// ============ EXPORT EXCEL ============

function toggleExportDropdown(event, dropdownId) {
    if (!dropdownId) dropdownId = 'export-dropdown';
    const dropdown = document.getElementById(dropdownId);
    if (dropdown) {
        dropdown.classList.toggle('active');
    }
    // Close other dropdowns
    document.querySelectorAll('.export-dropdown-content.active').forEach(d => {
        if (d.id !== dropdownId) d.classList.remove('active');
    });
    if (event) event.stopPropagation();
}

function exportExcel(type) {
    const dropdown = document.getElementById('export-dropdown');
    if (dropdown) dropdown.classList.remove('active');
    window.open(`${API_BASE}/export/excel?type=${type}`, '_blank');
    showToast(`Export ${type} descărcat!`, 'success');
}

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
    document.querySelectorAll('.export-dropdown-content.active').forEach(dropdown => {
        const dropdownId = dropdown.id;
        const btn = document.querySelector(`[onclick*="${dropdownId}"], [onclick*="toggleExportDropdown(event, '${dropdownId}')"]`);
        if (btn && !btn.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove('active');
        }
    });
});

function initSortableHeaders() {
    document.querySelectorAll('th.sortable').forEach(th => {
        th.style.cursor = 'pointer';
        th.addEventListener('click', function() {
            const col = this.getAttribute('data-col');
            if (sortCol === col) {
                sortDir = (sortDir + 1) % 3; // 0=none, 1=asc, 2=desc
            } else {
                sortCol = col;
                sortDir = 1; // default to asc
            }
            // Update indicators
            document.querySelectorAll('th.sortable').forEach(h => {
                const c = h.getAttribute('data-col');
                if (c === sortCol) {
                    h.textContent = h.textContent.replace(/[↕️↑↓]/g, '') + (sortDir === 1 ? ' ↑' : sortDir === 2 ? ' ↓' : ' ↕️');
                } else {
                    h.textContent = h.textContent.replace(/[↕️↑↓]/g, '') + ' ↕️';
                }
            });
            loadProjects();
        });
    });
}

// ============ STATS ============

async function updateStats() {
    try {
        const stats = await apiGet('/stats');
        document.getElementById('stat-total').textContent = stats.total || 0;
        document.getElementById('stat-active').textContent = stats.active || 0;
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

// ============ PROJECTS ============

async function loadProjects() {
    const skeleton = document.getElementById('projects-skeleton');
    const table = document.getElementById('projects-table');
    // Show the skeleton only if the load is genuinely slow. On a cache hit the
    // data resolves within a microtask, the timer never fires, the table is
    // never hidden — so there is no flash when switching to the Proiecte tab.
    const slowTimer = setTimeout(() => {
        if (skeleton) skeleton.style.display = 'block';
        if (table) table.style.display = 'none';
    }, 180);

    try {
        const status = document.getElementById('filter-status').value;
        const tip = document.getElementById('filter-type').value;
        const producator = document.getElementById('filter-producator').value;
        const search = document.getElementById('search-proiecte').value.trim().toLowerCase();

        let url = '/proiecte?';
        if (status) url += `status=${status}&`;
        if (tip) url += `tip=${tip}&`;
        if (producator) url += `producator=${producator}&`;

        let projects = await apiGet(url);

        // Client-side search filter
        if (search) {
            projects = projects.filter(p =>
                (p.nume || '').toLowerCase().includes(search) ||
                (p.client || '').toLowerCase().includes(search) ||
                (p.echipament_principal || '').toLowerCase().includes(search) ||
                (p.locatie || '').toLowerCase().includes(search) ||
                (p.cod_proiect || '').toLowerCase().includes(search) ||
                (p.producator || '').toLowerCase().includes(search)
            );
        }

        renderProjects(projects);
    } catch (e) {
        console.error('Failed to load projects:', e);
        showToast('Eroare la încărcarea proiectelor', 'error');
    } finally {
        clearTimeout(slowTimer);
        if (skeleton) skeleton.style.display = 'none';
        if (table) table.style.display = 'table';
    }
}

function renderProjects(projects) {
    const tbody = document.getElementById('projects-tbody');
    const emptyState = document.getElementById('empty-projects');
    const tableContainer = document.getElementById('projects-table-container');

    // Sort
    const _sort = (arr) => {
        if (sortCol && sortDir > 0) {
            arr.sort((a, b) => {
                let valA = a[sortCol] || '';
                let valB = b[sortCol] || '';
                if (typeof valA === 'string') valA = valA.toLowerCase();
                if (typeof valB === 'string') valB = valB.toLowerCase();
                let cmp = 0;
                if (valA < valB) cmp = -1;
                else if (valA > valB) cmp = 1;
                return sortDir === 2 ? -cmp : cmp;
            });
        }
        return arr;
    };

    // Split into active and archived (finalized).
    // When user explicitly filters by status, archive is hidden.
    const statusFilter = document.getElementById('filter-status')?.value || '';
    const activeProjects = _sort(projects.filter(p => p.status !== 'finalizat'));
    const archivedProjects = _sort(projects.filter(p => p.status === 'finalizat'));

    // Archive section
    const archSection = document.getElementById('projects-archive-section');
    const archTbody = document.getElementById('projects-archive-tbody');
    const archCount = document.getElementById('projects-archive-count');
    if (archSection && archTbody) {
        if (archivedProjects.length > 0 && !statusFilter) {
            archSection.style.display = 'block';
            archCount.textContent = archivedProjects.length;
            archTbody.innerHTML = archivedProjects.map(p => `
                <tr class="clickable-row" onclick="showProjectDetail('${p.id}')" title="${escapeHtml(p.nume)}">
                    <td title="${escapeHtml(p.nume)}">${escapeHtml(p.nume)}</td>
                    <td title="${escapeHtml(p.client || '')}">${escapeHtml(p.client || '-')}</td>
                    <td><span class="badge ${(p.tip || 'pif').toLowerCase()}">${p.tip || 'PIF'}</span></td>
                    <td title="${escapeHtml(p.producator || '')}">${escapeHtml(p.producator || '-')}</td>
                    <td>${p.data_finalizare || p.data_incepere || '-'}</td>
                </tr>
            `).join('');
        } else {
            archSection.style.display = 'none';
        }
    }

    if (activeProjects.length === 0) {
        tableContainer.style.display = 'none';
        emptyState.style.display = archivedProjects.length === 0 ? 'block' : 'none';
        // Mobile card list — clear it
        const mc = document.getElementById('projects-card-list');
        if (mc) mc.innerHTML = '';
        return;
    }

    {
        const projects = activeProjects;
        tableContainer.style.display = 'block';
        emptyState.style.display = 'none';

        tbody.innerHTML = projects.map(p => `
            <tr class="clickable-row" onclick="showProjectDetail('${p.id}')" title="${escapeHtml(p.nume)}">
                <td style="width:40px; text-align:center;">
                    <input type="checkbox" class="batch-checkbox project-row-checkbox" data-project-id="${p.id}" style="display:none;" onclick="event.stopPropagation(); toggleProjectSelection('${p.id}')">
                </td>
                <td title="${escapeHtml(p.nume)}">${escapeHtml(p.nume)}</td>
                <td title="${escapeHtml(p.client)}">${escapeHtml(p.client)}</td>
                <td><span class="badge ${(p.tip || 'pif').toLowerCase()}">${p.tip || 'PIF'}</span></td>
                <td title="${escapeHtml(p.producator)}">${escapeHtml(p.producator)}</td>
                <td><span class="badge ${p.status}">${getStatusLabel(p.status)}</span></td>
                <td>${p.data_incepere || '-'}</td>
            </tr>
        `).join('');

        // Mobile card view
        let cardList = document.getElementById('projects-card-list');
        if (!cardList) {
            cardList = document.createElement('div');
            cardList.id = 'projects-card-list';
            cardList.className = 'projects-card-list';
            document.getElementById('projects-table-container').parentNode
                .insertBefore(cardList, document.getElementById('projects-table-container'));
        }
        cardList.innerHTML = projects.map(p => `
            <div class="project-card-mobile" onclick="showProjectDetail('${p.id}')">
                <div class="pcm-header">
                    <div class="pcm-name">${escapeHtml(p.nume)}</div>
                    <span class="badge ${p.status}">${getStatusLabel(p.status)}</span>
                </div>
                <div class="pcm-meta">
                    <span><i data-lucide="user"></i> ${escapeHtml(p.client || '-')}</span>
                    <span class="badge ${(p.tip||'pif').toLowerCase()}">${p.tip||'PIF'}</span>
                    <span><i data-lucide="cpu"></i> ${escapeHtml(p.producator || '-')}</span>
                    ${p.data_incepere ? `<span><i data-lucide="calendar"></i> ${p.data_incepere}</span>` : ''}
                </div>
            </div>
        `).join('');
    }
}

function showNewProjectForm() {
    document.getElementById('project-id').value = '';
    document.getElementById('project-form').reset();
    document.querySelectorAll('.project-type-btn').forEach(btn => btn.classList.remove('selected'));
    document.getElementById('form-title').textContent = 'Proiect nou';
    const jd = document.getElementById('jurnal-data');
    if (jd) jd.value = new Date().toISOString().split('T')[0];
    document.getElementById('new-project-form').classList.add('active');
    initTemplateSelector();
    loadClientList();
    setTimeout(() => { initFlatpickr('#p-data-start'); initFlatpickr('#p-data-est'); }, 50);
}

function hideNewProjectForm() {
    document.getElementById('new-project-form').classList.remove('active');
}

async function saveProject(event) {
    event.preventDefault();

    const typeEl = document.querySelector('input[name="project-type"]:checked');
    if (!typeEl) {
        showToast('Selectați tipul proiectului!', true);
        return;
    }

    const id = document.getElementById('project-id').value;
    const projectType = typeEl.value;

    const projectData = {
        tip: projectType,
        nume: document.getElementById('p-nume').value,
        client: document.getElementById('p-client').value,
        locatie: document.getElementById('p-locatie').value,
        status: document.getElementById('p-status').value,
        producator: document.getElementById('p-producator').value,
        echipament_principal: document.getElementById('p-tip').value,
        data_incepere: document.getElementById('p-data-start').value,
        deadline: document.getElementById('p-data-est').value,
        observatii: document.getElementById('p-observatii').value,
        nr_comanda: document.getElementById('p-nr-comanda').value,
        nr_contract: document.getElementById('p-nr-contract').value
    };

    try {
        if (id) {
            await apiPut(`/proiecte/${id}`, projectData);
            showToast('Proiect actualizat!');
        } else {
            await apiPost('/proiecte', projectData);
            showToast('Proiect creat!');
        }

        hideNewProjectForm();
        await loadProjects();
        await updateStats();
        if (id && currentProjectId) {
            await showProjectDetail(currentProjectId);
        }
    } catch (e) {
        console.error('Failed to save project:', e);
        showToast('Eroare la salvarea proiectului', true);
    }
}

async function showProjectDetail(projectId) {
    // If invoked from another tab (Acasa cards), switch to Proiecte first so detail
    // view is visible. switchTab('proiecte') resets currentProjectId to null, so we
    // MUST switch BEFORE assigning currentProjectId. Otherwise click-from-home leaves
    // currentProjectId null and every subsequent action (status pill, addTodo,
    // saveServiceField, changeProjectStatus, ...) silently early-returns.
    const proiecteTab = document.getElementById('tab-proiecte');
    if (proiecteTab && !proiecteTab.classList.contains('active')) {
        switchTab('proiecte');
    }
    currentProjectId = projectId;

    try {
        const project = await apiGet(`/proiecte/${projectId}`);

        // Fill detail view
        document.getElementById('detail-nume').textContent = project.nume;
        document.getElementById('detail-client').textContent = project.client || '';

        // Render clickable status pills
        renderProjectStatusPills(project.status || 'in_lucru');

        // Set print attributes
        const detailView = document.getElementById('project-detail-view');
        detailView.setAttribute('data-print-date', new Date().toLocaleDateString('ro-RO'));
        detailView.setAttribute('data-project-name', project.nume);
        detailView.setAttribute('data-tip', project.tip || 'PIF');

        // Show/hide sections based on type
        const isPIF = project.tip === 'PIF';
        const isService = project.tip === 'Service';

        // PIF sections
        const pifObs = document.getElementById('pif-observatii-section');
        const checklist = document.getElementById('checklist-section');
        if (pifObs) pifObs.style.display = isPIF ? 'block' : 'none';
        if (checklist) checklist.style.display = isPIF ? 'block' : 'none';

        // Service sections
        const beforeAfter = document.getElementById('before-after-section');
        if (beforeAfter) beforeAfter.style.display = isService ? 'grid' : 'none';

        // BEGIN: PV (owned by spawned-pv session)
        const pvBtn = document.getElementById('btn-genereaza-pv');
        if (pvBtn) {
            const supportsPv = isService || isPIF;
            pvBtn.style.display = supportsPv ? 'inline-flex' : 'none';
            window.__pvDispatch = function (pid) {
                if (isService && window.openPvServiceModal) return openPvServiceModal(pid);
                if (isPIF && window.openPvPifModal) return openPvPifModal(pid);
            };
        }
        // END: PV

        // Common sections
        const timerJurnal = document.getElementById('timer-jurnal-section');
        const atasamente = document.getElementById('attachments-section');
        if (timerJurnal) timerJurnal.style.display = 'block';
        if (atasamente) atasamente.style.display = 'block';

        const toHide = ['service-fields', 'observations-section'];
        toHide.forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });

        // Service fields
        if (isService) {
            document.getElementById('detail-confirmat-client').checked = project.confirmat_client == 1;
            document.getElementById('detail-client-nume').value = project.client_nume_confirmare || '';
            document.getElementById('service-before').value = project.service_before || '';
            document.getElementById('service-after').value = project.service_after || '';
        }

        // PIF fields
        if (isPIF) {
            document.getElementById('pif-observatii').value = project.observatii || '';
        }

        // Render long-text preview cards now that hidden textareas hold values.
        renderAllLongTextPreviews();

        // Show/hide checklist section (only for PIF)
        document.getElementById('checklist-section').style.display = isPIF ? 'block' : 'none';

        // Load related data (including equipment)
        await Promise.all([
            loadTodos(projectId),
            loadJurnal(projectId),
            loadAttachments(projectId),
            isPIF ? loadChecklist(projectId) : Promise.resolve()
        ]);
        await loadEchipamente(projectId);

        // Switch views
        document.getElementById('project-list-view').classList.add('hidden');
        document.getElementById('project-detail-view').classList.add('active');

        setTimeout(() => { initFlatpickr('#todo-scadenta'); initFlatpickr('#jurnal-data'); }, 50);

    } catch (e) {
        console.error('Failed to load project:', e);
        showToast('Eroare la încărcarea detaliilor', true);
    }

    // Mobile: add back button at top if not exists
    if (!document.getElementById('mobile-back-btn')) {
        const backBtn = document.createElement('button');
        backBtn.id = 'mobile-back-btn';
        backBtn.className = 'btn btn-secondary btn-back-mobile';
        backBtn.innerHTML = '← Înapoi la Proiecte';
        backBtn.onclick = showProjectList;
        document.getElementById('project-detail-view').prepend(backBtn);
    }
    // Initialize accordions for mobile
    initAccordions();
}

function showProjectList() {
    currentProjectId = null;
    document.getElementById('project-list-view').classList.remove('hidden');
    document.getElementById('project-detail-view').classList.remove('active');
    loadProjects();
    updateStats();
}

function goHome() {
    const detailView = document.getElementById('project-detail-view');
    if (detailView && detailView.classList.contains('active')) {
        showProjectList();
    }
    switchTab('taskuri');
}

async function editCurrentProject() {
    if (!currentProjectId) return;

    try {
        const project = await apiGet(`/proiecte/${currentProjectId}`);
        document.getElementById('project-id').value = project.id;
        document.getElementById('p-nume').value = project.nume || '';
        document.getElementById('p-client').value = project.client || '';
        document.getElementById('p-locatie').value = project.locatie || '';
        document.getElementById('p-status').value = project.status || 'in_lucru';
        document.getElementById('p-producator').value = project.producator || 'Altul';
        document.getElementById('p-tip').value = project.echipament_principal || '';
        document.getElementById('p-data-start').value = project.data_incepere || '';
        document.getElementById('p-data-est').value = project.deadline || '';
        document.getElementById('p-observatii').value = project.observatii || '';
        document.getElementById('p-nr-comanda').value = project.nr_comanda || '';
        document.getElementById('p-nr-contract').value = project.nr_contract || '';

        const typeBtn = document.getElementById(
            project.tip === 'Service' ? 'type-service-btn' : 'type-pif-btn'
        );
        if (typeBtn) {
            document.querySelectorAll('.project-type-btn').forEach(b => b.classList.remove('selected'));
            typeBtn.classList.add('selected');
            typeBtn.querySelector('input[type="radio"]').checked = true;
        }

        document.getElementById('form-title').textContent = 'Editează proiect';
        document.getElementById('new-project-form').classList.add('active');
    } catch (e) {
        console.error('Failed to load project:', e);
        showToast('Eroare la încărcarea proiectului', true);
    }
}

async function deleteCurrentProject() {
    if (!currentProjectId) return;

    showConfirm('Sigur doriți să ștergeți acest proiect? Această acțiune nu poate fi anulată.', async () => {
        try {
            await apiDelete(`/proiecte/${currentProjectId}`);
            showToast('Proiect șters!');
            showProjectList();
        } catch (e) {
            console.error('Failed to delete project:', e);
            showToast('Eroare la ștergerea proiectului', true);
        }
    });
}


async function saveServiceField(field, value) {
    if (!currentProjectId) return;

    try {
        await apiPut(`/proiecte/${currentProjectId}`, { [field]: value });
        showToast('Salvat!');
    } catch (e) {
        console.error('Failed to update service field:', e);
        showToast('Eroare la salvare', true);
    }
}

// ============ LONG-TEXT EDITOR MODAL ============
// Used by PIF Observatii, Service Constatari inainte, Service Actiuni & rezultat.
// One DOM modal serves all three fields. State of the field-in-edit is held on the
// modal element so multiple openings are stateless from the caller's perspective.

let _longTextActiveField = null;  // current hidden textarea id being edited

function renderLongTextPreview(textareaId) {
    const ta = document.getElementById(textareaId);
    if (!ta) return;
    const scope = ta.closest('.form-group, .detail-section-body') || ta.parentElement;
    const preview = scope?.querySelector('.long-text-preview');
    if (!preview) return;
    const raw = ta.value || '';
    // Render HTML if stored as such, otherwise wrap plain text in paragraphs so
    // line breaks survive visually inside the preview card.
    if (raw.trim() === '') {
        preview.textContent = '';
        preview.classList.add('is-empty');
    } else {
        // SECURITY: never trust stored HTML — render as plain text with <br>.
        // Hermes assistant can write to these fields; raw HTML render would be
        // a stored XSS vector via _looksLikeHtml's permissive tag-sniff.
        preview.innerHTML = _plainToHtml(raw);
        preview.classList.remove('is-empty');
    }
    const counter = scope?.querySelector('[data-count-for="' + textareaId + '"]');
    if (counter) {
        // Char count based on visible text, not HTML markup
        const tmp = document.createElement('div');
        tmp.innerHTML = raw;
        counter.textContent = (tmp.innerText || '').length + ' caractere';
    }
    return;
}

function renderAllLongTextPreviews() {
    ['service-before', 'service-after', 'pif-observatii'].forEach(renderLongTextPreview);
}

// Detect whether the stored value is HTML or plain text. Older entries are plain.
function _looksLikeHtml(s) { return /<\/?(p|br|div|h[1-6]|ul|ol|li|strong|b|em|i|u|a|hr|blockquote)\b/i.test(s || ''); }
function _plainToHtml(s) {
    return (s || '').split(/\n\n+/).map(p => {
        const lines = p.replace(/\r/g, '').replace(/\n/g, '<br>');
        return `<p>${lines}</p>`;
    }).join('');
}
function _escAttr(s) { return (s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function openLongTextEditor(fieldId, title, iconName) {
    const ta = document.getElementById(fieldId);
    if (!ta) return;
    _longTextActiveField = fieldId;

    const modal = document.getElementById('long-text-modal');
    document.getElementById('ltm-title-text').textContent = title || 'Editor';
    const iconEl = document.getElementById('ltm-title-icon');
    if (iconEl && iconName) iconEl.setAttribute('data-lucide', iconName);

    const editor = document.getElementById('ltm-editor');
    const raw = ta.value || '';
    // SECURITY: never trust stored HTML — render as plain text with <br>.
    // Hermes assistant can write to these fields; raw HTML render would be
    // a stored XSS vector via _looksLikeHtml's permissive tag-sniff.
    editor.innerHTML = _plainToHtml(raw);
    _ltmUpdateCounter();

    modal.classList.add('active');
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
    setTimeout(() => editor.focus(), 50);

    editor.oninput = _ltmUpdateCounter;
    editor.onkeydown = (e) => {
        if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) { e.preventDefault(); saveLongText(); }
        else if (e.key === 'Escape') { e.preventDefault(); closeLongTextEditor(); }
    };
}

function closeLongTextEditor() {
    const modal = document.getElementById('long-text-modal');
    modal.classList.remove('active');
    _longTextActiveField = null;
}

async function saveLongText() {
    if (!_longTextActiveField) return;
    const ta = document.getElementById(_longTextActiveField);
    const editor = document.getElementById('ltm-editor');
    if (!ta || !editor) return;
    // Save the inner HTML — render as HTML on preview cards.
    const value = (editor.innerHTML || '').trim();
    ta.value = value;
    const backendField = (_longTextActiveField === 'pif-observatii') ? 'observatii' : _longTextActiveField.replace('-', '_');
    await saveServiceField(backendField, value);
    renderLongTextPreview(_longTextActiveField);
    closeLongTextEditor();
}

async function copyLongTextContent() {
    const editor = document.getElementById('ltm-editor');
    if (!editor) return;
    // Copy plain text version of the editor content for cross-app pasting.
    const text = editor.innerText || '';
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            const tmp = document.createElement('textarea');
            tmp.value = text;
            document.body.appendChild(tmp);
            tmp.select();
            document.execCommand('copy');
            tmp.remove();
        }
        showToast('Copiat în clipboard');
    } catch (e) {
        console.error('Copy failed:', e);
        showToast('Eroare la copiere', true);
    }
}

function _ltmUpdateCounter() {
    const editor = document.getElementById('ltm-editor');
    const counter = document.getElementById('ltm-counter');
    if (editor && counter) counter.textContent = (editor.innerText || '').length + ' caractere';
}

// WYSIWYG toolbar — uses document.execCommand which works in all browsers
// for contenteditable elements (deprecated in spec but still supported).
function ltmExec(cmd, value) {
    const editor = document.getElementById('ltm-editor');
    if (!editor) return;
    editor.focus();
    try { document.execCommand(cmd, false, value || null); } catch (e) {}
    _ltmUpdateCounter();
}
function ltmFormatBlock(tag) {
    // Firefox needs <h1>, Chrome accepts both h1 and H1
    ltmExec('formatBlock', tag);
}
function ltmInsertLink() {
    const url = prompt('URL-ul link-ului:');
    if (!url) return;
    ltmExec('createLink', url);
}
function ltmInsertDate() {
    const d = new Date().toLocaleDateString('ro-RO', { day: '2-digit', month: '2-digit', year: 'numeric' });
    ltmExec('insertText', d + ' ');
}
function ltmInsertSeparator() {
    ltmExec('insertHTML', '<hr>');
}

// Close on backdrop click
document.addEventListener('click', (e) => {
    const modal = document.getElementById('long-text-modal');
    if (modal && modal.classList.contains('active') && e.target === modal) {
        closeLongTextEditor();
    }
});

// ============ TASKS / TODOS ============

let draggedTaskId = null;
// Cached subtasks: { [taskId]: [subtask, ...] }
let _taskSubtasksCache = {};

// ─── Task card (tcard) — DOM glue for the unified renderer in core.js ───
// Persistent expand state survives re-renders triggered by inline saves.
const _expandedTaskIds = new Set();

function _tcardToggleExpand(taskId, cardEl) {
    if (_expandedTaskIds.has(taskId)) {
        _expandedTaskIds.delete(taskId);
        // Collapse via re-render of this single card.
        _tcardRerenderCard(cardEl);
    } else {
        _expandedTaskIds.add(taskId);
        const kind = cardEl.dataset.tcardKind || 'global';
        _tcardEnsureSubtasks(taskId, kind).then(() => _tcardRerenderCard(cardEl));
    }
}

function _tcardRerenderCard(cardEl) {
    const taskId = cardEl.dataset.taskId;
    const kind = cardEl.dataset.tcardKind || 'global';
    let task;
    try { task = JSON.parse(cardEl.dataset.taskJson || '{}'); }
    catch (e) { return; }
    task._tcard_expanded = _expandedTaskIds.has(taskId);
    const tmp = document.createElement('div');
    tmp.innerHTML = renderTaskCard(task, { kind, projectId: kind === 'project' ? currentProjectId : null });
    const fresh = tmp.firstElementChild;
    if (fresh) {
        cardEl.replaceWith(fresh);
        if (window.lucide) try { window.lucide.createIcons(); } catch {}
    }
}

async function _tcardEnsureSubtasks(taskId, kind) {
    if (_taskSubtasksCache[taskId] !== undefined && _taskSubtasksCache[taskId].length >= 0) return;
    try {
        const subs = await apiGet(`/tasks/${encodeURIComponent(taskId)}/subtasks`);
        _taskSubtasksCache[taskId] = Array.isArray(subs) ? subs : [];
    } catch (e) {
        _taskSubtasksCache[taskId] = [];
    }
}

function _tcardToggleMenu(taskId, btn) {
    const card = btn.closest('.tcard');
    if (!card) return;
    const wasOpen = card.classList.contains('tcard--menu-open');
    _tcardCloseMenus();
    if (!wasOpen) card.classList.add('tcard--menu-open');
}

function _tcardCloseMenus() {
    document.querySelectorAll('.tcard.tcard--menu-open').forEach(c => c.classList.remove('tcard--menu-open'));
}

function _tcardOpenManualTime(kind, taskId) {
    if (typeof openManualTimeForTask === 'function') openManualTimeForTask(kind, taskId);
    else if (typeof openManualTimeModal === 'function') openManualTimeModal(kind === 'project' ? 'task' : kind, taskId);
    else showToast('Intrare manuală indisponibilă', true);
}

// Outside-click closes any open tcard menu.
document.addEventListener('click', (e) => {
    if (!e.target.closest('.tcard__menu, .tcard__menu-btn')) _tcardCloseMenus();
});

async function loadTodos(projectId) {
    try {
        const tasks = await apiGet(`/proiecte/${projectId}/tasks`);
        // Pre-fetch subtasks for all tasks that have them (in parallel)
        const tasksWithSubs = tasks.filter(t => t.subtask_total > 0);
        await Promise.all(tasksWithSubs.map(async (t) => {
            try {
                const subs = await apiGet(`/tasks/${encodeURIComponent(t.id)}/subtasks`);
                _taskSubtasksCache[t.id] = Array.isArray(subs) ? subs : [];
            } catch (e) {
                _taskSubtasksCache[t.id] = [];
            }
        }));
        const filterStatus = document.getElementById('todo-filter-status')?.value || '';
        const filterPrioritate = document.getElementById('todo-filter-prioritate')?.value || '';
        const sortBy = document.getElementById('todo-sort')?.value || 'prioritate';
        let filtered = tasks;
        if (filterStatus) filtered = filtered.filter(t => t.status === filterStatus);
        if (filterPrioritate) filtered = filtered.filter(t => t.prioritate === filterPrioritate);
        const priorityOrder = { 'Urgent': 0, 'Normal': 1, 'Minor': 2 };
        const statusOrder = { 'to_do': 0, 'in_lucru': 1, 'done': 2 };
        filtered.sort((a, b) => {
            switch (sortBy) {
                case 'prioritate': return (priorityOrder[a.prioritate] ?? 1) - (priorityOrder[b.prioritate] ?? 1);
                case 'scadenta': if (!a.data_scadenta) return 1; if (!b.data_scadenta) return -1; return a.data_scadenta.localeCompare(b.data_scadenta);
                case 'status': return (statusOrder[a.status] ?? 0) - (statusOrder[b.status] ?? 0);
                case 'creat': return new Date(b.created_at) - new Date(a.created_at);
                default: return 0;
            }
        });
        renderTodos(filtered);
    } catch (e) { console.error('Failed to load tasks:', e); }
}

function renderTodos(tasks) {
    const container = document.getElementById('todo-list');
    if (!tasks.length) {
        container.innerHTML = '<p style="color: var(--text2); font-size:0.85rem;">Nu există task-uri.</p>';
        return;
    }
    const active = tasks.filter(t => t.status !== 'done');
    const done = tasks.filter(t => t.status === 'done');
    done.sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || ''));

    const renderOne = (task) => {
        task._tcard_expanded = _expandedTaskIds.has(task.id);
        return renderTaskCard(task, { kind: 'project', projectId: currentProjectId });
    };

    let html = '<div class="tcard-list">' + active.map(renderOne).join('') + '</div>';
    if (done.length > 0) {
        const collapsedKey = `pif:todo-done-collapsed:${currentProjectId}`;
        const isCollapsed = localStorage.getItem(collapsedKey) !== '0';
        html += `<div class="tcard-done-sep" onclick="toggleTodoDoneCollapse('${currentProjectId}')" data-collapsed="${isCollapsed ? '1' : '0'}">
            <i data-lucide="chevron-${isCollapsed ? 'right' : 'down'}"></i>
            <span>Finalizate (${done.length})</span>
        </div>`;
        html += `<div class="tcard-done-group${isCollapsed ? ' collapsed' : ''}"><div class="tcard-list">${done.map(renderOne).join('')}</div></div>`;
    }
    container.innerHTML = html;
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
    initTaskDragDrop();
}

// Status pills in project detail header — click to change status without opening
// the full edit modal. Optimistic update + save.
const _PROJECT_STATUSES = [
    { key: 'in_lucru', label: 'În Lucru' },
    { key: 'in_asteptare', label: 'În Așteptare' },
    { key: 'blocat', label: 'Blocat' },
    { key: 'finalizat', label: 'Finalizat' },
];
function renderProjectStatusPills(currentStatus) {
    const container = document.getElementById('detail-status-pills');
    if (!container) return;
    container.innerHTML = _PROJECT_STATUSES.map(s => `
        <span class="detail-status-pill ${s.key === currentStatus ? 'active ' + s.key : ''}"
              onclick="changeProjectStatus('${s.key}')">${s.label}</span>
    `).join('');
}
async function changeProjectStatus(newStatus) {
    if (!currentProjectId) return;
    try {
        await apiPut(`/proiecte/${currentProjectId}`, { status: newStatus });
        renderProjectStatusPills(newStatus);
        showToast('Status actualizat');
        // Refresh stats if user is using them
        if (typeof updateStats === 'function') updateStats();
    } catch (e) {
        console.error('Failed to change status:', e);
        showToast('Eroare la schimbarea statusului', true);
    }
}

function toggleTodoDoneCollapse(projectId) {
    const key = `pif:todo-done-collapsed:${projectId}`;
    const isCollapsed = localStorage.getItem(key) !== '0';
    localStorage.setItem(key, isCollapsed ? '0' : '1');
    const divider = document.querySelector('#todo-list .tcard-done-sep');
    const group = document.querySelector('#todo-list .tcard-done-group');
    if (divider && group) {
        divider.setAttribute('data-collapsed', isCollapsed ? '0' : '1');
        const icon = divider.querySelector('[data-lucide]');
        if (icon) {
            icon.setAttribute('data-lucide', isCollapsed ? 'chevron-down' : 'chevron-right');
            if (window.lucide) try { window.lucide.createIcons(); } catch {}
        }
        group.classList.toggle('collapsed', !isCollapsed);
    }
}

function initTaskDragDrop() {
    const container = document.getElementById('todo-list');
    if (!container) return;
    const items = container.querySelectorAll('.tcard[data-task-id]');
    items.forEach(item => {
        item.setAttribute('draggable', 'true');
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragend', handleDragEnd);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragleave', handleDragLeave);
    });
}

function handleDragStart(e) {
    draggedTaskId = e.target.dataset.taskId;
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    document.querySelectorAll('.todo-item').forEach(item => {
        item.classList.remove('drag-over');
    });
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const item = e.target.closest('.todo-item');
    if (item && !item.classList.contains('dragging')) {
        item.classList.add('drag-over');
    }
}

function handleDragLeave(e) {
    const item = e.target.closest('.todo-item');
    if (item) {
        item.classList.remove('drag-over');
    }
}

async function handleDrop(e) {
    e.preventDefault();
    const targetItem = e.target.closest('.todo-item');
    if (!targetItem || !draggedTaskId) return;

    targetItem.classList.remove('drag-over');

    const draggedItem = document.querySelector(`[data-task-id="${draggedTaskId}"]`);
    if (!draggedItem) return;

    const allItems = Array.from(document.querySelectorAll('.todo-item:not(.completed)'));
    const draggedIndex = allItems.indexOf(draggedItem);
    const targetIndex = allItems.indexOf(targetItem);

    if (draggedIndex === targetIndex) return;

    // Update ordine for all affected tasks
    const updates = [];
    if (draggedIndex < targetIndex) {
        // Moving down: decrease ordine for items between old and new position
        for (let i = draggedIndex + 1; i <= targetIndex; i++) {
            updates.push({ id: allItems[i].dataset.taskId, ordine: i - 1 });
        }
    } else {
        // Moving up: increase ordine for items between new and old position
        for (let i = targetIndex; i < draggedIndex; i++) {
            updates.push({ id: allItems[i].dataset.taskId, ordine: i + 1 });
        }
    }
    updates.push({ id: draggedTaskId, ordine: targetIndex });

    // Apply updates
    for (const update of updates) {
        try {
            await apiPut(`/tasks/${update.id}`, { ordine: update.ordine });
        } catch (err) {
            console.error('Failed to update task order:', err);
        }
    }

    // Reload todos to reflect new order
    loadTodos(currentProjectId);
}

async function addTodo() {
    const titleEl = document.getElementById('todo-title');
    const titlu = (titleEl?.value || '').trim();
    if (!titlu) return;
    const prioritate = document.getElementById('todo-priority')?.value || 'normal';
    const status = document.getElementById('todo-status')?.value || 'to_do';
    const scadentaEl = document.getElementById('todo-scadenta');
    const data_scadenta = (scadentaEl?.value || '').trim();
    try {
        const result = await apiPost(`/proiecte/${currentProjectId}/tasks`, { titlu, prioritate, status, data_scadenta });
        if (titleEl) titleEl.value = '';
        if (scadentaEl) {
            scadentaEl.value = '';
            if (scadentaEl._flatpickr) scadentaEl._flatpickr.clear();
        }
        loadTodos(currentProjectId);
        if (result !== null) {
            showToast('Task adăugat!');
        }
    } catch (e) {
        console.error('addTodo failed:', e);
        showToast('Eroare la adăugarea taskului', true);
    }
}

async function toggleTodo(taskId, checked) {
    try {
        await apiPut(`/tasks/${taskId}`, {
            status: checked ? 'done' : 'to_do',
            data_finalizare: checked ? new Date().toISOString() : ''
        });
        loadTodos(currentProjectId);
    } catch (e) {
        console.error('Failed to toggle todo:', e);
    }
}

async function deleteTodo(taskId) {
    try {
        await apiDelete(`/tasks/${taskId}`);
        loadTodos(currentProjectId);
    } catch (e) {
        console.error('Failed to delete todo:', e);
    }
}

// ============ TASK EDIT MODAL ============

let taskEditFlatpickr = null;
let _taskTimerInterval = null;       // 1s display tick for the per-task timer
let _taskTimerRunningSince = null;   // epoch ms when the running session started
let _taskTimerBaseTotal = 0;         // accumulated seconds from finished sessions
let _taskSubtasks = [];

// Set a cs-enhance <select> value and sync its custom dropdown display.
function _csSet(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = value;
    el.dispatchEvent(new Event('change'));
}

// The task modal is shared between project tasks and daily (global) tasks.
let _taskModalMode = 'project';   // 'project' | 'global'

function openTaskEditModal(task) {
    _taskModalMode = 'project';
    document.getElementById('task-edit-categorie-row').style.display = 'none';
    document.getElementById('task-edit-id').value = task.id;
    document.getElementById('task-edit-titlu').value = task.titlu || '';
    document.getElementById('task-edit-descriere').value = task.descriere || '';
    _csSet('task-edit-status', task.status || 'to_do');
    _csSet('task-edit-recurenta', task.recurenta || '');
    selectTaskPriority((task.prioritate || 'normal').toLowerCase());
    document.getElementById('task-edit-modal').classList.add('active');
    loadSubtasks(task.id);
    loadTaskTimer(task.id);   // shows the time-row
    setTimeout(() => {
        if (taskEditFlatpickr) taskEditFlatpickr.destroy();
        taskEditFlatpickr = initFlatpickr('#task-modal-scadenta');
        if (task.data_scadenta) taskEditFlatpickr.setDate(task.data_scadenta); else taskEditFlatpickr.clear();
    }, 50);
}

// Open the shared modal for a daily (global) task.
async function openGtEditModal(taskId) {
    try {
        const task = await apiGet(`/global-tasks/${taskId}`);
        _taskModalMode = 'global';
        document.getElementById('task-edit-id').value = task.id;
        document.getElementById('task-edit-titlu').value = task.titlu || '';
        document.getElementById('task-edit-descriere').value = task.descriere || '';
        _csSet('task-edit-status', task.status || 'to_do');
        _csSet('task-edit-recurenta', task.recurenta || '');
        selectTaskPriority((task.prioritate || 'normal').toLowerCase());
        // Global tasks have a free-text category and (now) their own timer.
        document.getElementById('task-edit-categorie-row').style.display = 'block';
        document.getElementById('task-edit-categorie').value = task.categorie || '';
        loadTaskTimer(task.id);
        document.getElementById('task-edit-modal').classList.add('active');
        loadSubtasks(task.id);
        setTimeout(() => {
            if (taskEditFlatpickr) taskEditFlatpickr.destroy();
            taskEditFlatpickr = initFlatpickr('#task-modal-scadenta');
            if (task.data_scadenta) taskEditFlatpickr.setDate(task.data_scadenta); else taskEditFlatpickr.clear();
        }, 50);
    } catch (e) {
        console.error('openGtEditModal failed:', e);
        showToast('Eroare la deschiderea taskului', true);
    }
}

function closeTaskEditModal() {
    document.getElementById('task-edit-modal').classList.remove('active');
    if (taskEditFlatpickr) { taskEditFlatpickr.destroy(); taskEditFlatpickr = null; }
    if (_taskTimerInterval) { clearInterval(_taskTimerInterval); _taskTimerInterval = null; }
    // Refresh whichever list this modal belonged to.
    if (_taskModalMode === 'global') {
        if (typeof loadGlobalTasks === 'function') loadGlobalTasks();
    } else if (currentProjectId) {
        loadTodos(currentProjectId);
    }
}

async function saveTaskFromModal() {
    const id = document.getElementById('task-edit-id').value;
    if (!id) return;
    const titlu = document.getElementById('task-edit-titlu').value.trim();
    const prioritate = document.getElementById('task-edit-prioritate').value;
    const status = document.getElementById('task-edit-status').value;
    const descriere = document.getElementById('task-edit-descriere').value;
    const recurenta = document.getElementById('task-edit-recurenta').value;
    const data_scadenta = (document.getElementById('task-modal-scadenta').value || '').trim();
    if (!titlu) { showToast('Titlul nu poate fi gol', true); return; }
    try {
        let res;
        if (_taskModalMode === 'global') {
            // Daily tasks store priority capitalised (Normal/Urgent/Minor).
            const prioCap = prioritate.charAt(0).toUpperCase() + prioritate.slice(1);
            const categorie = (document.getElementById('task-edit-categorie').value || '').trim() || 'General';
            res = await apiPut(`/global-tasks/${id}`, { titlu, prioritate: prioCap, status, categorie, data_scadenta, descriere, recurenta });
        } else {
            res = await apiPut(`/tasks/${id}`, { titlu, prioritate, status, data_scadenta, descriere, recurenta });
        }
        showToast((res && res.recurring_spawned)
            ? 'Task finalizat — următoarea apariție creată'
            : 'Task actualizat');
        closeTaskEditModal();
    } catch (e) {
        console.error('Save task error:', e);
        showToast('Eroare la salvare', true);
    }
}

async function deleteTaskFromModal() {
    const id = document.getElementById('task-edit-id').value;
    if (!id) return;
    const ok = await pifAsk({
        title: 'Șterge task',
        message: 'Sigur ștergi acest task?',
        okLabel: 'Șterge',
        danger: true
    });
    if (!ok) return;
    try {
        await apiDelete(_taskModalMode === 'global' ? `/global-tasks/${id}` : `/tasks/${id}`);
        closeTaskEditModal();
        showToast('Task șters');
    } catch (e) {
        showToast('Eroare la ștergere', true);
    }
}

function selectTaskPriority(val) {
    _csSet('task-edit-prioritate', (val || 'normal').toLowerCase());
}

// ── Subtasks (lightweight checklist inside the task modal) ──
async function loadSubtasks(taskId) {
    try {
        const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/subtasks`);
        const subs = await res.json();
        _taskSubtasks = Array.isArray(subs) ? subs : [];
    } catch (e) { _taskSubtasks = []; }
    renderSubtasks();
}

function renderSubtasks() {
    const listEl = document.getElementById('task-subtask-list');
    const progEl = document.getElementById('task-subtask-progress');
    if (!listEl) return;
    const total = _taskSubtasks.length;
    const done = _taskSubtasks.filter(s => s.done).length;
    if (progEl) progEl.textContent = total ? `(${done}/${total})` : '';
    listEl.innerHTML = _taskSubtasks.map(s => `
        <div class="task-subtask-item ${s.done ? 'done' : ''}">
            <input type="checkbox" ${s.done ? 'checked' : ''} onchange="toggleSubtask('${s.id}', this.checked)">
            <span class="task-subtask-titlu">${escapeHtml(s.titlu)}</span>
            <button class="task-subtask-del" onclick="deleteSubtask('${s.id}')" title="Șterge"><i data-lucide="x"></i></button>
        </div>`).join('');
    if (window.lucide) try { lucide.createIcons(); } catch (e) {}
}

async function addSubtask() {
    const taskId = document.getElementById('task-edit-id').value;
    const input = document.getElementById('task-subtask-input');
    const titlu = (input.value || '').trim();
    if (!taskId || !titlu) return;
    try {
        await apiPost(`/tasks/${taskId}/subtasks`, { titlu });
        input.value = '';
        loadSubtasks(taskId);
    } catch (e) { showToast('Eroare la adăugare subtask', true); }
}

async function toggleSubtask(subtaskId, done) {
    try {
        await apiPut(`/subtasks/${subtaskId}`, { done: done ? 1 : 0 });
        const s = _taskSubtasks.find(x => x.id === subtaskId);
        if (s) s.done = done ? 1 : 0;
        renderSubtasks();
    } catch (e) { showToast('Eroare', true); }
}

// Toggle subtask from the inline list (visible in todo list — no modal needed)
async function toggleSubtaskInline(subtaskId, done, parentTaskId) {
    try {
        await apiPut(`/subtasks/${subtaskId}`, { done: done ? 1 : 0 });
        // Update cache
        if (_taskSubtasksCache[parentTaskId]) {
            const s = _taskSubtasksCache[parentTaskId].find(x => x.id === subtaskId);
            if (s) s.done = done ? 1 : 0;
        }
        // Update the parent task's subtask counts (optimistic: update in current tasks array)
        // The parent task's subtask_done count will be refreshed on next loadTodos
        // For now, just re-render the inline subtasks
        const parentItem = document.querySelector(`[data-task-id-subtasks="${parentTaskId}"]`);
        if (parentItem) {
            const subtaskList = parentItem.querySelector('.todo-subtasks-list');
            if (subtaskList) {
                const subs = _taskSubtasksCache[parentTaskId] || [];
                subtaskList.innerHTML = subs.map(s => `
                    <div class="todo-subtask-item ${s.done ? 'done' : ''}" style="display:flex;align-items:center;gap:6px;padding:2px 0;font-size:0.82rem;color:var(--text-dim);">
                        <label class="subtask-touch-target" style="margin:0;padding:4px;border-radius:4px;">
                            <input type="checkbox" class="todo-checkbox" style="width:18px;height:18px;margin:0;cursor:pointer;" ${s.done ? 'checked' : ''}
                                onchange="event.stopPropagation(); toggleSubtaskInline('${s.id}', this.checked, '${parentTaskId}')">
                        </label>
                        <span style="${s.done ? 'text-decoration:line-through;opacity:0.6;' : ''}">${escapeHtml(s.titlu)}</span>
                    </div>`).join('');
            }
        }
    } catch (e) { showToast('Eroare la actualizare subtask', true); }
}

// Show/hide inline subtask add input
function toggleInlineSubtaskAdd(taskId) {
    const wrapper = document.getElementById(`inline-subtask-add-${taskId}`);
    if (!wrapper) return;
    const isVisible = wrapper.style.display !== 'none';
    // Hide all other inline add wrappers first
    document.querySelectorAll('.inline-subtask-wrapper').forEach(el => el.style.display = 'none');
    if (!isVisible) {
        wrapper.style.display = 'block';
        wrapper.querySelector('input').focus();
    }
}

// Add subtask inline (from the inline input field)
async function addSubtaskInline(taskId, titlu) {
    titlu = (titlu || '').trim();
    if (!titlu) return;
    try {
        await apiPost(`/tasks/${encodeURIComponent(taskId)}/subtasks`, { titlu });
        // Refresh subtasks cache
        const subs = await apiGet(`/tasks/${encodeURIComponent(taskId)}/subtasks`);
        _taskSubtasksCache[taskId] = Array.isArray(subs) ? subs : [];
        // Re-render the subtasks inline
        const parentItem = document.querySelector(`[data-task-id-subtasks="${taskId}"]`);
        if (parentItem) {
            const subtaskList = parentItem.querySelector('.todo-subtasks-list');
            if (subtaskList) {
                const allSubs = _taskSubtasksCache[taskId] || [];
                subtaskList.innerHTML = allSubs.map(s => `
                    <div class="todo-subtask-item ${s.done ? 'done' : ''}" style="display:flex;align-items:center;gap:6px;padding:2px 0;font-size:0.82rem;color:var(--text-dim);">
                        <label class="subtask-touch-target" style="margin:0;padding:4px;border-radius:4px;">
                            <input type="checkbox" class="todo-checkbox" style="width:18px;height:18px;margin:0;cursor:pointer;" ${s.done ? 'checked' : ''}
                                onchange="event.stopPropagation(); toggleSubtaskInline('${s.id}', this.checked, '${taskId}')">
                        </label>
                        <span style="${s.done ? 'text-decoration:line-through;opacity:0.6;' : ''}">${escapeHtml(s.titlu)}</span>
                    </div>`).join('');
            }
        }
        // Hide the add wrapper
        const wrapper = document.getElementById(`inline-subtask-add-${taskId}`);
        if (wrapper) wrapper.style.display = 'none';
        showToast('Subtask adăugat');
    } catch (e) { showToast('Eroare la adăugare subtask', true); }
}

// Toggle task timer from inline button in task list
let _inlineTimerIntervals = {};
async function toggleTaskTimerInline(taskId, isRunning, btnElement) {
    try {
        if (isRunning) {
            // Stop timer
            const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/timer/stop`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to stop timer');
            const data = await res.json();
            // Update button
            if (btnElement) {
                btnElement.classList.remove('running');
                btnElement.querySelector('.timer-icon').textContent = '▶';
                btnElement.querySelector('span:last-child').textContent = formatTimerDuration(data.total_secunde || 0);
            }
            // Clear interval
            if (_inlineTimerIntervals[taskId]) {
                clearInterval(_inlineTimerIntervals[taskId]);
                delete _inlineTimerIntervals[taskId];
            }
            showToast('Cronometru oprit');
        } else {
            // Start timer
            const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/timer/start`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to start timer');
            const data = await res.json();
            const startTime = new Date(data.start_time).getTime();
            // Update button
            if (btnElement) {
                btnElement.classList.add('running');
                btnElement.querySelector('.timer-icon').textContent = '⏸';
            }
            // Start interval to update elapsed time
            _inlineTimerIntervals[taskId] = setInterval(() => {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const btn = document.querySelector(`[data-task-id-subtasks="${taskId}"] .timer-btn`);
                if (btn) {
                    btn.querySelector('span:last-child').textContent = formatTimerDuration(elapsed);
                }
            }, 1000);
            showToast('Cronometru pornit');
        }
    } catch (e) {
        console.error('Timer error:', e);
        showToast('Eroare cronometru', true);
    }
}

// Global task versions for inline subtask add
function toggleInlineSubtaskAddGt(taskId) {
    const wrapper = document.getElementById(`inline-subtask-add-gt-${taskId}`);
    if (!wrapper) return;
    const isVisible = wrapper.style.display !== 'none';
    // Hide all other inline add wrappers first
    document.querySelectorAll('.inline-subtask-wrapper').forEach(el => el.style.display = 'none');
    if (!isVisible) {
        wrapper.style.display = 'block';
        wrapper.querySelector('input').focus();
    }
}

async function addSubtaskInlineGt(taskId, titlu) {
    titlu = (titlu || '').trim();
    if (!titlu) return;
    try {
        await apiPost(`/tasks/${encodeURIComponent(taskId)}/subtasks`, { titlu });
        // Refresh subtasks cache
        const subs = await apiGet(`/tasks/${encodeURIComponent(taskId)}/subtasks`);
        _taskSubtasksCache[taskId] = Array.isArray(subs) ? subs : [];
        // Re-render the subtasks inline
        const parentItem = document.querySelector(`[data-task-id-subtasks="${taskId}"]`);
        if (parentItem) {
            const subtaskList = parentItem.querySelector('.todo-subtasks-list');
            if (subtaskList) {
                const allSubs = _taskSubtasksCache[taskId] || [];
                subtaskList.innerHTML = allSubs.map(s => `
                    <div class="todo-subtask-item ${s.done ? 'done' : ''}" style="display:flex;align-items:center;gap:6px;padding:2px 0;font-size:0.82rem;color:var(--text-dim);">
                        <label class="subtask-touch-target" style="margin:0;padding:4px;border-radius:4px;">
                            <input type="checkbox" class="todo-checkbox" style="width:18px;height:18px;margin:0;cursor:pointer;" ${s.done ? 'checked' : ''}
                                onchange="event.stopPropagation(); toggleSubtaskInline('${s.id}', this.checked, '${taskId}')">
                        </label>
                        <span style="${s.done ? 'text-decoration:line-through;opacity:0.6;' : ''}">${escapeHtml(s.titlu)}</span>
                    </div>`).join('');
            }
        }
        // Hide the add wrapper
        const wrapper = document.getElementById(`inline-subtask-add-gt-${taskId}`);
        if (wrapper) wrapper.style.display = 'none';
        showToast('Subtask adăugat');
    } catch (e) { showToast('Eroare la adăugare subtask', true); }
}

// Toggle global task timer from inline button
let _gtInlineTimerIntervals = {};
async function toggleGtTimerInline(taskId, isRunning, btnElement) {
    try {
        if (isRunning) {
            // Stop timer
            const res = await fetch(`/api/global-tasks/${encodeURIComponent(taskId)}/timer/stop`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to stop timer');
            const data = await res.json();
            // Update button
            if (btnElement) {
                btnElement.classList.remove('running');
                btnElement.querySelector('.timer-icon').textContent = '▶';
                btnElement.querySelector('span:last-child').textContent = formatTimerDuration(data.total_secunde || 0);
            }
            // Clear interval
            if (_gtInlineTimerIntervals[taskId]) {
                clearInterval(_gtInlineTimerIntervals[taskId]);
                delete _gtInlineTimerIntervals[taskId];
            }
            showToast('Cronometru oprit');
        } else {
            // Start timer
            const res = await fetch(`/api/global-tasks/${encodeURIComponent(taskId)}/timer/start`, { method: 'POST' });
            if (!res.ok) throw new Error('Failed to start timer');
            const data = await res.json();
            const startTime = new Date(data.start_time).getTime();
            // Update button
            if (btnElement) {
                btnElement.classList.add('running');
                btnElement.querySelector('.timer-icon').textContent = '⏸';
            }
            // Start interval to update elapsed time
            _gtInlineTimerIntervals[taskId] = setInterval(() => {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                // Find button by the timer-icon span content
                document.querySelectorAll('.gt-task-card .timer-btn').forEach(btn => {
                    if (btn.querySelector('.timer-icon').textContent === '⏸') {
                        btn.querySelector('span:last-child').textContent = formatTimerDuration(elapsed);
                    }
                });
            }, 1000);
            showToast('Cronometru pornit');
        }
    } catch (e) {
        console.error('Timer error:', e);
        showToast('Eroare cronometru', true);
    }
}

async function deleteSubtask(subtaskId) {
    const taskId = document.getElementById('task-edit-id').value;
    try {
        await apiDelete(`/subtasks/${subtaskId}`);
        loadSubtasks(taskId);
    } catch (e) { showToast('Eroare la ștergere', true); }
}

// ── Per-task timer ── (works for project tasks AND daily/global tasks)
function _taskTimerBase(taskId) {
    return _taskModalMode === 'global'
        ? `/api/global-tasks/${encodeURIComponent(taskId)}/timer`
        : `/api/tasks/${encodeURIComponent(taskId)}/timer`;
}
async function loadTaskTimer(taskId) {
    const row = document.getElementById('task-time-row');
    if (row) row.style.display = 'block';
    if (_taskTimerInterval) { clearInterval(_taskTimerInterval); _taskTimerInterval = null; }
    try {
        const res = await fetch(_taskTimerBase(taskId));
        const data = await res.json();
        _taskTimerBaseTotal = data.total_secunde || 0;
        if (data.running && data.running_since) {
            _taskTimerRunningSince = new Date(data.running_since).getTime();
            _setTaskTimerBtn(true);
            _tickTaskTimer();
            _taskTimerInterval = setInterval(_tickTaskTimer, 1000);
        } else {
            _taskTimerRunningSince = null;
            _setTaskTimerBtn(false);
            _renderTaskTime(_taskTimerBaseTotal);
        }
    } catch (e) {
        _taskTimerRunningSince = null;
        _renderTaskTime(0);
    }
}

function _renderTaskTime(sec) {
    const el = document.getElementById('task-time-total');
    if (el) el.textContent = formatTime(Math.max(0, sec));
}

function _tickTaskTimer() {
    if (_taskTimerRunningSince == null) return;
    const elapsed = Math.floor((Date.now() - _taskTimerRunningSince) / 1000);
    _renderTaskTime(_taskTimerBaseTotal + elapsed);
}

function _setTaskTimerBtn(running) {
    const btn = document.getElementById('task-timer-btn');
    if (!btn) return;
    btn.innerHTML = running
        ? '<i data-lucide="square"></i> Oprește'
        : '<i data-lucide="play"></i> Pornește';
    btn.classList.toggle('btn-success', !running);
    btn.classList.toggle('btn-danger', running);
    if (window.lucide) try { lucide.createIcons(); } catch (e) {}
}

async function toggleTaskTimer() {
    const taskId = document.getElementById('task-edit-id').value;
    if (!taskId) return;
    const running = _taskTimerRunningSince != null;
    try {
        if (running) {
            const res = await fetch(_taskTimerBase(taskId) + '/stop', { method: 'POST' });
            const data = await res.json();
            if (_taskTimerInterval) { clearInterval(_taskTimerInterval); _taskTimerInterval = null; }
            _taskTimerRunningSince = null;
            _taskTimerBaseTotal = data.total_secunde || 0;
            _setTaskTimerBtn(false);
            _renderTaskTime(_taskTimerBaseTotal);
            showToast('Cronometru oprit');
        } else {
            const res = await fetch(_taskTimerBase(taskId) + '/start', { method: 'POST' });
            const data = await res.json();
            _taskTimerRunningSince = new Date(data.start_time).getTime();
            _setTaskTimerBtn(true);
            _tickTaskTimer();
            _taskTimerInterval = setInterval(_tickTaskTimer, 1000);
            showToast('Cronometru pornit');
        }
    } catch (e) { showToast('Eroare cronometru', true); }
}

// ── Intrare manuala de timp (timp lucrat fara cronometru) ──
let _manualTimeCtx = null;      // { kind: 'project'|'task'|'global', id }
let _manualTimeFp = null;

function openManualTimeModal(kind, id) {
    if (!id) return;
    _manualTimeCtx = { kind: kind, id: id };
    document.getElementById('manual-time-hours').value = '1';
    document.getElementById('manual-time-minutes').value = '0';
    document.getElementById('manual-time-modal').classList.add('active');
    setTimeout(() => {
        if (_manualTimeFp) { _manualTimeFp.destroy(); _manualTimeFp = null; }
        _manualTimeFp = initFlatpickr('#manual-time-date');
        if (_manualTimeFp) _manualTimeFp.setDate(new Date());
    }, 50);
}

// Open the manual-entry modal for whatever task the shared task modal holds.
function openManualTimeForTask() {
    const id = document.getElementById('task-edit-id').value;
    openManualTimeModal(_taskModalMode === 'global' ? 'global' : 'task', id);
}

function closeManualTimeModal() {
    document.getElementById('manual-time-modal').classList.remove('active');
    if (_manualTimeFp) { _manualTimeFp.destroy(); _manualTimeFp = null; }
    _manualTimeCtx = null;
}

async function saveManualTime() {
    if (!_manualTimeCtx) return;
    const h = parseInt(document.getElementById('manual-time-hours').value, 10) || 0;
    const m = parseInt(document.getElementById('manual-time-minutes').value, 10) || 0;
    const dur = h * 3600 + m * 60;
    if (dur <= 0) { showToast('Durata trebuie să fie mai mare ca zero', true); return; }
    const data = (document.getElementById('manual-time-date').value || '').trim();
    const body = { data: data, durata_secunde: dur };
    const ctx = _manualTimeCtx;
    try {
        if (ctx.kind === 'project') {
            await apiPost(`/proiecte/${ctx.id}/timer/manual`, body);
        } else if (ctx.kind === 'global') {
            await apiPost(`/global-tasks/${ctx.id}/timer/manual`, body);
        } else {
            await apiPost(`/tasks/${ctx.id}/timer/manual`, body);
        }
        closeManualTimeModal();
        showToast('Timp adăugat');
        if (ctx.kind === 'project') {
            if (currentProjectId) loadJurnal(currentProjectId);
        } else {
            loadTaskTimer(ctx.id);
        }
    } catch (e) {
        console.error('Manual time error:', e);
        showToast('Eroare la adăugarea timpului', true);
    }
}


var tEditModal = document.getElementById('task-edit-modal');
if (tEditModal) tEditModal.addEventListener('click', function(e) { if (e.target === this) closeTaskEditModal(); });

// ============ JURNAL ============

async function loadJurnal(projectId) {
    try {
        const [jurnalEntries, timerData] = await Promise.all([
            apiGet(`/proiecte/${projectId}/jurnal`),
            apiGet(`/proiecte/${projectId}/timer`).catch(() => ({ sessions: [], total_secunde: 0 }))
        ]);

        const sessions = (timerData.sessions || []).slice();

        // "Stop with note" creates BOTH a timer session and a jurnal entry within the
        // same transaction. Without dedupe both show up in the history, which Ion does
        // not want. Match each jurnal entry to a session whose end_time is within
        // ~2 minutes; the matched session is then hidden from the timer list, while
        // the jurnal entry inherits its duration badge.
        const matched = new Set();
        for (const j of jurnalEntries) {
            const jTime = new Date(j.created_at || j.data || 0).getTime();
            if (!jTime) continue;
            const found = sessions.find(s => {
                if (matched.has(s.id)) return false;
                // Backend column is `stop_time`, not `end_time` (this was the
                // bug — match always failed, so both rows showed).
                const stopIso = s.stop_time || s.end_time;
                if (!stopIso) return false;
                const sEnd = new Date(stopIso).getTime();
                return Math.abs(jTime - sEnd) < 2 * 60 * 1000;
            });
            if (found) {
                matched.add(found.id);
                j._duration_secunde = found.durata_secunde;
                j._session_id = found.id;
            }
        }
        const unmatchedSessions = sessions.filter(s => !matched.has(s.id));

        const container = document.getElementById('timer-sessions-list');
        let html = renderTimerSessions(unmatchedSessions, timerData.total_secunde);

        // Journal entries, with duration badge when they originate from a timer-with-note.
        if (jurnalEntries.length > 0) {
            html += jurnalEntries.map(entry => {
                const durBadge = entry._duration_secunde
                    ? `<span class="jurnal-duration"><i data-lucide="timer"></i> ${formatTimerDuration(entry._duration_secunde)}</span>`
                    : '';
                return `
                <div class="jurnal-item jurnal-enter">
                    <i data-lucide="notebook-pen" class="jurnal-icon"></i>
                    <span class="jurnal-date">${entry.data || ''}</span>
                    ${durBadge}
                    <span class="jurnal-text">${escapeHtml(entry.continut || '')}</span>
                    <button class="btn btn-icon btn-ghost btn-ghost-danger" onclick="deleteJurnalEntry('${entry.id}', ${entry._session_id ? `'${entry._session_id}'` : 'null'})" title="Șterge"><i data-lucide="trash-2"></i></button>
                </div>`;
            }).join('');
        }

        container.innerHTML = html || '<p style="color:var(--text2);">Nu există activități.</p>';
        if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
    } catch (e) {
        console.error('Failed to load jurnal:', e);
    }
}

async function addJurnalEntry() {
    const data = document.getElementById('jurnal-data').value;
    const continut = document.getElementById('jurnal-continut').value.trim();

    if (!continut) return;

    try {
        await apiPost(`/proiecte/${currentProjectId}/jurnal`, { data, continut });
        document.getElementById('jurnal-continut').value = '';
        loadJurnal(currentProjectId);
        showToast('Intrare adăugată!');
    } catch (e) {
        console.error('Failed to add jurnal entry:', e);
        showToast('Eroare la adăugarea intrării', true);
    }
}

async function deleteJurnalEntry(entryId, pairedSessionId) {
    try {
        // Delete the paired timer_session too (stop-with-note creates both).
        // Frontend belt-and-suspenders even though the backend now cascades —
        // covers servers running the old code and pre-fix orphan rows.
        const calls = [apiDelete(`/jurnal/${entryId}`)];
        if (pairedSessionId) calls.push(apiDelete(`/timer/${pairedSessionId}`).catch(() => {}));
        await Promise.all(calls);
        loadJurnal(currentProjectId);
    } catch (e) {
        console.error('Failed to delete jurnal entry:', e);
    }
}

// ============ ATTACHMENTS ============

async function loadAttachments(projectId) {
    try {
        const attachments = await apiGet(`/proiecte/${projectId}/atasamente`);
        renderAttachments(attachments);
    } catch (e) {
        console.error('Failed to load attachments:', e);
    }
}

function renderAttachments(attachments) {
    const container = document.getElementById('attachment-list');

    // "Download all" CTA — only meaningful with 2+ files. Lives above the list so it
    // never collides with per-row actions.
    const downloadAllBar = (attachments.length >= 2)
        ? `<div class="attachment-bulk-bar"><button class="btn btn-small btn-secondary" onclick="downloadAllAttachments()" title="Descarcă toate atașamentele"><i data-lucide="download-cloud"></i> Descarcă tot (${attachments.length})</button></div>`
        : '';

    if (!attachments.length) {
        container.innerHTML = '<p style="color: var(--text2);">Nu există atașamente.</p>';
        return;
    }

    const icons = {
        'PDF': 'file-text',
        'IMG': 'image',
        'EMAIL': 'mail',
        'DOC': 'file-edit',
        'XLS': 'file-spreadsheet',
        'ZIP': 'file-archive',
        'ALT': 'paperclip'
    };

    // Per-row actions are now icon-only with title tooltips. Solves the overlap on
    // narrow containers where the labels "Preview / Download / Sterge" used to wrap
    // onto each other.
    container.innerHTML = downloadAllBar + attachments.map(att => `
        <div class="attachment-item">
            <div class="attachment-icon"><i data-lucide="${icons[att.tip_fisier] || 'paperclip'}"></i></div>
            <div class="attachment-info">
                <div class="attachment-name">${escapeHtml(att.nume_fisier)}</div>
                <div class="attachment-meta">${formatFileSize(att.dimensiune)} · ${att.data || ''}</div>
            </div>
            <div class="attachment-actions">
                ${att.tip_fisier === 'PDF' || att.tip_fisier === 'IMG' ? `<button class="btn btn-icon btn-secondary" title="Previzualizare" onclick="openPreview('${att.id}', '${escapeHtml(att.nume_fisier)}', '${att.tip_fisier}')"><i data-lucide="eye"></i></button>` : ''}
                <button class="btn btn-icon btn-secondary" title="Descarcă" onclick="downloadAttachment('${att.id}')"><i data-lucide="download"></i></button>
                <button class="btn btn-icon btn-danger" title="Șterge" onclick="deleteAttachment('${att.id}')"><i data-lucide="trash-2"></i></button>
            </div>
        </div>
    `).join('');
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

// Trigger sequential downloads of every attachment of the current project.
// Browsers throttle parallel downloads so we space them out by ~250ms.
async function downloadAllAttachments() {
    if (!currentProjectId) return;
    try {
        const attachments = await apiGet(`/proiecte/${currentProjectId}/atasamente`);
        if (!attachments || !attachments.length) return;
        showToast(`Descarc ${attachments.length} fișiere...`);
        for (let i = 0; i < attachments.length; i++) {
            const att = attachments[i];
            const a = document.createElement('a');
            a.href = `${API_BASE}/atasamente/${att.id}/download`;
            a.download = att.nume_fisier || '';
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            await new Promise(r => setTimeout(r, 250));
        }
    } catch (e) {
        console.error('downloadAllAttachments failed:', e);
        showToast('Eroare la descărcare', true);
    }
}

function openPreview(attachmentId, filename, tipFisier) {
    const url = `${API_BASE}/atasamente/${attachmentId}/download`;
    const content = document.getElementById('preview-content');
    document.getElementById('preview-filename').textContent = filename;

    if (tipFisier === 'IMG') {
        content.innerHTML = `<img src="${url}" alt="${escapeHtml(filename)}">`;
    } else if (tipFisier === 'PDF') {
        content.innerHTML = `<iframe src="${url}" title="${escapeHtml(filename)}"></iframe>`;
    }

    document.getElementById('preview-modal').classList.add('active');
}

function closePreview() {
    document.getElementById('preview-modal').classList.remove('active');
    document.getElementById('preview-content').innerHTML = '';
}

// formatFileSize -> moved to shared core.js

async function handleFileUpload(event) {
    const files = event.target.files;
    if (!files.length) return;

    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            await apiUpload(`/proiecte/${currentProjectId}/atasamente`, formData);
            showToast(`Fișier încărcat: ${file.name}`);
        } catch (e) {
            console.error('Failed to upload file:', e);
            showToast(`Eroare la încărcarea fișierului`, true);
        }
    }

    event.target.value = '';
    loadAttachments(currentProjectId);
}

function downloadAttachment(attachmentId) {
    window.open(`${API_BASE}/atasamente/${attachmentId}/download`, '_blank');
}

async function deleteAttachment(attachmentId) {
    try {
        await apiDelete(`/atasamente/${attachmentId}`);
        loadAttachments(currentProjectId);
        showToast('Atașament șters!');
    } catch (e) {
        console.error('Failed to delete attachment:', e);
        showToast('Eroare la ștergerea atașamentului', true);
    }
}

// ============ BACKUP / RESTORE ============

async function exportBackup() {
    try {
        const data = await apiGet('/backup');
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `pif_backup_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Backup descărcat!');
    } catch (e) {
        console.error('Failed to export backup:', e);
        showToast('Eroare la exportarea backup-ului', true);
    }
}

async function importBackup(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const data = JSON.parse(e.target.result);
            await fetch(`${API_BASE}/restore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            showToast('Backup restaurat cu succes!');
            loadProjects();
            updateStats();
            if (currentProjectId) {
                showProjectDetail(currentProjectId);
            }
        } catch (err) {
            console.error('Failed to import backup:', err);
            showToast('Eroare la restaurarea backup-ului', true);
        }
    };
    reader.readAsText(file);
    event.target.value = '';
}

// ============ EXPORT ============

async function exportMarkdown() {
    if (!currentProjectId) return;

    try {
        const [project, tasks, jurnal, attachments, timer, checklist, checklistCat, echipamente] = await Promise.all([
            apiGet(`/proiecte/${currentProjectId}`),
            apiGet(`/proiecte/${currentProjectId}/tasks`),
            apiGet(`/proiecte/${currentProjectId}/jurnal`),
            apiGet(`/proiecte/${currentProjectId}/atasamente`),
            apiGet(`/proiecte/${currentProjectId}/timer`).catch(() => ({ sessions: [], total_secunde: 0 })),
            apiGet(`/proiecte/${currentProjectId}/checklist`).catch(() => []),
            apiGet(`/proiecte/${currentProjectId}/checklist-categorii`).catch(() => []),
            apiGet(`/proiecte/${currentProjectId}/echipamente`).catch(() => [])
        ]);

        const isPIF = project.tip === 'PIF';
        const isService = project.tip === 'Service';
        const today = new Date().toISOString().split('T')[0];

        const fmtHours = (s) => {
            if (!s) return '0h';
            const h = Math.floor(s / 3600);
            const m = Math.floor((s % 3600) / 60);
            return h > 0 ? `${h}h ${m}m` : `${m}m`;
        };
        const escMd = (txt) => (txt || '').replace(/\|/g, '\\|');

        let md = '';

        // FRONTMATTER YAML (Obsidian-compatible)
        md += `---\n`;
        md += `tags:\n`;
        if (isPIF) md += `  - proiect\n  - pif\n`;
        if (isService) md += `  - service\n  - interventie\n`;
        if (project.producator && project.producator !== 'Altul')
            md += `  - ${project.producator.toLowerCase()}\n`;
        md += `client: ${project.client || ''}\n`;
        md += `locatie: ${project.locatie || ''}\n`;
        md += `echipament_principal: ${project.echipament_principal || ''}\n`;
        md += `data_export: ${today}\n`;
        if (isPIF) {
            md += `data_incepere: ${project.data_incepere || ''}\n`;
            md += `deadline: ${project.deadline || ''}\n`;
        }
        if (isService) md += `data_crearii: ${project.data_crearii || today}\n`;
        md += `status: ${project.status || 'activ'}\n`;
        if (project.cod_proiect) md += `cod_proiect: ${project.cod_proiect}\n`;
        md += `total_ore_lucrate: ${fmtHours(timer.total_secunde)}\n`;
        md += `---\n\n`;

        // TITLU
        md += isPIF
            ? `# PIF — ${project.nume}\n\n`
            : `# Service — ${project.nume}\n\n`;

        let section = 1;

        // 1. DETALII ADMINISTRATIVE — un tabel curat în loc de bullet list
        md += `## ${section++}. Detalii administrative\n\n`;
        md += `| Câmp | Valoare |\n|---|---|\n`;
        md += `| Client | ${escMd(project.client) || '—'} |\n`;
        md += `| Locație | ${escMd(project.locatie) || '—'} |\n`;
        md += `| Producător | ${escMd(project.producator) || '—'} |\n`;
        md += `| Echipament principal | ${escMd(project.echipament_principal) || '—'} |\n`;
        if (project.pm) md += `| Project Manager | ${escMd(project.pm)} |\n`;
        if (project.nr_comanda) md += `| Nr. Comandă | ${escMd(project.nr_comanda)} |\n`;
        if (project.nr_contract) md += `| Nr. Contract | ${escMd(project.nr_contract)} |\n`;
        if (project.cod_proiect) md += `| Cod proiect | ${escMd(project.cod_proiect)} |\n`;
        if (project.folder_server) md += `| Folder server | ${escMd(project.folder_server)} |\n`;
        md += `| Status | ${escMd(project.status) || 'activ'} |\n`;
        md += `| Total ore lucrate | ${fmtHours(timer.total_secunde)} |\n`;
        md += `\n`;

        // 2. CONȚINUT TEHNIC (PIF: Observații / Service: Constatări + Acțiuni)
        if (isPIF && project.observatii) {
            md += `## ${section++}. Observații tehnice\n\n${project.observatii}\n\n`;
        }
        if (isService) {
            md += `## ${section++}. Fișă intervenție\n\n`;
            if (project.service_before) {
                md += `### Constatări înainte de intervenție\n\n${project.service_before}\n\n`;
            }
            if (project.service_after) {
                md += `### Acțiuni efectuate și rezultat\n\n${project.service_after}\n\n`;
            }
        }

        // 3. CHECKLIST PIF (only when project is PIF and there are items)
        if (isPIF && checklist.length > 0) {
            md += `## ${section++}. Checklist PIF\n\n`;
            // Group by category
            const byCat = new Map();
            for (const it of checklist) {
                const key = it.categorie_id != null ? String(it.categorie_id) : '0';
                if (!byCat.has(key)) byCat.set(key, []);
                byCat.get(key).push(it);
            }
            const ordered = [...checklistCat].sort((a, b) => (a.ordine ?? 0) - (b.ordine ?? 0));
            const renderItems = (its) => its.map(it => `- [${it.completed ? 'x' : ' '}] ${escMd(it.titlu)}`).join('\n');
            for (const cat of ordered) {
                const its = byCat.get(String(cat.id)) || [];
                if (!its.length) continue;
                const done = its.filter(i => i.completed).length;
                md += `### ${escMd(cat.nume)} (${done}/${its.length})\n\n${renderItems(its)}\n\n`;
            }
            const uncategorized = byCat.get('0') || [];
            if (uncategorized.length) {
                const done = uncategorized.filter(i => i.completed).length;
                md += `### Fără categorie (${done}/${uncategorized.length})\n\n${renderItems(uncategorized)}\n\n`;
            }
        }

        // 4. LISTA TASK-URI
        if (tasks.length > 0) {
            md += `## ${section++}. Listă taskuri\n\n`;
            const prioOrder = { 'Urgent': 0, 'Normal': 1, 'Minor': 2 };
            const prioBadge = { 'Urgent': '[Urgent]', 'Normal': '[Normal]', 'Minor': '[Minor]' };
            const sorted = [...tasks].sort((a, b) =>
                (prioOrder[a.prioritate] ?? 1) - (prioOrder[b.prioritate] ?? 1));

            const pending = sorted.filter(t => t.status !== 'done');
            const done = sorted.filter(t => t.status === 'done');

            if (pending.length > 0) {
                md += `### To Do\n\n`;
                pending.forEach(t => {
                    const badge = prioBadge[t.prioritate] || '[Normal]';
                    const term = t.data_scadenta ? ` · termen ${t.data_scadenta}` : '';
                    md += `- [ ] ${escMd(t.titlu)} ${badge}${term}\n`;
                });
                md += `\n`;
            }
            if (done.length > 0) {
                md += `### Finalizate\n\n`;
                done.forEach(t => {
                    const badge = prioBadge[t.prioritate] || '[Normal]';
                    const finalizat = t.data_finalizare ? ` · finalizat ${t.data_finalizare.split('T')[0]}` : '';
                    md += `- [x] ${escMd(t.titlu)} ${badge}${finalizat}\n`;
                });
                md += `\n`;
            }
        }

        // 5. ECHIPAMENTE
        if (echipamente && echipamente.length > 0) {
            md += `## ${section++}. Echipamente\n\n`;
            md += `| # | Nume | Producător | Model | Serie | Parametri |\n|---|---|---|---|---|---|\n`;
            echipamente.forEach((eq, idx) => {
                let params = {};
                try { params = typeof eq.params_json === 'string' ? JSON.parse(eq.params_json || '{}') : (eq.params_json || {}); } catch {}
                const paramCount = Object.keys(params).length;
                md += `| ${idx + 1} | ${escMd(eq.nume) || '—'} | ${escMd(eq.producator) || '—'} | ${escMd(eq.model) || '—'} | ${escMd(eq.serial_number) || '—'} | ${paramCount} |\n`;
            });
            md += `\n`;
            // Detalii params per echipament — anexă
            echipamente.forEach((eq, idx) => {
                let params = {};
                try { params = typeof eq.params_json === 'string' ? JSON.parse(eq.params_json || '{}') : (eq.params_json || {}); } catch {}
                const entries = Object.entries(params);
                if (entries.length === 0) return;
                md += `### Echipament #${idx + 1} — ${escMd(eq.nume)} · parametri modificați\n\n`;
                md += `| Cod | Valoare |\n|---|---|\n`;
                entries.forEach(([k, v]) => { md += `| \`${k}\` | ${escMd(String(v))} |\n`; });
                md += `\n`;
            });
        }

        // 6. JURNAL DE LUCRU + TIMER SESSIONS UNIFICATE
        if (jurnal.length > 0 || (timer.sessions && timer.sessions.length > 0)) {
            md += `## ${section++}. Jurnal de lucru\n\n`;
            // Match each jurnal entry to a timer session within ~2 min of its end (dedupe).
            const sessions = (timer.sessions || []).slice();
            const matched = new Set();
            for (const j of jurnal) {
                const jt = new Date(j.created_at || j.data || 0).getTime();
                if (!jt) continue;
                const found = sessions.find(s => {
                    // Backend column is `stop_time` — `end_time` was the bug.
                    const stopIso = s.stop_time || s.end_time;
                    if (matched.has(s.id) || !stopIso) return false;
                    return Math.abs(jt - new Date(stopIso).getTime()) < 2 * 60 * 1000;
                });
                if (found) { matched.add(found.id); j._duration_secunde = found.durata_secunde; }
            }
            [...jurnal].reverse().forEach(entry => {
                const durSuffix = entry._duration_secunde ? ` · ${fmtHours(entry._duration_secunde)}` : '';
                md += `### ${entry.data || ''}${durSuffix}\n\n${entry.continut || ''}\n\n`;
            });
            const unmatched = sessions.filter(s => !matched.has(s.id) && (s.stop_time || s.end_time));
            if (unmatched.length > 0) {
                md += `### Sesiuni timer fără notă\n\n`;
                unmatched.forEach(s => {
                    const date = s.start_time ? s.start_time.substring(0, 10) : '';
                    md += `- ${date} · ${fmtHours(s.durata_secunde)}\n`;
                });
                md += `\n`;
            }
        }

        // 7. ATAȘAMENTE
        if (attachments.length > 0) {
            md += `## ${section++}. Atașamente\n\n`;
            md += `| Fișier | Tip | Mărime | Adăugat |\n|---|---|---|---|\n`;
            attachments.forEach(att => {
                md += `| ${escMd(att.nume_fisier)} | ${escMd(att.tip_fisier)} | ${formatFileSize(att.dimensiune)} | ${escMd(att.data) || '—'} |\n`;
            });
            md += `\n`;
        }

        // FOOTER
        md += `\n---\n\n`;
        md += `*Document generat automat din PIF Dashboard · ${today} · Ion Ursu*\n`;

        // DOWNLOAD
        const filename = project.cod_proiect
            ? `${project.cod_proiect}_${(project.nume || 'proiect').replace(/[^a-z0-9]/gi, '_')}.md`
            : `${(project.nume || 'proiect').replace(/[^a-z0-9]/gi, '_')}.md`;

        const blob = new Blob([md], { type: 'text/markdown; charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Export Markdown descărcat!');

    } catch (e) {
        console.error('Export failed:', e);
        showToast('Eroare la export', true);
    }
}

// ============ PHASE 2c: PDF EXPORT ============

async function exportCurrentProjectPDF() {
    if (!currentProjectId) {
        showToast('Niciun proiect selectat', true);
        return;
    }

    try {
        // Use window.open for PDF download via API
        const response = await fetch(`${API_BASE}/export/pdf?project_id=${currentProjectId}`, {
            method: 'GET',
            headers: { 'Accept': 'application/pdf' }
        });

        if (!response.ok) {
            throw new Error('PDF export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `pif_report_${currentProjectId}.pdf`;
        if (contentDisposition) {
            const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (match) {
                filename = match[1].replace(/['"]/g, '');
            }
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showToast('PDF exportat cu succes!');
    } catch (e) {
        console.error('PDF export failed:', e);
        showToast('Eroare la export PDF', true);
    }
}

function exportClientPDF() {
    const clientName = prompt('Introduceți numele clientului:');
    if (!clientName || !clientName.trim()) {
        return;
    }
    const encodedName = encodeURIComponent(clientName.trim());
    window.open(`${API_BASE}/export/pdf/client/${encodedName}`, '_blank');
}

// ============ PHASE 2c: TELEGRAM NOTIFICATIONS ============


// ============ GLOBAL TASKS ============

function switchTab(tab) {
    document.querySelectorAll('.main-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`.main-tab[data-tab="${tab}"]`).classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');
    // Keep ARIA tab state in sync with the visible tab.
    document.querySelectorAll('.main-tab').forEach(t => {
        const on = t.classList.contains('active');
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.setAttribute('tabindex', on ? '0' : '-1');
    });

    // Hide project detail view when switching tabs
    const detailView = document.getElementById('project-detail-view');
    if (detailView) detailView.classList.remove('active');
    // Show project list when going back to projects tab
    if (tab === 'proiecte') {
        // Critical: project-list-view gets `hidden` added in showProjectDetail().
        // Without removing it here the list stays invisible after viewing a detail
        // and switching tabs, forcing a page refresh to recover.
        const listView = document.getElementById('project-list-view');
        if (listView) listView.classList.remove('hidden');
        currentProjectId = null;

        const tableContainer = document.getElementById('projects-table-container');
        if (tableContainer) tableContainer.style.display = 'block';
        // empty-state visibility is owned by renderProjects() — do not force it here.

        // Re-fetch in case data changed while viewing the detail. apiGet uses
        // stale-while-revalidate so the cached list shows instantly while a fresh
        // copy lands in the background.
        loadProjects();
        updateStats();
    }

    // Update bottom nav active state
    document.querySelectorAll('.bottom-nav-item').forEach(item => {
        item.classList.toggle('active', item.getAttribute('data-tab') === tab);
    });

    // Toggle projects-only header elements
    const headerActions = document.querySelector('.header-actions');
    if (headerActions) {
        headerActions.classList.toggle('project-tab-active', tab === 'proiecte');
    }

    // Context-specific header buttons
    const btnClienti = document.getElementById('header-btn-clienti');
    const btnManuale = document.getElementById('header-btn-manuale');
    if (btnClienti) btnClienti.style.display = (tab === 'proiecte') ? 'inline-flex' : 'none';
    if (btnManuale) btnManuale.style.display = (tab === 'parametri') ? 'inline-flex' : 'none';

    if (tab === 'taskuri') {
        loadGlobalTasks();
        loadProjectTasks();
        setTimeout(() => document.getElementById('quick-task-input')?.focus(), 100);
    }
    // tab === 'proiecte' is fully handled in the block above (list-view restore
    // + loadProjects + updateStats) — do not call them a second time here.
    if (tab === 'acasa') {
        loadDashboardHome();
    }
    if (tab === 'parametri') {
        // Parametri OR Coduri eroare, depending on the persisted mode.
        // Families load lazily; apiGet cache makes re-entry near-instant.
        paramTabEnter();
    }
    if (tab === 'admin') {
        loadAdminPanel();
    }
    if (tab === 'notite') {
        loadObsidianNotes();
    }
}

// ============ ADMIN PANEL ============
// Loads on-demand when user enters tab-admin. Pulls /stats, /stats/extended,
// /parametri (count) and renders all 6 stat cards + breakdown lists.

async function loadAdminPanel() {
    try {
        const [stats, ext, paramCount] = await Promise.all([
            apiGet('/stats').catch(() => null),
            apiGet('/stats/extended').catch(() => null),
            apiGet('/parametri?limit=1').catch(() => null)  // we only care about response shape
        ]);

        // Top stats
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        if (stats) {
            set('adm-stat-total', stats.total ?? '—');
            set('adm-stat-active', stats.active ?? '—');
            set('adm-stat-finished', stats.finished ?? '—');
        }
        if (ext) {
            const h = ext.total_billable_hours ?? ext.total_hours ?? 0;
            set('adm-stat-hours', `${Math.round(h)}h`);
            set('adm-stat-urgent', (ext.urgent_count ?? 0));
        }

        // Param count from dashboard endpoint (returns total + parametri)
        try {
            const audit = await apiGet('/parametri/audit');
            set('adm-stat-params', (audit.total ?? 0).toLocaleString('ro-RO'));
        } catch {}

        // Breakdown lists
        if (ext) {
            renderAdminBreakdown('adm-breakdown-producator', ext.by_manufacturer || [], 'producator');
            renderAdminBreakdown('adm-breakdown-status', ext.by_status || [], 'status', _statusLabel);
        }

        loadObsidianConfig();

        if (window.lucide) try { window.lucide.createIcons(); } catch {}
    } catch (e) {
        console.error('loadAdminPanel failed:', e);
    }
}

function _statusLabel(s) {
    return ({ in_lucru: 'În Lucru', finalizat: 'Finalizat', in_asteptare: 'În Așteptare', blocat: 'Blocat' })[s] || s || '—';
}

function renderAdminBreakdown(containerId, rows, field, labelFn) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!rows || rows.length === 0) {
        el.innerHTML = '<div style="font-size:0.78rem;color:var(--text-dim);font-style:italic;">Niciun rezultat</div>';
        return;
    }
    const max = rows.reduce((m, r) => Math.max(m, r.count || 0), 0) || 1;
    el.innerHTML = rows.map(r => {
        const label = labelFn ? labelFn(r[field]) : (r[field] || '—');
        const pct = Math.round(((r.count || 0) / max) * 100);
        return `
            <div class="admin-breakdown-row">
                <span class="admin-breakdown-name">${escapeHtml(label)}</span>
                <div class="admin-breakdown-bar"><div class="admin-breakdown-bar-fill" style="width:${pct}%"></div></div>
                <span class="admin-breakdown-count">${r.count || 0}</span>
            </div>
        `;
    }).join('');
}

async function runParamAudit() {
    const el = document.getElementById('adm-audit-result');
    if (!el) return;
    el.classList.add('show');
    el.innerHTML = '<div style="color:var(--text-dim);">Rulează audit...</div>';
    try {
        const r = await apiGet('/parametri/audit');
        const issues = r.issues || {};
        const health = r.health_pct ?? r.health ?? null;
        const healthColor = health == null ? 'var(--text-dim)' : (health >= 95 ? 'var(--success)' : health >= 80 ? 'var(--warning)' : 'var(--danger)');

        const issueItems = Object.entries(issues).map(([key, val]) => {
            const num = val.count ?? val.total ?? 0;
            const label = val.label || key;
            return `
                <div class="admin-audit-issue">
                    <span>${escapeHtml(label)}</span>
                    <span class="num ${num === 0 ? 'zero' : ''}">${num.toLocaleString('ro-RO')}</span>
                </div>`;
        }).join('');

        el.innerHTML = `
            <div class="admin-audit-health" style="color:${healthColor}">
                <i data-lucide="${health == null ? 'help-circle' : health >= 95 ? 'shield-check' : 'shield-alert'}"></i>
                <span class="admin-audit-health-pct">${health != null ? health + '%' : 'n/a'}</span>
                <span style="color:var(--text2); font-weight:normal; font-size:0.85rem;">
                    Sănătate DB — ${r.total ? r.total.toLocaleString('ro-RO') + ' parametri' : '—'}
                </span>
            </div>
            <div class="admin-audit-issues">${issueItems}</div>
        `;
        if (window.lucide) try { window.lucide.createIcons(); } catch {}
    } catch (e) {
        el.innerHTML = `<div style="color:var(--danger);">Audit eșuat: ${escapeHtml(e.message || String(e))}</div>`;
    }
}

async function clearLocalCache() {
    if (!confirm('Curăță tot cache-ul local? Asta șterge localStorage, IndexedDB și SW cache. La următorul reload datele se vor descărca din nou.')) return;
    try {
        // localStorage
        try { localStorage.clear(); } catch {}
        // IndexedDB — drop any database named pif-*
        try {
            const dbs = await (indexedDB.databases ? indexedDB.databases() : Promise.resolve([]));
            for (const d of dbs) { if (d.name && d.name.startsWith('pif')) indexedDB.deleteDatabase(d.name); }
        } catch {}
        // SW caches
        try {
            const keys = await caches.keys();
            for (const k of keys) if (k.startsWith('pif')) await caches.delete(k);
        } catch {}
        // Tell SW to skip waiting
        try {
            const reg = await navigator.serviceWorker.getRegistration();
            if (reg && reg.waiting) reg.waiting.postMessage('skipWaiting');
        } catch {}
        showToast('Cache curățat. Reîncarcă pagina (Ctrl+Shift+R).');
    } catch (e) {
        showToast('Eroare la curățarea cache-ului', true);
    }
}

async function forceSWUpdate() {
    try {
        const reg = await navigator.serviceWorker.getRegistration();
        if (!reg) { showToast('Niciun service worker activ'); return; }
        await reg.update();
        showToast('Service worker actualizat. Reîncarcă pagina.');
    } catch (e) {
        showToast('Eroare la update SW', true);
    }
}

// ============ OBSIDIAN NOTES (read-only vault integration) ============

let _obsidianNotes = [];
let _obsidianActivePath = null;
let _obsidianSearchTimer = null;

// _attrEsc() lives in core.js (shared with the mobile shell, as _obsAttr).

// Lightweight Markdown renderer (mdInline / _calloutMeta / renderMarkdown)
// lives in core.js — shared with the mobile shell.

async function _obsidianGet(path) {
    const res = await fetch('/api/obsidian' + path);
    return res.json();
}

async function loadObsidianNotes() {
    const listEl = document.getElementById('obsidian-note-list');
    const metaEl = document.getElementById('obsidian-list-meta');
    if (!listEl) return;
    try {
        const data = await _obsidianGet('/notes');
        if (data.error) {
            _obsidianNotes = [];
            if (metaEl) metaEl.textContent = '';
            listEl.innerHTML = `<div class="obsidian-placeholder" style="height:auto;padding:30px 12px;">
                <i data-lucide="folder-x"></i>
                <p style="font-size:0.82rem;text-align:center;">Vault Obsidian neconfigurat.<br>Administrativ → Integrare Obsidian.</p></div>`;
            if (window.lucide) try { lucide.createIcons(); } catch (e) {}
            return;
        }
        _obsidianNotes = data.notes || [];
        if (metaEl) metaEl.textContent = `${_obsidianNotes.length} notițe`;
        renderObsidianTree();
    } catch (e) {
        console.error('loadObsidianNotes failed:', e);
    }
}

// --- Folder tree (mirrors the Obsidian file explorer) ---
let _obsidianCollapsed = (function () {
    try { return new Set(JSON.parse(localStorage.getItem('pif:obsidian:collapsed') || '[]')); }
    catch (e) { return new Set(); }
})();
function _saveObsidianCollapsed() {
    try { localStorage.setItem('pif:obsidian:collapsed', JSON.stringify([..._obsidianCollapsed])); } catch (e) {}
}

// _buildNoteTree() and _countTreeNotes() live in core.js (shared with mobile).

function _renderTreeNode(node, depth, prefix) {
    let html = '';
    Object.keys(node.folders).sort((a, b) => a.localeCompare(b, 'ro')).forEach(fname => {
        const full = prefix ? prefix + '/' + fname : fname;
        const collapsed = _obsidianCollapsed.has(full);
        const child = node.folders[fname];
        html += `<div class="obsidian-folder-row" data-folder="${_attrEsc(full)}" style="padding-left:${8 + depth * 14}px">
            <i data-lucide="chevron-${collapsed ? 'right' : 'down'}" class="obsidian-chevron"></i>
            <i data-lucide="folder" class="obsidian-folder-icon"></i>
            <span class="obsidian-folder-name">${escapeHtml(fname)}</span>
            <span class="obsidian-folder-count">${_countTreeNotes(child)}</span>
        </div>`;
        if (!collapsed) html += _renderTreeNode(child, depth + 1, full);
    });
    node.notes.slice()
        .sort((a, b) => a.title.toLowerCase().localeCompare(b.title.toLowerCase(), 'ro'))
        .forEach(n => {
            html += `<div class="obsidian-note-item obsidian-tree-note ${n.path === _obsidianActivePath ? 'active' : ''}" data-path="${_attrEsc(n.path)}" style="padding-left:${12 + depth * 14}px">
                <i data-lucide="file-text" class="obsidian-note-icon"></i>
                <span class="obsidian-note-title">${escapeHtml(n.title)}</span>
            </div>`;
        });
    return html;
}

function renderObsidianTree() {
    const listEl = document.getElementById('obsidian-note-list');
    if (!listEl) return;
    if (!_obsidianNotes.length) {
        listEl.innerHTML = '<div style="padding:20px 12px;color:var(--text-dim);font-size:0.84rem;text-align:center;">Nicio notiță.</div>';
        return;
    }
    listEl.innerHTML = _renderTreeNode(_buildNoteTree(_obsidianNotes), 0, '');
    if (window.lucide) try { lucide.createIcons(); } catch (e) {}
}

// Flat list — used only for search results (across folders).
function renderObsidianList(notes, opts) {
    opts = opts || {};
    const listEl = document.getElementById('obsidian-note-list');
    if (!listEl) return;
    if (!notes.length) {
        listEl.innerHTML = '<div style="padding:20px 12px;color:var(--text-dim);font-size:0.84rem;text-align:center;">Niciun rezultat.</div>';
        return;
    }
    listEl.innerHTML = notes.map(n => `
        <div class="obsidian-note-item ${n.path === _obsidianActivePath ? 'active' : ''}" data-path="${_attrEsc(n.path)}">
            <div class="obsidian-note-title">${escapeHtml(n.title)}</div>
            ${n.folder ? `<div class="obsidian-note-folder">${escapeHtml(n.folder)}</div>` : ''}
            ${n.snippet ? `<div class="obsidian-note-snippet">${_highlightSnippet(n.snippet, opts.query)}</div>` : ''}
        </div>`).join('');
}

function _highlightSnippet(snippet, query) {
    let s = escapeHtml(snippet);
    if (query) {
        const q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        s = s.replace(new RegExp('(' + q + ')', 'gi'), '<mark>$1</mark>');
    }
    return s;
}

async function openObsidianNote(path, highlightTerm) {
    _obsidianActivePath = path;
    document.querySelectorAll('.obsidian-note-item').forEach(el =>
        el.classList.toggle('active', el.getAttribute('data-path') === path));
    const contentEl = document.getElementById('obsidian-content');
    if (!contentEl) return;
    contentEl.innerHTML = '<div class="obsidian-placeholder"><p>Se încarcă...</p></div>';
    try {
        const data = await _obsidianGet('/note?path=' + encodeURIComponent(path));
        if (data.error) {
            contentEl.innerHTML = `<div class="obsidian-placeholder"><i data-lucide="file-x"></i><p>${escapeHtml(data.error)}</p></div>`;
            if (window.lucide) try { lucide.createIcons(); } catch (e) {}
            return;
        }
        contentEl.innerHTML = `
            <div class="obsidian-note-header">
                <h1>${escapeHtml(data.title)}</h1>
                <span class="obsidian-note-path">${escapeHtml(data.path)}</span>
            </div>
            <div class="md-rendered">${renderMarkdown(data.content)}</div>`;
        contentEl.scrollTop = 0;
        if (window.lucide) try { lucide.createIcons(); } catch (e) {}
        if (typeof renderMathIn === 'function') try { renderMathIn(contentEl); } catch (e) {}
        // Came from global search — highlight + scroll to the searched term.
        if (highlightTerm && typeof _highlightTermIn === 'function') {
            _highlightTermIn(contentEl.querySelector('.md-rendered'), highlightTerm);
        }
    } catch (e) {
        contentEl.innerHTML = '<div class="obsidian-placeholder"><p>Eroare la încărcarea notiței.</p></div>';
    }
}

function onObsidianSearchInput() {
    clearTimeout(_obsidianSearchTimer);
    _obsidianSearchTimer = setTimeout(() => {
        const q = (document.getElementById('obsidian-search').value || '').trim();
        doObsidianSearch(q);
    }, 250);
}

async function doObsidianSearch(q) {
    const metaEl = document.getElementById('obsidian-list-meta');
    if (!q) {
        if (metaEl) metaEl.textContent = `${_obsidianNotes.length} notițe`;
        renderObsidianTree();
        return;
    }
    try {
        const data = await _obsidianGet('/search?q=' + encodeURIComponent(q));
        const results = data.results || [];
        if (metaEl) metaEl.textContent = `${results.length} rezultate`;
        renderObsidianList(results, { search: true, query: q });
    } catch (e) {
        console.error('Obsidian search failed:', e);
    }
}

async function saveObsidianConfig() {
    const input = document.getElementById('obsidian-vault-path');
    const foldersInput = document.getElementById('obsidian-folders');
    const statusEl = document.getElementById('obsidian-config-status');
    if (!input || !statusEl) return;
    const path = input.value.trim();
    const folders = foldersInput ? foldersInput.value.trim() : '';
    statusEl.classList.add('show');
    statusEl.innerHTML = '<span style="color:var(--text2)">Se verifică...</span>';
    try {
        const res = await fetch('/api/obsidian/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vault_path: path, folders: folders })
        });
        const data = await res.json();
        if (!res.ok) {
            statusEl.innerHTML = `<span style="color:var(--danger)">${escapeHtml(data.error || 'Eroare')}</span>`;
            return;
        }
        const foldersNote = data.folders
            ? ` (foldere: ${escapeHtml(data.folders)})`
            : ' (toate folderele)';
        if (data.valid) {
            statusEl.innerHTML = `<span style="color:var(--success)">Vault OK — ${data.note_count} notițe${foldersNote}.</span>`;
            showToast('Vault Obsidian salvat');
        } else if (data.configured) {
            statusEl.innerHTML = '<span style="color:var(--warning)">Calea e salvată dar nu pare validă.</span>';
        } else {
            statusEl.innerHTML = '<span style="color:var(--text2)">Cale ștearsă.</span>';
        }
    } catch (e) {
        statusEl.innerHTML = '<span style="color:var(--danger)">Eroare de rețea.</span>';
    }
}

async function loadObsidianConfig() {
    try {
        const data = await _obsidianGet('/config');
        const input = document.getElementById('obsidian-vault-path');
        if (input) input.value = data.vault_path || '';
        const foldersInput = document.getElementById('obsidian-folders');
        if (foldersInput) foldersInput.value = data.folders || '';
        const statusEl = document.getElementById('obsidian-config-status');
        if (statusEl && data.configured) {
            statusEl.classList.add('show');
            const foldersNote = data.folders ? ` (foldere: ${escapeHtml(data.folders)})` : '';
            statusEl.innerHTML = data.valid
                ? `<span style="color:var(--success)">Vault OK — ${data.note_count} notițe${foldersNote}.</span>`
                : '<span style="color:var(--warning)">Calea salvată nu pare validă.</span>';
        }
    } catch (e) { /* admin panel still usable without it */ }
}

// Delegated clicks: folder rows (collapse), note items, wikilinks.
document.addEventListener('click', function (e) {
    const folderRow = e.target.closest && e.target.closest('.obsidian-folder-row');
    if (folderRow) {
        const f = folderRow.getAttribute('data-folder');
        if (_obsidianCollapsed.has(f)) _obsidianCollapsed.delete(f);
        else _obsidianCollapsed.add(f);
        _saveObsidianCollapsed();
        renderObsidianTree();
        return;
    }
    const item = e.target.closest && e.target.closest('.obsidian-note-item');
    if (item) { openObsidianNote(item.getAttribute('data-path')); return; }
    const wl = e.target.closest && e.target.closest('.md-wikilink');
    if (wl) {
        const target = (wl.getAttribute('data-wikilink') || '').toLowerCase();
        const note = _obsidianNotes.find(n => n.title.toLowerCase() === target)
            || _obsidianNotes.find(n => n.path.toLowerCase().endsWith('/' + target + '.md'))
            || _obsidianNotes.find(n => n.path.toLowerCase() === target + '.md');
        if (note) openObsidianNote(note.path);
        else showToast('Nota „' + (wl.getAttribute('data-wikilink') || '') + '" nu a fost găsită', true);
    }
});

// ============ AI ASSISTANT (Hermes) ============

const _ASSISTANT_STORAGE_KEY = 'pif:hermes:conversation';
let _assistantMessages = [];
let _assistantBusy = false;
const _ASSISTANT_WRITE_TOOLS = [
    'create_proiect', 'create_task', 'add_checklist_item', 'add_jurnal',
    'update_task', 'update_task_status', 'add_subtask',
    'delete_task', 'delete_proiect', 'toggle_checklist_item',
    'add_echipament', 'create_client', 'update_proiect'
];

function _loadAssistantConversation() {
    try {
        const stored = localStorage.getItem(_ASSISTANT_STORAGE_KEY);
        if (stored) {
            const msgs = JSON.parse(stored);
            if (Array.isArray(msgs) && msgs.length > 0) {
                _assistantMessages = msgs;
            }
        }
    } catch (e) { /* ignore parse errors */ }
}

function _saveAssistantConversation() {
    try {
        // Keep only user + assistant messages (not typing/tools)
        const toSave = _assistantMessages.filter(
            m => m.role === 'user' || m.role === 'assistant'
        );
        localStorage.setItem(_ASSISTANT_STORAGE_KEY, JSON.stringify(toSave));
    } catch (e) { /* ignore */ }
}

function toggleAssistant() {
    const panel = document.getElementById('assistant-panel');
    if (!panel) return;
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
        if (_assistantMessages.length === 0) _loadAssistantConversation();
        renderAssistantMessages();
        setTimeout(() => document.getElementById('assistant-input')?.focus(), 150);
    }
}

function clearAssistantChat() {
    _assistantMessages = [];
    localStorage.removeItem(_ASSISTANT_STORAGE_KEY);
    renderAssistantMessages();
}

function renderAssistantMessages() {
    const box = document.getElementById('assistant-messages');
    if (!box) return;
    if (!_assistantMessages.length) {
        box.innerHTML = `<div class="assistant-welcome">
            <i data-lucide="sparkles"></i>
            <p>Salut, Ion. Sunt Hermes.<br>Pot căuta parametri, notițe și proiecte — și pot crea proiecte, taskuri, checklist-uri și intrări de jurnal. Spune-mi ce ai nevoie.</p>
        </div>`;
        if (window.lucide) try { lucide.createIcons(); } catch (e) {}
        return;
    }
    box.innerHTML = _assistantMessages.map(m => {
        if (m.role === 'user') return `<div class="assistant-msg user">${escapeHtml(m.content)}</div>`;
        if (m.role === 'typing') return `<div class="assistant-typing">Hermes scrie…</div>`;
        if (m.role === 'tools') return `<div class="assistant-tool-activity"><i data-lucide="settings-2"></i> ${escapeHtml(m.content)}</div>`;
        return `<div class="assistant-msg bot"><div class="md-rendered">${renderMarkdown(m.content)}</div></div>`;
    }).join('');
    box.scrollTop = box.scrollHeight;
    if (window.lucide) try { lucide.createIcons(); } catch (e) {}
}

async function sendAssistantMessage() {
    if (_assistantBusy) return;
    const input = document.getElementById('assistant-input');
    if (!input) return;
    const text = (input.value || '').trim();
    if (!text) return;
    input.value = '';
    input.style.height = 'auto';
    _assistantMessages.push({ role: 'user', content: text });
    _assistantMessages.push({ role: 'typing', content: '' });
    renderAssistantMessages();
    _assistantBusy = true;
    const sendBtn = document.getElementById('assistant-send-btn');
    if (sendBtn) sendBtn.disabled = true;

    const payload = _assistantMessages
        .filter(m => m.role === 'user' || m.role === 'assistant')
        .map(m => ({ role: m.role, content: m.content }));

    try {
        const res = await fetch('/api/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: payload })
        });
        const data = await res.json();
        _assistantMessages = _assistantMessages.filter(m => m.role !== 'typing');
        if (data.error) {
            _assistantMessages.push({ role: 'assistant', content: '⚠ ' + data.error });
        } else {
            if (Array.isArray(data.tool_log) && data.tool_log.length) {
                _assistantMessages.push({ role: 'tools', content: 'A folosit: ' + data.tool_log.map(t => t.tool).join(', ') });
            }
            _assistantMessages.push({ role: 'assistant', content: data.reply || '(răspuns gol)' });
            if (Array.isArray(data.tool_log) && data.tool_log.some(t => _ASSISTANT_WRITE_TOOLS.includes(t.tool))) {
                _assistantRefreshContext();
            }
        }
    } catch (e) {
        _assistantMessages = _assistantMessages.filter(m => m.role !== 'typing');
        _assistantMessages.push({ role: 'assistant', content: '⚠ Eroare de rețea.' });
    }
    _assistantBusy = false;
    if (sendBtn) sendBtn.disabled = false;
    _saveAssistantConversation();
    renderAssistantMessages();
}

// After the assistant changes data, refresh whatever the user is looking at.
function _assistantRefreshContext() {
    try {
        if (typeof loadProjects === 'function') loadProjects();
        if (currentProjectId) {
            if (typeof loadProjectDetails === 'function') loadProjectDetails(currentProjectId);
            if (typeof loadTodos === 'function') loadTodos(currentProjectId);
            if (typeof loadChecklist === 'function') loadChecklist(currentProjectId);
            if (typeof loadJurnal === 'function') loadJurnal(currentProjectId);
        }
    } catch (e) { /* refresh is best-effort */ }
}

// Auto-grow the assistant textarea. The panel DOM is parsed after app.js, so
// wait for DOMContentLoaded before binding.
(function () {
    function wireAssistantInput() {
        const ta = document.getElementById('assistant-input');
        if (ta) ta.addEventListener('input', () => {
            ta.style.height = 'auto';
            ta.style.height = Math.min(ta.scrollHeight, 110) + 'px';
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wireAssistantInput);
    else wireAssistantInput();
})();

// ============ GLOBAL SEARCH (command palette) ============

let _gsearchResults = [];
let _gsearchActive = 0;
let _gsearchTimer = null;

// _GS_META / _GS_ORDER (grouped-result metadata) live in core.js
// — shared with the mobile shell.

function openGlobalSearch() {
    const ov = document.getElementById('global-search');
    if (!ov) return;
    ov.classList.add('open');
    const inp = document.getElementById('gsearch-input');
    inp.value = '';
    _gsearchResults = []; _gsearchActive = 0;
    renderGlobalSearch();
    setTimeout(() => inp.focus(), 40);
}

function closeGlobalSearch() {
    const ov = document.getElementById('global-search');
    if (ov) ov.classList.remove('open');
}

function onGlobalSearchInput() {
    clearTimeout(_gsearchTimer);
    _gsearchTimer = setTimeout(doGlobalSearch, 200);
}

async function doGlobalSearch() {
    const q = (document.getElementById('gsearch-input').value || '').trim();
    if (q.length < 2) { _gsearchResults = []; _gsearchActive = 0; renderGlobalSearch(); return; }
    try {
        const res = await fetch('/api/search?q=' + encodeURIComponent(q));
        const data = await res.json();
        const raw = data.results || [];
        // Order by group so keyboard nav matches the on-screen order.
        _gsearchResults = [];
        for (const t of _GS_ORDER) for (const r of raw) if (r.type === t) _gsearchResults.push(r);
        _gsearchActive = 0;
        renderGlobalSearch();
    } catch (e) { console.error('Global search failed:', e); }
}

// _gsHi() is an alias for core.js's _gsHighlight() (shared with mobile).

function renderGlobalSearch() {
    const box = document.getElementById('gsearch-results');
    if (!box) return;
    const q = (document.getElementById('gsearch-input')?.value || '').trim();
    if (q.length < 2) {
        box.innerHTML = '<div class="gsearch-empty">Scrie cel puțin 2 caractere ca să cauți…</div>';
        return;
    }
    if (!_gsearchResults.length) {
        box.innerHTML = `<div class="gsearch-empty">Niciun rezultat pentru „${escapeHtml(q)}"</div>`;
        return;
    }
    let html = '';
    let lastType = null;
    _gsearchResults.forEach((r, idx) => {
        if (r.type !== lastType) {
            html += `<div class="gsearch-group-label">${(_GS_META[r.type] || {}).label || r.type}</div>`;
            lastType = r.type;
        }
        const meta = _GS_META[r.type] || { icon: 'circle' };
        html += `<div class="gsearch-item ${idx === _gsearchActive ? 'active' : ''}" data-idx="${idx}">
            <div class="gsearch-item-icon"><i data-lucide="${meta.icon}"></i></div>
            <div class="gsearch-item-body">
                <div class="gsearch-item-title">${_gsHi(r.title, q)}</div>
                ${r.subtitle ? `<div class="gsearch-item-sub">${escapeHtml(r.subtitle)}</div>` : ''}
                ${r.snippet ? `<div class="gsearch-item-snippet">${_gsHi(r.snippet, q)}</div>` : ''}
            </div>
        </div>`;
    });
    box.innerHTML = html;
    if (window.lucide) try { lucide.createIcons(); } catch (e) {}
    const activeEl = box.querySelector('.gsearch-item.active');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest' });
}

// Highlight every occurrence of `term` inside `container`, scroll the first into
// view. Used at search destinations (Obsidian notes, project observations).
function _highlightTermIn(container, term) {
    if (!container || !term) return null;
    container.querySelectorAll('mark.search-hit').forEach(m => {
        m.parentNode.replaceChild(document.createTextNode(m.textContent), m);
    });
    const lc = term.toLowerCase();
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    const nodes = [];
    while (walker.nextNode()) {
        if (walker.currentNode.nodeValue.toLowerCase().includes(lc)) nodes.push(walker.currentNode);
    }
    let first = null;
    for (const node of nodes) {
        let rest = node.nodeValue;
        const frag = document.createDocumentFragment();
        let pos;
        while ((pos = rest.toLowerCase().indexOf(lc)) >= 0) {
            if (pos > 0) frag.appendChild(document.createTextNode(rest.slice(0, pos)));
            const mark = document.createElement('mark');
            mark.className = 'search-hit';
            mark.textContent = rest.slice(pos, pos + term.length);
            frag.appendChild(mark);
            if (!first) first = mark;
            rest = rest.slice(pos + term.length);
        }
        if (rest) frag.appendChild(document.createTextNode(rest));
        node.parentNode.replaceChild(frag, node);
    }
    if (first) setTimeout(() => first.scrollIntoView({ block: 'center', behavior: 'smooth' }), 60);
    return first;
}

async function _openParamById(paramId) {
    try {
        const p = await apiGet('/parametri/' + encodeURIComponent(paramId));
        if (p && !p.error) openParamModal(p);
    } catch (e) { console.error('open param failed:', e); }
}

async function _openFaultById(faultId) {
    try {
        const f = await apiGet('/fault-codes/' + encodeURIComponent(faultId));
        if (f && !f.error) openFaultModal(f);
    } catch (e) { console.error('open fault failed:', e); }
}

function activateSearchResult(r) {
    const term = (document.getElementById('gsearch-input')?.value || '').trim();
    closeGlobalSearch();
    if (!r) return;
    switch (r.type) {
        case 'proiect':
        case 'task':
        case 'checklist':
        case 'echipament':
        case 'jurnal':
            if (r.proiect_id) showProjectDetail(r.proiect_id);
            break;
        case 'observatie':
            if (r.proiect_id) {
                showProjectDetail(r.proiect_id);
                setTimeout(() => {
                    _highlightTermIn(document.querySelector('#pif-observatii-section .long-text-preview'), term);
                }, 900);
            }
            break;
        case 'global_task':
            switchTab('taskuri');
            break;
        case 'parametru':
            switchTab('parametri');
            _openParamById(r.id);
            break;
        case 'fault_code':
            switchTab('parametri');
            paramSetMode('faults');
            _openFaultById(r.id);
            break;
        case 'obsidian':
            switchTab('notite');
            setTimeout(() => openObsidianNote(r.path, term), 350);
            break;
        case 'client':
            switchTab('proiecte');
            break;
    }
}

// Wire up the palette: Ctrl/Cmd+K toggles it; input + keyboard nav + clicks.
// The palette DOM is parsed AFTER app.js loads, so element wiring waits for
// DOMContentLoaded; the Ctrl+K handler can attach to document immediately.
(function () {
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
            e.preventDefault();
            const ov = document.getElementById('global-search');
            if (ov && ov.classList.contains('open')) closeGlobalSearch();
            else openGlobalSearch();
        }
    });
    function wireGlobalSearch() {
        const inp = document.getElementById('gsearch-input');
        if (inp) {
            inp.addEventListener('input', onGlobalSearchInput);
            inp.addEventListener('keydown', function (e) {
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    _gsearchActive = Math.min(_gsearchActive + 1, _gsearchResults.length - 1);
                    renderGlobalSearch();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    _gsearchActive = Math.max(_gsearchActive - 1, 0);
                    renderGlobalSearch();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    activateSearchResult(_gsearchResults[_gsearchActive]);
                } else if (e.key === 'Escape') {
                    closeGlobalSearch();
                }
            });
        }
        const box = document.getElementById('gsearch-results');
        if (box) box.addEventListener('click', function (e) {
            const item = e.target.closest('.gsearch-item');
            if (item) activateSearchResult(_gsearchResults[+item.getAttribute('data-idx')]);
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wireGlobalSearch);
    else wireGlobalSearch();
})();

async function loadGlobalTasks() {
    try {
        let url = '/global-tasks?';
        if (gtFilters.status) url += `status=${gtFilters.status}&`;
        if (gtFilters.prioritate) url += `prioritate=${gtFilters.prioritate}&`;
        if (gtFilters.categorie) url += `categorie=${gtFilters.categorie}&`;

        const tasks = await apiGet(url);
        // Pre-fetch subtasks for tasks that have them
        const tasksWithSubs = tasks.filter(t => t.subtask_total > 0);
        await Promise.all(tasksWithSubs.map(async (t) => {
            try {
                const subs = await apiGet(`/tasks/${encodeURIComponent(t.id)}/subtasks`);
                _taskSubtasksCache[t.id] = Array.isArray(subs) ? subs : [];
            } catch (e) {
                _taskSubtasksCache[t.id] = [];
            }
        }));
        renderGlobalTasks(tasks);
        updateGtStats(tasks);

        // Update archive count
        const archived = await apiGet('/global-tasks?arhiva=true');
        document.getElementById('archive-count').textContent = archived.length;
    } catch (e) {
        console.error('Failed to load global tasks:', e);
    }
}

function updateGtStats(tasks) {
    const today = new Date().toISOString().split('T')[0];
    const total = tasks.filter(t => !t.data_scadenta || t.data_scadenta === today).length;
    const finalizate = tasks.filter(t => t.status === 'done' && t.data_finalizare && t.data_finalizare.startsWith(today)).length;

    document.getElementById('gt-stat-total').textContent = total;
    document.getElementById('gt-stat-finalizate').textContent = finalizate;
}

function renderGlobalTasks(tasks) {
    const container = document.getElementById('gt-task-list');
    const search = gtFilters.search.toLowerCase();

    // Filter by search
    if (search) {
        tasks = tasks.filter(t =>
            (t.titlu && t.titlu.toLowerCase().includes(search)) ||
            (t.descriere && t.descriere.toLowerCase().includes(search))
        );
    }

    // Sort: Urgent first, then by data_scadenta asc
    const priorityOrder = { 'Urgent': 0, 'Normal': 1, 'Minor': 2 };
    tasks.sort((a, b) => {
        if (a.status === 'done' && b.status !== 'done') return 1;
        if (a.status !== 'done' && b.status === 'done') return -1;
        const pDiff = (priorityOrder[a.prioritate] || 1) - (priorityOrder[b.prioritate] || 1);
        if (pDiff !== 0) return pDiff;
        if (a.data_scadenta && b.data_scadenta) return a.data_scadenta.localeCompare(b.data_scadenta);
        if (a.data_scadenta) return -1;
        if (b.data_scadenta) return 1;
        return 0;
    });

    const today = new Date().toISOString().split('T')[0];

    if (!tasks.length) {
        container.innerHTML = '<p style="color: var(--text2);">Nu există task-uri.</p>';
        return;
    }

    // Group active vs done — Ion wants the finalised pile collapsed by default.
    const active = tasks.filter(t => t.status !== 'done');
    const done = tasks.filter(t => t.status === 'done');
    done.sort((a, b) => (b.data_finalizare || b.updated_at || b.created_at || '').localeCompare(a.data_finalizare || a.updated_at || a.created_at || ''));

    const renderOne = (task) => {
        task._tcard_expanded = _expandedTaskIds.has(task.id);
        return renderTaskCard(task, { kind: 'global' });
    };

    let html = '<div class="tcard-list">' + active.map(renderOne).join('') + '</div>';
    if (done.length > 0) {
        const isCollapsed = localStorage.getItem('pif:gt-done-collapsed') !== '0';
        html += `<div class="tcard-done-sep" onclick="toggleGtDoneCollapse()" data-collapsed="${isCollapsed ? '1' : '0'}">
            <i data-lucide="chevron-${isCollapsed ? 'right' : 'down'}"></i>
            <span>Finalizate (${done.length})</span>
        </div>`;
        html += `<div class="tcard-done-group${isCollapsed ? ' collapsed' : ''}"><div class="tcard-list">${done.map(renderOne).join('')}</div></div>`;
    }
    container.innerHTML = html;
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

function toggleGtDoneCollapse() {
    const key = 'pif:gt-done-collapsed';
    const isCollapsed = localStorage.getItem(key) !== '0';
    localStorage.setItem(key, isCollapsed ? '0' : '1');
    const divider = document.querySelector('#gt-task-list .tcard-done-sep');
    const group = document.querySelector('#gt-task-list .tcard-done-group');
    if (divider && group) {
        divider.setAttribute('data-collapsed', isCollapsed ? '0' : '1');
        const icon = divider.querySelector('[data-lucide]');
        if (icon) {
            icon.setAttribute('data-lucide', isCollapsed ? 'chevron-down' : 'chevron-right');
            if (window.lucide) try { window.lucide.createIcons(); } catch {}
        }
        group.classList.toggle('collapsed', !isCollapsed);
    }
}

// Cycle helpers: click on the priority/status pill rotates through values
// without opening a modal. Used by global tasks AND project todos.
const _PRIO_CYCLE = ['Normal', 'Minor', 'Urgent'];
// Status cycle does NOT include 'done' — to mark a task finalised use the
// checkbox. The status pill only toggles between active states (To Do <-> In Lucru).
const _STATUS_CYCLE = ['to_do', 'in_lucru'];

async function cycleGtPriority(taskId, current) {
    const idx = _PRIO_CYCLE.indexOf(current || 'Normal');
    const next = _PRIO_CYCLE[(idx + 1) % _PRIO_CYCLE.length];
    try {
        await apiPut(`/global-tasks/${taskId}`, { prioritate: next });
        loadGlobalTasks();
    } catch (e) { showToast('Eroare la schimbarea priorității', true); }
}

async function cycleGtStatus(taskId, current) {
    const idx = _STATUS_CYCLE.indexOf(current || 'to_do');
    const next = _STATUS_CYCLE[(idx + 1) % _STATUS_CYCLE.length];
    try {
        await apiPut(`/global-tasks/${taskId}`, { status: next });
        loadGlobalTasks();
    } catch (e) { showToast('Eroare la schimbarea statusului', true); }
}

async function cycleTodoPriority(taskId, current) {
    const idx = _PRIO_CYCLE.indexOf(current || 'Normal');
    const next = _PRIO_CYCLE[(idx + 1) % _PRIO_CYCLE.length];
    try {
        await apiPut(`/tasks/${taskId}`, { prioritate: next.toLowerCase() });
        if (currentProjectId) loadTodos(currentProjectId);
    } catch (e) { showToast('Eroare', true); }
}

async function cycleTodoStatus(taskId, current) {
    const idx = _STATUS_CYCLE.indexOf(current || 'to_do');
    const next = _STATUS_CYCLE[(idx + 1) % _STATUS_CYCLE.length];
    try {
        await apiPut(`/tasks/${taskId}`, { status: next });
        if (currentProjectId) loadTodos(currentProjectId);
    } catch (e) { showToast('Eroare', true); }
}

async function loadProjectTasks() {
    const status = document.getElementById('pt-filter-status')?.value || 'to_do,in_lucru';
    const prioritate = document.getElementById('pt-filter-prioritate')?.value || '';
    try {
        let url = '/global-tasks?';
        if (status) url += `status=${status}&`;
        if (prioritate) url += `prioritate=${prioritate}&`;
        const tasks = await apiGet(url);
        renderProjectTasks(tasks);
    } catch (e) { console.error('Load project tasks error:', e); }
}

function renderProjectTasks(tasks) {
    const container = document.getElementById('project-tasks-list');
    if (!tasks || tasks.length === 0) {
        container.innerHTML = `<p style="color:var(--text2); font-size:0.85rem; font-family:'Courier New',monospace;">Niciun task activ în proiecte.</p>`;
        return;
    }
    const priorityOrder = { 'Urgent': 0, 'Normal': 1, 'Minor': 2 };
    tasks.sort((a, b) => (priorityOrder[a.prioritate] ?? 1) - (priorityOrder[b.prioritate] ?? 1));
    container.innerHTML = tasks.map(t => `
        <div class="gt-task-card ${t.status === 'done' ? 'completed' : ''}" style="border-left:3px solid ${t.proiect_tip === 'PIF' ? 'var(--c3)' : 'var(--c1)'};">
            <input type="checkbox" class="todo-checkbox" ${t.status === 'done' ? 'checked' : ''} onchange="toggleProjectTaskGlobal('${t.id}', this.checked)">
            <div class="todo-content">
                <div class="gt-task-title ${t.status === 'done' ? 'done' : ''}">${escapeHtml(t.titlu)}</div>
                <div class="todo-meta" style="display:flex; gap:8px; flex-wrap:wrap;">
                    <span style="color:var(--accent); font-weight:600;">${escapeHtml(t.proiect_nume || '-')}</span>
                    <span class="badge">${t.proiect_tip || 'PIF'}</span>
                    ${t.data_scadenta ? `<span><i data-lucide="calendar"></i> ${t.data_scadenta}</span>` : ''}
                    ${t.proiect_client ? `<span>👤 ${escapeHtml(t.proiect_client)}</span>` : ''}
                </div>
            </div>
            <span class="todo-priority ${(t.prioritate||'normal').toLowerCase()}">${t.prioritate || 'Normal'}</span>
            <button class="btn btn-small btn-secondary" onclick="showProjectDetail('${t.proiect_id}')" title="Deschide proiectul">→</button>
        </div>
    `).join('');
}

async function toggleProjectTaskGlobal(taskId, checked) {
    try {
        await apiPut(`/tasks/${taskId}`, { status: checked ? 'done' : 'to_do', data_finalizare: checked ? new Date().toISOString() : '' });
        await loadProjectTasks();
    } catch (e) { console.error('Toggle project task error:', e); }
}

async function toggleGtTask(taskId, checked) {
    try {
        await apiPut(`/global-tasks/${taskId}`, {
            status: checked ? 'done' : 'to_do',
            data_finalizare: checked ? new Date().toISOString() : ''
        });
        await loadGlobalTasks();
        // Update archive badge count
        const archived = await apiGet('/global-tasks?arhiva=true');
        document.getElementById('archive-count').textContent = archived.length;
        if (archiveVisible) renderArchive(archived);
    } catch (e) {
        console.error('Failed to toggle global task:', e);
    }
}

// Daily tasks now open the full edit modal (descriere, recurență, subtaskuri).
function editGtTask(taskId) {
    openGtEditModal(taskId);
}

async function deleteGtTask(taskId) {
    try {
        await apiDelete(`/global-tasks/${taskId}`);
        loadGlobalTasks();
        showToast('Task șters!');
    } catch (e) {
        console.error('Failed to delete global task:', e);
    }
}

// ============ ARCHIVE SECTION ============

function toggleArchive() {
    archiveVisible = !archiveVisible;
    document.getElementById('archive-body').style.display = archiveVisible ? 'block' : 'none';
    document.getElementById('archive-chevron').textContent = archiveVisible ? '▲' : '▼';
    if (archiveVisible) loadArchive();
}

let _projectsArchiveOpen = false;
function toggleProjectsArchive() {
    _projectsArchiveOpen = !_projectsArchiveOpen;
    const body = document.getElementById('projects-archive-body');
    const chev = document.getElementById('projects-archive-chevron');
    if (body) body.style.display = _projectsArchiveOpen ? 'block' : 'none';
    if (chev) chev.style.transform = _projectsArchiveOpen ? 'rotate(180deg)' : '';
}

async function loadArchive() {
    try {
        const tasks = await apiGet('/global-tasks?arhiva=true');
        document.getElementById('archive-count').textContent = tasks.length;
        renderArchive(tasks);
    } catch (e) { console.error('Failed to load archive:', e); }
}

async function emptyArchive() {
    try {
        const tasks = await apiGet('/global-tasks?arhiva=true');
        await Promise.all(tasks.map(t => apiDelete(`/global-tasks/${t.id}`)));
        renderArchive(tasks);
    } catch (e) {
        console.error('Failed to load archive:', e);
    }
}

function renderArchive(tasks) {
    const container = document.getElementById('archive-list');
    if (!tasks.length) {
        container.innerHTML = '<p style="color:var(--text2); font-size:0.9rem; text-align:center; padding:16px 0;">Niciun task finalizat.</p>';
        return;
    }
    // Most-recently finalised first.
    tasks = tasks.slice().sort((a, b) => {
        const aDate = a.data_finalizare || a.updated_at || a.created_at || '';
        const bDate = b.data_finalizare || b.updated_at || b.created_at || '';
        return bDate.localeCompare(aDate);
    });
    container.innerHTML = tasks.map(t => `
        <div class="archive-item">
            <span class="archive-title">${escapeHtml(t.titlu)}</span>
            <span class="archive-meta">${t.categorie || ''} · ${t.data_finalizare ? t.data_finalizare.split('T')[0] : ''}</span>
            <button class="btn btn-icon btn-ghost" onclick="restoreTask('${t.id}')" title="Redeschide task"><i data-lucide="undo-2"></i></button>
            <button class="btn btn-icon btn-ghost btn-ghost-danger" onclick="deleteGtTask('${t.id}')" title="Șterge definitiv"><i data-lucide="trash-2"></i></button>
        </div>
    `).join('');
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

async function restoreTask(taskId) {
    try {
        await apiPut(`/global-tasks/${taskId}`, { status: 'to_do', data_finalizare: '' });
        await loadGlobalTasks();
        if (archiveVisible) await loadArchive();
        showToast('Task redeschis!');
    } catch (e) {
        showToast('Eroare la redeschiderea taskului', true);
    }
}

async function clearArchive() {
    if (!confirm('Ștergi definitiv toate taskurile finalizate?')) return;
    try {
        const tasks = await apiGet('/global-tasks?arhiva=true');
        await Promise.all(tasks.map(t => apiDelete(`/global-tasks/${t.id}`)));
        await loadArchive();
        showToast('Arhivă curățată!');
    } catch (e) {
        showToast('Eroare la ștergerea arhivei', true);
    }
}

// ============ QUICK ADD TASK ============

async function quickAddTask() {
    const input = document.getElementById('quick-task-input');
    const titlu = input.value.trim();
    if (!titlu) { input.focus(); return; }

    const prioritate = document.getElementById('quick-prioritate').value;
    const categorie = document.getElementById('quick-categorie').value;
    const scadenta = document.getElementById('quick-scadenta').value;

    input.disabled = true;
    document.getElementById('quick-add-btn').textContent = '✓';

    try {
        await apiPost('/global-tasks', {
            titlu, prioritate, categorie,
            data_scadenta: scadenta || '',
            status: 'to_do'
        });
        input.value = '';
        document.getElementById('quick-scadenta').value = '';
        await loadGlobalTasks();
    } catch (e) {
        showToast('Eroare la adăugarea taskului', true);
    } finally {
        input.disabled = false;
        document.getElementById('quick-add-btn').textContent = '+';
        input.focus();
    }
}

document.getElementById('quick-task-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); quickAddTask(); }
});

// ============ LOGOUT ============

async function logout() {
    try {
        await fetch('/logout');
        window.location.href = '/login';
    } catch (e) {
        console.error('Logout failed:', e);
        window.location.href = '/login';
    }
}

// ============ HOME PAGE ============

// TODO HIGH-Q2: consider unifying — desktop and mobile differ
// (mobile _greetingMobile returns 'Noapte bună' for h<5; this one returns 'Bună seara').
function _greetingRO() {
    const h = new Date().getHours();
    if (h < 5)  return 'Bună seara';
    if (h < 12) return 'Bună dimineața';
    if (h < 18) return 'Bună ziua';
    return 'Bună seara';
}
// TODO HIGH-Q2: consider unifying — desktop and mobile differ
// (mobile _fmtDateMobile uses hard-coded RO weekday/month arrays with capitalised "Luni";
// this one uses toLocaleDateString which yields lowercase "luni"). Different output style.
function _fmtDateRO(d = new Date()) {
    return d.toLocaleDateString('ro-RO', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
}
function _shortDateRO(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString('ro-RO', { day:'numeric', month:'short' });
}
// _elapsed() was a local duplicate of formatTime() — callsites now use formatTime() directly.

async function loadDashboardHome() {
    try {
        const data = await apiGet('/dashboard/home');
        const container = document.getElementById('home-content');
        if (!container) return;

        const { urgent_tasks, upcoming_deadlines, recent_journal, active_timer, todays_tasks, stats } = data;

        // — Page head with greeting —
        let html = `
            <div class="page-head">
                <div>
                    <div class="page-title">${_greetingRO()}, Ion <span class="page-greet">— iată ziua ta</span></div>
                    <div class="page-subtitle">${_fmtDateRO()}</div>
                </div>
            </div>
        `;

        // — 4-stat bar —
        const delta = stats.weekly_delta || 0;
        const deltaStr = delta === 0 ? 'la fel ca săptămâna trecută'
            : delta > 0 ? `<b class="up">+${delta}h</b> față de săpt. trecută`
            : `<b class="down">${delta}h</b> față de săpt. trecută`;

        html += `
            <div class="home-stats">
                <div class="h-stat">
                    <div class="h-stat-row">
                        <span class="h-stat-label">Proiecte Active</span>
                        <span class="h-stat-ico"><i data-lucide="folder-kanban"></i></span>
                    </div>
                    <div class="h-stat-value accent">${stats.active_projects}</div>
                    <div class="h-stat-delta">din <b>${stats.total_projects ?? '—'}</b> total</div>
                </div>
                <div class="h-stat warn">
                    <div class="h-stat-row">
                        <span class="h-stat-label">Task-uri Urgente</span>
                        <span class="h-stat-ico"><i data-lucide="alert-triangle"></i></span>
                    </div>
                    <div class="h-stat-value warn">${stats.urgent_count ?? urgent_tasks.length}</div>
                    <div class="h-stat-delta">${(stats.urgent_count ?? urgent_tasks.length) > 0 ? 'scadență apropiată' : 'fără urgențe'}</div>
                </div>
                <div class="h-stat success">
                    <div class="h-stat-row">
                        <span class="h-stat-label">Ore Săptămâna</span>
                        <span class="h-stat-ico"><i data-lucide="clock"></i></span>
                    </div>
                    <div class="h-stat-value success">${stats.weekly_hours}<span style="font-size:14px;color:var(--text2);">h</span></div>
                    <div class="h-stat-delta">${deltaStr}</div>
                </div>
                <div class="h-stat violet">
                    <div class="h-stat-row">
                        <span class="h-stat-label">Deadline-uri</span>
                        <span class="h-stat-ico"><i data-lucide="calendar-clock"></i></span>
                    </div>
                    <div class="h-stat-value violet">${stats.deadline_count ?? upcoming_deadlines.length}</div>
                    <div class="h-stat-delta">în următoarele 7 zile</div>
                </div>
            </div>
        `;

        // — Active timer banner —
        if (active_timer) {
            const startTime = new Date(active_timer.start_time);
            const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
            html += `
                <div class="h-timer">
                    <div class="h-timer-dot"></div>
                    <div class="h-timer-meta">
                        <div class="h-timer-title">
                            ${escapeHtml(active_timer.project_name || active_timer.proiect_nume || 'Proiect')}
                            <span class="h-timer-tag">Activ</span>
                        </div>
                        <div class="h-timer-sub">Pornit la ${startTime.toLocaleTimeString('ro-RO',{hour:'2-digit',minute:'2-digit'})}</div>
                    </div>
                    <div class="h-timer-elapsed" id="home-timer-elapsed" data-start="${active_timer.start_time}">${formatTime(elapsedSec)}</div>
                </div>
            `;
        }

        // — Card grid —
        html += `<div class="home-grid">`;

        // Card 1: Urgent
        html += `
            <div class="h-card">
                <div class="h-card-head">
                    <span class="h-card-ico danger"><i data-lucide="alert-triangle"></i></span>
                    <span class="h-card-title">Task-uri Urgente</span>
                    <span class="h-card-count">${urgent_tasks.length}</span>
                </div>
                <div class="h-card-body">
        `;
        if (!urgent_tasks.length) {
            html += `<div class="h-empty">Nicio sarcină urgentă</div>`;
        } else {
            urgent_tasks.forEach(t => {
                const proj = t.proiect_nume ? escapeHtml(t.proiect_nume) : '—';
                const date = t.data_scadenta ? `<span><i data-lucide="calendar"></i> ${t.data_scadenta}</span>` : '';
                const onclick = t.proiect_id ? `onclick="showProjectDetail('${t.proiect_id}')"` : '';
                html += `
                    <div class="h-row" ${onclick}>
                        <span class="h-row-dot urgent"></span>
                        <div class="h-row-content">
                            <div class="h-row-title">${escapeHtml(t.titlu)}</div>
                            <div class="h-row-meta"><span>${proj}</span>${date ? '<span>•</span>' + date : ''}</div>
                        </div>
                        <span class="h-row-badge urgent">Urgent</span>
                    </div>
                `;
            });
        }
        html += `</div></div>`;

        // Card 2: Deadlines
        html += `
            <div class="h-card">
                <div class="h-card-head">
                    <span class="h-card-ico violet"><i data-lucide="calendar-clock"></i></span>
                    <span class="h-card-title">Deadline-uri Următoare</span>
                    <span class="h-card-count">${upcoming_deadlines.length}</span>
                </div>
                <div class="h-card-body">
        `;
        if (!upcoming_deadlines.length) {
            html += `<div class="h-empty">Niciun deadline în 7 zile</div>`;
        } else {
            upcoming_deadlines.forEach(p => {
                html += `
                    <div class="h-row" onclick="showProjectDetail('${p.id}')">
                        <span class="h-row-dot due"></span>
                        <div class="h-row-content">
                            <div class="h-row-title">${escapeHtml(p.nume)}</div>
                            <div class="h-row-meta"><span>${escapeHtml(p.client || '—')}</span></div>
                        </div>
                        <span class="h-row-date">${_shortDateRO(p.deadline)}</span>
                    </div>
                `;
            });
        }
        html += `</div></div>`;

        // Card 3: Tasks Globale
        html += `
            <div class="h-card">
                <div class="h-card-head">
                    <span class="h-card-ico"><i data-lucide="list-checks"></i></span>
                    <span class="h-card-title">Task-uri Globale</span>
                    <span class="h-card-count">${todays_tasks.length}</span>
                </div>
                <div class="h-card-body">
        `;
        if (!todays_tasks.length) {
            html += `<div class="h-empty">Nicio sarcină globală activă</div>`;
        } else {
            todays_tasks.forEach(t => {
                const prio = (t.prioritate || 'Normal');
                const prioCls = prio.toLowerCase();
                // Click pe task global: dacă are proiect, du-te acolo; altfel deschide tab Taskuri.
                const onclickAttr = t.proiect_id
                    ? `onclick="showProjectDetail('${t.proiect_id}')"`
                    : `onclick="switchTab('taskuri')"`;
                html += `
                    <div class="h-row" ${onclickAttr}>
                        <span class="h-row-dot ${prioCls}"></span>
                        <div class="h-row-content">
                            <div class="h-row-title">${escapeHtml(t.titlu)}</div>
                            <div class="h-row-meta"><span>${escapeHtml(t.categorie || 'General')}</span></div>
                        </div>
                        <span class="h-row-badge ${prioCls}">${prio}</span>
                    </div>
                `;
            });
        }
        html += `</div></div>`;

        // Card 4: Jurnal Recent
        html += `
            <div class="h-card">
                <div class="h-card-head">
                    <span class="h-card-ico warning"><i data-lucide="notebook-pen"></i></span>
                    <span class="h-card-title">Jurnal Recent</span>
                    <span class="h-card-count">${recent_journal.length}</span>
                </div>
                <div class="h-card-body">
        `;
        if (!recent_journal.length) {
            html += `<div class="h-empty">Nicio intrare în jurnal</div>`;
        } else {
            recent_journal.forEach(e => {
                html += `
                    <div class="h-row" onclick="showProjectDetail('${e.proiect_id}')">
                        <span class="h-row-dot neutral"></span>
                        <div class="h-row-content">
                            <div class="h-row-title">${escapeHtml(e.continut)}</div>
                            <div class="h-row-meta">
                                <span>${escapeHtml(e.project_name || '')}</span>
                                <span>•</span>
                                <span><i data-lucide="calendar"></i> ${_shortDateRO(e.data)}</span>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        html += `</div></div>`;

        html += `</div>`;

        container.innerHTML = html;

        // Live timer update on home page
        if (active_timer) {
            if (window._homeTimerInterval) clearInterval(window._homeTimerInterval);
            window._homeTimerInterval = setInterval(() => {
                const el = document.getElementById('home-timer-elapsed');
                if (!el) { clearInterval(window._homeTimerInterval); return; }
                const start = new Date(el.dataset.start);
                el.textContent = formatTime(Math.floor((Date.now() - start) / 1000));
            }, 1000);
        }

    } catch (e) {
        console.error('Failed to load dashboard home:', e);
        const container = document.getElementById('home-content');
        if (container) {
            container.innerHTML = `<div style="color:var(--text2);padding:20px;text-align:center;">Eroare la încărcarea datelor.</div>`;
        }
    }
}

function quickAddTaskFromHome() {
    switchTab('taskuri');
    setTimeout(() => {
        const input = document.getElementById('quick-task-input');
        if (input) input.focus();
    }, 100);
}

// ============ CHECKLIST PIF ============

// ============ CHECKLIST PIF cu CATEGORII DINAMICE ============
// Fiecare proiect are propriile categorii (per-project, NOT global).
// Item-urile orfane (categorie_id NULL) intra in bucket-ul virtual "Fara categorie".

async function loadChecklist(projectId) {
    try {
        const [items, categorii] = await Promise.all([
            apiGet(`/proiecte/${projectId}/checklist`),
            apiGet(`/proiecte/${projectId}/checklist-categorii`).catch(() => [])
        ]);
        renderChecklist(items || [], categorii || []);
    } catch (e) {
        console.error('Failed to load checklist:', e);
    }
}

// Cache collapsed state per project in localStorage.
function _checklistCollapsedKey(projectId) { return `pif:checklist:collapsed:${projectId}`; }
function _getChecklistCollapsed(projectId) {
    try { return new Set(JSON.parse(localStorage.getItem(_checklistCollapsedKey(projectId)) || '[]')); }
    catch { return new Set(); }
}
function _setChecklistCollapsed(projectId, set) {
    try { localStorage.setItem(_checklistCollapsedKey(projectId), JSON.stringify([...set])); } catch {}
}

function toggleChecklistCategoryCollapse(catKey) {
    const projectId = currentProjectId;
    if (!projectId) return;
    const collapsed = _getChecklistCollapsed(projectId);
    if (collapsed.has(catKey)) collapsed.delete(catKey);
    else collapsed.add(catKey);
    _setChecklistCollapsed(projectId, collapsed);
    const el = document.querySelector(`.checklist-cat[data-cat-key="${catKey}"]`);
    if (el) el.classList.toggle('collapsed');
}

function renderChecklist(items, categorii) {
    const container = document.getElementById('checklist-list');
    const progressFill = document.getElementById('checklist-progress-fill');
    const progressText = document.getElementById('checklist-progress-text');
    if (!container) return;

    const total = items.length;
    const done = items.filter(i => i.completed).length;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    if (progressFill) progressFill.style.width = pct + '%';
    if (progressText) progressText.textContent = `${pct}% completat (${done}/${total})`;

    const collapsed = _getChecklistCollapsed(currentProjectId);

    // Group items by categorie_id (null -> bucket "0")
    const byCat = new Map();
    for (const it of items) {
        const key = it.categorie_id != null ? String(it.categorie_id) : '0';
        if (!byCat.has(key)) byCat.set(key, []);
        byCat.get(key).push(it);
    }

    // Build render order: user categories in their `ordine`, then "Fara categorie" bucket at the end.
    const orderedCats = [...categorii].sort((a, b) => (a.ordine ?? 0) - (b.ordine ?? 0));
    const uncategorizedItems = byCat.get('0') || [];

    const blocks = [];
    blocks.push(`
        <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
            <button class="btn btn-secondary btn-add-cat" onclick="addChecklistCategory()"><i data-lucide="folder-plus"></i> Categorie nouă</button>
        </div>
    `);

    for (const cat of orderedCats) {
        const its = byCat.get(String(cat.id)) || [];
        blocks.push(_renderChecklistCatBlock(cat, its, collapsed));
    }
    // "Fara categorie" — mereu vizibil pentru a aluneca items adăugate fără categorie.
    blocks.push(_renderChecklistCatBlock({ id: 0, nume: 'Fără categorie' }, uncategorizedItems, collapsed, true));

    container.innerHTML = blocks.join('');
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
}

function _renderChecklistCatBlock(cat, items, collapsed, isUncategorized = false) {
    const catKey = String(cat.id);
    const isCollapsed = collapsed.has(catKey);
    const total = items.length;
    const done = items.filter(i => i.completed).length;
    const progressClass = (total > 0 && done === total) ? 'done' : '';
    const progressText = total > 0 ? `${done}/${total}` : '0/0';

    const actions = isUncategorized ? '' : `
        <div class="checklist-cat-actions">
            <button class="cat-action" onclick="event.stopPropagation(); renameChecklistCategory(${cat.id})" title="Redenumește"><i data-lucide="pencil"></i></button>
            <button class="cat-action danger" onclick="event.stopPropagation(); deleteChecklistCategory(${cat.id}, '${escapeHtml(cat.nume).replace(/'/g, "\\'")}')" title="Șterge categorie"><i data-lucide="trash-2"></i></button>
        </div>`;

    const rows = items.map(it => `
        <div class="checklist-item ${it.completed ? 'done' : ''}">
            <input type="checkbox" ${it.completed ? 'checked' : ''}
                   onchange="toggleChecklistItem('${it.id}', this.checked)">
            <span class="checklist-title">${escapeHtml(it.titlu || '')}</span>
            <button class="btn btn-icon btn-ghost btn-ghost-danger" onclick="deleteChecklistItem('${it.id}')" title="Șterge"><i data-lucide="trash-2"></i></button>
        </div>
    `).join('') || `<div class="checklist-cat-empty">Niciun item în această categorie.</div>`;

    const addRow = `
        <div class="checklist-add-row">
            <input type="text" placeholder="${isUncategorized ? 'Adaugă item fără categorie...' : 'Adaugă item...'}"
                   onkeydown="if(event.key==='Enter') addChecklistItem(${isUncategorized ? 'null' : cat.id})">
            <button class="btn btn-primary btn-small" onclick="addChecklistItem(${isUncategorized ? 'null' : cat.id})"><i data-lucide="plus"></i></button>
        </div>
    `;

    return `
        <div class="checklist-cat ${isCollapsed ? 'collapsed' : ''} ${isUncategorized ? 'uncategorized' : ''}" data-cat-key="${catKey}">
            <div class="checklist-cat-head" onclick="toggleChecklistCategoryCollapse('${catKey}')">
                <span class="cat-chevron"><i data-lucide="chevron-down"></i></span>
                <span class="checklist-cat-name">${escapeHtml(cat.nume)}</span>
                <span class="checklist-cat-progress ${progressClass}">${progressText}</span>
                ${actions}
            </div>
            <div class="checklist-cat-body">
                ${rows}
                ${addRow}
            </div>
        </div>
    `;
}

// ===== Universal ask modal (replaces prompt() / confirm()) =====
let _pifAskResolve = null;
function pifAsk({ title = 'Confirmare', message = '', input = false, defaultValue = '', okLabel = 'OK', cancelLabel = 'Anulează', danger = false }) {
    return new Promise(resolve => {
        _pifAskResolve = resolve;
        document.getElementById('pif-ask-title').textContent = title;
        document.getElementById('pif-ask-message').textContent = message;
        const inputEl = document.getElementById('pif-ask-input');
        if (input) {
            inputEl.style.display = '';
            inputEl.value = defaultValue;
        } else {
            inputEl.style.display = 'none';
        }
        const okBtn = document.getElementById('pif-ask-ok');
        okBtn.textContent = okLabel;
        okBtn.className = danger ? 'btn btn-danger' : 'btn btn-primary';
        document.getElementById('pif-ask-cancel').textContent = cancelLabel;
        document.getElementById('pif-ask-modal').classList.add('active');
        setTimeout(() => { if (input) inputEl.focus(); else okBtn.focus(); }, 50);
    });
}
function _pifAskClose(value) {
    document.getElementById('pif-ask-modal').classList.remove('active');
    const r = _pifAskResolve; _pifAskResolve = null;
    if (r) r(value);
}
function _pifAskSubmit() {
    const inputEl = document.getElementById('pif-ask-input');
    if (inputEl.style.display !== 'none') {
        _pifAskClose(inputEl.value.trim());
    } else {
        _pifAskClose(true);
    }
}

async function addChecklistCategory() {
    if (!currentProjectId) return;
    const nume = await pifAsk({
        title: 'Categorie nouă',
        message: 'Cum se numește noua categorie de checklist? (ex: Verificări mecanice, Electrice...)',
        input: true,
        okLabel: 'Creează'
    });
    if (!nume) return;
    try {
        await apiPost(`/proiecte/${currentProjectId}/checklist-categorii`, { nume });
        showToast('Categorie creată!');
        loadChecklist(currentProjectId);
    } catch (e) {
        console.error('Failed to add category:', e);
        showToast('Eroare la creare: ' + (e.message || e), true);
    }
}

async function renameChecklistCategory(catId) {
    if (!currentProjectId) return;
    const current = document.querySelector(`.checklist-cat[data-cat-key="${catId}"] .checklist-cat-name`)?.textContent || '';
    const newName = await pifAsk({
        title: 'Redenumește categorie',
        message: `Categoria "${current}"`,
        input: true,
        defaultValue: current,
        okLabel: 'Salvează'
    });
    if (!newName || newName === current) return;
    try {
        await apiPut(`/checklist-categorii/${catId}`, { nume: newName });
        loadChecklist(currentProjectId);
    } catch (e) {
        showToast('Eroare la redenumire: ' + (e.message || e), true);
    }
}

async function deleteChecklistCategory(catId, catName) {
    if (!currentProjectId) return;
    const ok = await pifAsk({
        title: 'Șterge categorie',
        message: `Ștergi categoria "${catName}"? Item-urile vor fi mutate la "Fără categorie", nu se șterg.`,
        okLabel: 'Șterge categoria',
        danger: true
    });
    if (!ok) return;
    try {
        await apiDelete(`/checklist-categorii/${catId}?move=1`);
        loadChecklist(currentProjectId);
        showToast('Categorie ștearsă, items mutate la "Fără categorie"');
    } catch (e) {
        console.error('Delete category failed:', e);
        showToast('Eroare la ștergere: ' + (e.message || e), true);
    }
}

async function addChecklistItem(categorieId) {
    // Find the input inside the matching category's add-row
    const catKey = categorieId == null ? '0' : String(categorieId);
    const root = document.querySelector(`.checklist-cat[data-cat-key="${catKey}"] .checklist-add-row input`);
    const title = (root?.value || '').trim();
    if (!title || !currentProjectId) return;

    try {
        await apiPost(`/proiecte/${currentProjectId}/checklist`, {
            titlu: title,
            completed: 0,
            ordine: 0,
            categorie_id: categorieId
        });
        if (root) root.value = '';
        loadChecklist(currentProjectId);
    } catch (e) {
        console.error('Failed to add checklist item:', e);
        showToast('Eroare la adăugare', true);
    }
}

async function toggleChecklistItem(itemId, checked) {
    try {
        await apiPut(`/checklist/${itemId}`, {
            completed: checked ? 1 : 0
        });
        loadChecklist(currentProjectId);
    } catch (e) {
        console.error('Failed to toggle checklist item:', e);
    }
}

async function deleteChecklistItem(itemId) {
    try {
        await apiDelete(`/checklist/${itemId}`);
        loadChecklist(currentProjectId);
        showToast('Item șters!');
    } catch (e) {
        console.error('Failed to delete checklist item:', e);
    }
}

// ============ TIMER ============

let timerInterval = null;
let activeSessionId = null;

async function loadTimerSessions(projectId) {
    try {
        const data = await apiGet(`/proiecte/${projectId}/timer`);
        renderTimerSessions(data.sessions, data.total_secunde);
    } catch (e) {
        console.error('Failed to load timer sessions:', e);
    }
}

function renderTimerSessions(sessions, totalSeconds) {
    // Return '' when there are no bare timer sessions — the caller (loadJurnal)
    // already shows a unified fallback if both this AND the journal are empty.
    // Don't claim "Nu există sesiuni timer" when journal entries cover them.
    if (!sessions || sessions.length === 0) return '';
    return sessions.map(s => `
        <div class="timer-session jurnal-enter">
            <i data-lucide="timer" class="jurnal-icon"></i>
            <span class="jurnal-duration-plain">${formatTimerDuration(s.durata_secunde)}</span>
            <span class="jurnal-date">${s.start_time ? new Date(s.start_time).toLocaleDateString('ro-RO') : ''}</span>
            <span class="jurnal-text" style="color:var(--text-dim); font-style:italic;">Timer fără notă</span>
            <button class="btn btn-icon btn-ghost btn-ghost-danger" onclick="deleteTimerSession('${s.id}')" title="Șterge"><i data-lucide="trash-2"></i></button>
        </div>
    `).join('');
}

function formatTimerDuration(seconds) {
    if (!seconds) return '0m';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

async function startTimer() {
    if (!currentProjectId) return;

    try {
        const data = await apiPost(`/proiecte/${currentProjectId}/timer/start`, {});
        activeSessionId = data.id;

        document.getElementById('timer-start').style.display = 'none';
        document.getElementById('timer-stop').style.display = 'inline-flex';

        // Start interval to update display.
        // Use LOCAL Date.now() instead of server's start_time to avoid clock drift between Pi and client.
        // Server-side stop_timer computes the real duration from its own clock.
        const startTime = Date.now();
        timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            document.getElementById('timer-display').textContent = formatTime(elapsed);
        }, 1000);

        showToast('Timer pornit!');
    } catch (e) {
        console.error('Failed to start timer:', e);
        showToast('Eroare la pornirea timer-ului', true);
    }
}

async function stopTimer() {
    if (!currentProjectId) return;

    // Hide form synchronously before the network call — Ion expects fields to
    // disappear the moment he clicks save, not after the round-trip.
    stopTimerUI();
    try {
        await apiPost(`/proiecte/${currentProjectId}/timer/stop`, {});
        loadJurnal(currentProjectId);
        showToast('Timer oprit!');
    } catch (e) {
        console.error('Failed to stop timer:', e);
        showToast('Eroare la oprirea timer-ului', true);
    }
}

function showStopTimerForm() {
    document.getElementById('timer-stop-form').style.display = 'block';
    document.getElementById('timer-titlu').focus();
}

async function stopTimerWithNote() {
    if (!currentProjectId) return;
    const titlu = document.getElementById('timer-titlu').value.trim() || 'Activitate';
    const note  = document.getElementById('timer-note').value.trim();
    // Hide form synchronously before the network call.
    stopTimerUI();
    try {
        await apiPost(`/proiecte/${currentProjectId}/timer/stop-with-note`, { titlu, note });
        await loadJurnal(currentProjectId);
        showToast('Activitate salvată în jurnal!');
    } catch (e) { console.error('Stop timer error:', e); showToast('Eroare la oprirea timerului', true); }
}

// Single source of truth for resetting the timer UI after stop (both with and
// without note). Clears inputs and hides the stop-form so fields disappear once
// the entry is saved.
function stopTimerUI() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    const display = document.getElementById('timer-display');
    if (display) display.textContent = '00:00:00';
    const titluEl = document.getElementById('timer-titlu');
    const noteEl  = document.getElementById('timer-note');
    if (titluEl) titluEl.value = '';
    if (noteEl)  noteEl.value  = '';
    const form = document.getElementById('timer-stop-form');
    if (form) form.style.display = 'none';
    const startBtn = document.getElementById('timer-start');
    const stopBtn  = document.getElementById('timer-stop');
    if (startBtn) startBtn.style.display = 'inline-flex';
    if (stopBtn)  stopBtn.style.display  = 'none';
}

async function deleteTimerSession(sessionId) {
    try {
        await apiDelete(`/timer/${sessionId}`);
        loadJurnal(currentProjectId);
        showToast('Sesiune ștearsă!');
    } catch (e) {
        console.error('Failed to delete timer session:', e);
    }
}

// formatTime() lives in core.js (shared with the mobile shell, as formatDuration).

// ============ SVG CHARTS (pure SVG, no Chart.js dependency) ============

function cssVar(name) {
    return getComputedStyle(document.documentElement)
        .getPropertyValue(name).trim();
}

function svgEl(tag, attrs = {}) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
}

function makeSVG(width, height) {
    return svgEl('svg', {
        viewBox: `0 0 ${width} ${height}`,
        xmlns: 'http://www.w3.org/2000/svg',
        'aria-hidden': 'true'
    });
}

function svgEmptyState(message) {
    return `<div style="text-align:center; padding:24px 16px;
        color:var(--chart-text);
        font-family:'Courier New',monospace; font-size:0.82rem;
        opacity:0.6;">
        [ — ] ${message}
    </div>`;
}

function renderDonutChart(containerId, data, labels) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const colors = [cssVar('--c1'), cssVar('--c2'), cssVar('--c3'), cssVar('--c4'), cssVar('--c5')];
    const textColor = cssVar('--chart-text');
    const bgColor = cssVar('--chart-bg') || cssVar('--bg2') || '#0e1117';
    if (!data || data.length === 0) { container.innerHTML = svgEmptyState('Nu există date'); return; }
    const W = 280, H = 280, cx = 100, cy = 130, R = 85, r = 52;
    const total = data.reduce((a, b) => a + b, 0);
    const svg = makeSVG(W, H);
    svg.appendChild(svgEl('circle', { cx, cy, r: R, fill: 'none', stroke: cssVar('--chart-grid') || 'rgba(138,122,90,0.15)', 'stroke-width': '1' }));
    let angle = -Math.PI / 2;
    data.forEach((val, i) => {
        const slice = (val / total) * 2 * Math.PI;
        const x1 = cx + R * Math.cos(angle), y1 = cy + R * Math.sin(angle);
        const x2 = cx + R * Math.cos(angle + slice), y2 = cy + R * Math.sin(angle + slice);
        const x3 = cx + r * Math.cos(angle + slice), y3 = cy + r * Math.sin(angle + slice);
        const x4 = cx + r * Math.cos(angle), y4 = cy + r * Math.sin(angle);
        const large = slice > Math.PI ? 1 : 0;
        svg.appendChild(svgEl('path', {
            d: `M ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2} L ${x3} ${y3} A ${r} ${r} 0 ${large} 0 ${x4} ${y4} Z`,
            fill: colors[i % colors.length], stroke: bgColor, 'stroke-width': '2'
        }));
        angle += slice;
    });
    const totalText = svgEl('text', { x: cx, y: cy - 6, 'text-anchor': 'middle', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '22', 'font-weight': '700' });
    totalText.textContent = total; svg.appendChild(totalText);
    const totalLabel = svgEl('text', { x: cx, y: cy + 14, 'text-anchor': 'middle', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '10', opacity: '0.7' });
    totalLabel.textContent = 'TOTAL'; svg.appendChild(totalLabel);
    const legendX = 210, legendStartY = 60;
    labels.forEach((label, i) => {
        const ly = legendStartY + i * 28;
        svg.appendChild(svgEl('rect', { x: legendX, y: ly - 9, width: 12, height: 12, rx: '2', fill: colors[i % colors.length] }));
        const t = svgEl('text', { x: legendX + 18, y: ly + 1, fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '11' });
        t.textContent = `${label} (${data[i]})`; svg.appendChild(t);
    });
    container.innerHTML = ''; container.appendChild(svg);
}

function renderBarChart(containerId, labels, values, colorIndex = 0) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!values || values.length === 0) { container.innerHTML = svgEmptyState('Nu există date'); return; }
    const colors = [cssVar('--c1'), cssVar('--c2'), cssVar('--c3'), cssVar('--c4'), cssVar('--c5')];
    const textColor = cssVar('--chart-text');
    const gridColor = cssVar('--chart-grid') || 'rgba(138,122,90,0.15)';
    const W = 380, H = 200, padL = 30, padR = 10, padT = 15, padB = 45;
    const chartW = W - padL - padR, chartH = H - padT - padB;
    const maxVal = Math.max(...values, 1);
    const barW = Math.min(40, (chartW / values.length) * 0.6);
    const gap = chartW / values.length;
    const svg = makeSVG(W, H);
    [0, 0.25, 0.5, 0.75, 1].forEach(fraction => {
        const y = padT + chartH * (1 - fraction);
        svg.appendChild(svgEl('line', { x1: padL, y1: y, x2: W - padR, y2: y, stroke: gridColor, 'stroke-width': '0.5', 'stroke-dasharray': fraction === 0 ? 'none' : '3,3' }));
        if (fraction > 0) {
            const t = svgEl('text', { x: padL - 4, y: y + 3, 'text-anchor': 'end', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '9' });
            t.textContent = Math.round(maxVal * fraction); svg.appendChild(t);
        }
    });
    values.forEach((val, i) => {
        const barH = (val / maxVal) * chartH;
        const x = padL + gap * i + gap / 2 - barW / 2, y = padT + chartH - barH;
        svg.appendChild(svgEl('rect', { x, y, width: barW, height: Math.max(barH, 1), rx: '2', fill: colors[(colorIndex + i) % colors.length] }));
        const valT = svgEl('text', { x: x + barW / 2, y: y - 4, 'text-anchor': 'middle', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '10', 'font-weight': '600' });
        valT.textContent = val; svg.appendChild(valT);
        const labelT = svgEl('text', { x: x + barW / 2, y: H - padB + 14, 'text-anchor': 'middle', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '10' });
        labelT.textContent = labels[i].length > 8 ? labels[i].substring(0, 7) + '…' : labels[i]; svg.appendChild(labelT);
    });
    container.innerHTML = ''; container.appendChild(svg);
}

function renderLineChart(containerId, labels, values) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!values || values.length === 0) { container.innerHTML = svgEmptyState('Nu există date'); return; }
    const accentColor = cssVar('--c1');
    const textColor = cssVar('--chart-text');
    const gridColor = cssVar('--chart-grid') || 'rgba(138,122,90,0.15)';
    const fillColor = accentColor + '22';
    const W = 380, H = 200, padL = 30, padR = 15, padT = 15, padB = 40;
    const chartW = W - padL - padR, chartH = H - padT - padB;
    const maxVal = Math.max(...values, 1);
    const stepX = chartW / (values.length - 1 || 1);
    const svg = makeSVG(W, H);
    [0, 0.25, 0.5, 0.75, 1].forEach(f => {
        const y = padT + chartH * (1 - f);
        svg.appendChild(svgEl('line', { x1: padL, y1: y, x2: W - padR, y2: y, stroke: gridColor, 'stroke-width': '0.5', 'stroke-dasharray': f === 0 ? 'none' : '3,3' }));
        if (f > 0) { const t = svgEl('text', { x: padL - 4, y: y + 3, 'text-anchor': 'end', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '9' }); t.textContent = Math.round(maxVal * f); svg.appendChild(t); }
    });
    const pts = values.map((v, i) => ({ x: padL + i * stepX, y: padT + chartH - (v / maxVal) * chartH }));
    const fillPath = ['M', pts[0].x, padT + chartH];
    pts.forEach(p => fillPath.push('L', p.x, p.y));
    fillPath.push('L', pts[pts.length - 1].x, padT + chartH, 'Z');
    svg.appendChild(svgEl('path', { d: fillPath.join(' '), fill: fillColor, stroke: 'none' }));
    const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
    svg.appendChild(svgEl('path', { d: linePath, fill: 'none', stroke: accentColor, 'stroke-width': '2', 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    pts.forEach((p, i) => {
        svg.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: '3.5', fill: accentColor, stroke: cssVar('--chart-bg') || cssVar('--bg') || '#0e1117', 'stroke-width': '1.5' }));
        const t = svgEl('text', { x: p.x, y: H - padB + 14, 'text-anchor': 'middle', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '9' });
        t.textContent = labels[i].length > 7 ? labels[i].substring(2) : labels[i]; svg.appendChild(t);
    });
    container.innerHTML = ''; container.appendChild(svg);
}

function renderHBarChart(containerId, labels, values) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!values || values.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:32px 16px; color:var(--chart-text); font-family:'Courier New',monospace; font-size:0.85rem;"><div style="font-size:1.4rem; margin-bottom:8px; opacity:0.4;">[ 0h ]</div>nicio sesiune timer înregistrată</div>`;
        return;
    }
    const accentColor = cssVar('--c2');
    const textColor = cssVar('--chart-text');
    const gridColor = cssVar('--chart-grid') || 'rgba(138,122,90,0.15)';
    const rowH = 28, padL = 130, padR = 50, padT = 10, padB = 10;
    const maxVal = Math.max(...values, 1);
    const chartW = 380 - padL - padR;
    const H = padT + padB + values.length * rowH;
    const svg = makeSVG(380, H);
    values.forEach((val, i) => {
        const y = padT + i * rowH, barW = (val / maxVal) * chartW;
        if (i % 2 === 0) svg.appendChild(svgEl('rect', { x: 0, y, width: 380, height: rowH, fill: gridColor, opacity: '0.4' }));
        const labelT = svgEl('text', { x: padL - 8, y: y + rowH / 2 + 4, 'text-anchor': 'end', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '10' });
        labelT.textContent = labels[i].length > 18 ? labels[i].substring(0, 17) + '…' : labels[i]; svg.appendChild(labelT);
        svg.appendChild(svgEl('rect', { x: padL, y: y + 5, width: Math.max(barW, 2), height: rowH - 10, rx: '2', fill: accentColor }));
        const valT = svgEl('text', { x: padL + barW + 6, y: y + rowH / 2 + 4, fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '10', 'font-weight': '600' });
        valT.textContent = val + 'h'; svg.appendChild(valT);
    });
    container.innerHTML = ''; container.appendChild(svg);
}

function initCharts(data) {
    renderDonutChart('chart-status', (data.by_status || []).map(s => s.count), (data.by_status || []).map(s => getStatusLabel(s.status)));
    renderBarChart('chart-manufacturer', (data.by_manufacturer || []).map(m => m.producator || 'Altul'), (data.by_manufacturer || []).map(m => m.count), 0);
    renderLineChart('chart-monthly', (data.by_month || []).map(m => m.month), (data.by_month || []).map(m => m.count));
    renderHBarChart('chart-hours', (data.hours_per_project || []).map(h => h.nume), (data.hours_per_project || []).map(h => h.hours));
}


// ============ TIMELINE ============

function renderTimeline(projects) {
    const container = document.getElementById('timeline-container');
    if (!container) return;
    const withDates = (projects || []).filter(p => p.data_incepere || p.deadline);
    if (withDates.length === 0) { container.innerHTML = svgEmptyState('Nu există proiecte cu date definite'); return; }
    const today = new Date();
    let minDate = new Date(today.getTime() - 60 * 86400000);
    let maxDate = new Date(today.getTime() + 60 * 86400000);
    withDates.forEach(p => {
        if (p.data_incepere) { const d = new Date(p.data_incepere); if (d < minDate) minDate = d; }
        if (p.deadline) { const d = new Date(p.deadline); if (d > maxDate) maxDate = d; }
    });
    const totalRange = maxDate - minDate;
    const statusColors = { in_lucru: cssVar('--c3'), finalizat: cssVar('--c2'), in_asteptare: cssVar('--c1') };
    const textColor = cssVar('--chart-text');
    const gridColor = cssVar('--chart-grid') || 'rgba(138,122,90,0.15)';
    const accentColor = cssVar('--c1');
    const rowH = 32, padL = 160, padR = 16, padT = 8, padB = 24;
    const W = 800, chartW = W - padL - padR;
    const H = padT + padB + withDates.length * rowH;
    const svg = makeSVG(W, H);
    const cursor = new Date(minDate.getFullYear(), minDate.getMonth(), 1);
    while (cursor <= maxDate) {
        const x = padL + ((cursor - minDate) / totalRange) * chartW;
        svg.appendChild(svgEl('line', { x1: x, y1: padT, x2: x, y2: H - padB, stroke: gridColor, 'stroke-width': '0.5', 'stroke-dasharray': '3,4' }));
        const t = svgEl('text', { x, y: H - 6, 'text-anchor': 'middle', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '9' });
        t.textContent = cursor.toLocaleDateString('ro-RO', { month: 'short', year: '2-digit' }); svg.appendChild(t);
        cursor.setMonth(cursor.getMonth() + 1);
    }
    withDates.forEach((p, i) => {
        const y = padT + i * rowH;
        const start = p.data_incepere ? new Date(p.data_incepere) : minDate;
        const end = p.deadline ? new Date(p.deadline) : maxDate;
        const left = Math.max(0, ((start - minDate) / totalRange) * chartW);
        const width = Math.min(chartW - left, Math.max(6, ((end - start) / totalRange) * chartW));
        const color = statusColors[p.status] || cssVar('--c3');
        if (i % 2 === 0) svg.appendChild(svgEl('rect', { x: 0, y, width: W, height: rowH, fill: gridColor, opacity: '0.3' }));
        const labelT = svgEl('text', { x: padL - 8, y: y + rowH / 2 + 4, 'text-anchor': 'end', fill: textColor, 'font-family': "'Courier New', monospace", 'font-size': '10' });
        labelT.textContent = p.nume.length > 22 ? p.nume.substring(0, 21) + '…' : p.nume; svg.appendChild(labelT);
        const barG = svgEl('g', { style: 'cursor:pointer' });
        barG.addEventListener('click', () => { if (typeof showProjectDetail === 'function') showProjectDetail(p.id); });
        barG.appendChild(svgEl('rect', { x: padL + left, y: y + 6, width, height: rowH - 12, rx: '3', fill: color, opacity: '0.85' }));
        if (width > 40) {
            const barT = svgEl('text', { x: padL + left + 6, y: y + rowH / 2 + 4, fill: '#fff', 'font-family': "'Courier New', monospace", 'font-size': '9', opacity: '0.9' });
            barT.textContent = p.nume.length > Math.floor(width / 6.5) ? p.nume.substring(0, Math.floor(width / 6.5) - 1) + '…' : p.nume; barG.appendChild(barT);
        }
        const title = svgEl('title');
        title.textContent = `${p.nume}\n${p.data_incepere || '?'} → ${p.deadline || '?'}\nStatus: ${getStatusLabel(p.status)}`; barG.appendChild(title);
        svg.appendChild(barG);
    });
    const todayX = padL + ((today - minDate) / totalRange) * chartW;
    svg.appendChild(svgEl('line', { x1: todayX, y1: padT, x2: todayX, y2: H - padB, stroke: accentColor, 'stroke-width': '1.5', 'stroke-dasharray': '4,3', opacity: '0.8' }));
    const todayT = svgEl('text', { x: todayX + 4, y: padT + 10, fill: accentColor, 'font-family': "'Courier New', monospace", 'font-size': '9', 'font-weight': '600' });
    todayT.textContent = 'azi'; svg.appendChild(todayT);
    container.innerHTML = ''; container.appendChild(svg);
}

// ============ SWIPE TO COMPLETE (Mobile) ============

let touchStartX = 0;
let touchStartY = 0;

document.addEventListener('touchstart', function(e) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
}, { passive: true });

document.addEventListener('touchend', function(e) {
    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;
    const deltaX = touchEndX - touchStartX;
    const deltaY = touchEndY - touchStartY;
    
    // Swipe right to complete task (only if horizontal swipe > 50px and small vertical)
    if (deltaX > 50 && Math.abs(deltaY) < 30) {
        const target = e.target.closest('.todo-item, .gt-task-card');
        if (target) {
            const checkbox = target.querySelector('input[type="checkbox"]');
            if (checkbox && !checkbox.checked) {
                checkbox.checked = true;
                checkbox.dispatchEvent(new Event('change'));
            }
        }
    }
}, { passive: true });

// ============ UTILITIES ============

// debounce, escapeHtml (+_ESC_MAP), getStatusLabel -> moved to shared core.js

function showToast(message, type = 'success') {
    // Back-compat: several call sites pass a boolean (true = error toast).
    if (type === true) type = 'error';
    else if (type === false) type = 'success';
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        'success': '✓',
        'error': '✗',
        'warning': '⚠',
        'info': 'ℹ'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.success}</span>
        <span class="toast-message">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);

    // Limit to MAX_TOASTS visible
    while (container.children.length > MAX_TOASTS) {
        const oldest = container.firstChild;
        if (oldest) {
            oldest.classList.remove('show');
            setTimeout(() => {
                if (oldest.parentNode) {
                    oldest.parentNode.removeChild(oldest);
                }
            }, 300);
        }
    }
}

function showConfirm(message, callback) {
    document.getElementById('confirm-message').textContent = message;
    confirmCallback = callback;
    document.getElementById('confirm-modal').classList.add('active');
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').classList.remove('active');
    confirmCallback = null;
}

function confirmAction() {
    if (confirmCallback) {
        confirmCallback();
    }
    closeConfirmModal();
}

// Drag and drop for file upload
const dropZone = document.getElementById('drop-zone');
if (dropZone) {
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const input = document.getElementById('file-input');
            const dt = new DataTransfer();
            for (const f of files) dt.items.add(f);
            input.files = dt.files;
            handleFileUpload({ target: input });
        }
    });
}

function initAccordions() {
    if (window.innerWidth > 768) return;
    document.querySelectorAll('.detail-section-header').forEach(header => {
        // Remove existing listeners by cloning
        const newHeader = header.cloneNode(true);
        header.parentNode.replaceChild(newHeader, header);
        newHeader.addEventListener('click', () => {
            const section = newHeader.parentElement;
            section.classList.toggle('collapsed');
        });
    });
    // On mobile, collapse all sections except the first one
    document.querySelectorAll('.detail-section').forEach((s, i) => {
        if (i > 0) s.classList.add('collapsed');
    });
}

// ============ CLIENTI (CLIENT DATABASE) ============

var clientListCache = [];

async function loadClientList() {
    try {
        clientListCache = await apiGet('/clienti');
        return clientListCache;
    } catch (e) {
        console.error('Failed to load client list:', e);
        return [];
    }
}

function onClientSearch() {
    const input = document.getElementById('p-client');
    const dropdown = document.getElementById('client-dropdown');
    const searchText = input.value.toLowerCase().trim();
    
    if (searchText.length === 0) {
        dropdown.classList.remove('active');
        return;
    }
    
    // Filter clients
    const filtered = clientListCache.filter(c => 
        (c.nume && c.nume.toLowerCase().includes(searchText)) ||
        (c.adresa && c.adresa.toLowerCase().includes(searchText)) ||
        (c.telefon && c.telefon.includes(searchText))
    );
    
    if (filtered.length === 0 && searchText.length > 0) {
        dropdown.innerHTML = `
            <div class="client-add-new" onclick="addNewClientFromAutocomplete('${escapeHtml(searchText)}')">
                + Adaugă "${escapeHtml(searchText)}" ca client nou
            </div>
        `;
    } else {
        dropdown.innerHTML = filtered.slice(0, 10).map(c => `
            <div class="client-option" onclick="selectClient('${c.id}', '${escapeHtml(c.nume)}')">
                <div class="client-option-name">${escapeHtml(c.nume)}</div>
                <div class="client-option-meta">${escapeHtml(c.adresa || '')} ${c.telefon ? '| ' + c.telefon : ''}</div>
            </div>
        `).join('') + `
            <div class="client-add-new" onclick="addNewClientFromAutocomplete('${escapeHtml(searchText)}')">
                + Adaugă "${escapeHtml(searchText)}" ca client nou
            </div>
        `;
    }
    
    dropdown.classList.add('active');
}

function selectClient(clientId, clientName) {
    document.getElementById('p-client').value = clientName;
    document.getElementById('p-client-id').value = clientId;
    document.getElementById('client-dropdown').classList.remove('active');
}

async function addNewClientFromAutocomplete(name) {
    document.getElementById('client-dropdown').classList.remove('active');
    document.getElementById('p-client').value = name;
    document.getElementById('p-client-id').value = '';
    
    // Try to add the client automatically
    try {
        await apiPost('/clienti', { nume: name });
        await loadClientList();
        const newClient = clientListCache.find(c => c.nume.toLowerCase() === name.toLowerCase());
        if (newClient) {
            document.getElementById('p-client-id').value = newClient.id;
        }
    } catch (e) {
        console.error('Failed to add client:', e);
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
    const autocomplete = document.querySelector('.client-autocomplete');
    if (autocomplete && !autocomplete.contains(e.target)) {
        document.getElementById('client-dropdown').classList.remove('active');
    }
});

// ============ CLIENT LIST MODAL ============

async function showClientList() {
    await loadClientList();
    renderClientList(clientListCache);
    document.getElementById('client-list-modal').classList.add('active');
}

function closeClientListModal() {
    document.getElementById('client-list-modal').classList.remove('active');
}

function renderClientList(clients) {
    const container = document.getElementById('client-list-container');
    
    if (clients.length === 0) {
        container.innerHTML = '<p style="color: var(--text2); text-align: center; padding: 24px;">Nu există clienți. Adaugă primul client!</p>';
        return;
    }
    
    container.innerHTML = clients.map(c => `
        <div class="client-list-item" onclick="editClientFromList('${c.id}')">
            <div class="client-list-info">
                <div class="client-list-name">${escapeHtml(c.nume)}</div>
                <div class="client-list-details">
                    ${c.adresa ? escapeHtml(c.adresa) + ' | ' : ''}
                    ${c.telefon || ''}
                    ${c.email ? ' | ' + c.email : ''}
                </div>
            </div>
            <div class="client-list-actions">
                <button class="btn btn-small btn-secondary" onclick="event.stopPropagation(); editClientFromList('${c.id}')" title="Editează"><i data-lucide="pencil"></i></button>
                <button class="btn btn-small btn-danger" onclick="event.stopPropagation(); deleteClientFromList('${c.id}')" title="Șterge"><i data-lucide="x"></i></button>
            </div>
        </div>
    `).join('');
}

function filterClientList() {
    const search = document.getElementById('client-list-search').value.toLowerCase().trim();
    if (!search) {
        renderClientList(clientListCache);
        return;
    }
    const filtered = clientListCache.filter(c =>
        (c.nume && c.nume.toLowerCase().includes(search)) ||
        (c.adresa && c.adresa.toLowerCase().includes(search)) ||
        (c.telefon && c.telefon.includes(search)) ||
        (c.email && c.email.toLowerCase().includes(search))
    );
    renderClientList(filtered);
}

function showAddClientForm(clientId = null) {
    document.getElementById('add-client-form').reset();
    document.getElementById('edit-client-id').value = clientId || '';
    
    if (clientId) {
        const client = clientListCache.find(c => c.id === clientId);
        if (client) {
            document.getElementById('add-client-title').textContent = 'Editează Client';
            document.getElementById('client-nume').value = client.nume || '';
            document.getElementById('client-adresa').value = client.adresa || '';
            document.getElementById('client-telefon').value = client.telefon || '';
            document.getElementById('client-email').value = client.email || '';
            document.getElementById('client-contact').value = client.contact_principal || '';
            document.getElementById('client-note').value = client.note || '';
        }
    } else {
        document.getElementById('add-client-title').textContent = 'Adaugă Client Nou';
    }
    
    document.getElementById('add-client-modal').classList.add('active');
}

function closeAddClientModal() {
    document.getElementById('add-client-modal').classList.remove('active');
}

async function saveClient(event) {
    event.preventDefault();
    
    const clientId = document.getElementById('edit-client-id').value;
    const clientData = {
        nume: document.getElementById('client-nume').value,
        adresa: document.getElementById('client-adresa').value,
        telefon: document.getElementById('client-telefon').value,
        email: document.getElementById('client-email').value,
        contact_principal: document.getElementById('client-contact').value,
        note: document.getElementById('client-note').value
    };
    
    try {
        if (clientId) {
            await apiPut(`/clienti/${clientId}`, clientData);
            showToast('Client actualizat!');
        } else {
            await apiPost('/clienti', clientData);
            showToast('Client adăugat!');
        }
        
        await loadClientList();
        closeAddClientModal();
        renderClientList(clientListCache);
    } catch (e) {
        console.error('Failed to save client:', e);
        showToast('Eroare la salvarea clientului', true);
    }
}

function editClientFromList(clientId) {
    showAddClientForm(clientId);
}

async function deleteClientFromList(clientId) {
    showConfirm('Sigur doriți să ștergeți acest client?', async () => {
        try {
            await apiDelete(`/clienti/${clientId}`);
            showToast('Client șters!');
            await loadClientList();
            renderClientList(clientListCache);
        } catch (e) {
            console.error('Failed to delete client:', e);
            showToast('Eroare la ștergerea clientului', true);
        }
    });
}

// ============ PROJECT TEMPLATES ============

let templateCache = [];

async function loadTemplates() {
    try {
        templateCache = await apiGet('/templates');
        return templateCache;
    } catch (e) {
        console.error('Failed to load templates:', e);
        return [];
    }
}

async function initTemplateSelector() {
    const templates = await loadTemplates();
    const select = document.getElementById('p-template');
    select.innerHTML = '<option value="">-- Fără template --</option>' + 
        templates.map(t => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
}

async function onTemplateChange() {
    const templateId = document.getElementById('p-template').value;
    if (!templateId) return;
    
    const template = templateCache.find(t => t.id === templateId);
    if (!template) return;
    
    // Set project type
    const typeRadio = document.querySelector(`input[name="project-type"][value="${template.tip}"]`);
    if (typeRadio) {
        typeRadio.checked = true;
        document.querySelectorAll('.project-type-btn').forEach(b => b.classList.remove('selected'));
        typeRadio.closest('.project-type-btn').classList.add('selected');
    }
}

// ============ EQUIPMENT (ECHIPAMENTE) ============

async function loadEchipamente(projectId) {
    try {
        const echipamente = await apiGet(`/proiecte/${projectId}/echipamente`);
        
        // Load param descriptions for each unique manufacturer
        const producatori = [...new Set(echipamente.map(e => e.producator).filter(p => p && p !== 'Altul'))];
        const descLookup = {};
        await Promise.all(producatori.map(async (prod) => {
            try {
                const params = await apiGet(`/parametri/by-producator/${prod}`);
                descLookup[prod] = {};
                params.forEach(p => { descLookup[prod][p.parametru] = p.descriere_scurta || ''; });
            } catch (err) { descLookup[prod] = {}; }
        }));
        
        renderEchipamente(echipamente, descLookup);
    } catch (e) {
        console.error('Failed to load echipamente:', e);
    }
}

function renderEchipamente(echipamente, descLookup) {
    const container = document.getElementById('echipamente-list');
    
    if (!echipamente || echipamente.length === 0) {
        container.innerHTML = '<p style="color: var(--text2); font-size: 0.9rem;">Nu există echipamente adăugate.</p>';
        return;
    }
    
    container.innerHTML = echipamente.map(e => {
        let params = {};
        try {
            params = JSON.parse(e.params_json || '{}');
        } catch (err) {}

        const paramCount = Object.keys(params).length;
        const hasParams = paramCount > 0;
        const lookup = descLookup[e.producator] || {};
        const paramsRows = Object.entries(params).map(([key, value]) => {
            const desc = lookup[key] || '';
            const shortDesc = desc ? extractParamName(desc) : '-';
            return `<tr><td style="font-weight:600;color:var(--accent);font-family:'JetBrains Mono',monospace;font-size:0.82rem;">${escapeHtml(key)}</td><td style="font-size:0.78rem;color:var(--text2);padding-right:12px;">${escapeHtml(shortDesc)}</td><td style="font-weight:600;text-align:right;font-family:'JetBrains Mono',monospace;font-size:0.82rem;">${escapeHtml(value)}</td></tr>`;
        }).join('');

        const expandedBody = hasParams
            ? `<table class="echipament-params-table">
                    <thead><tr><th style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text2);">Cod</th><th style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text2);">Descriere</th><th style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text2);text-align:right;">Valoare</th></tr></thead>
                    <tbody>${paramsRows}</tbody>
                </table>`
            : `<div style="color:var(--text2); font-size:0.85rem; padding:8px 0;">Niciun parametru salvat. Click pe <i data-lucide="pencil" style="width:12px;height:12px;vertical-align:-1px;"></i> pentru a edita.</div>`;

        return `
            <div class="echipament-card is-clickable" onclick="toggleEchipamentCard(this, event)">
                <div class="echipament-header">
                    <span class="echipament-name">${escapeHtml(e.nume)}</span>
                    <div class="echipament-actions" onclick="event.stopPropagation()">
                        <button class="btn btn-small btn-secondary" onclick="event.stopPropagation(); editEchipament('${e.id}')" title="Editează"><i data-lucide="pencil"></i></button>
                        <button class="btn btn-small btn-danger" onclick="event.stopPropagation(); deleteEchipament('${e.id}')" title="Șterge"><i data-lucide="x"></i></button>
                    </div>
                </div>
                <div class="echipament-meta">
                    ${e.producator ? `<span>${escapeHtml(e.producator)}</span>` : ''}
                    ${e.model ? `<span>${escapeHtml(e.model)}</span>` : ''}
                    ${e.serial_number ? `<span>S/N: ${escapeHtml(e.serial_number)}</span>` : ''}
                    ${hasParams ? `<span style="color:var(--accent);"><i data-lucide="sliders-horizontal" style="width:12px;height:12px;vertical-align:-1px;"></i> ${paramCount} parametri</span>` : ''}
                    <span class="echipament-chevron" style="margin-left:auto; color:var(--text-dim); transition:transform 0.15s; display:inline-flex;"><i data-lucide="chevron-down" style="width:14px;height:14px;"></i></span>
                </div>
                <div class="echipament-expanded" style="display: none;">
                    ${expandedBody}
                </div>
            </div>
        `;
    }).join('');
    if (window.lucide) lucide.createIcons();
}

function toggleEchipamentCard(card, ev) {
    if (!card) return;
    const expanded = card.querySelector('.echipament-expanded');
    const chevron = card.querySelector('.echipament-chevron');
    if (expanded) {
        const isOpen = expanded.style.display !== 'none';
        expanded.style.display = isOpen ? 'none' : 'block';
        if (chevron) chevron.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
        card.classList.toggle('is-open', !isOpen);
    }
}

let availableParams = [];
let currentEchipamentId = null;
let currentParams = {};

async function loadParamsForProducator(producator) {
    if (!producator || producator === 'Altul') { availableParams = []; return; }
    try { availableParams = await apiGet(`/parametri/by-producator/${producator}`); } catch (e) { availableParams = []; }
}

function filterParamSuggestions(query) {
    const suggestions = document.getElementById('param-suggestions');
    if (!query || query.length < 2) { suggestions.style.display = 'none'; return; }
    const q = query.toLowerCase();
    const filtered = availableParams.filter(p => (p.parametru && p.parametru.toLowerCase().includes(q)) || (p.descriere_scurta && p.descriere_scurta.toLowerCase().includes(q))).slice(0, 15);
    if (filtered.length === 0) { suggestions.style.display = 'none'; return; }
    suggestions.innerHTML = filtered.map(p => `<div onclick="selectParam('${escapeHtml(p.parametru)}', '${escapeHtml(p.descriere_scurta || '')}', '${p.valoare_default_str || p.valoare_default || ''}')" style="padding:10px 14px; cursor:pointer; border-bottom:1px solid var(--border); font-family:'Courier New',monospace; font-size:0.85rem; display:flex; justify-content:space-between; align-items:center;" onmouseenter="this.style.background='var(--bg3)'" onmouseleave="this.style.background=''"><div><span style="color:var(--accent); font-weight:600;">${escapeHtml(p.parametru)}</span><span style="color:var(--text2); margin-left:8px; font-size:0.78rem;">${escapeHtml(p.descriere_scurta ? p.descriere_scurta.substring(0, 50) + (p.descriere_scurta.length > 50 ? '…' : '') : '')}</span></div><span style="color:var(--text2); font-size:0.78rem; flex-shrink:0; margin-left:8px;">${p.familie || ''}${p.unitate ? ' | ' + p.unitate : ''}</span></div>`).join('');
    suggestions.style.display = 'block';
}

function selectParam(code, description, defaultValue) {
    document.getElementById('param-suggestions').style.display = 'none';
    document.getElementById('param-search-input').value = '';
    openParamValueInput(code, description, defaultValue);
}

function openParamValueInput(code, description, defaultValue) {
    const existing = currentParams[code];
    const value = existing !== undefined ? existing : defaultValue;
    const tempId = 'param-input-' + code.replace(/\./g, '_');
    if (document.getElementById(tempId)) return;
    const list = document.getElementById('current-params-list');
    const div = document.createElement('div');
    div.id = tempId;
    div.style.cssText = 'display:flex; gap:8px; align-items:center; margin-bottom:6px;';
    div.innerHTML = `<span style="font-family:'Courier New',monospace; font-size:0.85rem; color:var(--accent); min-width:60px;">${escapeHtml(code)}</span><span style="font-size:0.78rem; color:var(--text2); flex:1;">${escapeHtml(description.substring(0, 40))}${description.length > 40 ? '…' : ''}</span><input type="text" id="pval-${code.replace(/\./g, '_')}" value="${escapeHtml(String(value))}" style="width:100px; height:32px; padding:0 8px; font-family:'Courier New',monospace; font-size:0.85rem; text-align:right;" placeholder="Valoare"><button class="btn btn-small btn-primary" onclick="confirmParamValue('${code}', '${escapeHtml(description)}')" style="height:32px; padding:0 10px;">✓</button><button class="btn btn-small btn-secondary" onclick="document.getElementById('${tempId}').remove()" style="height:32px; padding:0 10px;">✗</button>`;
    list.appendChild(div);
    document.getElementById(`pval-${code.replace(/\./g, '_')}`)?.focus();
}

function confirmParamValue(code, description) {
    const input = document.getElementById(`pval-${code.replace(/\./g, '_')}`);
    if (!input) return;
    const value = input.value.trim();
    if (!value) return;
    currentParams[code] = value;
    renderCurrentParams();
    document.getElementById('param-input-' + code.replace(/\./g, '_'))?.remove();
}

function renderCurrentParams() {
    const list = document.getElementById('current-params-list');
    const entries = Object.entries(currentParams);
    if (entries.length === 0) { list.innerHTML = `<p style="color:var(--text2); font-size:0.82rem; font-family:'Courier New',monospace; padding:8px 0;">Niciun parametru setat.</p>`; return; }

    const lookupDesc = (code) => {
        const p = availableParams.find(ap => ap.parametru === code);
        if (p && p.descriere_scurta) {
            const name = typeof extractParamName === 'function' ? extractParamName(p.descriere_scurta) : p.descriere_scurta;
            return name.length > 35 ? name.substring(0, 32) + '…' : name;
        }
        return '—';
    };

    const header = `<div style="display:flex; gap:8px; align-items:center; padding:4px 10px; font-family:'Courier New',monospace; font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; color:var(--text2); border-bottom:1px solid var(--border); margin-bottom:4px;">
        <span style="min-width:65px;">Cod</span>
        <span style="flex:2;">Descriere</span>
        <span style="min-width:70px; text-align:right;">Valoare</span>
        <span style="width:58px;"></span>
    </div>`;

    const rows = entries.map(([code, value]) => {
        const desc = lookupDesc(code);
        const param = availableParams.find(ap => ap.parametru === code);
        return `<div style="display:flex; gap:8px; align-items:center; padding:5px 10px; border-radius:var(--radius); border:1px solid var(--border); margin-bottom:3px; background:var(--bg3); font-family:'Courier New',monospace; font-size:0.8rem;">
            <span style="color:var(--accent); font-weight:600; min-width:65px;">${escapeHtml(code)}</span>
            <span style="flex:2; color:var(--text2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(param?.descriere || desc)}">${escapeHtml(desc)}</span>
            <span style="min-width:70px; text-align:right; color:var(--text); font-weight:600;">${escapeHtml(String(value))}</span>
            <button class="btn btn-small btn-secondary" onclick="editParamValue('${code}')" style="height:26px; padding:0 6px; font-size:0.7rem; width:26px;" title="Editează"><i data-lucide="pencil"></i></button>
            <button class="btn btn-small btn-danger" onclick="deleteParam('${code}')" title="Șterge"><i data-lucide="x"></i></button>
        </div>`;
    }).join('');

    list.innerHTML = header + rows;
}

function editParamValue(code) { const param = availableParams.find(p => p.parametru === code); openParamValueInput(code, param?.descriere || '', currentParams[code] || ''); }
function deleteParam(code) { delete currentParams[code]; renderCurrentParams(); }

function showAddEquipmentForm() {
    if (!currentProjectId) return;

    // Reset state for new equipment
    currentParams = {};
    availableParams = [];
    currentEchipamentId = null;

    // Remove existing form/overlay if any
    document.querySelectorAll('.echipament-form-overlay, .echipament-form').forEach(el => el.remove());

    const formHtml = `
      <div class="modal-overlay echipament-form-overlay active" onclick="if(event.target === this) hideEchipamentForm()">
        <div class="modal" style="max-width: 720px; max-height: 92vh; overflow-y: auto;">
          <div class="modal-header">
            <h3 class="modal-title"><i data-lucide="cpu"></i> Echipament nou</h3>
            <button class="modal-close" onclick="hideEchipamentForm()">&times;</button>
          </div>
          <div class="modal-body">
        <div class="echipament-form" id="echipament-form-container">
            <div class="form-group">
                <label>Nume Echipament *</label>
                <input type="text" id="eq-nume" placeholder="ex: Convertizor de Frecvență" required>
            </div>
            <div class="form-group">
                <label>Producător</label>
                <select id="eq-producator" onchange="onProducatorChange()">
                    <option value="ABB">ABB</option>
                    <option value="Siemens">Siemens</option>
                    <option value="Danfoss">Danfoss</option>
                    <option value="Lenze">Lenze</option>
                    <option value="Altul" selected>Altul</option>
                </select>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Model</label>
                    <input type="text" id="eq-model" placeholder="ex: ACS880-01">
                </div>
                <div class="form-group">
                    <label>Număr Serie</label>
                    <input type="text" id="eq-serial" placeholder="ex: 3AXD10012345">
                </div>
            </div>
            <div class="form-group">
                <label>📋 Încarcă Template Parametri</label>
                <select id="eq-template" onchange="loadParamTemplate()">
                    <option value="">-- Selectează familie --</option>
                    <option value="ACS880">ABB ACS880</option>
                    <option value="SINAMICS_G120">Siemens SINAMICS G120</option>
                    <option value="FC302">Danfoss FC302</option>
                </select>
            </div>
            <div class="form-group">
                <label>📋 Copiază din Proiectul...</label>
                <select id="eq-copy-project" onchange="loadEquipmentFromProject()">
                    <option value="">-- Selectează proiect --</option>
                </select>
                <div id="eq-copy-equipment-container" style="display:none; margin-top:8px;">
                    <select id="eq-copy-equipment">
                        <option value="">-- Selectează echipament --</option>
                    </select>
                </div>
            </div>
            <!-- Parameter search from database -->
            <div id="echipament-params-section" style="margin-top:16px;">
                <div style="font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--text2); margin-bottom:8px;">Caută și adaugă parametri din baza de date</div>
                <div style="display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap; align-items:center;">
                    <input type="text" id="param-search-input" placeholder="Caută parametru (ex: p1120, Speed ref...)" style="flex:1; height:38px; padding:0 12px; font-family:'JetBrains Mono',monospace; font-size:0.85rem; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius); color:var(--text);" oninput="filterParamSuggestions(this.value)">
                    <button type="button" class="btn btn-secondary btn-small" onclick="triggerImportParams()" title="Import parametri din export softul producătorului (Danfoss .txt etc)">
                        <i data-lucide="file-up"></i> Import din fișier
                    </button>
                    <input type="file" id="import-params-file" style="display:none" accept=".txt,.pdf,.csv,.dcparamsbak" onchange="onImportParamsFileSelected(event)">
                </div>
                <div id="param-suggestions" style="display:none; max-height:200px; overflow-y:auto; border:1px solid var(--border); border-radius:var(--radius); background:var(--bg2); margin-bottom:10px;"></div>
                <div id="current-params-list"></div>
            </div>
            <div class="echipament-form-actions">
                <button type="button" class="btn btn-secondary btn-small" onclick="hideEchipamentForm()">Anulează</button>
                <button type="button" class="btn btn-primary btn-small" onclick="saveEchipament()">Salvează</button>
            </div>
        </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', formHtml);
    if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
    setTimeout(() => enhanceAllSelects && enhanceAllSelects(), 50);

    // Populate projects dropdown for copy function
    populateProjectsForCopy();

    // Initialize empty params display
    renderCurrentParams();
    if (window.lucide) lucide.createIcons();
}

// Populate projects dropdown for copying equipment
async function populateProjectsForCopy() {
    const select = document.getElementById('eq-copy-project');
    if (!select) return;
    
    try {
        const projects = await apiGet('/proiecte');
        // Filter out current project and build options
        const options = projects
            .filter(p => p.id !== currentProjectId)
            .map(p => `<option value="${p.id}">${escapeHtml(p.nume)}</option>`)
            .join('');
        
        select.innerHTML = '<option value="">-- Selectează proiect --</option>' + options;
    } catch (e) {
        console.error('Failed to load projects for copy:', e);
    }
}

// Load equipment from selected project
async function loadEquipmentFromProject() {
    const projectSelect = document.getElementById('eq-copy-project');
    const equipmentContainer = document.getElementById('eq-copy-equipment-container');
    const equipmentSelect = document.getElementById('eq-copy-equipment');
    
    if (!projectSelect || !equipmentContainer || !equipmentSelect) return;
    
    const projectId = projectSelect.value;
    
    if (!projectId) {
        equipmentContainer.style.display = 'none';
        return;
    }
    
    try {
        const data = await apiGet(`/proiecte/${projectId}/echipamente/export`);
        
        if (data.equipment && data.equipment.length > 0) {
            const options = data.equipment
                .map(eq => `<option value="${eq.id}">${escapeHtml(eq.nume)} (${eq.producator} ${eq.model})</option>`)
                .join('');
            equipmentSelect.innerHTML = '<option value="">-- Selectează echipament --</option>' + options;
            equipmentContainer.style.display = 'block';
            
            // Add onchange to auto-fill params when equipment is selected
            equipmentSelect.onchange = () => fillParamsFromEquipment(projectId, equipmentSelect.value);
        } else {
            equipmentSelect.innerHTML = '<option value="">Nu există echipamente</option>';
            equipmentContainer.style.display = 'block';
        }
    } catch (e) {
        console.error('Failed to load equipment from project:', e);
        equipmentContainer.style.display = 'none';
    }
}

// Fill form fields from selected equipment
async function fillParamsFromEquipment(projectId, equipmentId) {
    if (!projectId || !equipmentId) return;
    
    try {
        const data = await apiGet(`/proiecte/${projectId}/echipamente/export`);
        const eq = data.equipment.find(e => e.id === equipmentId);
        
        if (eq) {
            // Fill basic fields
            document.getElementById('eq-nume').value = eq.nume || '';
            document.getElementById('eq-model').value = eq.model || '';
            document.getElementById('eq-serial').value = eq.serial_number || '';
            
            // Set producer if matches
            const producatorSelect = document.getElementById('eq-producator');
            if (producatorSelect) {
                for (let opt of producatorSelect.options) {
                    if (opt.value.toLowerCase() === (eq.producator || '').toLowerCase()) {
                        producatorSelect.value = opt.value;
                        break;
                    }
                }
            }
            
            // Fill parameters
            if (eq.params) {
                currentParams = { ...eq.params };
                renderCurrentParams();
            }
            
            showToast(`Parametri copiați din ${eq.nume}`, false);
        }
    } catch (e) {
        console.error('Failed to fill params from equipment:', e);
    }
}

function hideEchipamentForm() {
    document.querySelectorAll('.echipament-form-overlay, .echipament-form').forEach(el => el.remove());
}

// Auto-select template based on producator selection
function onProducatorChange() {
    const producator = document.getElementById('eq-producator')?.value;
    const templateSelect = document.getElementById('eq-template');
    
    // Auto-select template
    if (producator && templateSelect) {
        const familyMap = { 'ABB': 'ACS880', 'Siemens': 'SINAMICS_G120', 'Danfoss': 'FC302' };
        const family = familyMap[producator];
        if (family) {
            for (let opt of templateSelect.options) {
                if (opt.value === family) { templateSelect.value = family; break; }
            }
        } else {
            templateSelect.value = '';
        }
    }
    
    // Load available parameters from DB for this manufacturer
    if (producator && producator !== 'Altul') {
        loadParamsForProducator(producator);
    } else {
        availableParams = [];
    }
    
    // Reset current params
    currentParams = {};
    renderCurrentParams();
}

// Load parameter template for selected drive family
async function loadParamTemplate() {
    const familie = document.getElementById('eq-template')?.value;
    if (!familie) return;
    
    try {
        const response = await fetch(`/api/parametri-templates?familie=${encodeURIComponent(familie)}`);
        if (!response.ok) throw new Error('Failed to load template');
        
        const data = await response.json();
        if (data.parameters && data.parameters.length > 0) {
            // Check if currentParams already has content
            const hasExistingParams = Object.keys(currentParams).length > 0;
            
            if (hasExistingParams) {
                if (!confirm('Dorești să înlocuiești parametrii existenți sau să adaugi la cei existenți?')) {
                    // Append mode
                    data.parameters.forEach(p => {
                        const val = p.valoare_default || '';
                        const unit = p.unitate && p.unitate !== '-' ? ` ${p.unitate}` : '';
                        currentParams[p.parametru] = `${val}${unit}`;
                    });
                } else {
                    // Replace mode
                    currentParams = {};
                    data.parameters.forEach(p => {
                        const val = p.valoare_default || '';
                        const unit = p.unitate && p.unitate !== '-' ? ` ${p.unitate}` : '';
                        currentParams[p.parametru] = `${val}${unit}`;
                    });
                }
            } else {
                // No existing params, just load
                data.parameters.forEach(p => {
                    const val = p.valoare_default || '';
                    const unit = p.unitate && p.unitate !== '-' ? ` ${p.unitate}` : '';
                    currentParams[p.parametru] = `${val}${unit}`;
                });
            }
            renderCurrentParams();
            showToast(`Template ${familie} încărcat!`);
        }
    } catch (e) {
        console.error('Failed to load param template:', e);
        showToast('Eroare la încărcarea template-ului', true);
    }
}

let editingEchipamentId = null;

async function editEchipament(echipamentId) {
    try {
        const eq = await apiGet(`/echipamente/${echipamentId}`);
        editingEchipamentId = echipamentId;
        
        // Remove existing form if any
        document.querySelectorAll('.echipament-form-overlay, .echipament-form').forEach(el => el.remove());

        // Load current params from equipment
        currentParams = {};
        try {
            currentParams = JSON.parse(eq.params_json || '{}');
        } catch (err) {}

        // Load available params for this manufacturer
        if (eq.producator && eq.producator !== 'Altul') {
            await loadParamsForProducator(eq.producator);
        } else {
            availableParams = [];
        }

        const formHtml = `
          <div class="modal-overlay echipament-form-overlay active" onclick="if(event.target === this) hideEchipamentForm()">
            <div class="modal" style="max-width: 720px; max-height: 92vh; overflow-y: auto;">
              <div class="modal-header">
                <h3 class="modal-title"><i data-lucide="pencil"></i> Editează echipament</h3>
                <button class="modal-close" onclick="hideEchipamentForm()">&times;</button>
              </div>
              <div class="modal-body">
            <div class="echipament-form" id="echipament-form-container">
                <div class="form-group">
                    <label>Nume Echipament *</label>
                    <input type="text" id="eq-nume" value="${escapeHtml(eq.nume || '')}" required>
                </div>
                <div class="form-group">
                    <label>Producător</label>
                    <select id="eq-producator" onchange="onProducatorChange()">
                        <option value="ABB" ${eq.producator === 'ABB' ? 'selected' : ''}>ABB</option>
                        <option value="Siemens" ${eq.producator === 'Siemens' ? 'selected' : ''}>Siemens</option>
                        <option value="Danfoss" ${eq.producator === 'Danfoss' ? 'selected' : ''}>Danfoss</option>
                        <option value="Lenze" ${eq.producator === 'Lenze' ? 'selected' : ''}>Lenze</option>
                        <option value="Altul" ${!eq.producator || eq.producator === 'Altul' ? 'selected' : ''}>Altul</option>
                    </select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Model</label>
                        <input type="text" id="eq-model" value="${escapeHtml(eq.model || '')}">
                    </div>
                    <div class="form-group">
                        <label>Număr Serie</label>
                        <input type="text" id="eq-serial" value="${escapeHtml(eq.serial_number || '')}">
                    </div>
                </div>
                <!-- Parameter search from database -->
                <div id="echipament-params-section" style="margin-top:16px;">
                    <div style="font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--text2); margin-bottom:8px;">Caută și adaugă parametri din baza de date</div>
                    <div style="display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap; align-items:center;">
                        <input type="text" id="param-search-input" placeholder="Caută parametru (ex: p1120, Speed ref...)" style="flex:1; height:38px; padding:0 12px; font-family:'JetBrains Mono',monospace; font-size:0.85rem; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius); color:var(--text);" oninput="filterParamSuggestions(this.value)">
                        <button type="button" class="btn btn-secondary btn-small" onclick="triggerImportParams()" title="Import parametri din export softul producătorului (Danfoss .txt etc)">
                            <i data-lucide="file-up"></i> Import din fișier
                        </button>
                        <input type="file" id="import-params-file" style="display:none" accept=".txt,.pdf,.csv,.dcparamsbak" onchange="onImportParamsFileSelected(event)">
                    </div>
                    <div id="param-suggestions" style="display:none; max-height:200px; overflow-y:auto; border:1px solid var(--border); border-radius:var(--radius); background:var(--bg2); margin-bottom:10px;"></div>
                    <div id="current-params-list"></div>
                </div>
                <div class="echipament-form-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="hideEchipamentForm()">Anulează</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="saveEchipament()">Salvează</button>
                </div>
            </div>
              </div>
            </div>
          </div>
        `;
        document.body.insertAdjacentHTML('beforeend', formHtml);
        if (window.lucide) try { window.lucide.createIcons(); } catch (e) {}
        setTimeout(() => enhanceAllSelects && enhanceAllSelects(), 50);
        
        // Render the loaded params and reset search UI
        renderCurrentParams();
        const searchInput = document.getElementById('param-search-input');
        if (searchInput) searchInput.value = '';
        const suggestions = document.getElementById('param-suggestions');
        if (suggestions) suggestions.style.display = 'none';
    } catch (e) {
        console.error('Failed to load echipament:', e);
        showToast('Eroare la încărcarea echipamentului', true);
    }
}

async function saveEchipament() {
    const nume = document.getElementById('eq-nume').value.trim();
    if (!nume) {
        showToast('Completați numele echipamentului', true);
        return;
    }
    
    const data = {
        nume: nume,
        producator: document.getElementById('eq-producator').value,
        model: document.getElementById('eq-model').value,
        serial_number: document.getElementById('eq-serial').value,
        params_json: JSON.stringify(currentParams)
    };
    
    try {
        if (editingEchipamentId) {
            await apiPut(`/echipamente/${editingEchipamentId}`, data);
            showToast('Echipament actualizat!');
            editingEchipamentId = null;
        } else {
            await apiPost(`/proiecte/${currentProjectId}/echipamente`, data);
            showToast('Echipament adăugat!');
        }
        
        hideEchipamentForm();
        loadEchipamente(currentProjectId);
    } catch (e) {
        console.error('Failed to save echipament:', e);
        showToast('Eroare la salvarea echipamentului', true);
    }
}

async function deleteEchipament(echipamentId) {
    showConfirm('Sigur doriți să ștergeți acest echipament?', async () => {
        try {
            await apiDelete(`/echipamente/${echipamentId}`);
            showToast('Echipament șters!');
            loadEchipamente(currentProjectId);
        } catch (e) {
            console.error('Failed to delete echipament:', e);
            showToast('Eroare la ștergerea echipamentului', true);
        }
    });
}

// ============ IMPORT PARAMETRI DIN EXPORT PRODUCATOR ============

let _importParamsPreview = null;

function triggerImportParams() {
    const producator = document.getElementById('eq-producator')?.value || '';
    if (!producator || producator === 'Altul') {
        showToast('Selectează mai întâi un producător (Danfoss, ABB, Siemens, Lenze)', true);
        return;
    }
    const input = document.getElementById('import-params-file');
    if (input) {
        input.value = '';
        input.click();
    }
}

async function onImportParamsFileSelected(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    const producator = document.getElementById('eq-producator')?.value || '';
    const model = document.getElementById('eq-model')?.value || '';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('producator', producator);
    formData.append('model', model);

    showToast(`Se parsează ${file.name}...`);
    try {
        const data = await apiUpload('/import-params/preview', formData);
        _importParamsPreview = data;
        showImportParamsModal(data);
    } catch (e) {
        console.error('Import params preview failed:', e);
        let msg = 'Eroare la parsare';
        try {
            const res = await fetch(API_BASE + '/import-params/preview', { method: 'POST', body: formData });
            const j = await res.json();
            if (j && j.error) msg = j.error;
        } catch (_) {}
        showToast(msg, true);
    }
}

function showImportParamsModal(data) {
    const modal = document.getElementById('import-params-modal');
    const body = document.getElementById('import-params-body');
    if (!modal || !body) return;

    const params = data.params || [];
    const rows = params.map((p, idx) => {
        const conflictBadge = p.conflict
            ? `<span title="Valori diferite pe Setup-uri: ${escapeHtml(JSON.stringify(p.per_setup))}" style="display:inline-flex; align-items:center; gap:4px; padding:2px 6px; border-radius:4px; background:rgba(245,177,77,0.15); color:var(--warning); font-size:0.7rem;"><i data-lucide="alert-triangle" style="width:12px; height:12px;"></i> conflict</span>`
            : '';
        const setupsBadge = p.setups && p.setups.length
            ? `<span style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:var(--text-dim);">S${p.setups.join(',')}</span>`
            : '';
        const denumire = p.descriere_db || p.name || '';
        const existing = (typeof p.existing_value !== 'undefined')
            ? `<span title="Valoare existentă: ${escapeHtml(p.existing_value)}" style="margin-left:6px; color:var(--violet); font-size:0.7rem;">override</span>`
            : '';
        const valueSelector = p.conflict
            ? `<select class="cs-enhance imp-value-select" data-idx="${idx}" style="width:100%; font-family:'JetBrains Mono',monospace;">${
                Object.entries(p.per_setup).map(([s, v]) =>
                    `<option value="${escapeHtml(v)}"${v === p.value ? ' selected' : ''}>S${escapeHtml(s)}: ${escapeHtml(v)}</option>`
                ).join('')
              }</select>`
            : `<span class="imp-value-display" data-idx="${idx}" style="font-family:'JetBrains Mono',monospace;">${escapeHtml(p.value)}</span>`;
        return `
            <tr data-idx="${idx}">
                <td style="text-align:center;"><input type="checkbox" class="imp-check" data-idx="${idx}" checked></td>
                <td style="font-family:'JetBrains Mono',monospace; color:var(--accent);">${escapeHtml(p.db_id)}</td>
                <td>${escapeHtml(denumire)} ${conflictBadge}</td>
                <td>${valueSelector}</td>
                <td style="font-family:'JetBrains Mono',monospace; color:var(--text-dim); font-size:0.8rem;">${escapeHtml(p.default || '')}</td>
                <td>${setupsBadge} ${existing}</td>
            </tr>`;
    }).join('');

    body.innerHTML = `
        <div style="display:flex; gap:16px; flex-wrap:wrap; align-items:center; margin-bottom:12px; padding:10px 12px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius);">
            <div><span style="color:var(--text-dim); font-size:0.8rem;">Producător:</span> <strong>${escapeHtml(data.producator_detected || '')}</strong></div>
            <div><span style="color:var(--text-dim); font-size:0.8rem;">Familie:</span> <span style="font-family:'JetBrains Mono',monospace;">${escapeHtml(data.familie || '-')}</span></div>
            <div><span style="color:var(--text-dim); font-size:0.8rem;">Fișier:</span> <span style="font-family:'JetBrains Mono',monospace; font-size:0.8rem;">${escapeHtml(data.filename || '')}</span></div>
            <div><span style="color:var(--text-dim); font-size:0.8rem;">Parametri:</span> <strong>${data.count}</strong></div>
            ${data.conflicts ? `<div style="color:var(--warning);"><i data-lucide="alert-triangle" style="width:14px; height:14px; vertical-align:-2px;"></i> ${data.conflicts} conflicte între Setup-uri</div>` : ''}
        </div>
        <div style="display:flex; gap:8px; margin-bottom:8px;">
            <button type="button" class="btn btn-secondary btn-small" onclick="toggleAllImportParams(true)"><i data-lucide="check-square"></i> Toate</button>
            <button type="button" class="btn btn-secondary btn-small" onclick="toggleAllImportParams(false)"><i data-lucide="square"></i> Niciunul</button>
        </div>
        <div style="max-height:55vh; overflow-y:auto; border:1px solid var(--border); border-radius:var(--radius);">
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead style="position:sticky; top:0; background:var(--bg-elev2); z-index:1;">
                    <tr style="text-align:left;">
                        <th style="padding:8px; width:36px; border-bottom:1px solid var(--border);"></th>
                        <th style="padding:8px; border-bottom:1px solid var(--border);">Cod</th>
                        <th style="padding:8px; border-bottom:1px solid var(--border);">Denumire</th>
                        <th style="padding:8px; border-bottom:1px solid var(--border); width:200px;">Valoare</th>
                        <th style="padding:8px; border-bottom:1px solid var(--border);">Default</th>
                        <th style="padding:8px; border-bottom:1px solid var(--border);">Note</th>
                    </tr>
                </thead>
                <tbody id="import-params-tbody">
                    ${rows || '<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text2);">Nu s-au găsit parametri în fișier.</td></tr>'}
                </tbody>
            </table>
        </div>
        <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:14px;">
            <button type="button" class="btn btn-secondary btn-small" onclick="closeImportParamsModal()">Anulează</button>
            <button type="button" class="btn btn-primary btn-small" onclick="applyImportedParams()"><i data-lucide="check"></i> Importă selectați</button>
        </div>
    `;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    if (window.lucide) lucide.createIcons();
    if (typeof enhanceAllSelects === 'function') enhanceAllSelects();
}

function toggleAllImportParams(checked) {
    document.querySelectorAll('.imp-check').forEach(cb => cb.checked = checked);
}

function applyImportedParams() {
    if (!_importParamsPreview) return;
    const params = _importParamsPreview.params || [];
    let added = 0, overridden = 0;
    document.querySelectorAll('.imp-check').forEach(cb => {
        if (!cb.checked) return;
        const idx = parseInt(cb.dataset.idx, 10);
        const p = params[idx];
        if (!p) return;
        let value = p.value;
        const sel = document.querySelector(`.imp-value-select[data-idx="${idx}"]`);
        if (sel) value = sel.value;
        if (typeof currentParams === 'object' && currentParams !== null) {
            if (Object.prototype.hasOwnProperty.call(currentParams, p.db_id)) overridden++;
            else added++;
            currentParams[p.db_id] = String(value);
        }
    });
    closeImportParamsModal();
    if (typeof renderCurrentParams === 'function') renderCurrentParams();
    const msg = overridden
        ? `${added} parametri adăugați, ${overridden} suprascriși`
        : `${added} parametri adăugați`;
    showToast(msg);
}

function closeImportParamsModal() {
    const modal = document.getElementById('import-params-modal');
    if (modal) modal.classList.remove('active');
    document.body.style.overflow = '';
    _importParamsPreview = null;
}

// ============ BATCH OPERATIONS ============

let batchMode = false;
let selectedProjects = new Set();

function toggleBatchMode() {
    batchMode = !batchMode;
    selectedProjects.clear();
    
    const batchBtn = document.getElementById('batch-mode-btn');
    const batchBar = document.getElementById('batch-action-bar');
    const headerCheckbox = document.getElementById('batch-select-all');
    
    if (batchBtn) {
        batchBtn.classList.toggle('active', batchMode);
        batchBtn.textContent = batchMode ? '✓ Mod Selectare' : 'Mod Selectare';
    }
    
    if (batchBar) {
        batchBar.style.display = batchMode ? 'flex' : 'none';
    }
    
    // Toggle checkbox column visibility
    document.querySelectorAll('.batch-checkbox').forEach(cb => {
        cb.style.display = batchMode ? 'inline-block' : 'none';
    });
    
    if (headerCheckbox) {
        headerCheckbox.style.display = batchMode ? 'inline-block' : 'none';
    }
    
    if (!batchMode) {
        updateBatchActionBar();
    }
}

function toggleProjectSelection(projectId) {
    if (selectedProjects.has(projectId)) {
        selectedProjects.delete(projectId);
    } else {
        selectedProjects.add(projectId);
    }
    updateBatchActionBar();
}

function selectAllProjects() {
    const checkboxes = document.querySelectorAll('.project-row-checkbox');
    const headerCheckbox = document.getElementById('batch-select-all');
    const allSelected = headerCheckbox?.checked;
    
    checkboxes.forEach(cb => {
        cb.checked = allSelected;
        const pid = cb.dataset.projectId;
        if (allSelected) {
            selectedProjects.add(pid);
        } else {
            selectedProjects.delete(pid);
        }
    });
    updateBatchActionBar();
}

function updateBatchActionBar() {
    const count = selectedProjects.size;
    const countEl = document.getElementById('batch-selected-count');
    const actionBtns = document.getElementById('batch-action-buttons');
    
    if (countEl) countEl.textContent = `${count} selectat${count !== 1 ? 'e' : ''}`;
    if (actionBtns) {
        actionBtns.style.display = count > 0 ? 'flex' : 'none';
    }
}

async function batchUpdateStatus(newStatus) {
    if (selectedProjects.size === 0) return;
    
    const action = newStatus === 'finalizat' ? 'Marchează Finalizat' : 
                   newStatus === 'in_lucru' ? 'Marchează În Lucru' : newStatus;
    
    showConfirm(`Doriți să ${action} proiectele selectate?`, async () => {
        try {
            await apiPost('/proiecte/batch', {
                action: 'update_status',
                project_ids: Array.from(selectedProjects),
                status: newStatus
            });
            showToast(`${selectedProjects.size} proiecte actualizate!`);
            toggleBatchMode();
            await loadProjects();
        } catch (e) {
            console.error('Batch update failed:', e);
            showToast('Eroare la actualizarea proiectelor', true);
        }
    });
}

async function batchDeleteProjects() {
    if (selectedProjects.size === 0) return;
    
    showConfirm(`Sigur doriți să ștergeți ${selectedProjects.size} proiecte? Această acțiune nu poate fi anulată!`, async () => {
        try {
            await apiPost('/proiecte/batch', {
                action: 'delete',
                project_ids: Array.from(selectedProjects)
            });
            showToast(`${selectedProjects.size} proiecte șterse!`);
            toggleBatchMode();
            await loadProjects();
            await updateStats();
        } catch (e) {
            console.error('Batch delete failed:', e);
            showToast('Eroare la ștergerea proiectelor', true);
        }
    });
}

// ============ UNDO/REDO SYSTEM ============

const MAX_UNDO_STACK = 10;
let undoStack = [];
let redoStack = [];

function pushUndo(action) {
    undoStack.push(action);
    if (undoStack.length > MAX_UNDO_STACK) {
        undoStack.shift();
    }
    redoStack = []; // Clear redo stack on new action
    updateUndoRedoButtons();
}

function updateUndoRedoButtons() {
    const undoBtn = document.getElementById('undo-btn');
    const redoBtn = document.getElementById('redo-btn');
    
    if (undoBtn) {
        undoBtn.style.display = undoStack.length > 0 ? 'flex' : 'none';
        undoBtn.title = undoStack.length > 0 ? `Anulează: ${undoStack[undoStack.length - 1].description}` : '';
    }
    if (redoBtn) {
        redoBtn.style.display = redoStack.length > 0 ? 'flex' : 'none';
        redoBtn.title = redoStack.length > 0 ? `Refă: ${redoStack[redoStack.length - 1].description}` : '';
    }
}

async function undo() {
    if (undoStack.length === 0) return;
    
    const action = undoStack.pop();
    redoStack.push(action);
    
    try {
        if (action.type === 'task_toggle') {
            await apiPut(`/global-tasks/${action.taskId}`, {
                status: action.previousState.status,
                data_finalizare: action.previousState.data_finalizare || ''
            });
            showToast(`Acțiune anulată: ${action.description}`);
        } else if (action.type === 'task_delete') {
            // Recreate the deleted task
            await apiPost('/global-tasks', action.previousState);
            showToast(`Acțiune anulată: ${action.description}`);
        } else if (action.type === 'task_create') {
            // Delete the created task
            await apiDelete(`/global-tasks/${action.taskId}`);
            showToast(`Acțiune anulată: ${action.description}`);
        } else if (action.type === 'checklist_toggle') {
            await apiPut(`/proiecte/${action.projectId}/checklist/${action.itemId}`, {
                completat: action.previousState ? 0 : 1
            });
            showToast(`Acțiune anulată: ${action.description}`);
        }
        
        await loadGlobalTasks();
        updateUndoRedoButtons();
    } catch (e) {
        console.error('Undo failed:', e);
        showToast('Eroare la anularea acțiunii', true);
    }
}

async function redo() {
    if (redoStack.length === 0) return;
    
    const action = redoStack.pop();
    undoStack.push(action);
    
    try {
        if (action.type === 'task_toggle') {
            await apiPut(`/global-tasks/${action.taskId}`, {
                status: action.newState.status,
                data_finalizare: action.newState.data_finalizare || ''
            });
            showToast(`Acțiune refăcută: ${action.description}`);
        } else if (action.type === 'task_delete') {
            // Delete the task again
            await apiDelete(`/global-tasks/${action.taskId}`);
            showToast(`Acțiune refăcută: ${action.description}`);
        } else if (action.type === 'task_create') {
            // Recreate the task
            await apiPost('/global-tasks', action.newState);
            showToast(`Acțiune refăcută: ${action.description}`);
        } else if (action.type === 'checklist_toggle') {
            await apiPut(`/proiecte/${action.projectId}/checklist/${action.itemId}`, {
                completat: action.previousState ? 0 : 1
            });
            showToast(`Acțiune refăcută: ${action.description}`);
        }
        
        await loadGlobalTasks();
        updateUndoRedoButtons();
    } catch (e) {
        console.error('Redo failed:', e);
        showToast('Eroare la refacerea acțiunii', true);
    }
}

// Override task functions to track undo

const originalToggleGtTask = toggleGtTask;
toggleGtTask = async function(taskId, checked) {
    // Get current task state before toggle for undo
    try {
        const task = await apiGet(`/global-tasks/${taskId}`);
        const previousState = {
            status: task.status,
            data_finalizare: task.data_finalizare
        };
        const newState = {
            status: checked ? 'done' : 'to_do',
            data_finalizare: checked ? new Date().toISOString() : ''
        };
        
        pushUndo({
            type: 'task_toggle',
            taskId: taskId,
            description: `Toggle task: ${task.titlu}`,
            previousState: previousState,
            newState: newState
        });
    } catch (e) {
        console.error('Failed to capture task state for undo:', e);
    }
    
    await originalToggleGtTask(taskId, checked);
};

const originalDeleteGtTask = deleteGtTask;
deleteGtTask = async function(taskId) {
    // Get task data before delete for undo
    try {
        const task = await apiGet(`/global-tasks/${taskId}`);
        if (task) {
            pushUndo({
                type: 'task_delete',
                taskId: taskId,
                description: `Ștergere task: ${task.titlu}`,
                previousState: task
            });
        }
    } catch (e) {
        console.error('Failed to capture task state for undo:', e);
    }
    
    await originalDeleteGtTask(taskId);
};

const originalQuickAddTask = quickAddTask;
quickAddTask = async function() {
    const input = document.getElementById('quick-task-input');
    const titlu = input.value.trim();
    
    // Capture the task data that will be created
    const taskData = {
        titlu: titlu,
        prioritate: document.getElementById('quick-prioritate').value,
        categorie: document.getElementById('quick-categorie').value,
        data_scadenta: document.getElementById('quick-scadenta').value || '',
        status: 'to_do'
    };
    
    await originalQuickAddTask();
    
    // Find the created task and push to undo stack
    // Since we can't easily get the ID, we'll push with a placeholder
    // The undo will still work by matching title
    setTimeout(async () => {
        try {
            const tasks = await apiGet('/global-tasks');
            const created = tasks.find(t => t.titlu === titlu && t.status === 'to_do');
            if (created) {
                // Remove the auto-pushed undo and replace with correct one
                undoStack.pop();
                pushUndo({
                    type: 'task_create',
                    taskId: created.id,
                    description: `Creare task: ${titlu}`,
                    newState: created
                });
            }
        } catch (e) {
            console.error('Failed to capture created task for undo:', e);
        }
    }, 100);
};

// ============ PARAMETRI MASTER BROWSER ============

const debounceLoadParametri = debounce(loadParametri, 300);

// Map manufacturer -> their families (mirrors PRODUCATOR_FAMILII on the server)
const PARAM_PRODUCATORI = {
    'ABB':     { icon: 'cpu',  families: ['ACS580', 'ACS880'], label: 'ABB' },
    'Siemens': { icon: 'cpu',  families: ['SINAMICS_G120', 'SINAMICS_G130_G150', 'SINAMICS_S120_S150'], label: 'Siemens' },
    'Danfoss': { icon: 'cpu',  families: ['Danfoss_VLT_FC302'], label: 'Danfoss' },
    'Lenze':   { icon: 'cpu',  families: ['Lenze_i550', 'Lenze_i950'], label: 'Lenze' },
};

let _paramSelectedProducator = null;
let _paramFamilieCounts = {};  // { 'ACS580': 1337, ... }

async function loadParametriFamilii() {
    try {
        const data = await apiGet('/parametri/familii');
        parametriFamilii = data.families;
        _paramFamilieCounts = {};
        data.families.forEach(f => { _paramFamilieCounts[f.familie] = f.count; });

        // Keep the hidden select in sync (used by loadParametri for the filter)
        const select = document.getElementById('param-familie');
        if (select) {
            select.innerHTML = '<option value="">Toate Familii</option>';
            data.families.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.familie;
                opt.textContent = `${f.familie} (${f.count})`;
                select.appendChild(opt);
            });
        }

        renderProducatorPicker();
    } catch (e) {
        console.error('Failed to load parametri families:', e);
    }
}

function renderProducatorPicker() {
    const grid = document.getElementById('param-producator-grid');
    if (!grid) return;
    grid.innerHTML = Object.entries(PARAM_PRODUCATORI).map(([key, info]) => {
        const totalCount = info.families.reduce((sum, f) => sum + (_paramFamilieCounts[f] || 0), 0);
        const familiesLabel = info.families
            .map(f => f.replace(/^(SINAMICS_|Lenze_|Danfoss_VLT_)/, ''))
            .join(' · ');
        return `
            <button class="param-producator-card ${key.toLowerCase()}" onclick="paramSelectProducator('${key}')">
                <span class="ppc-icon"><i data-lucide="${info.icon}"></i></span>
                <div class="ppc-body">
                    <div class="ppc-name">${info.label}</div>
                    <div class="ppc-meta">${totalCount.toLocaleString('ro-RO')} parametri</div>
                    <div class="ppc-families">${familiesLabel}</div>
                </div>
            </button>
        `;
    }).join('');
}

function paramSelectProducator(producator) {
    const info = PARAM_PRODUCATORI[producator];
    if (!info) return;
    _paramSelectedProducator = producator;

    document.getElementById('param-step-producator').style.display = 'none';
    document.getElementById('param-step-list').style.display = 'block';
    document.getElementById('param-breadcrumb-producator').textContent = info.label;

    // Build family mini-tabs
    const tabsEl = document.getElementById('param-mini-tabs');
    tabsEl.innerHTML = info.families.map(f => {
        const count = _paramFamilieCounts[f] || 0;
        const label = f.replace(/^(SINAMICS_|Lenze_|Danfoss_VLT_)/, '');
        return `<button class="param-mini-tab" data-familie="${f}" onclick="paramSelectFamilie('${f}')">${label}<span class="count">${count.toLocaleString('ro-RO')}</span></button>`;
    }).join('');

    // Auto-select the first family
    if (info.families.length > 0) paramSelectFamilie(info.families[0]);
}

function paramSelectFamilie(familie) {
    // Update active tab
    document.querySelectorAll('.param-mini-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.familie === familie);
    });

    // Set hidden select value and reload parametri
    const select = document.getElementById('param-familie');
    if (select) select.value = familie;

    // Reveal filters + table containers (hidden initially)
    document.getElementById('param-filters').style.display = 'flex';
    document.getElementById('parametri-table-container').style.display = 'block';
    document.getElementById('param-family-empty').style.display = 'none';
    document.getElementById('parametri-pagination').style.display = 'flex';

    parametriPage = 1;
    loadParametri();
}

function paramBackToProducator() {
    _paramSelectedProducator = null;
    document.getElementById('param-step-list').style.display = 'none';
    document.getElementById('param-step-producator').style.display = 'block';
    // Reset hidden select
    const select = document.getElementById('param-familie');
    if (select) select.value = '';
}

async function loadParametri() {
    const familie = document.getElementById('param-familie').value;
    const search = document.getElementById('param-search').value.trim();
    const loading = document.getElementById('parametri-loading');
    const table = document.getElementById('parametri-table');

    // Show the loading indicator only if the fetch is genuinely slow — a cache
    // hit resolves within a microtask and renders the table with no flash.
    const slowTimer = setTimeout(() => {
        if (loading) loading.style.display = 'block';
        if (table) table.style.display = 'none';
        const empty = document.getElementById('parametri-empty');
        if (empty) empty.style.display = 'none';
    }, 180);

    try {
        let url = `/parametri?page=${parametriPage}&limit=${parametriLimit}`;
        if (familie) url += `&familie=${encodeURIComponent(familie)}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;

        const data = await apiGet(url);
        parametriTotal = data.total;

        document.getElementById('param-count').textContent =
            `Total: ${data.total} parametri`;

        renderParametri(data.params);
        updateParametriPagination(data);
    } catch (e) {
        console.error('Failed to load parametri:', e);
        if (loading) loading.style.display = 'none';
        showToast('Eroare la încărcarea parametrilor', 'error');
    } finally {
        clearTimeout(slowTimer);
    }
}

function renderParametri(params) {
    const tbody = document.getElementById('parametri-tbody');
    const table = document.getElementById('parametri-table');
    const empty = document.getElementById('parametri-empty');
    const loading = document.getElementById('parametri-loading');
    
    loading.style.display = 'none';
    
    if (params.length === 0) {
        table.style.display = 'none';
        empty.style.display = 'block';
        return;
    }
    
    table.style.display = 'table';
    empty.style.display = 'none';
    
    window._currentParametriParams = params;
    parametriData = params;
    tbody.innerHTML = params.map((p, i) => `
        <tr class="param-row" onclick="openParamModal(parametriData[${i}])" title="Click pentru detalii">
            <td style="font-weight: 600; color: var(--accent);">${escapeHtml(p.parametru)}</td>
            <td><span class="param-name">${escapeHtml(extractParamName(p.descriere_scurta))}</span></td>
            <td><span class="badge" style="font-size: 0.7rem;">${escapeHtml(p.acces || '-')}</span></td>
            <td style="font-size: var(--font-small); color: var(--text2);">${escapeHtml(p.tip_date || '-')}</td>
            <td style="font-size: var(--font-small);">${formatParamValue(p.valoare_default, p.valoare_default_str)}</td>
            <td style="font-size: var(--font-small); color: var(--text2);">${p.min != null ? p.min : '-'}</td>
            <td style="font-size: var(--font-small); color: var(--text2);">${p.max != null ? p.max : '-'}</td>
            <td style="font-size: var(--font-small); color: var(--text2);">${escapeHtml(p.unitate || '-')}</td>
        </tr>
    `).join('');
}

// extractParamName() lives in core.js (shared with the mobile shell).

function formatParamValue(def, defStr) {
    if (defStr !== null && defStr !== undefined && defStr !== '') {
        return escapeHtml(defStr);
    }
    if (def !== null && def !== undefined) {
        return def;
    }
    return '-';
}

function updateParametriPagination(data) {
    const prevBtn = document.getElementById('param-prev');
    const nextBtn = document.getElementById('param-next');
    const pageInfo = document.getElementById('param-page-info');
    
    prevBtn.disabled = data.page <= 1;
    nextBtn.disabled = data.page >= data.totalPages;
    pageInfo.textContent = `Pagina ${data.page} din ${data.totalPages} (${data.total} rezultate)`;
}

function parametriChangePage(delta) {
    parametriPage += delta;
    if (parametriPage < 1) parametriPage = 1;
    loadParametri();
}

// ============ PARAM MODAL ============

function openParamModal(param) {
    if (!param) return;
    currentParam = param;
    document.getElementById('param-modal-code').textContent = param.parametru || '-';
    document.getElementById('param-modal-familie').textContent = param.familie || '';
    document.getElementById('param-modal-name').textContent = extractParamName(param.descriere) || param.descriere_scurta || '-';
    document.getElementById('param-modal-descriere').textContent = param.descriere || '-';
    document.getElementById('param-modal-acces').textContent = param.acces || '-';
    document.getElementById('param-modal-tip').textContent = param.tip_date || '-';
    const def = param.valoare_default_str || (param.valoare_default !== null && param.valoare_default !== undefined ? param.valoare_default : '-');
    document.getElementById('param-modal-default').textContent = def;
    document.getElementById('param-modal-unitate').textContent = param.unitate || '-';
    document.getElementById('param-modal-min').textContent = param.min !== null && param.min !== undefined ? param.min : '-';
    document.getElementById('param-modal-max').textContent = param.max !== null && param.max !== undefined ? param.max : '-';
    const paginaRow = document.getElementById('param-modal-pagina-row');
    if (param.pagina) {
        document.getElementById('param-modal-pagina').textContent = param.pagina;
        paginaRow.style.display = 'block';
    } else {
        paginaRow.style.display = 'none';
    }

    // Interconexiuni — ascunse (Ion vrea doar explicație + influențe, 10 Mai 2026)
    const interconnRow = document.getElementById('param-modal-interconn-row');
    if (interconnRow) interconnRow.style.display = 'none';

    // Influențe — ascunde temporar până la fetch (ambele rânduri).
    const inflRow = document.getElementById('param-modal-influenteaza-row');
    if (inflRow) inflRow.style.display = 'none';
    const inflByRow = document.getElementById('param-modal-influentat-de-row');
    if (inflByRow) inflByRow.style.display = 'none';

    // Show manual button if family has a known manual
    const manualBtn = document.getElementById('param-manual-btn');
    const familie = param.familie || '';
    const manualMap = {
        'ACS880': 'ACS880_Primary_Firmware_Manual.pdf',
        'ACS580': 'ACS580_Firmware_Manual.pdf',
        'ACS380': 'ACS580_Firmware_Manual.pdf',
        'ACS180': 'ACS580_Firmware_Manual.pdf',
        'SINAMICS_G120': 'SINAMICS_G120_List_Manual.pdf',
        'SINAMICS_G120C': 'SINAMICS_G120_List_Manual.pdf',
        'SINAMICS_S120': 'SINAMICS_S120_S150_List_Manual.pdf',
        'SINAMICS_S150': 'SINAMICS_S120_S150_List_Manual.pdf',
        'SINAMICS_S120_S150': 'SINAMICS_S120_S150_List_Manual.pdf',
        'SINAMICS_G130_G150': 'SINAMICS_G120_List_Manual.pdf',
        'Danfoss_VLT_FC302': 'Danfoss_VLT_FC302_Programming_Guide.pdf',
        'FC302': 'Danfoss_VLT_FC302_Programming_Guide.pdf',
        'FC301': 'Danfoss_VLT_FC302_Programming_Guide.pdf',
        'FC202': 'Danfoss_VLT_FC302_Programming_Guide.pdf',
        'Lenze_i550': 'Lenze_i550_Manual.pdf',
        'i550': 'Lenze_i550_Manual.pdf',
        'Lenze_i950': 'Lenze_i950_Manual.pdf',
        'i650': 'Lenze_i950_Manual.pdf',
        'i950': 'Lenze_i950_Manual.pdf',
    };
    _currentParamManual = manualMap[familie] || null;
    if (_currentParamManual) {
        manualBtn.style.display = 'block';
    } else {
        manualBtn.style.display = 'none';
    }

    document.getElementById('param-detail-modal').classList.add('active');

    // Fetch detaliu complet pentru explicatie + influenteaza
    const paramId = param.id || param.parametru;
    fetch('/api/parametri/' + encodeURIComponent(paramId))
        .then(function(r) { return r.ok ? r.json() : Promise.reject(); })
        .then(function(detail) {
            // Merge detail into currentParam
            if (currentParam) Object.assign(currentParam, detail);
            // Explicatie
            const explicatieRow = document.getElementById('param-modal-explicatie-row');
            const explicatieDiv = document.getElementById('param-modal-explicatie');
            if (detail.explicatie && detail.explicatie.trim().length > 0) {
                // Use textContent (safe) then let KaTeX scan text nodes for $...$ delimiters.
                // Avoids treating < > chars in technical notation as HTML tags.
                explicatieDiv.textContent = detail.explicatie;
                renderMathIn(explicatieDiv);
                explicatieRow.style.display = 'block';
            } else {
                explicatieRow.style.display = 'none';
            }
            // Influenteaza (X →) + Influentat_de (← X) — bidirectional
            renderInfluenteazaDesktop(detail);
            renderInfluentatDeDesktop(detail);
        })
        .catch(function() {});
}

function closeParamModal() {
    document.getElementById('param-detail-modal').classList.remove('active');
    currentParam = null;
}

// Parse `influenteaza` into a list of {code, label, efect, tip}.
// _parseInfluenteaza() lives in core.js (shared with the mobile shell).

// Build a clickable chip for a referenced parameter code. On click, navigates
// to that param's modal if we have it in cache; otherwise just copies the code.
// TODO HIGH-Q2: consider unifying — desktop _influChip and mobile _mobChip differ
// (desktop chip is clickable: has the .influ-chip class + data-code attr + cursor/transition;
// mobile chip is display-only). Different behaviour, intentionally left alone.
function _influChip(entry, color) {
    const code = entry.code || entry.parametru || '?';
    const tipTag = entry.tip ? ` <span style="font-size:0.7em;opacity:0.6;">[${entry.tip}]</span>` : '';
    const labelText = entry.descriere_scurta ? ` <span style="font-size:0.8em;opacity:0.75;">${entry.descriere_scurta}</span>` : '';
    const efectText = entry.efect ? `<div style="font-size:0.8em;opacity:0.8;margin-top:1px;">${entry.efect}</div>` : '';
    return `<div class="influ-chip" data-code="${code}" style="margin:4px 0;padding:6px 10px;background:var(--bg);border-radius:6px;border-left:3px solid ${color};cursor:pointer;transition:background 0.12s;">
        <span style="font-family:'JetBrains Mono', monospace;font-weight:600;color:${color};">${code}</span>${tipTag}${labelText}
        ${efectText}
    </div>`;
}

// Generic row builder: creates the influence/influenced-by panel before
// `param-modal-explicatie-row` and renders chips inside it.
function _renderInfluRow(rowId, divId, label, iconName, color, entries) {
    const modal = document.getElementById('param-detail-modal');
    if (!modal) return;
    let row = document.getElementById(rowId);
    if (!row) {
        const explicatieRow = document.getElementById('param-modal-explicatie-row');
        row = document.createElement('div');
        row.id = rowId;
        row.style.cssText = `display:none;margin-top:8px;padding:12px;background:rgba(116,212,165,0.06);border:1px solid ${color};border-radius:6px;`;
        row.innerHTML = `<strong style="display:flex;align-items:center;gap:6px;"><i data-lucide="${iconName}" style="width:16px;height:16px;"></i> ${label}</strong><div id="${divId}" style="margin-top:6px;font-size:0.9em;"></div>`;
        if (explicatieRow && explicatieRow.parentNode) {
            explicatieRow.parentNode.insertBefore(row, explicatieRow);
        } else {
            modal.appendChild(row);
        }
        scheduleIconRefresh();
    }
    const div = document.getElementById(divId);
    if (!div) return;
    // Ion wants both sections visible always — show an empty-state line when
    // the list is empty instead of hiding the row.
    if (!entries || entries.length === 0) {
        div.innerHTML = '<div style="font-size:0.85em;opacity:0.55;font-style:italic;padding:4px 2px;">— niciun parametru —</div>';
    } else {
        div.innerHTML = entries.map(e => _influChip(e, color)).join('');
    }
    row.style.display = 'block';
}

// X → others
function renderInfluenteazaDesktop(param) {
    const entries = _parseInfluenteaza(param.influenteaza);
    _renderInfluRow(
        'param-modal-influenteaza-row',
        'param-modal-influenteaza',
        'Influențează',
        'arrow-right',
        'var(--success)',
        entries
    );
}

// others → X
function renderInfluentatDeDesktop(param) {
    const arr = Array.isArray(param.influentat_de) ? param.influentat_de : [];
    const entries = arr.map(o => ({
        code: o.parametru,
        descriere_scurta: o.descriere_scurta || '',
        efect: '',
        tip: '',
    }));
    _renderInfluRow(
        'param-modal-influentat-de-row',
        'param-modal-influentat-de',
        'Influențat de',
        'arrow-left',
        'var(--violet)',
        entries
    );
}

function copyParamCode() {
    if (!currentParam) return;
    navigator.clipboard.writeText(currentParam.parametru || '').then(() => {
        showToast('Cod copiat: ' + currentParam.parametru);
    });
}

var el = document.getElementById('param-detail-modal');
if (el) el.addEventListener('click', function(e) {
    if (e.target === this) closeParamModal();
});

// Influ-chip click navigation: clicking a referenced parameter chip swaps the
// modal to that parameter. Document-level delegation so we don't depend on
// modal-attach timing or on the chips being children of the modal at the
// moment the listener was registered (capture phase to beat any preventing
// stopPropagation in deeper handlers).
document.addEventListener('click', async function(e) {
    const chip = e.target.closest && e.target.closest('.influ-chip');
    if (!chip) return;
    e.stopPropagation();
    e.preventDefault();
    const code = chip.getAttribute('data-code');
    console.debug('[influ-chip] click', { code, currentParam });
    if (!code || code === '?') return;
    // Snapshot familie before openParamModal overwrites currentParam.
    const familie = currentParam && currentParam.familie;
    if (!familie) {
        showToast('Familie necunoscuta pentru param curent', true);
        return;
    }

    let found = (Array.isArray(parametriData) ? parametriData : [])
        .find(p => p && p.parametru === code && p.familie === familie);

    if (!found) {
        try {
            const url = '/api/parametri?familie=' + encodeURIComponent(familie)
                + '&search=' + encodeURIComponent(code) + '&limit=50';
            const r = await fetch(url);
            if (r.ok) {
                const data = await r.json();
                const list = (data && data.params) || [];
                found = list.find(p => p.parametru === code && p.familie === familie)
                    || list.find(p => p.parametru === code);
            }
        } catch (err) {
            console.error('[influ-chip] fetch failed:', err);
        }
    }

    console.debug('[influ-chip] resolved', { found });
    if (found) {
        openParamModal(found);
    } else {
        showToast('Parametrul ' + code + ' nu a fost gasit', true);
    }
}, true);

// ============ MANUALS MODAL ============
const MANUAL_LABELS = {
    'ACS880_Primary_Firmware_Manual.pdf': 'ABB ACS880 — Primary Firmware Manual',
    'ACS580_Firmware_Manual.pdf': 'ABB ACS580 — Firmware Manual',
    'SINAMICS_G120_List_Manual.pdf': 'Siemens SINAMICS G120 — List Manual',
    'SINAMICS_S120_S150_List_Manual.pdf': 'Siemens SINAMICS S120/S150 — List Manual',
    'Danfoss_VLT_FC302_Programming_Guide.pdf': 'Danfoss VLT FC302 — Programming Guide',
    'Lenze_i550_Manual.pdf': 'Lenze i550 — Manual',
    'Lenze_i950_Manual.pdf': 'Lenze i950 — Project Planning Manual',
};

function showManualsModal() {
    const list = document.getElementById('manuals-list');
    list.innerHTML = '<div style="color:var(--text2);font-size:0.9rem;text-align:center;padding:20px;">Se încarcă...</div>';
    document.getElementById('manuals-modal').classList.add('active');
    fetch('/api/manuals')
        .then(r => r.json())
        .then(data => {
            if (!data.manuals || data.manuals.length === 0) {
                list.innerHTML = '<div style="color:var(--text2);font-size:0.9rem;text-align:center;">Niciun manual găsit.</div>';
                return;
            }
            list.innerHTML = '';
            data.manuals.forEach(m => {
                const filename = m.filename || m;
                const label = (typeof MANUAL_LABELS !== 'undefined' && MANUAL_LABELS[filename]) || m.name || filename.replace(/_/g, ' ').replace('.pdf', '');
                const sizeText = m.size_kb ? `${(m.size_kb / 1024).toFixed(1)} MB` : 'PDF';
                const a = document.createElement('a');
                a.href = '#';
                a.style.cssText = 'display:flex;align-items:center;gap:12px;padding:12px 16px;border-radius:6px;border:1px solid var(--border);background:var(--bg2);color:var(--text);text-decoration:none;transition:background 0.15s;';
                a.innerHTML = `<span style="display:inline-flex;color:var(--accent);"><i data-lucide="file-text" style="width:22px;height:22px;"></i></span><span style="flex:1;font-size:0.9rem;">${escapeHtml(label)}</span><span style="font-size:0.75rem;color:var(--text2);">${sizeText}</span>`;
                a.onclick = (e) => { e.preventDefault(); window.open('/manuals/' + encodeURIComponent(filename), '_blank'); };
                a.onmouseenter = () => { a.style.background = 'var(--hover)'; };
                a.onmouseleave = () => { a.style.background = 'var(--bg2)'; };
                list.appendChild(a);
            });
        })
        .catch(() => {
            list.innerHTML = '<div style="color:var(--danger);font-size:0.9rem;">Eroare la încărcarea manualelor.</div>';
        });
}

function closeManualsModal() {
    document.getElementById('manuals-modal').classList.remove('active');
}

var el = document.getElementById('manuals-modal');
if (el) el.addEventListener('click', function(e) {
    if (e.target === this) closeManualsModal();
});

let _currentParamManual = null;

function openParamManual() {
    if (_currentParamManual) {
        var url = '/manuals/' + encodeURIComponent(_currentParamManual);
        if (currentParam && currentParam.pagina) {
            url += '#page=' + currentParam.pagina;
        }
        window.open(url, '_blank');
    }
}

// ============ CODURI EROARE (mod in tab-ul Parametri) ============
// Drive fault / alarm / warning codes. Same producator -> familie -> list
// navigation as the Parametri mode, reusing its CSS.

let paramMode = 'params';            // 'params' | 'faults'
let faultFamilies = [];              // [{producator, familie, count}]
let _faultFamilieCounts = {};        // { 'ACS580': 191, ... }
let _faultProducatori = {};          // { 'ABB': ['ACS580','ACS880'], ... }
let _faultSelectedProducator = null;
let _faultSelectedFamilie = null;
let _faultFamiliiLoaded = false;
let faultPage = 1;
let faultTotal = 0;
const faultLimit = 50;
let faultData = [];                  // current page rows
let currentFault = null;
let _currentFaultManual = null;
let _faultSearchTimer = null;

const FAULT_TIP_LABEL = {
    fault: 'Fault', warning: 'Warning', alarm: 'Alarm', safety: 'Safety',
    event: 'Event', trouble: 'Trouble', info: 'Info',
    no_response: 'No resp.', warning_alarm: 'Warn/Alarm'
};

// Switch between the Parametri and Coduri-eroare modes of the Parametri tab.
function paramSetMode(mode) {
    paramMode = (mode === 'faults') ? 'faults' : 'params';
    try { localStorage.setItem('pif:param-mode', paramMode); } catch (e) {}
    const isF = paramMode === 'faults';
    const mp = document.getElementById('param-mode-params');
    const mf = document.getElementById('param-mode-faults');
    if (mp) mp.style.display = isF ? 'none' : 'block';
    if (mf) mf.style.display = isF ? 'block' : 'none';
    const bP = document.getElementById('pmode-btn-params');
    const bF = document.getElementById('pmode-btn-faults');
    if (bP) { bP.classList.toggle('active', !isF); bP.setAttribute('aria-selected', String(!isF)); }
    if (bF) { bF.classList.toggle('active', isF); bF.setAttribute('aria-selected', String(isF)); }
    if (isF) {
        if (!_faultFamiliiLoaded) loadFaultFamilii();
    } else {
        loadParametriFamilii();   // cached -> instant
    }
}

// Called when the Parametri tab is entered — applies the persisted mode.
function paramTabEnter() {
    let mode = 'params';
    try { mode = localStorage.getItem('pif:param-mode') || 'params'; } catch (e) {}
    paramSetMode(mode);
}

async function loadFaultFamilii() {
    try {
        const data = await apiGet('/fault-codes/familii');
        faultFamilies = data.families || [];
        _faultFamilieCounts = {};
        _faultProducatori = {};
        faultFamilies.forEach(f => {
            _faultFamilieCounts[f.familie] = f.count;
            if (!_faultProducatori[f.producator]) _faultProducatori[f.producator] = [];
            _faultProducatori[f.producator].push(f.familie);
        });
        _faultFamiliiLoaded = true;
        renderFaultProducatorPicker();
    } catch (e) {
        console.error('Failed to load fault families:', e);
    }
}

function renderFaultProducatorPicker() {
    const grid = document.getElementById('fault-producator-grid');
    if (!grid) return;
    const order = ['ABB', 'Siemens', 'Danfoss', 'Lenze'];
    const prods = order.filter(p => _faultProducatori[p]);
    Object.keys(_faultProducatori).forEach(p => { if (!prods.includes(p)) prods.push(p); });
    grid.innerHTML = prods.map(prod => {
        const fams = _faultProducatori[prod] || [];
        const total = fams.reduce((s, f) => s + (_faultFamilieCounts[f] || 0), 0);
        const famLabel = fams.map(f => f.replace(/^(SINAMICS_|Lenze_|Danfoss_VLT_)/, '')).join(' · ');
        return `
            <button class="param-producator-card ${prod.toLowerCase()}" onclick="faultSelectProducator('${prod}')">
                <span class="ppc-icon"><i data-lucide="cpu"></i></span>
                <div class="ppc-body">
                    <div class="ppc-name">${escapeHtml(prod)}</div>
                    <div class="ppc-meta">${total.toLocaleString('ro-RO')} coduri</div>
                    <div class="ppc-families">${escapeHtml(famLabel)}</div>
                </div>
            </button>`;
    }).join('');
    if (window.lucide) try { lucide.createIcons(); } catch (e) {}
}

function faultSelectProducator(prod) {
    const fams = _faultProducatori[prod];
    if (!fams || !fams.length) return;
    _faultSelectedProducator = prod;
    document.getElementById('fault-step-producator').style.display = 'none';
    document.getElementById('fault-step-list').style.display = 'block';
    document.getElementById('fault-breadcrumb-producator').textContent = prod;

    const tabsEl = document.getElementById('fault-mini-tabs');
    tabsEl.innerHTML = fams.map(f => {
        const count = _faultFamilieCounts[f] || 0;
        const label = f.replace(/^(SINAMICS_|Lenze_|Danfoss_VLT_)/, '');
        return `<button class="param-mini-tab" data-familie="${f}" onclick="faultSelectFamilie('${f}')">${escapeHtml(label)}<span class="count">${count.toLocaleString('ro-RO')}</span></button>`;
    }).join('');
    if (window.lucide) try { lucide.createIcons(); } catch (e) {}

    if (fams.length > 0) faultSelectFamilie(fams[0]);
}

function faultSelectFamilie(familie) {
    _faultSelectedFamilie = familie;
    document.querySelectorAll('#fault-mini-tabs .param-mini-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.familie === familie);
    });
    document.getElementById('fault-filters').style.display = 'flex';
    document.getElementById('fault-table-container').style.display = 'block';
    document.getElementById('fault-family-empty').style.display = 'none';
    document.getElementById('fault-pagination').style.display = 'flex';
    const searchEl = document.getElementById('fault-search');
    if (searchEl) searchEl.value = '';
    faultPage = 1;
    loadFaultCodes();
}

function faultBackToProducator() {
    _faultSelectedProducator = null;
    _faultSelectedFamilie = null;
    document.getElementById('fault-step-list').style.display = 'none';
    document.getElementById('fault-step-producator').style.display = 'block';
}

function debounceLoadFaultCodes() {
    clearTimeout(_faultSearchTimer);
    _faultSearchTimer = setTimeout(function () { faultPage = 1; loadFaultCodes(); }, 220);
}

async function loadFaultCodes() {
    if (!_faultSelectedFamilie) return;
    const search = (document.getElementById('fault-search').value || '').trim();
    const loading = document.getElementById('fault-loading');
    const table = document.getElementById('fault-table');

    const slowTimer = setTimeout(() => {
        if (loading) loading.style.display = 'block';
        if (table) table.style.display = 'none';
        const empty = document.getElementById('fault-empty');
        if (empty) empty.style.display = 'none';
    }, 180);

    try {
        let url = `/fault-codes?familie=${encodeURIComponent(_faultSelectedFamilie)}&page=${faultPage}&limit=${faultLimit}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        const data = await apiGet(url);
        faultTotal = data.total;
        document.getElementById('fault-count').textContent = `Total: ${data.total} coduri`;
        renderFaultCodes(data.codes);
        updateFaultPagination(data);
    } catch (e) {
        console.error('Failed to load fault codes:', e);
        if (loading) loading.style.display = 'none';
        showToast('Eroare la încărcarea codurilor', true);
    } finally {
        clearTimeout(slowTimer);
    }
}

function faultTipBadge(tip) {
    const t = tip || '';
    const label = FAULT_TIP_LABEL[t] || (t || '—');
    return `<span class="fault-tip-badge fault-tip-${t}">${escapeHtml(label)}</span>`;
}

function renderFaultCodes(codes) {
    const tbody = document.getElementById('fault-tbody');
    const table = document.getElementById('fault-table');
    const empty = document.getElementById('fault-empty');
    const loading = document.getElementById('fault-loading');
    loading.style.display = 'none';
    faultData = codes || [];

    if (!faultData.length) {
        table.style.display = 'none';
        empty.style.display = 'block';
        return;
    }
    table.style.display = 'table';
    empty.style.display = 'none';
    tbody.innerHTML = faultData.map((c, i) => `
        <tr class="fault-row param-row" onclick="openFaultModal(faultData[${i}])" title="Click pentru detalii">
            <td>${escapeHtml(c.cod)}${c.cod_secundar ? ` <span style="color:var(--text-dim);font-size:0.82em;">${escapeHtml(c.cod_secundar)}</span>` : ''}</td>
            <td>${faultTipBadge(c.tip)}</td>
            <td>${escapeHtml(c.nume || '-')}</td>
        </tr>`).join('');
}

function updateFaultPagination(data) {
    const prev = document.getElementById('fault-prev');
    const next = document.getElementById('fault-next');
    const info = document.getElementById('fault-page-info');
    if (prev) prev.disabled = data.page <= 1;
    if (next) next.disabled = data.page >= data.totalPages;
    if (info) info.textContent = `Pagina ${data.page} din ${data.totalPages} (${data.total} rezultate)`;
}

function faultChangePage(delta) {
    faultPage += delta;
    if (faultPage < 1) faultPage = 1;
    loadFaultCodes();
}

function openFaultModal(code) {
    if (!code) return;
    currentFault = code;
    document.getElementById('fault-modal-code').textContent = code.cod || '-';
    const tipEl = document.getElementById('fault-modal-tip');
    tipEl.className = 'fault-tip-badge fault-tip-' + (code.tip || '');
    tipEl.textContent = FAULT_TIP_LABEL[code.tip] || code.tip || '';
    tipEl.style.display = code.tip ? 'inline-block' : 'none';
    document.getElementById('fault-modal-familie').textContent =
        code.familie ? code.familie.replace(/_/g, ' ') : '';
    document.getElementById('fault-modal-name').textContent = code.nume || '...';
    ['fault-modal-cauza-row', 'fault-modal-remediu-row', 'fault-modal-meta',
     'fault-modal-extra', 'fault-modal-pagina-row'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    document.getElementById('fault-manual-btn').style.display = 'none';
    document.getElementById('fault-detail-modal').classList.add('active');

    apiGet('/fault-codes/' + encodeURIComponent(code.id))
        .then(d => { currentFault = d; renderFaultDetail(d); })
        .catch(() => {});
}

function renderFaultDetail(d) {
    document.getElementById('fault-modal-name').textContent = d.nume || '-';

    const cauzaRow = document.getElementById('fault-modal-cauza-row');
    if (d.cauza && d.cauza.trim()) {
        document.getElementById('fault-modal-cauza').textContent = d.cauza;
        cauzaRow.style.display = 'block';
    } else { cauzaRow.style.display = 'none'; }

    const remRow = document.getElementById('fault-modal-remediu-row');
    if (d.remediu && d.remediu.trim()) {
        document.getElementById('fault-modal-remediu').textContent = d.remediu;
        remRow.style.display = 'block';
    } else { remRow.style.display = 'none'; }

    const metaEl = document.getElementById('fault-modal-meta');
    const cards = [];
    if (d.reactie) cards.push(['Reacție', d.reactie]);
    if (d.confirmare) cards.push(['Confirmare', d.confirmare]);
    if (d.cod_secundar) cards.push(['Cod secundar', d.cod_secundar]);
    if (cards.length) {
        metaEl.innerHTML = cards.map(([k, v]) =>
            `<div style="padding:8px 12px;background:var(--bg);border-radius:6px;">
                <div style="font-size:0.7em;color:var(--text2);margin-bottom:2px;">${escapeHtml(k)}</div>
                <div style="font-weight:500;">${escapeHtml(v)}</div>
            </div>`).join('');
        metaEl.style.display = 'grid';
    } else { metaEl.style.display = 'none'; }

    renderFaultExtra(d.extra);

    const pagRow = document.getElementById('fault-modal-pagina-row');
    if (d.pagina) {
        document.getElementById('fault-modal-pagina').textContent = d.pagina;
        pagRow.style.display = 'block';
    } else { pagRow.style.display = 'none'; }

    _currentFaultManual = d.sursa || null;
    document.getElementById('fault-manual-btn').style.display = _currentFaultManual ? 'block' : 'none';
}

function renderFaultExtra(extra) {
    const el = document.getElementById('fault-modal-extra');
    if (!extra || typeof extra !== 'object') { el.style.display = 'none'; return; }
    let html = '';

    if (Array.isArray(extra.aux_codes) && extra.aux_codes.length) {
        html += `<div class="fault-modal-label">Coduri auxiliare</div>`;
        html += extra.aux_codes.map(a => `
            <div style="margin:4px 0;padding:7px 10px;background:var(--bg);border-radius:6px;border-left:3px solid var(--border);">
                <span style="font-family:'JetBrains Mono',monospace;font-weight:600;color:var(--accent);">${escapeHtml(a.cod || '?')}</span>
                ${a.cauza ? `<div style="font-size:0.85em;color:var(--text2);margin-top:2px;">${escapeHtml(a.cauza)}</div>` : ''}
                ${a.remediu ? `<div style="font-size:0.85em;margin-top:2px;">${escapeHtml(a.remediu)}</div>` : ''}
            </div>`).join('');
    }

    const mv = extra.message_value || extra.fault_value || extra.alarm_value;
    if (mv) {
        html += `<div class="fault-modal-label" style="margin-top:10px;">Valoare mesaj</div>
            <div class="fault-modal-text" style="font-size:0.85em;">${escapeHtml(mv)}</div>`;
    }
    if (extra.note) {
        html += `<div class="fault-modal-label" style="margin-top:10px;">Notă</div>
            <div class="fault-modal-text" style="font-size:0.85em;">${escapeHtml(extra.note)}</div>`;
    }
    const refs = [];
    if (extra.parametru) refs.push(extra.parametru);
    if (extra.configurable_in) refs.push(extra.configurable_in);
    if (extra.see_also) refs.push(extra.see_also);
    if (refs.length) {
        html += `<div class="fault-modal-label" style="margin-top:10px;">Parametri asociați</div>
            <div class="fault-modal-text" style="font-size:0.85em;">${escapeHtml(refs.join('  ·  '))}</div>`;
    }
    if (extra.trip_lock) {
        html += `<div style="margin-top:8px;font-size:0.82em;">
            <strong style="color:var(--warning);">Trip lock:</strong> necesită oprirea alimentării înainte de reset.</div>`;
    }

    if (html) { el.innerHTML = html; el.style.display = 'block'; }
    else { el.style.display = 'none'; }
}

function closeFaultModal() {
    document.getElementById('fault-detail-modal').classList.remove('active');
    currentFault = null;
}

function openFaultManual() {
    if (!_currentFaultManual) return;
    let url = '/manuals/' + encodeURIComponent(_currentFaultManual);
    if (currentFault && currentFault.pagina) url += '#page=' + currentFault.pagina;
    window.open(url, '_blank');
}

// ============ PWA / OFFLINE SUPPORT ============

let deferredPrompt = null;
// Set to true ONLY when the user clicks "Reîncarcă" in the update banner.
// Guards the controllerchange handler so a background SW activation can never
// reload the page on its own (this was the "page flashes / reloads" bug).
let _swUpdateAccepted = false;

function initPWA() {
    if ('serviceWorker' in navigator) {
        // Reload the page only after the user has explicitly accepted an update.
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            if (_swUpdateAccepted) window.location.reload();
        });

        // Listen for SW_UPDATED messages sent by the service worker's activate
        // handler. This is the primary update-notification path — it fires even
        // when the page's old app.js never ran updatefound (the root bug).
        navigator.serviceWorker.addEventListener('message', (event) => {
            if (event.data && event.data.type === 'SW_UPDATED') {
                showSWUpdateBanner();
            }
        });

        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/service-worker.js')
                .then(registration => {
                    console.log('SW registered:', registration.scope);
                    // A worker may already be waiting from a previous visit.
                    if (registration.waiting && navigator.serviceWorker.controller) {
                        promptSWUpdate(registration.waiting);
                    }
                    // A new worker installed while the app is open.
                    registration.addEventListener('updatefound', () => {
                        const newWorker = registration.installing;
                        if (!newWorker) return;
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                promptSWUpdate(newWorker);
                            }
                        });
                    });
                })
                .catch(error => {
                    console.error('SW registration failed:', error);
                });
        });
    }

    // Capture install prompt
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        console.log('Install prompt captured');
        // Show the install button
        const installBtn = document.getElementById('install-pwa-btn');
        if (installBtn) installBtn.style.display = 'flex';
    });
}

// Non-blocking banner offering to apply a pending update. The page reloads
// ONLY when the user clicks "Reîncarcă" — never on its own.
// Extract banner creation so it can be called from both the message handler
// AND the existing updatefound flow. The worker parameter is optional — if
// absent the "Reîncarcă" button sends skipWaiting directly to the SW.
function showSWUpdateBanner(worker) {
    if (document.getElementById('sw-update-banner')) return;
    const banner = document.createElement('div');
    banner.id = 'sw-update-banner';
    banner.className = 'sw-update-banner';
    banner.innerHTML = `
        <span class="sw-update-text">Versiune nouă disponibilă</span>
        <button type="button" class="sw-update-apply" id="sw-update-apply">Reîncarcă</button>
        <button type="button" class="sw-update-dismiss" id="sw-update-dismiss" aria-label="Închide">&times;</button>
    `;
    document.body.appendChild(banner);
    requestAnimationFrame(() => banner.classList.add('visible'));

    document.getElementById('sw-update-apply').addEventListener('click', () => {
        _swUpdateAccepted = true;
        if (worker) worker.postMessage('skipWaiting');
        banner.classList.remove('visible');
    });
    document.getElementById('sw-update-dismiss').addEventListener('click', () => {
        banner.classList.remove('visible');
        setTimeout(() => banner.remove(), 300);
    });
}

// Backwards-compatible wrapper — delegates to the new standalone function.
function promptSWUpdate(worker) {
    showSWUpdateBanner(worker);
}

async function installPWA() {
    if (!deferredPrompt) {
        showToast('Instalare nu este disponibilă', true);
        return;
    }
    
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
        showToast('PIF Dashboard instalat!', 'success');
    }
    deferredPrompt = null;
}

// Initialize PWA on load
document.addEventListener('DOMContentLoaded', initPWA);

// Keyboard shortcuts for undo/redo
document.addEventListener('keydown', function(e) {
    // isContentEditable so Ctrl+Z inside the notes editor stays native.
    const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)
        || e.target.isContentEditable;
    
    // Ctrl+Z - Undo
    if (e.key === 'z' && (e.ctrlKey || e.metaKey) && !e.shiftKey && !isInput) {
        e.preventDefault();
        undo();
        return;
    }
    
    // Ctrl+Shift+Z or Ctrl+Y - Redo
    if ((e.key === 'z' && (e.ctrlKey || e.metaKey) && e.shiftKey) || 
        (e.key === 'y' && (e.ctrlKey || e.metaKey)) && !isInput) {
        e.preventDefault();
        redo();
        return;
    }
});
