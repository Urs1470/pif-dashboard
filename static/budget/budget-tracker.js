// ====================================================================
// Budget Tracker - Vanilla JS (no framework, no JSX, no CDN)
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
  credit: {
    dobanda: DATI_INITIALE.credit.dobanda,
    dae: DATI_INITIALE.credit.dae,
    rata: DATI_INITIALE.credit.rata,
    asigurare: DATI_INITIALE.credit.asigurare,
    comisionRambursare: DATI_INITIALE.credit.comisionRambursare,
    soldActual: DATI_INITIALE.credit.soldActual,
    suma: DATI_INITIALE.credit.suma,
  },
  venituri: JSON.parse(JSON.stringify(DATI_INITIALE.venituri)),
  cheltuieli: JSON.parse(JSON.stringify(DATI_INITIALE.cheltuieli)),
  fondUrgenta: JSON.parse(JSON.stringify(DATI_INITIALE.fondUrgenta)),
  tezaur: JSON.parse(JSON.stringify(DATI_INITIALE.tezaur)),
  evolutie: JSON.parse(JSON.stringify(DATI_INITIALE.evolutie)),
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
      if (!state.data.profil) state.data.profil = JSON.parse(JSON.stringify(DATI_INITIALE.profil));
      // Ensure credit fields have defaults (from server they may be missing)
      if (!state.data.credit) state.data.credit = JSON.parse(JSON.stringify(DATI_INITIALE.credit));
      if (!state.data.credit.durata) state.data.credit.durata = DATI_INITIALE.credit.durata;
      if (!state.data.credit.dataStart) state.data.credit.dataStart = DATI_INITIALE.credit.dataStart;
      if (!state.data.credit.dobanda) state.data.credit.dobanda = DATI_INITIALE.credit.dobanda;
      if (!state.data.credit.rataLunara) state.data.credit.rataLunara = DATI_INITIALE.credit.rataLunara;
      if (!state.data.credit.soldActual) state.data.credit.soldActual = DATI_INITIALE.credit.soldActual;
      if (!state.data.credit.sumaTotala) state.data.credit.sumaTotala = DATI_INITIALE.credit.sumaTotala;
    } else {
      state.data = JSON.parse(JSON.stringify(INITIAL_DATA));
      await saveDataNow();
    }
  } catch(e) {
    console.error('Load failed, using initial data:', e);
    state.data = JSON.parse(JSON.stringify(INITIAL_DATA));
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
    pending: { text: '⏳ Salvare...', color: '#fbbf24' },
    saved:   { text: '✓ Salvat',     color: '#34d399' },
    error:   { text: '✗ Eroare',     color: '#f87171' }
  };
  var s = map[status] || map.saved;
  el.textContent = s.text;
  el.style.color = s.color;
}

async function resetData() {
  if (!confirm('Resetezi toate datele la valorile inițiale?')) return;
  state.data = JSON.parse(JSON.stringify(INITIAL_DATA));
  await saveDataNow();
  render();
}

// --- CSS styles (dark theme, inline) ---
var CSS = [
  '*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }',
  'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }',
  '.app-header { position: sticky; top: 0; z-index: 100; background: rgba(30,41,59,0.95); backdrop-filter: blur(8px); border-bottom: 1px solid #334155; }',
  '.header-inner { max-width: 1280px; margin: 0 auto; padding: 1rem 1rem 0; display: flex; align-items: center; justify-content: space-between; }',
  '.header-title { font-size: 1.25rem; font-weight: 700; color: #2dd4bf; }',
  '.header-sub { font-size: 0.75rem; color: #64748b; }',
  '.header-actions { display: flex; gap: 0.5rem; align-items: center; }',
  '.btn { padding: 0.4rem 0.8rem; border-radius: 0.375rem; font-size: 0.8rem; cursor: pointer; transition: all 0.2s; border: 1px solid #334155; background: #1e293b; color: #94a3b8; }',
  '.btn:hover { border-color: #475569; color: #cbd5e1; }',
  '.btn-reset:hover { color: #f87171; border-color: rgba(248,113,113,0.5); }',
  '.tab-bar { max-width: 1280px; margin: 0 auto; display: flex; border-bottom: 1px solid #334155; }',
  '.tab-btn { padding: 0.75rem 1rem; font-size: 0.875rem; font-weight: 500; color: #64748b; background: none; border: none; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }',
  '.tab-btn:hover { color: #cbd5e1; }',
  '.tab-btn.active { color: #2dd4bf; border-bottom-color: #2dd4bf; }',
  '.main-content { max-width: 1280px; margin: 0 auto; padding: 1.5rem 1rem 5rem; }',
  '.card { background: rgba(30,41,59,0.5); border-radius: 0.75rem; padding: 1rem; border: 1px solid; }',
  '.card-teal { border-color: rgba(45,212,191,0.3); }',
  '.card-red { border-color: rgba(248,113,113,0.3); }',
  '.card-yellow { border-color: rgba(250,204,21,0.3); }',
  '.card-blue { border-color: rgba(96,165,250,0.3); }',
  '.card-title { font-size: 0.8rem; font-weight: 600; color: #cbd5e1; margin-bottom: 0.75rem; }',
  '.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }',
  '.stat-row { display: flex; justify-content: space-between; font-size: 0.875rem; padding: 0.25rem 0; }',
  '.stat-row-light { color: #94a3b8; }',
  '.stat-row-dark { color: #e2e8f0; font-weight: 600; }',
  '.stat-val { color: #2dd4bf; }',
  '.stat-val-red { color: #f87171; }',
  '.stat-big { text-align: center; padding: 1rem 0; }',
  '.stat-big-num { font-size: 2rem; font-weight: 700; }',
  '.stat-big-num.pos { color: #2dd4bf; }',
  '.stat-big-num.neg { color: #f87171; }',
  '.stat-big-label { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }',
  '.border-top { border-top: 1px solid #334155; margin-top: 0.25rem; padding-top: 0.5rem; }',
  'input[type="number"], input[type="text"], input[type="date"], select { background: rgba(15,23,42,0.6); border: 1px solid #334155; border-radius: 0.375rem; padding: 0.25rem 0.5rem; color: #e2e8f0; font-size: 0.875rem; outline: none; }',
  'input[type="number"]:focus, input[type="text"]:focus, input[type="date"]:focus, select:focus { border-color: #2dd4bf; }',
  'input[type="number"] { text-align: right; width: 80px; }',
  'input[type="text"] { width: 100%; }',
  'input.w-full { width: 100%; }',
  'input.w-20 { width: 80px; }',
  'input.w-28 { width: 112px; }',
  'input.w-40 { width: 160px; }',
  'select { cursor: pointer; }',
  'table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }',
  'th { text-align: left; padding: 0.5rem 0.25rem; color: #64748b; border-bottom: 1px solid #334155; }',
  'th.text-right { text-align: right; }',
  'td { padding: 0.35rem 0.25rem; }',
  'td.text-right { text-align: right; }',
  '.section { margin-bottom: 2rem; }',
  '.section-title { font-size: 1rem; font-weight: 600; color: #e2e8f0; margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center; }',
  '.btn-add { background: #0d766e; color: #fff; border: none; padding: 0.35rem 0.75rem; border-radius: 0.375rem; font-size: 0.8rem; cursor: pointer; }',
  '.btn-add:hover { background: #115e59; }',
  '.btn-del { color: #f87171; background: none; border: none; cursor: pointer; font-size: 0.875rem; padding: 0 0.25rem; }',
  '.btn-del:hover { color: #fca5a5; }',
  '.tab-content { display: none; }',
  '.tab-content.active { display: block; }',
  'tfoot td { border-top: 1px solid #334155; padding-top: 0.5rem; font-weight: 600; color: #e2e8f0; }',
  'tr.border-b { border-bottom: 1px solid #1e293b; }',
  '.cell-input { background: rgba(15,23,42,0.5) !important; }',
  'label { font-size: 0.8rem; color: #94a3b8; display: block; margin-bottom: 0.25rem; }',
  '.flex-row { display: flex; gap: 1rem; flex-wrap: wrap; }',
  '.flex-col { flex: 1; min-width: 200px; }',
  '.range-val { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }',
  'input[type="range"] { width: 100%; accent-color: #2dd4bf; }',
  '.info-box { background: rgba(30,41,59,0.5); border: 1px solid rgba(45,212,191,0.3); border-radius: 0.5rem; padding: 0.75rem; font-size: 0.8rem; color: #94a3b8; }',
  '.tag { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 500; }',
  '.tag-teal { background: rgba(13,118,110,0.4); color: #2dd4bf; }',
  '.tag-red { background: rgba(127,29,29,0.4); color: #f87171; }',
  '.help-text { font-size: 0.7rem; color: #64748b; margin-top: 0.25rem; }',
].join('\n');

function injectStyles() {
  var el = document.createElement('style');
  el.textContent = CSS;
  document.head.appendChild(el);
}

// --- Helpers ---
function getNextId(arr) {
  if (!arr || arr.length === 0) return 1;
  return Math.max.apply(null, arr.map(function(x) { return x.id; })) + 1;
}

function cloneObj(obj) {
  return JSON.parse(JSON.stringify(obj));
}

// ====================================================================
// RENDER: Buget Lunar (Overview)
// ====================================================================
function renderBugetLunar() {
  var d = state.data;
  var mediiVenituri = calcMediiVenituri(d);
  var mediiCheltuieli = calcMediiCheltuieli(d);
  var surplus = mediiVenituri.total - mediiCheltuieli.total;

  var totalTezaur = d.tezaur.reduce(function(s, t) { return s + (parseRON(t.suma) || 0); }, 0);
  var totalFond = d.fondUrgenta.reduce(function(s, f) { return s + (parseRON(f.suma) || 0); }, 0);
  var buffer = Object.keys(d.evolutie).reduce(function(s, l) { return s + (d.evolutie[l].buffer || 0); }, 0);
  var totalActive = totalTezaur + totalFond + buffer;
  var soldCredit = d.credit.soldActual;
  var avereNeta = totalActive - soldCredit;

  var html = '<div class="card-grid">';

  // Venituri Medii
  html += '<div class="card card-teal">';
  html += '<h3 class="card-title">Venituri Medii Lunare</h3>';
  html += '<div class="stat-row stat-row-light"><span>Salariu net</span><span class="stat-val">' + formatRON(mediiVenituri.salariu) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Bonuri de masă</span><span class="stat-val">' + formatRON(mediiVenituri.bonuri) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Bonus</span><span class="stat-val">' + formatRON(mediiVenituri.bonus) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Diurnă</span><span class="stat-val">' + formatRON(mediiVenituri.diurna) + ' RON</span></div>';
  html += '<div class="stat-row border-top stat-row-dark"><span>TOTAL</span><span class="stat-val">' + formatRON(mediiVenituri.total) + ' RON</span></div>';
  html += '</div>';

  // Cheltuieli Medii
  html += '<div class="card card-red">';
  html += '<h3 class="card-title">Cheltuieli Medii Lunare</h3>';
  html += '<div class="stat-row stat-row-light"><span>Chirie</span><span class="stat-val-red">' + formatRON(mediiCheltuieli.chirie) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Rată credit</span><span class="stat-val-red">' + formatRON(mediiCheltuieli.rataCredit) + ' RON</span></div>';
  CHELTUIELI_VARIABILE.forEach(function(cat) {
    html += '<div class="stat-row stat-row-light"><span>' + cat + '</span><span class="stat-val-red">' + formatRON(mediiCheltuieli[cat] || 0) + ' RON</span></div>';
  });
  html += '<div class="stat-row border-top stat-row-dark"><span>TOTAL</span><span class="stat-val-red">' + formatRON(mediiCheltuieli.total) + ' RON</span></div>';
  html += '</div>';

  // Surplus
  html += '<div class="card ' + (surplus >= 0 ? 'card-teal' : 'card-red') + '">';
  html += '<h3 class="card-title">Surplus Lunar Mediu</h3>';
  html += '<div class="stat-big">';
  html += '<div class="stat-big-num ' + (surplus >= 0 ? 'pos' : 'neg') + '">' + formatRON(surplus) + ' RON</div>';
  html += '<div class="stat-big-label">' + (surplus >= 0 ? 'Pozitiv' : 'Negativ') + '</div>';
  html += '</div></div>';

  // Active
  html += '<div class="card card-teal">';
  html += '<h3 class="card-title">Active</h3>';
  html += '<div class="stat-row stat-row-light"><span>Tezaur</span><span class="stat-val">' + formatRON(totalTezaur) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Fond urgență</span><span class="stat-val">' + formatRON(totalFond) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Buffer cont</span><span class="stat-val">' + formatRON(buffer) + ' RON</span></div>';
  html += '<div class="stat-row border-top stat-row-dark"><span>TOTAL ACTIVE</span><span class="stat-val">' + formatRON(totalActive) + ' RON</span></div>';
  html += '</div>';

  // Credit
  html += '<div class="card card-red">';
  html += '<h3 class="card-title">Credit Activ</h3>';
  html += '<div class="stat-row stat-row-light" style="justify-content:flex-start;gap:0.5rem;align-items:center;">';
  html += '<span>Sold actual</span>';
  html += '<input type="number" value="' + d.credit.soldActual + '" onchange="updateCreditSold(this.value)" class="cell-input" style="width:100px;">';
  html += '</div>';
  html += '<div class="stat-row stat-row-light"><span>Dobândă</span><span>' + d.credit.dobanda + '%</span></div>';
  html += '<div class="stat-row stat-row-light"><span>DAE</span><span>' + d.credit.dae + '%</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Rată</span><span class="stat-val-red">' + formatRON(d.credit.rata) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Asigurare</span><span class="stat-val-red">' + formatRON(d.credit.asigurare) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Comision rambursare</span><span>' + d.credit.comisionRambursare + '%</span></div>';
  html += '</div>';

  // Avere Netă
  html += '<div class="card ' + (avereNeta >= 0 ? 'card-teal' : 'card-red') + '">';
  html += '<h3 class="card-title">Avere Netă</h3>';
  html += '<div class="stat-big">';
  html += '<div class="stat-big-num ' + (avereNeta >= 0 ? 'pos' : 'neg') + '">' + formatRON(avereNeta) + ' RON</div>';
  html += '<div class="stat-big-label">Total Active - Credit</div>';
  html += '</div></div>';

  html += '</div>';

  // Info row
  html += '<div class="info-box" style="margin-top:1rem;">';
  html += '<strong>Profil:</strong> ' + DATI_INITIALE.profil.nume + ' &nbsp;|&nbsp; ';
  html += '<strong>Salariu net:</strong> ' + formatRON(DATI_INITIALE.profil.salariuNet) + ' RON &nbsp;|&nbsp; ';
  html += '<strong>Bonus medie:</strong> ' + formatRON(DATI_INITIALE.profil.bonusMedie) + ' RON &nbsp;|&nbsp; ';
  html += '<strong>Credit rămas:</strong> ' + d.credit.durata + ' luni &nbsp;|&nbsp; ';
  html += '<strong>Data start:</strong> ' + d.credit.dataStart;
  html += '</div>';

  return html;
}

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
  var total = salariuNet + bonuri + bonus + diurna;
  return { salariu: salariuNet, bonuri: bonuri, bonus: bonus, diurna: diurna, total: total };
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

function updateCreditSold(val) {
  state.data.credit.soldActual = parseRON(val);
  saveData();
  render();
}

// ====================================================================
// RENDER: Credite
// ====================================================================
function renderCredite() {
  var d = state.data;
  var cr = d.credit;

  // Calculăm cât mai rămas din credit
  var luniRamase = cr.durata; // simplificat
  var dobandaLunara = cr.dobanda / 12;

  var html = '<div class="section">';
  html += '<div class="card-grid" style="grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));">';

  // Card info credit
  html += '<div class="card card-red">';
  html += '<h3 class="card-title">Detalii Credit</h3>';
  html += '<div class="stat-row stat-row-light"><span>Suma inițială</span><span class="stat-val-red">' + formatRON(cr.suma) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Sold actual</span>';
  html += '<input type="number" value="' + cr.soldActual + '" onchange="updateCreditSold(this.value)" class="cell-input" style="width:110px;"></input>';
  html += '</div>';
  html += '<div class="stat-row stat-row-light"><span>Dobândă anuală</span><span>' + cr.dobanda + '%</span></div>';
  html += '<div class="stat-row stat-row-light"><span>DAE</span><span>' + cr.dae + '%</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Rată lunară</span><span class="stat-val-red">' + formatRON(cr.rata) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Asigurare</span><span class="stat-val-red">' + formatRON(cr.asigurare) + ' RON</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Comision rambursare anticip.</span><span>' + cr.comisionRambursare + '%</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Durată rămasă</span><span>' + cr.durata + ' luni</span></div>';
  html += '<div class="stat-row stat-row-light"><span>Data start</span><span>' + cr.dataStart + '</span></div>';
  html += '</div>';

  // Simulare rambursare
  html += '<div class="card card-teal">';
  html += '<h3 class="card-title">Simulare Rambursare Anticipată</h3>';
  html += '<div style="margin-bottom:0.75rem;">';
  html += '<label>Sold credit curent (RON)</label>';
  html += '<input type="number" id="sim-sold" value="' + cr.soldActual + '" class="w-full cell-input" oninput="recalcSimulare()"></input>';
  html += '</div>';
  html += '<div style="margin-bottom:0.75rem;">';
  html += '<label>Sumă rambursare anticipată (RON)</label>';
  html += '<input type="number" id="sim-suma" value="5000" class="w-full cell-input" oninput="recalcSimulare()"></input>';
  html += '</div>';
  html += '<div style="margin-bottom:0.75rem;">';
  html += '<label>Luni rămase din credit</label>';
  html += '<input type="number" id="sim-luni" value="' + calcLuniRamase() + '" class="w-full cell-input" oninput="recalcSimulare()"></input>';
  html += '</div>';
  html += '<div id="sim-rezultat" class="info-box" style="margin-top:0.5rem;"></div>';
  html += '</div>';

  // Evoluție credit lunară
  html += '<div class="card card-yellow" style="grid-column: 1/-1;">';
  html += '<h3 class="card-title">Evoluție Sold Credit</h3>';
  html += '<div class="overflow-x-auto">';
  html += '<table style="min-width:600px;">';
  html += '<thead><tr><th class="text-right">Lună</th><th class="text-right">Sold inițial</th><th class="text-right">Rată</th><th class="text-right">Dobândă</th><th class="text-right">Sold final</th></tr></thead>';
  html += '<tbody>';

  var soldCurent = cr.soldActual;
  var rataLunara = cr.rata;
  for (var i = 0; i < 6 && i < LUNI_KEYS.length; i++) {
    var l = LUNI_KEYS[i];
    var dobanda = soldCurent * (cr.dobanda / 100 / 12);
    var principal = rataLunara - dobanda;
    var soldFinal = Math.max(0, soldCurent - principal);
    var evol = d.evolutie[l] || {};
    var displaySold = evol.soldCredit || soldFinal;

    html += '<tr class="border-b">';
    html += '<td class="text-right" style="color:#94a3b8;">' + LUNI[i] + '</td>';
    html += '<td class="text-right stat-val">' + formatRON(soldCurent) + '</td>';
    html += '<td class="text-right stat-val-red">' + formatRON(rataLunara) + '</td>';
    html += '<td class="text-right stat-val-red">' + formatRON(dobanda) + '</td>';
    html += '<td class="text-right stat-val">' + formatRON(displaySold) + '</td>';
    html += '</tr>';
    soldCurent = soldFinal;
  }
  html += '</tbody></table></div>';
  html += '</div>';

  html += '</div></div>';

  // Tabel cu toate lunile - sold credit
  html += '<div class="section">';
  html += '<h3 class="section-title">Sold Credit pe Luni</h3>';
  html += '<div class="card card-red">';
  html += '<div class="overflow-x-auto">';
  html += '<table style="min-width:500px;">';
  html += '<thead><tr><th>Activ</th>';
  LUNI.forEach(function(l) { html += '<th class="text-right">' + l + '</th>'; });
  html += '</tr></thead><tbody>';
  html += '<tr><td style="color:#94a3b8;">Sold credit (RON)</td>';
  LUNI_KEYS.forEach(function(l) {
    var evol = d.evolutie[l] || {};
    var val = evol.soldCredit || '';
    html += '<td class="text-right"><input type="number" class="cell-input w-20" value="' + val + '" placeholder="' + (l === 'mai' ? '84.450' : '') + '" onchange="updateEvolutie(\'' + l + '\', \'soldCredit\', this.value)"></td>';
  });
  html += '</tr></tbody></table></div></div></div>';

  return html;
}

function updateEvolutie(luna, field, val) {
  if (!state.data.evolutie[luna]) state.data.evolutie[luna] = {};
  state.data.evolutie[luna][field] = parseRON(val);
  saveData();
}

// ====================================================================
// RENDER: Fond Urgență
// ====================================================================
function renderFondUrgenta() {
  var d = state.data;

  var html = '<div class="section">';
  html += '<h3 class="section-title">';
  html += '<span>Fond de Urgență</span>';
  html += '<button class="btn-add" onclick="addFond()">+ Adaugă cont</button>';
  html += '</h3>';

  html += '<div class="card card-teal">';
  html += '<div class="overflow-x-auto">';
  html += '<table style="min-width:600px;">';
  html += '<thead><tr>';
  html += '<th>Cont</th>';
  html += '<th class="text-right">Sumă (RON)</th>';
  html += '<th class="text-right">Dobândă (%)</th>';
  html += '<th>Dobândă anuală</th>';
  html += '<th>Lichid?</th>';
  html += '<th>Notă</th>';
  html += '<th></th>';
  html += '</tr></thead>';
  html += '<tbody>';

  d.fondUrgenta.forEach(function(f) {
    var suma = parseRON(f.suma) || 0;
    var dobanda = parseRON(f.dobanda) || 0;
    var dobAnuala = suma * dobanda / 100;
    html += '<tr class="border-b">';
    html += '<td><input type="text" class="cell-input w-40" value="' + f.cont + '" onchange="updateFond(' + f.id + ', \'cont\', this.value)"></td>';
    html += '<td><input type="number" class="cell-input w-24 text-right" value="' + f.suma + '" onchange="updateFond(' + f.id + ', \'suma\', this.value)"></td>';
    html += '<td><input type="number" step="0.01" class="cell-input w-20 text-right" value="' + f.dobanda + '" onchange="updateFond(' + f.id + ', \'dobanda\', this.value)"></td>';
    html += '<td style="color:#2dd4bf;text-align:right;">' + formatRON(dobAnuala) + ' RON</td>';
    html += '<td><select class="cell-input" onchange="updateFond(' + f.id + ', \'lichid\', this.value)">';
    ['Da', 'Nu', 'Parțial'].forEach(function(opt) {
      html += '<option value="' + opt + '"' + (f.lichid === opt ? ' selected' : '') + '>' + opt + '</option>';
    });
    html += '</select></td>';
    html += '<td><input type="text" class="cell-input w-32" value="' + (f.nota || '') + '" onchange="updateFond(' + f.id + ', \'nota\', this.value)"></td>';
    html += '<td><button class="btn-del" onclick="removeFond(' + f.id + ')">✕</button></td>';
    html += '</tr>';
  });

  html += '</tbody>';
  var totalFond = d.fondUrgenta.reduce(function(s, f) { return s + (parseRON(f.suma) || 0); }, 0);
  var totalDob = d.fondUrgenta.reduce(function(s, f) { return s + (parseRON(f.suma) || 0) * (parseRON(f.dobanda) || 0) / 100; }, 0);
  html += '<tfoot><tr>';
  html += '<td style="color:#e2e8f0;">Total Fond Urgență</td>';
  html += '<td style="text-align:right;color:#2dd4bf;">' + formatRON(totalFond) + ' RON</td>';
  html += '<td colspan="2" style="text-align:right;color:#2dd4bf;">' + formatRON(totalDob) + ' RON / an</td>';
  html += '<td colspan="2"></td>';
  html += '</tr></tfoot>';
  html += '</table></div></div></div>';

  // --- Tezaur ---
  html += '<div class="section">';
  html += '<h3 class="section-title">';
  html += '<span>Titluri de stat Tezaur</span>';
  html += '<button class="btn-add" onclick="addTezaur()">+ Adaugă subscriere</button>';
  html += '</h3>';

  html += '<div class="card card-teal">';
  html += '<div class="overflow-x-auto">';
  html += '<table style="min-width:800px;">';
  html += '<thead><tr>';
  html += '<th>Emisiune</th>';
  html += '<th>Data subsc.</th>';
  html += '<th class="text-right">Sumă (RON)</th>';
  html += '<th class="text-right">Dobândă (%)</th>';
  html += '<th>Maturit.</th>';
  html += '<th>Data scad.</th>';
  html += '<th class="text-right">Dobândă câșt.</th>';
  html += '<th class="text-right">Total</th>';
  html += '<th></th>';
  html += '</tr></thead><tbody>';

  d.tezaur.forEach(function(t) {
    var suma = parseRON(t.suma) || 0;
    var dobPct = parseRON(t.dobanda) || 0;
    var dobCistigata = suma * dobPct / 100;
    var total = suma + dobCistigata;
    html += '<tr class="border-b">';
    html += '<td><select class="cell-input" onchange="updateTezaur(' + t.id + ', \'emisiune\', this.value)">';
    ['Tezaur 1 an','Tezaur 3 ani','Tezaur 5 ani','Fidelis RON','Fidelis EUR'].forEach(function(opt) {
      html += '<option value="' + opt + '"' + (t.emisiune === opt ? ' selected' : '') + '>' + opt + '</option>';
    });
    html += '</select></td>';
    html += '<td><input type="date" class="cell-input w-28" value="' + (t.dataSubscriere || '') + '" onchange="updateTezaur(' + t.id + ', \'dataSubscriere\', this.value)"></td>';
    html += '<td><input type="number" class="cell-input w-24 text-right" value="' + t.suma + '" onchange="updateTezaur(' + t.id + ', \'suma\', this.value)"></td>';
    html += '<td><input type="number" step="0.01" class="cell-input w-20 text-right" value="' + t.dobanda + '" onchange="updateTezaur(' + t.id + ', \'dobanda\', this.value)"></td>';
    html += '<td><select class="cell-input" onchange="updateTezaur(' + t.id + ', \'maturitate\', this.value)">';
    ['1 an','3 ani','5 ani'].forEach(function(opt) {
      html += '<option value="' + opt + '"' + (t.maturitate === opt ? ' selected' : '') + '>' + opt + '</option>';
    });
    html += '</select></td>';
    html += '<td><input type="date" class="cell-input w-28" value="' + (t.dataScadenta || '') + '" onchange="updateTezaur(' + t.id + ', \'dataScadenta\', this.value)"></td>';
    html += '<td class="text-right" style="color:#2dd4bf;">' + formatRON(dobCistigata) + '</td>';
    html += '<td class="text-right" style="color:#2dd4bf;">' + formatRON(total) + '</td>';
    html += '<td><button class="btn-del" onclick="removeTezaur(' + t.id + ')">✕</button></td>';
    html += '</tr>';
  });

  html += '</tbody>';
  var totalTezaur = d.tezaur.reduce(function(s, t) { return s + (parseRON(t.suma) || 0); }, 0);
  var totalDobTezaur = d.tezaur.reduce(function(s, t) { return s + (parseRON(t.suma) || 0) * (parseRON(t.dobanda) || 0) / 100; }, 0);
  html += '<tfoot><tr>';
  html += '<td style="color:#e2e8f0;">Total Tezaur investit</td>';
  html += '<td colspan="2" style="text-align:right;color:#2dd4bf;">' + formatRON(totalTezaur) + ' RON</td>';
  html += '<td colspan="2" style="text-align:right;color:#2dd4bf;">+' + formatRON(totalDobTezaur) + ' RON / an</td>';
  html += '<td colspan="3"></td>';
  html += '</tr></tfoot>';
  html += '</table></div></div></div>';

  // --- Evoluție lunară active ---
  html += '<div class="section">';
  html += '<h3 class="section-title">Evoluție Lunară Active</h3>';
  html += '<div class="card card-blue">';
  html += '<div class="overflow-x-auto">';
  html += '<table style="min-width:700px;">';
  html += '<thead><tr><th>Activ</th>';
  LUNI.forEach(function(l) { html += '<th class="text-right">' + l + '</th>'; });
  html += '</tr></thead><tbody>';

  var campuriEvolutie = [
    { key: 'fondUrgenta', label: 'Fond urgență', placeholder: '14.000' },
    { key: 'tezaur', label: 'Tezaur investit', placeholder: '5.000' },
    { key: 'buffer', label: 'Buffer cont curent', placeholder: '3.450' },
  ];

  campuriEvolutie.forEach(function(camp) {
    html += '<tr><td style="color:#94a3b8;">' + camp.label + '</td>';
    LUNI_KEYS.forEach(function(l) {
      var val = (state.data.evolutie[l] || {})[camp.key] || '';
      html += '<td class="text-right"><input type="number" class="cell-input w-20" value="' + val + '" placeholder="' + (l === 'mai' ? camp.placeholder : '') + '" onchange="updateEvolutie(\'' + l + '\', \'' + camp.key + '\', this.value)"></td>';
    });
    html += '</tr>';
  });

  // Total active per luna
  html += '<tr style="font-weight:600;color:#e2e8f0;border-top:1px solid #334155;"><td>Total Active</td>';
  LUNI_KEYS.forEach(function(l) {
    var e = state.data.evolutie[l] || {};
    var total = (e.fondUrgenta || 0) + (e.tezaur || 0) + (e.buffer || 0);
    html += '<td class="text-right" style="color:#2dd4bf;">' + formatRON(total) + '</td>';
  });
  html += '</tr>';

  // Avere Netă per luna
  html += '<tr style="font-weight:700;color:#e2e8f0;border-top:1px solid #475569;"><td>Avere Netă</td>';
  LUNI_KEYS.forEach(function(l) {
    var e = state.data.evolutie[l] || {};
    var active = (e.fondUrgenta || 0) + (e.tezaur || 0) + (e.buffer || 0);
    var avereNeta = active - (e.soldCredit || 0);
    var cls = avereNeta >= 0 ? 'color:#2dd4bf;' : 'color:#f87171;';
    html += '<td class="text-right" style="' + cls + '">' + formatRON(avereNeta) + '</td>';
  });
  html += '</tr>';

  html += '</tbody></table></div></div></div>';

  return html;
}

function addFond() {
  var newId = getNextId(state.data.fondUrgenta);
  state.data.fondUrgenta.push({ id: newId, cont: '', suma: '', dobanda: '', lichid: 'Da', nota: '' });
  saveData();
  render();
}
function updateFond(id, field, value) {
  state.data.fondUrgenta = state.data.fondUrgenta.map(function(f) {
    if (f.id === id) {
      var updated = cloneObj(f);
      if (field === 'suma' || field === 'dobanda') updated[field] = parseRON(value);
      else updated[field] = value;
      return updated;
    }
    return f;
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
  var newId = getNextId(state.data.tezaur);
  state.data.tezaur.push({ id: newId, emisiune: 'Tezaur 1 an', dataSubscriere: '', suma: '', dobanda: 6.30, maturitate: '1 an', dataScadenta: '' });
  saveData();
  render();
}
function updateTezaur(id, field, value) {
  state.data.tezaur = state.data.tezaur.map(function(t) {
    if (t.id === id) {
      var updated = cloneObj(t);
      if (field === 'suma' || field === 'dobanda') updated[field] = parseRON(value);
      else updated[field] = value;
      return updated;
    }
    return t;
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
// RENDER: Venituri
// ====================================================================
function renderVenituri() {
  var d = state.data;

  // Venituri
  var html = '<div class="section">';
  html += '<h3 class="section-title">Venituri Lunare</h3>';
  html += '<div class="card card-teal">';
  html += '<div class="overflow-x-auto">';
  html += '<table style="min-width:900px;">';
  html += '<thead><tr><th>Categorie</th>';
  LUNI.forEach(function(l) { html += '<th class="text-right">' + l + '</th>'; });
  html += '</tr></thead><tbody>';

  // Salariu fix
  html += '<tr class="border-b" style="background:rgba(30,41,59,0.3);">';
  html += '<td style="color:#cbd5e1;font-weight:500;">Salariu net</td>';
  LUNI.forEach(function() { html += '<td class="text-right" style="color:#2dd4bf;">7.000 RON</td>'; });
  html += '</tr>';

  // Bonuri
  html += '<tr><td style="color:#94a3b8;">Bonuri de masă</td>';
  LUNI_KEYS.forEach(function(l) {
    var val = (d.venituri[l] || {}).bonuri || '';
    html += '<td class="text-right"><input type="number" class="cell-input w-20" value="' + val + '" placeholder="' + (l === 'mai' ? '360' : '') + '" onchange="updateVenit(\'' + l + '\', \'bonuri\', this.value)"></td>';
  });
  html += '</tr>';

  // Bonus
  html += '<tr><td style="color:#94a3b8;">Bonus</td>';
  LUNI_KEYS.forEach(function(l) {
    var val = (d.venituri[l] || {}).bonus || '';
    html += '<td class="text-right"><input type="number" class="cell-input w-20" value="' + val + '" placeholder="' + (l === 'mai' ? '1.750' : '') + '" onchange="updateVenit(\'' + l + '\', \'bonus\', this.value)"></td>';
  });
  html += '</tr>';

  // Diurnă
  html += '<tr><td style="color:#94a3b8;">Diurnă</td>';
  LUNI_KEYS.forEach(function(l) {
    var val = (d.venituri[l] || {}).diurna || '';
    html += '<td class="text-right"><input type="number" class="cell-input w-20" value="' + val + '" placeholder="' + (l === 'mai' ? '1.200' : '') + '" onchange="updateVenit(\'' + l + '\', \'diurna\', this.value)"></td>';
  });
  html += '</tr>';

  // Total Venituri
  var totalsVenituri = LUNI_KEYS.map(function(l) {
    var v = d.venituri[l] || {};
    return 7000 + (v.bonuri || 0) + (v.bonus || 0) + (v.diurna || 0);
  });
  html += '<tr style="font-weight:600;border-top:1px solid #334155;">';
  html += '<td style="color:#e2e8f0;">TOTAL VENITURI</td>';
  totalsVenituri.forEach(function(t) {
    html += '<td class="text-right" style="color:#2dd4bf;">' + formatRON(t) + ' RON</td>';
  });
  html += '</tr>';

  html += '</tbody></table></div></div></div>';

  // Cheltuieli
  html += '<div class="section">';
  html += '<h3 class="section-title">Cheltuieli Lunare</h3>';
  html += '<div class="card card-red">';
  html += '<div class="overflow-x-auto">';
  html += '<table style="min-width:900px;">';
  html += '<thead><tr><th>Categorie</th>';
  LUNI.forEach(function(l) { html += '<th class="text-right">' + l + '</th>'; });
  html += '</tr></thead><tbody>';

  // Cheltuieli fixe
  html += '<tr class="border-b" style="background:rgba(30,41,59,0.3);">';
  html += '<td style="color:#cbd5e1;font-weight:500;">Chirie</td>';
  LUNI.forEach(function() { html += '<td class="text-right" style="color:#f87171;">2.000 RON</td>'; });
  html += '</tr>';
  html += '<tr class="border-b" style="background:rgba(30,41,59,0.3);">';
  html += '<td style="color:#cbd5e1;font-weight:500;">Rată credit + asig.</td>';
  LUNI.forEach(function() { html += '<td class="text-right" style="color:#f87171;">' + formatRON(d.cheltuieliFixe.rataCredit) + ' RON</td>'; });
  html += '</tr>';

  // Cheltuieli variabile
  CHELTUIELI_VARIABILE.forEach(function(cat) {
    html += '<tr><td style="color:#94a3b8;">' + cat + '</td>';
    LUNI_KEYS.forEach(function(l) {
      var val = (d.cheltuieli[l] || {})[cat] || '';
      html += '<td class="text-right"><input type="number" class="cell-input w-20" value="' + val + '" onchange="updateCheltuiala(\'' + l + '\', \'' + cat + '\', this.value)"></td>';
    });
    html += '</tr>';
  });

  // Total Cheltuieli
  var totalsCheltuieli = LUNI_KEYS.map(function(l) {
    var c = d.cheltuieli[l] || {};
    return d.cheltuieliFixe.chirie + d.cheltuieliFixe.rataCredit + Object.values(c).reduce(function(s, v) { return s + v; }, 0);
  });
  html += '<tr style="font-weight:600;border-top:1px solid #334155;">';
  html += '<td style="color:#e2e8f0;">TOTAL CHELTUIELI</td>';
  totalsCheltuieli.forEach(function(t) {
    html += '<td class="text-right" style="color:#f87171;">' + formatRON(t) + ' RON</td>';
  });
  html += '</tr>';

  // Surplus/Deficit
  var surplus = LUNI_KEYS.map(function(_, i) { return totalsVenituri[i] - totalsCheltuieli[i]; });
  html += '<tr style="font-weight:700;border-top:1px solid #475569;">';
  html += '<td style="color:#e2e8f0;">SURPLUS / DEFICIT</td>';
  surplus.forEach(function(t) {
    var cls = t >= 0 ? 'color:#2dd4bf;' : 'color:#f87171;';
    html += '<td class="text-right" style="' + cls + '">' + formatRON(t) + ' RON</td>';
  });
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
    { id: 'buget-lunar', label: '📊 Buget lunar' },
    { id: 'credite', label: '🏦 Credite' },
    { id: 'fond-urgenta', label: '🛡️ Fond Urgență' },
    { id: 'venituri', label: '💰 Venituri' },
  ];

  var tabContent = {
    'buget-lunar': renderBugetLunar(),
    'credite': renderCredite(),
    'fond-urgenta': renderFondUrgenta(),
    'venituri': renderVenituri(),
  };

  var html = '';
  html += '<div class="app-header">';
  html += '<div class="header-inner">';
  html += '<div>';
  html += '<div class="header-title">Budget Tracker</div>';
  html += '<div class="header-sub">Ion • RON • 2026</div>';
  html += '</div>';
  html += '<div class="header-actions">';
  html += '<span id="save-status" style="font-size:0.75rem;color:#34d399;margin-right:0.5rem;">✓ Salvat</span>';
  html += '<button class="btn btn-reset" onclick="resetData()">Resetează</button>';
  html += '<button class="btn" onclick="exportCSV()">Export CSV</button>';
  html += '</div>';
  html += '</div>';
  html += '<div class="tab-bar">';
  tabs.forEach(function(tab) {
    var active = state.activeTab === tab.id ? ' active' : '';
    html += '<button class="tab-btn' + active + '" onclick="switchTab(\'' + tab.id + '\')">' + tab.label + '</button>';
  });
  html += '</div>';
  html += '</div>';
  html += '<div class="main-content">';
  html += '<div id="tab-content" class="tab-content active">' + (tabContent[state.activeTab] || '') + '</div>';
  html += '</div>';

  document.getElementById('app').innerHTML = html;
}

function switchTab(tabId) {
  state.activeTab = tabId;
  render();
}

function exportCSV() {
  var d = state.data;
  var lines = [];
  lines.push('Budget Tracker - Ion - Export CSV');

  // Venituri
  lines.push('\nVENITURI');
  lines.push('Categorie,' + LUNI.join(','));
  lines.push('Salariu net,' + LUNI.map(function() { return '7000'; }).join(','));
  lines.push('Bonuri de masa,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).bonuri || 0; }).join(','));
  lines.push('Bonus,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).bonus || 0; }).join(','));
  lines.push('Diurna,' + LUNI_KEYS.map(function(l) { return (d.venituri[l] || {}).diurna || 0; }).join(','));

  // Cheltuieli
  lines.push('\nCHELTUIELI');
  lines.push('Categorie,' + LUNI.join(','));
  lines.push('Chirie,' + LUNI.map(function() { return '2000'; }).join(','));
  lines.push('Rata credit,' + LUNI.map(function() { return d.cheltuieliFixe.rataCredit; }).join(','));
  CHELTUIELI_VARIABILE.forEach(function(cat) {
    var row = cat + ',' + LUNI_KEYS.map(function(l) { return (d.cheltuieli[l] || {})[cat] || 0; }).join(',');
    lines.push(row);
  });

  // Fond Urgență
  lines.push('\nFOND URGENTA');
  lines.push('Cont,Suma,Dobanda,Lichid,Nota');
  d.fondUrgenta.forEach(function(f) {
    lines.push((f.cont || '') + ',' + (f.suma || 0) + ',' + (f.dobanda || 0) + ',' + (f.lichid || '') + ',' + (f.nota || ''));
  });

  // Tezaur
  lines.push('\nTEZAUR');
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
// SIMULARE CREDIT FUNCTIONS
// ====================================================================
function calcLuniRamase() {
  var cr = state.data.credit;
  if (!cr || !cr.dataStart) return cr ? cr.durata : 60;
  var parts = cr.dataStart.split('-');
  var start = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
  var now = new Date();
  var luniTrecute = (now.getFullYear() - start.getFullYear()) * 12 +
                    (now.getMonth() - start.getMonth());
  return Math.max(0, (cr.durata || 60) - luniTrecute);
}

function calcEconomieDobanda(suma, sold, dobandaAnuala, luniRamase, comisionProcent) {
  if (suma <= 0 || luniRamase <= 0) return { economie: 0, comision: 0, net: 0 };
  var dobandaLunara = dobandaAnuala / 100 / 12;
  var economieBruta = suma * dobandaLunara * (luniRamase / 2);
  var comision = suma * (comisionProcent / 100);
  var net = economieBruta - comision;
  return { economie: economieBruta, comision: comision, net: net };
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
  html += '<strong>Economie dobândă totală:</strong> ' + formatRON(r.economie) + ' RON<br>';
  html += '<strong>Comision rambursare (' + cr.comisionRambursare + '%):</strong> ' +
          formatRON(r.comision) + ' RON<br>';
  html += '<strong style="color:' + (r.net >= 0 ? '#34d399' : '#f87171') +
          ';">Economie netă: ' + formatRON(r.net) + ' RON</strong><br>';
  if (suma > sold) {
    html += '<p class="help-text" style="color:#fbbf24;">⚠ Suma depășește soldul actual.</p>';
  } else if (suma > 0) {
    html += '<p class="help-text" style="margin-top:0.5rem;">';
    html += 'Sold după rambursare: ' + formatRON(sold - suma) + ' RON.';
    html += '</p>';
  }
  el.innerHTML = html;
}

// ====================================================================
// BOOT
// ====================================================================
async function init() {
  injectStyles();
  await loadData();
  render();
  // trigger simulare recalc after DOM is ready
  setTimeout(recalcSimulare, 0);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
