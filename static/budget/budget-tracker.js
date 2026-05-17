// ====================================================================
// Budget Tracker - Vanilla JS (PIF design system)
// ====================================================================

const LUNI = ['Mai', 'Iun', 'Iul', 'Aug', 'Sep', 'Oct', 'Noi', 'Dec'];
const LUNI_KEYS = ['mai', 'iun', 'iul', 'aug', 'sep', 'oct', 'noi', 'dec'];
const CHELTUIELI_VARIABILE = ['Alimente', 'Facturi', 'Transport', 'Sănătate', 'Îmbrăcăminte', 'Divertisment', 'Abonamente', 'Alte'];

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
  profil: { nume: 'Ion', salariuNet: 7000, bonusMedie: 2000 },
  cheltuieliFixe: { chirie: 2000, rataCredit: 1934 },
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
    mai: { fondUrgenta: 14000, tezaur: 5000, buffer: 3450, soldCredit: 84450 },
  },
  venituri: {
    mai: { bonuri: 360, bonus: 1750, diurna: 1200 },
    iun: {}, iul: {}, aug: {}, sep: {}, oct: {}, noi: {}, dec: {}
  },
  cheltuieli: {
    mai: { 'Sănătate': 200 },
    iun: {}, iul: {}, aug: {}, sep: {}, oct: {}, noi: {}, dec: {}
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
      LUNI_KEYS.forEach(function(l) {
        if (!state.data.venituri[l]) state.data.venituri[l] = {};
        if (!state.data.cheltuieli[l]) state.data.cheltuieli[l] = {};
      });
      if (!state.data.fondUrgenta) state.data.fondUrgenta = [];
      if (!state.data.tezaur) state.data.tezaur = [];
      if (!state.data.evolutie) state.data.evolutie = {};
      if (!state.data.profil) state.data.profil = cloneObj(DATI_INITIALE.profil);
      if (!state.data.credit) state.data.credit = cloneObj(DATI_INITIALE.credit);
      if (!state.data.credit.durata) state.data.credit.durata = DATI_INITIALE.credit.durata;
      if (!state.data.credit.dataStart) state.data.credit.dataStart = DATI_INITIALE.credit.dataStart;
      if (!state.data.credit.dobanda) state.data.credit.dobanda = DATI_INITIALE.credit.dobanda;
      if (!state.data.credit.soldActual) state.data.credit.soldActual = DATI_INITIALE.credit.soldActual;
      if (!state.data.credit.suma) state.data.credit.suma = DATI_INITIALE.credit.suma;
    } else {
      state.data = cloneObj(INITIAL_DATA);
      await saveDataNow();
    }
  } catch(e) {
    console.error('Load failed, using initial data:', e);
    state.data = cloneObj(INITIAL_DATA);
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
  await saveDataNow();
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
  var fixe = d.cheltuieliFixe;
  var variabile = LUNI_KEYS.map(function(l) { return d.cheltuieli[l] || {}; });
  var count = variabile.filter(function(v) { return Object.values(v).some(function(x) { return x > 0; }); }).length || 1;
  var result = { chirie: fixe.chirie, rataCredit: fixe.rataCredit };
  var totalVar = 0;
  CHELTUIELI_VARIABILE.forEach(function(cat) {
    result[cat] = variabile.reduce(function(s, v) { return s + (v[cat] || 0); }, 0) / count;
    totalVar += result[cat];
  });
  result.total = fixe.chirie + fixe.rataCredit + totalVar;
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
  html += '<div class="stat-row"><span>Chirie</span><span class="stat-val danger">' + formatRON(mediiC.chirie) + '</span></div>';
  html += '<div class="stat-row"><span>Rată credit</span><span class="stat-val danger">' + formatRON(mediiC.rataCredit) + '</span></div>';
  CHELTUIELI_VARIABILE.forEach(function(cat) {
    html += '<div class="stat-row"><span>' + esc(cat) + '</span><span class="stat-val danger">' + formatRON(mediiC[cat] || 0) + '</span></div>';
  });
  html += '<div class="stat-row total"><span>Total</span><span class="stat-val danger">' + formatRON(mediiC.total) + ' RON</span></div>';
  html += '</div>';

  html += '</div></div>';

  // INFO ROW
  html += '<div class="info-box">';
  html += '<i data-lucide="user"></i>';
  html += '<div>';
  html += '<strong>' + esc(d.profil ? d.profil.nume : DATI_INITIALE.profil.nume) + '</strong>';
  html += '<span class="sep">·</span>Salariu net <strong class="mono">' + formatRON(DATI_INITIALE.profil.salariuNet) + ' RON</strong>';
  html += '<span class="sep">·</span>Credit rămas <strong class="mono">' + d.credit.durata + ' luni</strong>';
  html += '<span class="sep">·</span>Start <strong class="mono">' + esc(d.credit.dataStart) + '</strong>';
  html += '</div></div>';

  return html;
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

  html += '<tr class="fixed"><td>Salariu net</td>';
  LUNI.forEach(function() { html += '<td class="num accent">7.000,00</td>'; });
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
    return 7000 + (v.bonuri || 0) + (v.bonus || 0) + (v.diurna || 0);
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

  html += '<tr class="fixed"><td>Chirie</td>';
  LUNI.forEach(function() { html += '<td class="num neg">2.000,00</td>'; });
  html += '</tr>';
  html += '<tr class="fixed"><td>Rată credit + asig.</td>';
  LUNI.forEach(function() { html += '<td class="num neg">' + formatRON(d.cheltuieliFixe.rataCredit) + '</td>'; });
  html += '</tr>';

  CHELTUIELI_VARIABILE.forEach(function(cat) {
    html += '<tr><td class="muted">' + esc(cat) + '</td>';
    LUNI_KEYS.forEach(function(l) {
      var val = (d.cheltuieli[l] || {})[cat] || '';
      html += '<td class="num"><input type="number" class="input num w-20" value="' + val + '" onchange="updateCheltuiala(\'' + l + '\', \'' + esc(cat) + '\', this.value)"></td>';
    });
    html += '</tr>';
  });

  var totalsC = LUNI_KEYS.map(function(l) {
    var c = d.cheltuieli[l] || {};
    return d.cheltuieliFixe.chirie + d.cheltuieliFixe.rataCredit + Object.values(c).reduce(function(s, v) { return s + v; }, 0);
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

  document.getElementById('app').innerHTML = html;
  applyEnhancements();
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
  lines.push('Salariu net,' + LUNI.map(function() { return '7000'; }).join(','));
  lines.push('Bonuri de masa,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).bonuri || 0; }).join(','));
  lines.push('Bonus,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).bonus || 0; }).join(','));
  lines.push('Diurna,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).diurna || 0; }).join(','));

  lines.push('');
  lines.push('CHELTUIELI');
  lines.push('Categorie,' + LUNI.join(','));
  lines.push('Chirie,' + LUNI.map(function() { return '2000'; }).join(','));
  lines.push('Rata credit,' + LUNI.map(function() { return d.cheltuieliFixe.rataCredit; }).join(','));
  CHELTUIELI_VARIABILE.forEach(function(cat) {
    lines.push(cat + ',' + LUNI_KEYS.map(function(l) { return (d.cheltuieli[l] || {})[cat] || 0; }).join(','));
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
  render();
  if (state.activeTab === 'credite') setTimeout(recalcSimulare, 0);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
