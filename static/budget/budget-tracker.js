// ====================================================================
// Budget Tracker - Vanilla JS (PIF design system)
// ====================================================================

var LUNI_LABELS_RO = ['Ian','Feb','Mar','Apr','Mai','Iun','Iul','Aug','Sep','Oct','Noi','Dec'];
var LUNI = ['Mai','Iun','Iul','Aug','Sep','Oct','Noi','Dec']; // recomputed by refreshLuni()
var LUNI_KEYS = ['2026-05','2026-06','2026-07','2026-08','2026-09','2026-10','2026-11','2026-12']; // recomputed
var LUNI_COUNT = 12; // default; overridden by d.profil.numarLuni
var CHELTUIELI_VARIABILE_DEFAULT = ['Alimente', 'Facturi', 'Transport', 'Sănătate', 'Îmbrăcăminte', 'Divertisment', 'Abonamente', 'Alte'];

// Generate N months starting from "YYYY-MM"; returns {keys, labels}
function generateLuni(startMonth, count) {
  startMonth = startMonth || '2026-05';
  var n = Math.max(1, Math.min(120, parseInt(count, 10) || LUNI_COUNT));
  var parts = String(startMonth).split('-');
  var year = parseInt(parts[0], 10) || 2026;
  var month = parseInt(parts[1], 10) || 5;
  var keys = [], labels = [];
  for (var i = 0; i < n; i++) {
    var idx = (month - 1 + i);
    var m = (idx % 12) + 1;
    var y = year + Math.floor(idx / 12);
    keys.push(y + '-' + (m < 10 ? '0' : '') + m);
    labels.push(LUNI_LABELS_RO[m-1] + (y !== year ? " '" + String(y % 100).padStart(2, '0') : ''));
  }
  return { keys: keys, labels: labels };
}

function refreshLuni() {
  var prof = (state.data && state.data.profil) || {};
  var sm = prof.startMonth || '2026-05';
  var n = parseInt(prof.numarLuni, 10) || LUNI_COUNT;
  var cfg = generateLuni(sm, n);
  LUNI_KEYS = cfg.keys;
  LUNI = cfg.labels;
}

// Ensure d.categoriiVar exists as [{id,label}]; seed from default constant if missing
function migrateCategoriiVar(data) {
  if (!data) return;
  if (Array.isArray(data.categoriiVar) && data.categoriiVar.length > 0 && typeof data.categoriiVar[0] === 'object') return;
  // Accept legacy "array of strings" too
  if (Array.isArray(data.categoriiVar) && data.categoriiVar.length > 0 && typeof data.categoriiVar[0] === 'string') {
    data.categoriiVar = data.categoriiVar.map(function(s, i) { return { id: i + 1, label: s }; });
    return;
  }
  data.categoriiVar = CHELTUIELI_VARIABILE_DEFAULT.map(function(s, i) { return { id: i + 1, label: s }; });
}

// Convert legacy cheltuieliFixe object {chirie, rataCredit} to array of {id,label,suma}
function migrateCheltuieliFixe(data) {
  if (!data) return;
  if (Array.isArray(data.cheltuieliFixe)) return;
  var arr = [];
  var nextId = 1;
  if (data.cheltuieliFixe && typeof data.cheltuieliFixe === 'object') {
    if (data.cheltuieliFixe.chirie != null) arr.push({ id: nextId++, label: 'Chirie', suma: data.cheltuieliFixe.chirie });
    if (data.cheltuieliFixe.rataCredit != null) arr.push({ id: nextId++, label: 'Rată credit + asig.', suma: data.cheltuieliFixe.rataCredit });
  }
  if (arr.length === 0) {
    arr = cloneObj(DATI_INITIALE.cheltuieliFixe);
  }
  data.cheltuieliFixe = arr;
}

// Convert legacy keys (mai/iun/etc) → YYYY-MM. Called once at load.
function migrateLegacyMonthKeys(data) {
  if (!data) return data;
  var legacy = ['mai','iun','iul','aug','sep','oct','noi','dec'];
  var target = ['2026-05','2026-06','2026-07','2026-08','2026-09','2026-10','2026-11','2026-12'];
  ['venituri','cheltuieli','evolutie'].forEach(function(field) {
    if (!data[field] || typeof data[field] !== 'object') return;
    legacy.forEach(function(k, i) {
      if (data[field][k] !== undefined) {
        if (data[field][target[i]] === undefined) data[field][target[i]] = data[field][k];
        delete data[field][k];
      }
    });
  });
  return data;
}

// --- Formatare RON ---
function formatRON(num) {
  if (num === null || num === undefined || num === '') return '';
  const n = parseFloat(num) || 0;
  return new Intl.NumberFormat('ro-RO', { style: 'decimal', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}
function parseRON(str) {
  return parseFloat(((str == null ? '0' : String(str)).replace(/\s/g, '').replace(',', '.'))) || 0;
}
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

// --- Date inițiale Ion ---
var DATI_INITIALE = {
  profil: { nume: 'Ion', salariuNet: 7000, bonusMedie: 2000, startMonth: '2026-05', numarLuni: 12 },
  cheltuieliFixe: [
    { id: 1, label: 'Chirie', suma: 2000 },
    { id: 2, label: 'Rată credit + asig.', suma: 1934 },
  ],
  categoriiVar: [
    { id: 1, label: 'Alimente' },
    { id: 2, label: 'Facturi' },
    { id: 3, label: 'Transport' },
    { id: 4, label: 'Sănătate' },
    { id: 5, label: 'Îmbrăcăminte' },
    { id: 6, label: 'Divertisment' },
    { id: 7, label: 'Abonamente' },
    { id: 8, label: 'Alte' },
  ],
  credit: {
    suma: 84450, dobanda: 9.99, dae: 12.96, rata: 1787, asigurare: 147,
    durata: 60, comisionRambursare: 1, dataStart: '2026-05', soldActual: 84450
  },
  fondUrgenta: [
    { id: 1, cont: 'Cont economii ING', suma: 8000, dobanda: 2, lichid: 'Da', nota: 'Acces instant' },
    { id: 2, cont: 'Depozit bonus ING', suma: 6000, dobanda: 6, lichid: 'Da', nota: 'Lichid, păstrează dobânda' },
  ],
  tezaur: [
    { id: 1, emisiune: 'Tezaur 1 an', dataSubscriere: '2026-06-01', suma: 5000, dobanda: 6.30, maturitate: '1 an', dataScadenta: '2027-06-01' },
  ],
  evolutie: {
    '2026-05': { fondUrgenta: 14000, tezaur: 5000, buffer: 3450, soldCredit: 84450 },
  },
  venituri: {
    '2026-05': { bonuri: 360, bonus: 1750, diurna: 1200 },
    '2026-06': {}, '2026-07': {}, '2026-08': {}, '2026-09': {}, '2026-10': {}, '2026-11': {}, '2026-12': {}
  },
  cheltuieli: {
    '2026-05': { 'Sănătate': 200 },
    '2026-06': {}, '2026-07': {}, '2026-08': {}, '2026-09': {}, '2026-10': {}, '2026-11': {}, '2026-12': {}
  }
};

var INITIAL_DATA = {
  profil: JSON.parse(JSON.stringify(DATI_INITIALE.profil)),
  cheltuieliFixe: DATI_INITIALE.cheltuieliFixe,
  credit: cloneObj(DATI_INITIALE.credit),
  venituri: cloneObj(DATI_INITIALE.venituri),
  cheltuieli: cloneObj(DATI_INITIALE.cheltuieli),
  fondUrgenta: cloneObj(DATI_INITIALE.fondUrgenta),
  tezaur: cloneObj(DATI_INITIALE.tezaur),
  evolutie: cloneObj(DATI_INITIALE.evolutie),
};

// --- State global ---
var state = {
  activeTab: 'buget-lunar',
  data: null,
};

// --- API client (Flask backend) ---
var API_BASE = '/budget/api';
var saveTimer = null;
var SAVE_DEBOUNCE_MS = 600;

async function loadData() {
  try {
    var r = await fetch(API_BASE + '/state', { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    var payload = await r.json();
    if (payload && payload.data) {
      state.data = payload.data;
      if (!state.data.venituri) state.data.venituri = {};
      if (!state.data.cheltuieli) state.data.cheltuieli = {};
      if (!state.data.fondUrgenta) state.data.fondUrgenta = [];
      if (!state.data.tezaur) state.data.tezaur = [];
      if (!state.data.evolutie) state.data.evolutie = {};
      if (!state.data.profil) state.data.profil = cloneObj(DATI_INITIALE.profil);
      if (!state.data.profil.startMonth) state.data.profil.startMonth = DATI_INITIALE.profil.startMonth;
      if (!state.data.profil.numarLuni) state.data.profil.numarLuni = DATI_INITIALE.profil.numarLuni;
      if (state.data.profil.salariuNet == null) state.data.profil.salariuNet = DATI_INITIALE.profil.salariuNet;
      migrateCheltuieliFixe(state.data);
      migrateCategoriiVar(state.data);
      if (!state.data.credit) state.data.credit = cloneObj(DATI_INITIALE.credit);
      if (!state.data.credit.durata) state.data.credit.durata = DATI_INITIALE.credit.durata;
      if (!state.data.credit.dataStart) state.data.credit.dataStart = DATI_INITIALE.credit.dataStart;
      if (!state.data.credit.dobanda) state.data.credit.dobanda = DATI_INITIALE.credit.dobanda;
      if (!state.data.credit.soldActual) state.data.credit.soldActual = DATI_INITIALE.credit.soldActual;
      if (!state.data.credit.suma) state.data.credit.suma = DATI_INITIALE.credit.suma;
      migrateLegacyMonthKeys(state.data);
      refreshLuni();
      LUNI_KEYS.forEach(function(l) {
        if (!state.data.venituri[l]) state.data.venituri[l] = {};
        if (!state.data.cheltuieli[l]) state.data.cheltuieli[l] = {};
      });
    } else {
      state.data = cloneObj(INITIAL_DATA);
      refreshLuni();
      await saveDataNow();
    }
  } catch(e) {
    console.error('Load failed, using initial data:', e);
    state.data = cloneObj(INITIAL_DATA);
    refreshLuni();
  }
}

async function saveDataNow() {
  try {
    var r = await fetch(API_BASE + '/state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ data: state.data })
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    setSaveStatus('saved');
  } catch(e) {
    console.error('Save failed:', e);
    setSaveStatus('error');
  }
}

function saveData() {
  setSaveStatus('pending');
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(saveDataNow, SAVE_DEBOUNCE_MS);
}

function setSaveStatus(status) {
  var el = document.getElementById('save-status');
  if (!el) return;
  var map = {
    pending: { cls: 'pending', icon: 'cloud-upload', text: 'Salvare...' },
    saved:   { cls: '',        icon: 'cloud-check',  text: 'Salvat' },
    error:   { cls: 'error',   icon: 'cloud-alert',  text: 'Eroare' }
  };
  var s = map[status] || map.saved;
  el.className = 'save-chip ' + s.cls;
  el.innerHTML = '<i data-lucide="' + s.icon + '"></i> ' + s.text;
  refreshIcons();
}

function cloneObj(obj) { return JSON.parse(JSON.stringify(obj)); }
function getNextId(arr) {
  if (!arr || arr.length === 0) return 1;
  return Math.max.apply(null, arr.map(function(x) { return x.id; })) + 1;
}

// --- Lucide icons render with re-entry guard ---
var _iconsRendering = false;
function refreshIcons() {
  if (_iconsRendering) return;
  if (typeof lucide === 'undefined') return;
  _iconsRendering = true;
  try { lucide.createIcons(); } finally { _iconsRendering = false; }
}

// --- Custom select (cs-enhance pattern from PIF Dashboard) ---
function enhanceSelect(select) {
  if (!select || select.dataset.csInit === '1') return;
  select.dataset.csInit = '1';
  select.style.display = 'none';

  var wrap = document.createElement('div');
  wrap.className = 'cs';

  var trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'cs-trigger';
  trigger.innerHTML = '<span class="cs-trigger-label"></span>' +
    '<svg class="cs-trigger-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>';

  var menu = document.createElement('div');
  menu.className = 'cs-menu';
  var labelEl = trigger.querySelector('.cs-trigger-label');

  function sync() {
    menu.innerHTML = '';
    for (var i = 0; i < select.options.length; i++) {
      (function(opt) {
        var item = document.createElement('div');
        item.className = 'cs-option' + (opt.value === select.value ? ' selected' : '');
        item.textContent = opt.textContent;
        item.dataset.value = opt.value;
        item.addEventListener('click', function() {
          select.value = opt.value;
          select.dispatchEvent(new Event('change', { bubbles: true }));
          close();
        });
        menu.appendChild(item);
      })(select.options[i]);
    }
    var sel = select.options[select.selectedIndex];
    labelEl.textContent = sel ? sel.textContent : '';
    wrap.setAttribute('data-value', select.value);
  }
  function open() { wrap.classList.add('open'); document.addEventListener('mousedown', onDocClick, true); }
  function close() { wrap.classList.remove('open'); document.removeEventListener('mousedown', onDocClick, true); }
  function onDocClick(e) { if (!wrap.contains(e.target)) close(); }

  trigger.addEventListener('click', function(e) {
    e.stopPropagation();
    wrap.classList.contains('open') ? close() : open();
  });
  document.addEventListener('keydown', function(e) { if (e.key === 'Escape') close(); });
  select.addEventListener('change', sync);

  select.parentNode.insertBefore(wrap, select);
  wrap.appendChild(trigger);
  wrap.appendChild(menu);
  wrap.appendChild(select);
  sync();
}

function enhanceAllSelects() {
  document.querySelectorAll('select.cs-enhance:not([data-cs-init])').forEach(enhanceSelect);
}

// --- Flatpickr ---
function initAllFlatpickrs() {
  if (typeof flatpickr !== 'function') return;
  document.querySelectorAll('input.fp-date:not([data-fp-init])').forEach(function(el) {
    el.dataset.fpInit = '1';
    flatpickr(el, {
      locale: 'ro',
      dateFormat: 'Y-m-d',
      allowInput: true,
      disableMobile: true
    });
  });
}

function applyEnhancements() {
  refreshIcons();
  enhanceAllSelects();
  initAllFlatpickrs();
}

// --- Theme toggle ---
function toggleTheme() {
  var cur = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
  var next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('budget-theme', next); } catch (e) {}
  render();
}

// --- Custom modal ---
function showConfirm(opts) {
  return new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML =
      '<div class="modal" role="dialog" aria-modal="true">' +
      '  <div class="modal-title"><i data-lucide="' + (opts.icon || 'alert-triangle') + '"></i> ' + esc(opts.title) + '</div>' +
      '  <div class="modal-body">' + esc(opts.body) + '</div>' +
      '  <div class="modal-actions">' +
      '    <button class="modal-btn" data-act="cancel">' + esc(opts.cancelLabel || 'Anulează') + '</button>' +
      '    <button class="modal-btn primary" data-act="ok">' + esc(opts.okLabel || 'Confirmă') + '</button>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(overlay);
    refreshIcons();
    function close(val) {
      document.body.removeChild(overlay);
      document.removeEventListener('keydown', onKey);
      resolve(val);
    }
    function onKey(e) {
      if (e.key === 'Escape') close(false);
      else if (e.key === 'Enter') close(true);
    }
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) close(false);
      var act = e.target.closest('[data-act]');
      if (act) close(act.dataset.act === 'ok');
    });
    document.addEventListener('keydown', onKey);
  });
}

async function resetData() {
  var ok = await showConfirm({
    title: 'Resetează datele',
    body: 'Toate datele introduse vor fi înlocuite cu valorile inițiale. Acțiunea nu poate fi anulată.',
    okLabel: 'Resetează',
    cancelLabel: 'Anulează',
    icon: 'alert-triangle'
  });
  if (!ok) return;
  state.data = cloneObj(INITIAL_DATA);
  refreshLuni();
  await saveDataNow();
  render();
}

// --- Audit history modal ---
async function showAudit() {
  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML =
    '<div class="modal audit-modal" role="dialog" aria-modal="true">' +
    '  <div class="modal-title"><i data-lucide="history"></i> Istoric modificări</div>' +
    '  <div class="audit-body"><div class="audit-empty">Se încarcă...</div></div>' +
    '  <div class="modal-actions"><button class="modal-btn" data-act="close">Închide</button></div>' +
    '</div>';
  document.body.appendChild(overlay);
  refreshIcons();
  function close() {
    document.body.removeChild(overlay);
    document.removeEventListener('keydown', onKey);
  }
  function onKey(e) { if (e.key === 'Escape') close(); }
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) return close();
    if (e.target.closest('[data-act="close"]')) close();
  });
  document.addEventListener('keydown', onKey);

  try {
    var r = await fetch(API_BASE + '/audit?limit=100', { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    var rows = await r.json();
    var body = overlay.querySelector('.audit-body');
    if (!rows || rows.length === 0) {
      body.innerHTML = '<div class="audit-empty">Nicio modificare înregistrată.</div>';
      return;
    }
    var html = '<div class="audit-list">';
    rows.forEach(function(row) {
      var ts = row.ts ? new Date(row.ts) : null;
      var when = ts ? ts.toLocaleString('ro-RO', { dateStyle: 'short', timeStyle: 'short' }) : '';
      html += '<div class="audit-item">';
      html += '  <div class="audit-row">';
      html += '    <span class="audit-when mono">' + esc(when) + '</span>';
      html += '    <span class="audit-field mono">' + esc(row.field || row.action || '') + '</span>';
      html += '  </div>';
      if (row.old_value != null || row.new_value != null) {
        html += '  <div class="audit-diff">';
        if (row.old_value != null) html += '<span class="audit-old mono">' + esc(String(row.old_value)) + '</span>';
        html += '<i data-lucide="arrow-right"></i>';
        if (row.new_value != null) html += '<span class="audit-new mono">' + esc(String(row.new_value)) + '</span>';
        html += '  </div>';
      }
      html += '</div>';
    });
    html += '</div>';
    body.innerHTML = html;
    refreshIcons();
  } catch (e) {
    overlay.querySelector('.audit-body').innerHTML = '<div class="audit-empty audit-error">Eroare la încărcare: ' + esc(String(e.message || e)) + '</div>';
  }
}

// --- Profil & cheltuieli fixe updaters ---
function updateProfil(field, value) {
  if (!state.data.profil) state.data.profil = cloneObj(DATI_INITIALE.profil);
  if (field === 'nume') {
    state.data.profil[field] = value;
  } else if (field === 'startMonth') {
    state.data.profil.startMonth = value;
    refreshLuni();
    LUNI_KEYS.forEach(function(l) {
      if (!state.data.venituri[l]) state.data.venituri[l] = {};
      if (!state.data.cheltuieli[l]) state.data.cheltuieli[l] = {};
    });
  } else if (field === 'numarLuni') {
    var n = Math.max(1, Math.min(120, parseInt(value, 10) || 12));
    state.data.profil.numarLuni = n;
    refreshLuni();
    LUNI_KEYS.forEach(function(l) {
      if (!state.data.venituri[l]) state.data.venituri[l] = {};
      if (!state.data.cheltuieli[l]) state.data.cheltuieli[l] = {};
    });
  } else {
    state.data.profil[field] = parseRON(value);
  }
  saveData();
  render();
}
function updateCheltuialaFixa(id, field, value) {
  if (!Array.isArray(state.data.cheltuieliFixe)) state.data.cheltuieliFixe = cloneObj(DATI_INITIALE.cheltuieliFixe);
  state.data.cheltuieliFixe = state.data.cheltuieliFixe.map(function(f) {
    if (f.id !== id) return f;
    var u = cloneObj(f);
    if (field === 'suma') u.suma = parseRON(value);
    else u[field] = value;
    return u;
  });
  saveData();
  render();
}
function addCheltuialaFixa() {
  if (!Array.isArray(state.data.cheltuieliFixe)) state.data.cheltuieliFixe = [];
  state.data.cheltuieliFixe.push({ id: getNextId(state.data.cheltuieliFixe), label: '', suma: 0 });
  saveData();
  render();
}
function removeCheltuialaFixa(id) {
  state.data.cheltuieliFixe = state.data.cheltuieliFixe.filter(function(f) { return f.id !== id; });
  saveData();
  render();
}

function addCategorie() {
  if (!Array.isArray(state.data.categoriiVar)) state.data.categoriiVar = [];
  state.data.categoriiVar.push({ id: getNextId(state.data.categoriiVar), label: '' });
  saveData();
  render();
}
function updateCategorie(id, newLabel) {
  if (!Array.isArray(state.data.categoriiVar)) return;
  var old;
  state.data.categoriiVar = state.data.categoriiVar.map(function(c) {
    if (c.id !== id) return c;
    old = c.label;
    return { id: c.id, label: newLabel };
  });
  // Rename data keys across all months so existing numbers stick to the renamed category
  if (old && newLabel && old !== newLabel && state.data.cheltuieli) {
    Object.keys(state.data.cheltuieli).forEach(function(luna) {
      var m = state.data.cheltuieli[luna];
      if (m && m[old] !== undefined) {
        m[newLabel] = m[old];
        delete m[old];
      }
    });
  }
  saveData();
  render();
}
async function removeCategorie(id) {
  var cat = (state.data.categoriiVar || []).filter(function(c) { return c.id === id; })[0];
  if (!cat) return;
  // Check if any month has data for this category
  var hasData = false;
  Object.keys(state.data.cheltuieli || {}).forEach(function(luna) {
    var m = state.data.cheltuieli[luna];
    if (m && m[cat.label] != null && parseRON(m[cat.label]) !== 0) hasData = true;
  });
  if (hasData) {
    var alsoDelete = await showConfirm({
      title: 'Șterge categoria "' + cat.label + '"',
      body: 'Există sume introduse pentru această categorie. Le ștergi și pe ele, sau le păstrezi (orfan) în date?',
      okLabel: 'Șterge tot',
      cancelLabel: 'Păstrează sumele',
      icon: 'trash-2'
    });
    if (alsoDelete) {
      Object.keys(state.data.cheltuieli).forEach(function(luna) {
        var m = state.data.cheltuieli[luna];
        if (m && m[cat.label] !== undefined) delete m[cat.label];
      });
    }
  }
  state.data.categoriiVar = state.data.categoriiVar.filter(function(c) { return c.id !== id; });
  saveData();
  render();
}

// ====================================================================
// CALCULATIONS
// ====================================================================
function calcMediiVenituri(d) {
  var luniCuDate = LUNI_KEYS.filter(function(l) {
    var v = d.venituri[l] || {};
    return (v.bonuri > 0 || v.bonus > 0 || v.diurna > 0);
  });
  var count = luniCuDate.length || 1;
  var bonuri = luniCuDate.reduce(function(s, l) { return s + ((d.venituri[l] || {}).bonuri || 0); }, 0) / count;
  var bonus = luniCuDate.reduce(function(s, l) { return s + ((d.venituri[l] || {}).bonus || 0); }, 0) / count;
  var diurna = luniCuDate.reduce(function(s, l) { return s + ((d.venituri[l] || {}).diurna || 0); }, 0) / count;
  var salariuNet = (d.profil && d.profil.salariuNet) ? d.profil.salariuNet : DATI_INITIALE.profil.salariuNet;
  return { salariu: salariuNet, bonuri: bonuri, bonus: bonus, diurna: diurna, total: salariuNet + bonuri + bonus + diurna };
}

function calcMediiCheltuieli(d) {
  var fixe = Array.isArray(d.cheltuieliFixe) ? d.cheltuieliFixe : [];
  var totalFixe = fixe.reduce(function(s, f) { return s + (parseRON(f.suma) || 0); }, 0);
  var variabile = LUNI_KEYS.map(function(l) { return d.cheltuieli[l] || {}; });
  var count = variabile.filter(function(v) { return Object.values(v).some(function(x) { return x > 0; }); }).length || 1;
  var cats = Array.isArray(d.categoriiVar) ? d.categoriiVar : [];
  var result = { fixe: fixe, totalFixe: totalFixe, variabile: {}, categorii: cats };
  var totalVar = 0;
  cats.forEach(function(c) {
    var label = c.label || '';
    result.variabile[label] = variabile.reduce(function(s, v) { return s + (v[label] || 0); }, 0) / count;
    totalVar += result.variabile[label];
  });
  result.total = totalFixe + totalVar;
  return result;
}

function calcLuniRamase() {
  var cr = state.data.credit;
  if (!cr || !cr.dataStart) return cr ? cr.durata : 60;
  var parts = cr.dataStart.split('-');
  var start = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
  var now = new Date();
  var luniTrecute = (now.getFullYear() - start.getFullYear()) * 12 + (now.getMonth() - start.getMonth());
  return Math.max(0, (cr.durata || 60) - luniTrecute);
}

function calcEconomieDobanda(suma, sold, dobandaAnuala, luniRamase, comisionProcent) {
  if (suma <= 0 || luniRamase <= 0) return { economie: 0, comision: 0, net: 0 };
  var dobandaLunara = dobandaAnuala / 100 / 12;
  var economieBruta = suma * dobandaLunara * (luniRamase / 2);
  var comision = suma * (comisionProcent / 100);
  return { economie: economieBruta, comision: comision, net: economieBruta - comision };
}

// ====================================================================
// RENDER: Buget Lunar (overview)
// ====================================================================
function renderBugetLunar() {
  var d = state.data;
  var mediiV = calcMediiVenituri(d);
  var mediiC = calcMediiCheltuieli(d);
  var surplus = mediiV.total - mediiC.total;

  var totalTezaur = d.tezaur.reduce(function(s, t) { return s + (parseRON(t.suma) || 0); }, 0);
  var totalFond = d.fondUrgenta.reduce(function(s, f) { return s + (parseRON(f.suma) || 0); }, 0);
  var buffer = Object.keys(d.evolutie).reduce(function(s, l) { return s + (d.evolutie[l].buffer || 0); }, 0);
  var totalActive = totalTezaur + totalFond + buffer;
  var soldCredit = d.credit.soldActual;
  var avereNeta = totalActive - soldCredit;

  var html = '';

  // STAT CARDS
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="trending-up"></i> Sumar lunar (medii)</div></div>';
  html += '<div class="stat-grid">';
  html += statCard('wallet',       'Venituri medii',  formatRON(mediiV.total),  'Salariu + bonuri + bonus + diurnă', '');
  html += statCard('trending-down','Cheltuieli medii',formatRON(mediiC.total),  'Fixe + variabile', 'danger');
  html += statCard(surplus >= 0 ? 'piggy-bank' : 'alert-triangle', 'Surplus lunar', (surplus >= 0 ? '+' : '') + formatRON(surplus), surplus >= 0 ? 'Disponibil pentru economii' : 'Deficit lunar', surplus >= 0 ? 'success' : 'danger');
  html += statCard('shield',       'Fond urgență',    formatRON(totalFond),     d.fondUrgenta.length + ' conturi', 'violet');
  html += statCard('coins',        'Tezaur investit', formatRON(totalTezaur),   d.tezaur.length + ' emisiuni', '');
  html += statCard(avereNeta >= 0 ? 'gem' : 'alert-octagon', 'Avere netă', (avereNeta >= 0 ? '+' : '') + formatRON(avereNeta), 'Active - Sold credit', avereNeta >= 0 ? 'success' : 'danger');
  html += '</div></div>';

  // BREAKDOWN VENITURI / CHELTUIELI
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="list"></i> Distribuție venituri vs cheltuieli</div></div>';
  html += '<div class="stat-grid">';

  // Venituri panel
  html += '<div class="panel">';
  html += '<div class="panel-head"><div class="panel-title"><i data-lucide="coins"></i> Venituri medii</div></div>';
  html += '<div class="stat-row"><span>Salariu net</span><span class="stat-val">' + formatRON(mediiV.salariu) + '</span></div>';
  html += '<div class="stat-row"><span>Bonuri masă</span><span class="stat-val">' + formatRON(mediiV.bonuri) + '</span></div>';
  html += '<div class="stat-row"><span>Bonus</span><span class="stat-val">' + formatRON(mediiV.bonus) + '</span></div>';
  html += '<div class="stat-row"><span>Diurnă</span><span class="stat-val">' + formatRON(mediiV.diurna) + '</span></div>';
  html += '<div class="stat-row total"><span>Total</span><span class="stat-val">' + formatRON(mediiV.total) + ' RON</span></div>';
  html += '</div>';

  // Cheltuieli panel
  html += '<div class="panel">';
  html += '<div class="panel-head"><div class="panel-title"><i data-lucide="receipt"></i> Cheltuieli medii</div></div>';
  mediiC.fixe.forEach(function(f) {
    html += '<div class="stat-row"><span>' + esc(f.label) + '</span><span class="stat-val danger">' + formatRON(f.suma) + '</span></div>';
  });
  if (mediiC.fixe.length > 0) {
    html += '<div class="stat-row" style="border-top:1px dashed var(--border); padding-top:0.5rem; margin-top:0.25rem;"><span class="text-mid">Total fixe</span><span class="stat-val danger">' + formatRON(mediiC.totalFixe) + '</span></div>';
  }
  (mediiC.categorii || []).forEach(function(c) {
    html += '<div class="stat-row"><span>' + esc(c.label) + '</span><span class="stat-val danger">' + formatRON(mediiC.variabile[c.label] || 0) + '</span></div>';
  });
  html += '<div class="stat-row total"><span>Total</span><span class="stat-val danger">' + formatRON(mediiC.total) + ' RON</span></div>';
  html += '</div>';

  html += '</div></div>';

  // INFO ROW
  html += '<div class="info-box">';
  html += '<i data-lucide="user"></i>';
  html += '<div>';
  html += '<strong>' + esc(d.profil.nume || DATI_INITIALE.profil.nume) + '</strong>';
  html += '<span class="sep">·</span>Salariu net <strong class="mono">' + formatRON(d.profil.salariuNet) + ' RON</strong>';
  html += '<span class="sep">·</span>Credit rămas <strong class="mono">' + d.credit.durata + ' luni</strong>';
  html += '<span class="sep">·</span>Start credit <strong class="mono">' + esc(d.credit.dataStart) + '</strong>';
  html += '<span class="sep">·</span>Start buget <strong class="mono">' + esc(d.profil.startMonth || '2026-05') + '</strong>';
  html += '</div></div>';

  // PROFIL PANEL (editable)
  html += '<div class="section" style="margin-top:1.5rem;">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="settings"></i> Profil</div></div>';
  html += '<div class="panel">';
  html += '<div class="profil-grid">';
  html += '  <div class="field"><label class="field-label">Nume</label>';
  html += '    <input type="text" class="input w-full" value="' + esc(d.profil.nume || '') + '" onchange="updateProfil(\'nume\', this.value)"></div>';
  html += '  <div class="field"><label class="field-label">Salariu net (RON)</label>';
  html += '    <input type="number" class="input num w-full" value="' + (d.profil.salariuNet || 0) + '" onchange="updateProfil(\'salariuNet\', this.value)"></div>';
  html += '  <div class="field"><label class="field-label">Bonus mediu (RON)</label>';
  html += '    <input type="number" class="input num w-full" value="' + (d.profil.bonusMedie || 0) + '" onchange="updateProfil(\'bonusMedie\', this.value)"></div>';
  html += '  <div class="field"><label class="field-label">Lună start buget</label>';
  html += startMonthPicker(d.profil.startMonth || '2026-05');
  html += '  </div>';
  html += '  <div class="field"><label class="field-label">Număr luni vizibile (1–120)</label>';
  html += '    <input type="number" min="1" max="120" class="input num w-full" value="' + (d.profil.numarLuni || 12) + '" onchange="updateProfil(\'numarLuni\', this.value)"></div>';
  html += '</div>';
  html += '<div class="info-box" style="margin-top:0.85rem;">';
  html += '<i data-lucide="info"></i>';
  html += '<div>Bugetul afișează N luni consecutive începând cu luna selectată. Treci peste 12 ca să vezi anul viitor; valorile cu an diferit primesc suffix (ex: <span class="mono">Ian \'27</span>).</div>';
  html += '</div>';
  html += '</div></div>';

  // CHELTUIELI FIXE PANEL (editable list)
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="repeat"></i> Cheltuieli fixe lunare</div>';
  html += '  <button class="btn-add" onclick="addCheltuialaFixa()"><i data-lucide="plus"></i> Adaugă</button>';
  html += '</div>';
  html += '<div class="panel">';
  if (!d.cheltuieliFixe || d.cheltuieliFixe.length === 0) {
    html += '<div class="audit-empty">Nicio cheltuială fixă. Apasă "Adaugă" pentru a introduce chirie, abonamente, rate, etc.</div>';
  } else {
    html += '<div class="table-wrap"><table>';
    html += '<thead><tr><th>Denumire</th><th class="num">Sumă (RON / lună)</th><th></th></tr></thead><tbody>';
    d.cheltuieliFixe.forEach(function(f) {
      html += '<tr>';
      html += '<td><input type="text" class="input w-full" value="' + esc(f.label || '') + '" placeholder="Ex: Netflix, Card credit..." onchange="updateCheltuialaFixa(' + f.id + ', \'label\', this.value)"></td>';
      html += '<td class="num"><input type="number" class="input num w-28" value="' + (f.suma || 0) + '" onchange="updateCheltuialaFixa(' + f.id + ', \'suma\', this.value)"></td>';
      html += '<td><button class="btn-del" onclick="removeCheltuialaFixa(' + f.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
      html += '</tr>';
    });
    var totalFixe = d.cheltuieliFixe.reduce(function(s, f) { return s + (parseRON(f.suma) || 0); }, 0);
    html += '</tbody><tfoot><tr><td>Total cheltuieli fixe</td><td class="num">' + formatRON(totalFixe) + '</td><td></td></tr></tfoot>';
    html += '</table></div>';
  }
  html += '</div></div>';

  // CATEGORII CHELTUIELI VARIABILE PANEL
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="tag"></i> Categorii cheltuieli variabile</div>';
  html += '  <button class="btn-add" onclick="addCategorie()"><i data-lucide="plus"></i> Adaugă categorie</button>';
  html += '</div>';
  html += '<div class="panel">';
  if (!d.categoriiVar || d.categoriiVar.length === 0) {
    html += '<div class="audit-empty">Nicio categorie. Apasă "Adaugă" pentru a defini categorii (Alimente, Facturi, Cadouri, etc.).</div>';
  } else {
    html += '<div class="table-wrap"><table>';
    html += '<thead><tr><th>Denumire categorie</th><th class="num">Total mediu / lună</th><th></th></tr></thead><tbody>';
    var medii = calcMediiCheltuieli(d);
    d.categoriiVar.forEach(function(c) {
      var avg = medii.variabile[c.label] || 0;
      html += '<tr>';
      html += '<td><input type="text" class="input w-full" value="' + esc(c.label || '') + '" placeholder="Ex: Cadouri, Masina..." onchange="updateCategorie(' + c.id + ', this.value)"></td>';
      html += '<td class="num mono text-mid">' + formatRON(avg) + '</td>';
      html += '<td><button class="btn-del" onclick="removeCategorie(' + c.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += '<div class="info-box" style="margin-top:0.85rem;">';
    html += '<i data-lucide="info"></i>';
    html += '<div>Categoriile apar ca rânduri în tabelul "Cheltuieli lunare". La ștergerea unei categorii primești opțiunea să păstrezi sau să elimini și sumele introduse pentru ea.</div>';
    html += '</div>';
  }
  html += '</div></div>';

  return html;
}

function startMonthPicker(current) {
  var parts = String(current || '2026-05').split('-');
  var curY = parseInt(parts[0], 10) || 2026;
  var curM = parseInt(parts[1], 10) || 5;
  var thisYear = new Date().getFullYear();
  var minY = Math.min(curY, thisYear - 1);
  var maxY = Math.max(curY + 2, thisYear + 2);
  var monthOpts = '';
  for (var m = 1; m <= 12; m++) {
    monthOpts += '<option value="' + m + '"' + (m === curM ? ' selected' : '') + '>' + LUNI_LABELS_RO[m-1] + '</option>';
  }
  var yearOpts = '';
  for (var y = minY; y <= maxY; y++) {
    yearOpts += '<option value="' + y + '"' + (y === curY ? ' selected' : '') + '>' + y + '</option>';
  }
  return '<div style="display:flex;gap:0.4rem;">' +
    '<select class="select cs-enhance" data-sm-part="month" onchange="onStartMonthChange()">' + monthOpts + '</select>' +
    '<select class="select cs-enhance" data-sm-part="year" onchange="onStartMonthChange()">' + yearOpts + '</select>' +
    '</div>';
}

function onStartMonthChange() {
  var monthSel = document.querySelector('select[data-sm-part="month"]');
  var yearSel = document.querySelector('select[data-sm-part="year"]');
  if (!monthSel || !yearSel) return;
  var m = parseInt(monthSel.value, 10);
  var y = parseInt(yearSel.value, 10);
  var sm = y + '-' + (m < 10 ? '0' : '') + m;
  updateProfil('startMonth', sm);
}

function statCard(icon, label, value, sub, variant) {
  var v = variant ? ' ' + variant : '';
  return '<div class="stat-card' + v + '">' +
    '<div class="stat-label"><i data-lucide="' + icon + '"></i> ' + esc(label) + '</div>' +
    '<div class="stat-value">' + value + '</div>' +
    (sub ? '<div class="stat-sub">' + esc(sub) + '</div>' : '') +
    '</div>';
}

// ====================================================================
// RENDER: Credite
// ====================================================================
function renderCredite() {
  var d = state.data;
  var cr = d.credit;

  var html = '';

  // Two-column: details + simulare
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="landmark"></i> Credit activ</div></div>';
  html += '<div class="stat-grid" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));">';

  // Detalii
  html += '<div class="panel danger">';
  html += '<div class="panel-head"><div class="panel-title"><i data-lucide="file-text"></i> Detalii credit</div></div>';
  html += '<div class="stat-row"><span>Sumă inițială</span><span class="stat-val danger">' + formatRON(cr.suma) + '</span></div>';
  html += '<div class="stat-row"><span>Sold actual</span>';
  html += '<input type="number" class="input num w-28" value="' + cr.soldActual + '" onchange="updateCreditSold(this.value)"></div>';
  html += '<div class="stat-row"><span>Dobândă anuală</span><span class="mono">' + cr.dobanda + ' %</span></div>';
  html += '<div class="stat-row"><span>DAE</span><span class="mono">' + cr.dae + ' %</span></div>';
  html += '<div class="stat-row"><span>Rată lunară</span><span class="stat-val danger">' + formatRON(cr.rata) + '</span></div>';
  html += '<div class="stat-row"><span>Asigurare</span><span class="stat-val danger">' + formatRON(cr.asigurare) + '</span></div>';
  html += '<div class="stat-row"><span>Comision rambursare</span><span class="mono">' + cr.comisionRambursare + ' %</span></div>';
  html += '<div class="stat-row"><span>Durată rămasă</span><span class="mono">' + cr.durata + ' luni</span></div>';
  html += '<div class="stat-row"><span>Data start</span><span class="mono">' + esc(cr.dataStart) + '</span></div>';
  html += '</div>';

  // Simulare
  html += '<div class="panel accent">';
  html += '<div class="panel-head"><div class="panel-title"><i data-lucide="calculator"></i> Simulare rambursare anticipată</div></div>';
  html += '<div class="field"><label class="field-label">Sold credit curent (RON)</label>';
  html += '<input type="number" id="sim-sold" class="input num w-full" value="' + cr.soldActual + '" oninput="recalcSimulare()"></div>';
  html += '<div class="field"><label class="field-label">Sumă rambursare (RON)</label>';
  html += '<input type="number" id="sim-suma" class="input num w-full" value="5000" oninput="recalcSimulare()"></div>';
  html += '<div class="field"><label class="field-label">Luni rămase</label>';
  html += '<input type="number" id="sim-luni" class="input num w-full" value="' + calcLuniRamase() + '" oninput="recalcSimulare()"></div>';
  html += '<div id="sim-rezultat" class="sim-result"></div>';
  html += '</div>';

  html += '</div></div>';

  // Evoluție sold credit
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="trending-down"></i> Evoluție sold credit (estimare)</div></div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Lună</th><th class="num">Sold inițial</th><th class="num">Rată</th><th class="num">Dobândă</th><th class="num">Sold final</th></tr></thead><tbody>';

  var soldCurent = cr.soldActual;
  var rataLunara = cr.rata;
  for (var i = 0; i < 6 && i < LUNI_KEYS.length; i++) {
    var l = LUNI_KEYS[i];
    var dobanda = soldCurent * (cr.dobanda / 100 / 12);
    var principal = rataLunara - dobanda;
    var soldFinal = Math.max(0, soldCurent - principal);
    var evol = d.evolutie[l] || {};
    var displaySold = evol.soldCredit || soldFinal;
    html += '<tr>';
    html += '<td class="muted">' + LUNI[i] + '</td>';
    html += '<td class="num">' + formatRON(soldCurent) + '</td>';
    html += '<td class="num neg">' + formatRON(rataLunara) + '</td>';
    html += '<td class="num neg">' + formatRON(dobanda) + '</td>';
    html += '<td class="num accent">' + formatRON(displaySold) + '</td>';
    html += '</tr>';
    soldCurent = soldFinal;
  }
  html += '</tbody></table></div></div></div>';

  // Sold credit pe luni (input)
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="calendar"></i> Sold credit înregistrat lunar</div></div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Activ</th>';
  LUNI.forEach(function(l) { html += '<th class="num">' + l + '</th>'; });
  html += '</tr></thead><tbody>';
  html += '<tr><td class="muted">Sold credit</td>';
  LUNI_KEYS.forEach(function(l) {
    var val = (d.evolutie[l] || {}).soldCredit || '';
    html += '<td class="num"><input type="number" class="input num w-20" value="' + val + '" onchange="updateEvolutie(\'' + l + '\', \'soldCredit\', this.value)"></td>';
  });
  html += '</tr></tbody></table></div></div></div>';

  return html;
}

function updateCreditSold(val) {
  state.data.credit.soldActual = parseRON(val);
  saveData();
  render();
}
function updateEvolutie(luna, field, val) {
  if (!state.data.evolutie[luna]) state.data.evolutie[luna] = {};
  state.data.evolutie[luna][field] = parseRON(val);
  saveData();
}

function recalcSimulare() {
  var suma = parseRON((document.getElementById('sim-suma') || {}).value || '0');
  var sold = parseRON((document.getElementById('sim-sold') || {}).value || '0');
  var luni = parseInt((document.getElementById('sim-luni') || {}).value || '0', 10);
  var cr = state.data.credit;
  var r = calcEconomieDobanda(suma, sold, cr.dobanda, luni, cr.comisionRambursare);
  var el = document.getElementById('sim-rezultat');
  if (!el) return;
  var html = '';
  html += '<div><strong>Economie dobândă:</strong> <span class="mono">' + formatRON(r.economie) + ' RON</span></div>';
  html += '<div><strong>Comision rambursare (' + cr.comisionRambursare + '%):</strong> <span class="mono">' + formatRON(r.comision) + ' RON</span></div>';
  html += '<div style="margin-top:0.4rem;"><span class="' + (r.net >= 0 ? 'pos' : 'neg') + '">Economie netă: <span class="mono">' + formatRON(r.net) + ' RON</span></span></div>';
  if (suma > sold) {
    html += '<div class="callout" style="margin-top:0.6rem;"><i data-lucide="alert-triangle"></i> Suma depășește soldul actual.</div>';
  } else if (suma > 0) {
    html += '<div style="margin-top:0.4rem;font-size:0.78rem;color:var(--text-mid);">Sold după rambursare: <span class="mono">' + formatRON(sold - suma) + ' RON</span></div>';
  }
  el.innerHTML = html;
  refreshIcons();
}

// ====================================================================
// RENDER: Fond Urgență
// ====================================================================
function renderFondUrgenta() {
  var d = state.data;
  var html = '';

  // Fond Urgență table
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '<div class="section-title-left"><i data-lucide="shield"></i> Fond de urgență</div>';
  html += '<button class="btn-add" onclick="addFond()"><i data-lucide="plus"></i> Adaugă cont</button>';
  html += '</div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Cont</th><th class="num">Sumă</th><th class="num">Dobândă %</th><th class="num">Dobândă anuală</th><th>Lichid</th><th>Notă</th><th></th></tr></thead><tbody>';

  d.fondUrgenta.forEach(function(f) {
    var suma = parseRON(f.suma) || 0;
    var dobanda = parseRON(f.dobanda) || 0;
    var dobAnuala = suma * dobanda / 100;
    html += '<tr>';
    html += '<td><input type="text" class="input w-40" value="' + esc(f.cont) + '" onchange="updateFond(' + f.id + ', \'cont\', this.value)"></td>';
    html += '<td class="num"><input type="number" class="input num w-28" value="' + f.suma + '" onchange="updateFond(' + f.id + ', \'suma\', this.value)"></td>';
    html += '<td class="num"><input type="number" step="0.01" class="input num w-20" value="' + f.dobanda + '" onchange="updateFond(' + f.id + ', \'dobanda\', this.value)"></td>';
    html += '<td class="num accent">' + formatRON(dobAnuala) + '</td>';
    html += '<td><select class="select cs-enhance" onchange="updateFond(' + f.id + ', \'lichid\', this.value)">';
    ['Da', 'Nu', 'Parțial'].forEach(function(opt) {
      html += '<option value="' + opt + '"' + (f.lichid === opt ? ' selected' : '') + '>' + opt + '</option>';
    });
    html += '</select></td>';
    html += '<td><input type="text" class="input w-32" value="' + esc(f.nota || '') + '" onchange="updateFond(' + f.id + ', \'nota\', this.value)"></td>';
    html += '<td><button class="btn-del" onclick="removeFond(' + f.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
    html += '</tr>';
  });

  var totalFond = d.fondUrgenta.reduce(function(s, f) { return s + (parseRON(f.suma) || 0); }, 0);
  var totalDob = d.fondUrgenta.reduce(function(s, f) { return s + (parseRON(f.suma) || 0) * (parseRON(f.dobanda) || 0) / 100; }, 0);
  html += '</tbody><tfoot>';
  html += '<tr><td>Total fond urgență</td>';
  html += '<td class="num">' + formatRON(totalFond) + '</td>';
  html += '<td></td>';
  html += '<td class="num">+' + formatRON(totalDob) + ' / an</td>';
  html += '<td colspan="3"></td></tr>';
  html += '</tfoot></table></div></div></div>';

  // Tezaur
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '<div class="section-title-left"><i data-lucide="coins"></i> Titluri de stat Tezaur</div>';
  html += '<button class="btn-add" onclick="addTezaur()"><i data-lucide="plus"></i> Adaugă subscriere</button>';
  html += '</div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Emisiune</th><th>Data subsc.</th><th class="num">Sumă</th><th class="num">Dobândă %</th><th>Maturitate</th><th>Data scad.</th><th class="num">Dobândă câștigată</th><th class="num">Total</th><th></th></tr></thead><tbody>';

  d.tezaur.forEach(function(t) {
    var suma = parseRON(t.suma) || 0;
    var dobPct = parseRON(t.dobanda) || 0;
    var dobCistigata = suma * dobPct / 100;
    var total = suma + dobCistigata;
    html += '<tr>';
    html += '<td><select class="select cs-enhance" onchange="updateTezaur(' + t.id + ', \'emisiune\', this.value)">';
    ['Tezaur 1 an','Tezaur 3 ani','Tezaur 5 ani','Fidelis RON','Fidelis EUR'].forEach(function(opt) {
      html += '<option value="' + opt + '"' + (t.emisiune === opt ? ' selected' : '') + '>' + opt + '</option>';
    });
    html += '</select></td>';
    html += '<td><input type="text" class="input fp-date w-32" value="' + esc(t.dataSubscriere || '') + '" placeholder="YYYY-MM-DD" onchange="updateTezaur(' + t.id + ', \'dataSubscriere\', this.value)"></td>';
    html += '<td class="num"><input type="number" class="input num w-28" value="' + t.suma + '" onchange="updateTezaur(' + t.id + ', \'suma\', this.value)"></td>';
    html += '<td class="num"><input type="number" step="0.01" class="input num w-20" value="' + t.dobanda + '" onchange="updateTezaur(' + t.id + ', \'dobanda\', this.value)"></td>';
    html += '<td><select class="select cs-enhance" onchange="updateTezaur(' + t.id + ', \'maturitate\', this.value)">';
    ['1 an','3 ani','5 ani'].forEach(function(opt) {
      html += '<option value="' + opt + '"' + (t.maturitate === opt ? ' selected' : '') + '>' + opt + '</option>';
    });
    html += '</select></td>';
    html += '<td><input type="text" class="input fp-date w-32" value="' + esc(t.dataScadenta || '') + '" placeholder="YYYY-MM-DD" onchange="updateTezaur(' + t.id + ', \'dataScadenta\', this.value)"></td>';
    html += '<td class="num accent">' + formatRON(dobCistigata) + '</td>';
    html += '<td class="num accent">' + formatRON(total) + '</td>';
    html += '<td><button class="btn-del" onclick="removeTezaur(' + t.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
    html += '</tr>';
  });

  var totalTez = d.tezaur.reduce(function(s, t) { return s + (parseRON(t.suma) || 0); }, 0);
  var totalDobTez = d.tezaur.reduce(function(s, t) { return s + (parseRON(t.suma) || 0) * (parseRON(t.dobanda) || 0) / 100; }, 0);
  html += '</tbody><tfoot>';
  html += '<tr><td colspan="2">Total Tezaur investit</td>';
  html += '<td class="num">' + formatRON(totalTez) + '</td>';
  html += '<td colspan="3"></td>';
  html += '<td class="num">+' + formatRON(totalDobTez) + ' / an</td>';
  html += '<td colspan="2"></td></tr>';
  html += '</tfoot></table></div></div></div>';

  // Evoluție lunară active
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="line-chart"></i> Evoluție lunară active</div></div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Activ</th>';
  LUNI.forEach(function(l) { html += '<th class="num">' + l + '</th>'; });
  html += '</tr></thead><tbody>';

  var campuri = [
    { key: 'fondUrgenta', label: 'Fond urgență' },
    { key: 'tezaur', label: 'Tezaur investit' },
    { key: 'buffer', label: 'Buffer cont curent' },
  ];
  campuri.forEach(function(c) {
    html += '<tr><td class="muted">' + c.label + '</td>';
    LUNI_KEYS.forEach(function(l) {
      var val = (d.evolutie[l] || {})[c.key] || '';
      html += '<td class="num"><input type="number" class="input num w-20" value="' + val + '" onchange="updateEvolutie(\'' + l + '\', \'' + c.key + '\', this.value)"></td>';
    });
    html += '</tr>';
  });

  // Total active per luna
  html += '<tr class="total"><td>Total active</td>';
  LUNI_KEYS.forEach(function(l) {
    var e = d.evolutie[l] || {};
    var total = (e.fondUrgenta || 0) + (e.tezaur || 0) + (e.buffer || 0);
    html += '<td class="num">' + formatRON(total) + '</td>';
  });
  html += '</tr>';

  // Avere netă per luna
  html += '<tr class="total-strong"><td>Avere netă</td>';
  LUNI_KEYS.forEach(function(l) {
    var e = d.evolutie[l] || {};
    var active = (e.fondUrgenta || 0) + (e.tezaur || 0) + (e.buffer || 0);
    var an = active - (e.soldCredit || 0);
    html += '<td class="num ' + (an >= 0 ? 'pos' : 'neg') + '">' + formatRON(an) + '</td>';
  });
  html += '</tr>';

  html += '</tbody></table></div></div></div>';

  return html;
}

function addFond() {
  state.data.fondUrgenta.push({ id: getNextId(state.data.fondUrgenta), cont: '', suma: '', dobanda: '', lichid: 'Da', nota: '' });
  saveData();
  render();
}
function updateFond(id, field, value) {
  state.data.fondUrgenta = state.data.fondUrgenta.map(function(f) {
    if (f.id !== id) return f;
    var u = cloneObj(f);
    if (field === 'suma' || field === 'dobanda') u[field] = parseRON(value);
    else u[field] = value;
    return u;
  });
  saveData();
  render();
}
function removeFond(id) {
  state.data.fondUrgenta = state.data.fondUrgenta.filter(function(f) { return f.id !== id; });
  saveData();
  render();
}
function addTezaur() {
  state.data.tezaur.push({ id: getNextId(state.data.tezaur), emisiune: 'Tezaur 1 an', dataSubscriere: '', suma: '', dobanda: 6.30, maturitate: '1 an', dataScadenta: '' });
  saveData();
  render();
}
function updateTezaur(id, field, value) {
  state.data.tezaur = state.data.tezaur.map(function(t) {
    if (t.id !== id) return t;
    var u = cloneObj(t);
    if (field === 'suma' || field === 'dobanda') u[field] = parseRON(value);
    else u[field] = value;
    return u;
  });
  saveData();
  render();
}
function removeTezaur(id) {
  state.data.tezaur = state.data.tezaur.filter(function(t) { return t.id !== id; });
  saveData();
  render();
}

// ====================================================================
// RENDER: Venituri & Cheltuieli (lunar table)
// ====================================================================
function renderVenituri() {
  var d = state.data;
  var html = '';

  // Venituri
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="coins"></i> Venituri lunare</div></div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Categorie</th>';
  LUNI.forEach(function(l) { html += '<th class="num">' + l + '</th>'; });
  html += '</tr></thead><tbody>';

  var salariu = d.profil.salariuNet || 0;
  html += '<tr class="fixed"><td>Salariu net</td>';
  LUNI.forEach(function() { html += '<td class="num accent">' + formatRON(salariu) + '</td>'; });
  html += '</tr>';

  var cats = [
    { key: 'bonuri', label: 'Bonuri masă' },
    { key: 'bonus', label: 'Bonus' },
    { key: 'diurna', label: 'Diurnă' },
  ];
  cats.forEach(function(c) {
    html += '<tr><td class="muted">' + c.label + '</td>';
    LUNI_KEYS.forEach(function(l) {
      var val = (d.venituri[l] || {})[c.key] || '';
      html += '<td class="num"><input type="number" class="input num w-20" value="' + val + '" onchange="updateVenit(\'' + l + '\', \'' + c.key + '\', this.value)"></td>';
    });
    html += '</tr>';
  });

  var totalsV = LUNI_KEYS.map(function(l) {
    var v = d.venituri[l] || {};
    return salariu + (v.bonuri || 0) + (v.bonus || 0) + (v.diurna || 0);
  });
  html += '<tr class="total"><td>Total venituri</td>';
  totalsV.forEach(function(t) { html += '<td class="num">' + formatRON(t) + '</td>'; });
  html += '</tr>';

  html += '</tbody></table></div></div></div>';

  // Cheltuieli
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="receipt"></i> Cheltuieli lunare</div></div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Categorie</th>';
  LUNI.forEach(function(l) { html += '<th class="num">' + l + '</th>'; });
  html += '</tr></thead><tbody>';

  (d.cheltuieliFixe || []).forEach(function(f) {
    html += '<tr class="fixed"><td>' + esc(f.label || '—') + '</td>';
    LUNI.forEach(function() { html += '<td class="num neg">' + formatRON(f.suma) + '</td>'; });
    html += '</tr>';
  });

  (d.categoriiVar || []).forEach(function(c) {
    var label = c.label || '';
    var labelAttr = label.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    html += '<tr><td class="muted">' + esc(label) + '</td>';
    LUNI_KEYS.forEach(function(l) {
      var val = (d.cheltuieli[l] || {})[label] || '';
      html += '<td class="num"><input type="number" class="input num w-20" value="' + val + '" onchange="updateCheltuiala(\'' + l + '\', \'' + labelAttr + '\', this.value)"></td>';
    });
    html += '</tr>';
  });

  var totalFixeLunare = (d.cheltuieliFixe || []).reduce(function(s, f) { return s + (parseRON(f.suma) || 0); }, 0);
  var totalsC = LUNI_KEYS.map(function(l) {
    var c = d.cheltuieli[l] || {};
    return totalFixeLunare + Object.values(c).reduce(function(s, v) { return s + v; }, 0);
  });
  html += '<tr class="total danger"><td>Total cheltuieli</td>';
  totalsC.forEach(function(t) { html += '<td class="num">' + formatRON(t) + '</td>'; });
  html += '</tr>';

  var surplus = LUNI_KEYS.map(function(_, i) { return totalsV[i] - totalsC[i]; });
  html += '<tr class="total-strong"><td>Surplus / deficit</td>';
  surplus.forEach(function(t) { html += '<td class="num ' + (t >= 0 ? 'pos' : 'neg') + '">' + formatRON(t) + '</td>'; });
  html += '</tr>';

  html += '</tbody></table></div></div></div>';

  return html;
}

function updateVenit(luna, camp, val) {
  if (!state.data.venituri[luna]) state.data.venituri[luna] = {};
  state.data.venituri[luna][camp] = parseRON(val);
  saveData();
  render();
}
function updateCheltuiala(luna, categorie, val) {
  if (!state.data.cheltuieli[luna]) state.data.cheltuieli[luna] = {};
  state.data.cheltuieli[luna][categorie] = parseRON(val);
  saveData();
  render();
}

// ====================================================================
// MAIN RENDER
// ====================================================================
function render() {
  var tabs = [
    { id: 'buget-lunar',  label: 'Buget lunar',  icon: 'bar-chart-3' },
    { id: 'credite',      label: 'Credite',      icon: 'landmark' },
    { id: 'fond-urgenta', label: 'Fond urgență', icon: 'shield' },
    { id: 'venituri',     label: 'Venituri',     icon: 'coins' },
  ];

  var tabContent = {
    'buget-lunar': renderBugetLunar,
    'credite': renderCredite,
    'fond-urgenta': renderFondUrgenta,
    'venituri': renderVenituri,
  };

  var theme = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
  var themeIcon = theme === 'dark' ? 'sun' : 'moon';

  var html = '';
  // HEADER
  html += '<div class="app-header">';
  html += '  <div class="header-inner">';
  html += '    <div class="header-left">';
  html += '      <a class="btn-back" href="/" title="Înapoi la Dashboard"><i data-lucide="arrow-left"></i> Dashboard</a>';
  html += '      <div class="header-brand">';
  html += '        <div class="header-title"><i data-lucide="wallet"></i> Budget Tracker</div>';
  html += '        <div class="header-sub">Ion · RON · 2026</div>';
  html += '      </div>';
  html += '    </div>';
  html += '    <div class="header-actions">';
  html += '      <span id="save-status" class="save-chip"><i data-lucide="cloud-check"></i> Salvat</span>';
  html += '      <button class="icon-btn" onclick="showAudit()" title="Istoric modificări"><i data-lucide="history"></i></button>';
  html += '      <button class="icon-btn" onclick="exportCSV()" title="Export CSV"><i data-lucide="download"></i></button>';
  html += '      <button class="icon-btn" onclick="toggleTheme()" title="Comută tema"><i data-lucide="' + themeIcon + '"></i></button>';
  html += '      <button class="icon-btn danger" onclick="resetData()" title="Resetează date"><i data-lucide="rotate-ccw"></i></button>';
  html += '      <a class="icon-btn danger" href="/logout" title="Ieșire"><i data-lucide="log-out"></i></a>';
  html += '    </div>';
  html += '  </div>';
  html += '</div>';

  // TABS
  html += '<div class="tabs-wrap"><div class="tabs">';
  tabs.forEach(function(t) {
    var active = state.activeTab === t.id ? ' active' : '';
    html += '<button class="tab' + active + '" onclick="switchTab(\'' + t.id + '\')"><i data-lucide="' + t.icon + '"></i> ' + t.label + '</button>';
  });
  html += '</div></div>';

  // MAIN
  html += '<div class="main">';
  var fn = tabContent[state.activeTab];
  html += fn ? fn() : '';
  html += '</div>';

  var savedScroll = window.scrollY;
  document.getElementById('app').innerHTML = html;
  applyEnhancements();
  window.scrollTo(0, savedScroll);
}

function switchTab(tabId) {
  state.activeTab = tabId;
  render();
  // recalc simulation if on Credite
  if (tabId === 'credite') setTimeout(recalcSimulare, 0);
}

// ====================================================================
// EXPORT CSV
// ====================================================================
function exportCSV() {
  var d = state.data;
  var lines = [];
  lines.push('Budget Tracker - Ion - Export CSV');

  lines.push('');
  lines.push('VENITURI');
  lines.push('Categorie,' + LUNI.join(','));
  lines.push('Salariu net,' + LUNI.map(function() { return d.profil.salariuNet || 0; }).join(','));
  lines.push('Bonuri de masa,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).bonuri || 0; }).join(','));
  lines.push('Bonus,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).bonus || 0; }).join(','));
  lines.push('Diurna,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).diurna || 0; }).join(','));

  lines.push('');
  lines.push('CHELTUIELI');
  lines.push('Categorie,' + LUNI.join(','));
  (d.cheltuieliFixe || []).forEach(function(f) {
    lines.push((f.label || '').replace(/,/g, ' ') + ',' + LUNI.map(function() { return f.suma; }).join(','));
  });
  (d.categoriiVar || []).forEach(function(c) {
    var label = c.label || '';
    lines.push(label.replace(/,/g, ' ') + ',' + LUNI_KEYS.map(function(l) { return (d.cheltuieli[l] || {})[label] || 0; }).join(','));
  });

  lines.push('');
  lines.push('FOND URGENTA');
  lines.push('Cont,Suma,Dobanda,Lichid,Nota');
  d.fondUrgenta.forEach(function(f) {
    lines.push((f.cont || '') + ',' + (f.suma || 0) + ',' + (f.dobanda || 0) + ',' + (f.lichid || '') + ',' + (f.nota || ''));
  });

  lines.push('');
  lines.push('TEZAUR');
  lines.push('Emisiune,DataSubscriere,Suma,Dobanda,Maturitate,DataScadenta');
  d.tezaur.forEach(function(t) {
    lines.push((t.emisiune || '') + ',' + (t.dataSubscriere || '') + ',' + (t.suma || 0) + ',' + (t.dobanda || 0) + ',' + (t.maturitate || '') + ',' + (t.dataScadenta || ''));
  });

  var blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'budget-tracker-ion.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ====================================================================
// BOOT
// ====================================================================
async function init() {
  await loadData();
  refreshLuni();
  render();
  if (state.activeTab === 'credite') setTimeout(recalcSimulare, 0);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
