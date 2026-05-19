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

// Months between two "YYYY-MM" strings (b - a). Negative if b before a.
function diffMonths(a, b) {
  if (!a || !b) return 0;
  var ap = String(a).split('-'); var bp = String(b).split('-');
  return (parseInt(bp[0], 10) - parseInt(ap[0], 10)) * 12 + (parseInt(bp[1], 10) - parseInt(ap[1], 10));
}

// True if recurring fixed-expense item is active in given month key
function cheltuialaFixaActiva(item, lunaKey) {
  if (!item) return false;
  var start = item.startMonth || (state.data.profil && state.data.profil.startMonth) || '2026-05';
  var diff = diffMonths(start, lunaKey);
  if (diff < 0) return false;
  var luni = parseInt(item.luni, 10);
  if (!luni || luni <= 0) return true; // perpetual
  return diff < luni;
}

// Sum of fixed-expense items active in given month key
function totalFixeLuna(d, lunaKey) {
  return (d.cheltuieliFixe || []).reduce(function(s, f) {
    if (!cheltuialaFixaActiva(f, lunaKey)) return s;
    return s + (parseRON(f.suma) || 0);
  }, 0);
}

// Seed d.reguliCategorizare from defaults if missing
function migrateReguliCategorizare(data) {
  if (!data) return;
  if (Array.isArray(data.reguliCategorizare) && data.reguliCategorizare.length > 0) return;
  data.reguliCategorizare = cloneObj(REGULI_CATEGORIZARE_DEFAULT);
}

// Seed d.credit.scadentar from real ING amortisation table if missing
function migrateCreditScadentar(data) {
  if (!data) return;
  if (!data.credit) data.credit = cloneObj(DATI_INITIALE.credit);
  if (!Array.isArray(data.credit.scadentar) || data.credit.scadentar.length === 0) {
    data.credit.scadentar = cloneObj(SCADENTAR_REAL_DEFAULT);
  }
}

// Ensure d.emisiuniTezaur exists as [{id,label}]
function migrateEmisiuniTezaur(data) {
  if (!data) return;
  if (Array.isArray(data.emisiuniTezaur) && data.emisiuniTezaur.length > 0 && typeof data.emisiuniTezaur[0] === 'object') return;
  if (Array.isArray(data.emisiuniTezaur) && data.emisiuniTezaur.length > 0 && typeof data.emisiuniTezaur[0] === 'string') {
    data.emisiuniTezaur = data.emisiuniTezaur.map(function(s, i) { return { id: i + 1, label: s }; });
    return;
  }
  data.emisiuniTezaur = cloneObj(DATI_INITIALE.emisiuniTezaur);
}

// Ensure d.categoriiVenit exists; migrate legacy bonuri/bonus/diurna keys to labels
function migrateCategoriiVenit(data) {
  if (!data) return;
  var seed = function() {
    data.categoriiVenit = cloneObj(DATI_INITIALE.categoriiVenit);
  };
  if (!Array.isArray(data.categoriiVenit) || data.categoriiVenit.length === 0) seed();
  // Rename legacy keys in venituri buckets
  var mapping = { bonuri: 'Bonuri masă', bonus: 'Bonus', diurna: 'Diurnă' };
  Object.keys(data.venituri || {}).forEach(function(luna) {
    var v = data.venituri[luna];
    if (!v || typeof v !== 'object') return;
    Object.keys(mapping).forEach(function(oldKey) {
      if (v[oldKey] !== undefined) {
        if (v[mapping[oldKey]] === undefined) v[mapping[oldKey]] = v[oldKey];
        delete v[oldKey];
      }
    });
  });
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

// --- Auto-categorization rules for bank CSV import (ING) ---
var REGULI_CATEGORIZARE_DEFAULT = [
  { id: 1,  pattern: 'Rata Credit',                       categorie: 'Rată credit + asig.' },
  { id: 2,  pattern: 'Prima asigurare ING Credit Protect',categorie: 'Rată credit + asig.' },
  { id: 3,  pattern: 'Detalii:chirie',                    categorie: 'Chirie' },
  { id: 4,  pattern: 'Subscriere Tezaur',                 categorie: '__SKIP__' },
  { id: 5,  pattern: 'KAUFLAND|AUCHAN|CARREFOUR|MEGA IMAGE|LIDL|PROFI|PENNY|SELGROS',          categorie: 'Alimente' },
  { id: 6,  pattern: 'ENGIE|ELECTRICA|APA NOVA|E\\.ON|HIDROELECTRICA|ENEL',                    categorie: 'Facturi' },
  { id: 7,  pattern: 'VODAFONE|DIGI|RDS|RCS|ORANGE|TELEKOM',                                   categorie: 'Facturi' },
  { id: 8,  pattern: 'MEDICAL|FARMACIE|FARMACIA|CATENA|SENSIBLU|HELPNET|REGINA MARIA|MEDLIFE|MEDICOVER|CLUJ MEDICAL', categorie: 'Sănătate' },
  { id: 9,  pattern: 'BOLT|UBER|FREE NOW|FREENOW|TAXIFY',                                      categorie: 'Transport' },
  { id: 10, pattern: 'OMV|MOL|PETROM|ROMPETROL|LUKOIL|SOCAR',                                  categorie: 'Transport' },
  { id: 11, pattern: 'NETFLIX|SPOTIFY|HBO|YOUTUBE|APPLE\\.COM|GOOGLE|MICROSOFT|ADOBE',         categorie: 'Abonamente' },
  { id: 12, pattern: 'H\\&M|ZARA|RESERVED|BERSHKA|PULL\\&BEAR|C\\&A|DECATHLON',                categorie: 'Îmbrăcăminte' },
  { id: 13, pattern: 'CINEMA|RESTAURANT|MCDONALDS|KFC|STARBUCKS|BURGER KING|PIZZA',            categorie: 'Divertisment' },
];

// --- Scadentar real (sursa: ING Home'Bank scadenţar 19.05.2026) ---
var SCADENTAR_REAL_DEFAULT = [
  { data: "2026-06-18", suma: 1793.9, dobanda: 682.11, principal: 1111.79, soldFinal: 80823.9, asigurare: 145.0 },
  { data: "2026-07-18", suma: 1793.9, dobanda: 672.86, principal: 1121.04, soldFinal: 79702.86, asigurare: 142.99 },
  { data: "2026-08-18", suma: 1786.52, dobanda: 663.53, principal: 1122.99, soldFinal: 78579.87, asigurare: 140.97 },
  { data: "2026-09-18", suma: 1786.52, dobanda: 654.18, principal: 1132.34, soldFinal: 77447.53, asigurare: 138.94 },
  { data: "2026-10-18", suma: 1786.52, dobanda: 644.75, principal: 1141.77, soldFinal: 76305.76, asigurare: 136.89 },
  { data: "2026-11-18", suma: 1786.52, dobanda: 635.24, principal: 1151.28, soldFinal: 75154.48, asigurare: 134.83 },
  { data: "2026-12-18", suma: 1786.52, dobanda: 625.66, principal: 1160.86, soldFinal: 73993.62, asigurare: 132.74 },
  { data: "2027-01-18", suma: 1786.52, dobanda: 616.0, principal: 1170.52, soldFinal: 72823.1, asigurare: 130.64 },
  { data: "2027-02-18", suma: 1786.53, dobanda: 606.25, principal: 1180.28, soldFinal: 71642.82, asigurare: 128.53 },
  { data: "2027-03-18", suma: 1786.53, dobanda: 596.43, principal: 1190.1, soldFinal: 70452.72, asigurare: 126.39 },
  { data: "2027-04-18", suma: 1786.53, dobanda: 586.52, principal: 1200.01, soldFinal: 69252.71, asigurare: 124.24 },
  { data: "2027-05-18", suma: 1786.52, dobanda: 576.53, principal: 1209.99, soldFinal: 68042.72, asigurare: 122.07 },
  { data: "2027-06-18", suma: 1786.52, dobanda: 566.45, principal: 1220.07, soldFinal: 66822.65, asigurare: 119.88 },
  { data: "2027-07-18", suma: 1786.52, dobanda: 556.3, principal: 1230.22, soldFinal: 65592.43, asigurare: 117.67 },
  { data: "2027-08-18", suma: 1786.52, dobanda: 546.06, principal: 1240.46, soldFinal: 64351.97, asigurare: 115.45 },
  { data: "2027-09-18", suma: 1786.52, dobanda: 535.73, principal: 1250.79, soldFinal: 63101.18, asigurare: 113.2 },
  { data: "2027-10-18", suma: 1786.52, dobanda: 525.32, principal: 1261.2, soldFinal: 61839.98, asigurare: 110.94 },
  { data: "2027-11-18", suma: 1786.52, dobanda: 514.81, principal: 1271.71, soldFinal: 60568.27, asigurare: 108.66 },
  { data: "2027-12-18", suma: 1786.52, dobanda: 504.23, principal: 1282.29, soldFinal: 59285.98, asigurare: 106.36 },
  { data: "2028-01-18", suma: 1786.52, dobanda: 493.56, principal: 1292.96, soldFinal: 57993.02, asigurare: 104.04 },
  { data: "2028-02-18", suma: 1786.53, dobanda: 482.79, principal: 1303.74, soldFinal: 56689.28, asigurare: 101.7 },
  { data: "2028-03-18", suma: 1786.53, dobanda: 471.94, principal: 1314.59, soldFinal: 55374.69, asigurare: 99.34 },
  { data: "2028-04-18", suma: 1786.53, dobanda: 460.99, principal: 1325.54, soldFinal: 54049.15, asigurare: 96.96 },
  { data: "2028-05-18", suma: 1786.53, dobanda: 449.96, principal: 1336.57, soldFinal: 52712.58, asigurare: 94.57 },
  { data: "2028-06-18", suma: 1786.53, dobanda: 438.84, principal: 1347.69, soldFinal: 51364.89, asigurare: 92.15 },
  { data: "2028-07-18", suma: 1786.53, dobanda: 427.61, principal: 1358.92, soldFinal: 50005.97, asigurare: 89.71 },
  { data: "2028-08-18", suma: 1786.52, dobanda: 416.3, principal: 1370.22, soldFinal: 48635.75, asigurare: 87.25 },
  { data: "2028-09-18", suma: 1786.52, dobanda: 404.89, principal: 1381.63, soldFinal: 47254.12, asigurare: 84.77 },
  { data: "2028-10-18", suma: 1786.52, dobanda: 393.39, principal: 1393.13, soldFinal: 45860.99, asigurare: 82.27 },
  { data: "2028-11-18", suma: 1786.53, dobanda: 381.79, principal: 1404.74, soldFinal: 44456.25, asigurare: 79.75 },
  { data: "2028-12-18", suma: 1786.53, dobanda: 370.1, principal: 1416.43, soldFinal: 43039.82, asigurare: 77.21 },
  { data: "2029-01-18", suma: 1786.53, dobanda: 358.31, principal: 1428.22, soldFinal: 41611.6, asigurare: 74.65 },
  { data: "2029-02-18", suma: 1786.53, dobanda: 346.42, principal: 1440.11, soldFinal: 40171.49, asigurare: 72.07 },
  { data: "2029-03-18", suma: 1786.53, dobanda: 334.42, principal: 1452.11, soldFinal: 38719.38, asigurare: 69.46 },
  { data: "2029-04-18", suma: 1786.53, dobanda: 322.34, principal: 1464.19, soldFinal: 37255.19, asigurare: 66.84 },
  { data: "2029-05-18", suma: 1786.52, dobanda: 310.15, principal: 1476.37, soldFinal: 35778.82, asigurare: 64.19 },
  { data: "2029-06-18", suma: 1786.52, dobanda: 297.86, principal: 1488.66, soldFinal: 34290.16, asigurare: 61.52 },
  { data: "2029-07-18", suma: 1786.52, dobanda: 285.47, principal: 1501.05, soldFinal: 32789.11, asigurare: 58.82 },
  { data: "2029-08-18", suma: 1786.53, dobanda: 272.96, principal: 1513.57, soldFinal: 31275.54, asigurare: 56.11 },
  { data: "2029-09-18", suma: 1786.53, dobanda: 260.37, principal: 1526.16, soldFinal: 29749.38, asigurare: 53.37 },
  { data: "2029-10-18", suma: 1786.53, dobanda: 247.67, principal: 1538.86, soldFinal: 28210.52, asigurare: 50.61 },
  { data: "2029-11-18", suma: 1786.52, dobanda: 234.85, principal: 1551.67, soldFinal: 26658.85, asigurare: 47.83 },
  { data: "2029-12-18", suma: 1786.52, dobanda: 221.93, principal: 1564.59, soldFinal: 25094.26, asigurare: 45.02 },
  { data: "2030-01-18", suma: 1786.52, dobanda: 208.91, principal: 1577.61, soldFinal: 23516.65, asigurare: 42.19 },
  { data: "2030-02-18", suma: 1786.52, dobanda: 195.78, principal: 1590.74, soldFinal: 21925.91, asigurare: 39.34 },
  { data: "2030-03-18", suma: 1786.52, dobanda: 182.53, principal: 1603.99, soldFinal: 20321.92, asigurare: 36.46 },
  { data: "2030-04-18", suma: 1786.52, dobanda: 169.18, principal: 1617.34, soldFinal: 18704.58, asigurare: 33.56 },
  { data: "2030-05-18", suma: 1786.53, dobanda: 155.72, principal: 1630.81, soldFinal: 17073.77, asigurare: 30.63 },
  { data: "2030-06-18", suma: 1786.53, dobanda: 142.14, principal: 1644.39, soldFinal: 15429.38, asigurare: 27.68 },
  { data: "2030-07-18", suma: 1786.53, dobanda: 128.45, principal: 1658.08, soldFinal: 13771.3, asigurare: 24.71 },
  { data: "2030-08-18", suma: 1786.52, dobanda: 114.64, principal: 1671.88, soldFinal: 12099.42, asigurare: 21.71 },
  { data: "2030-09-18", suma: 1786.52, dobanda: 100.73, principal: 1685.79, soldFinal: 10413.63, asigurare: 18.68 },
  { data: "2030-10-18", suma: 1786.52, dobanda: 86.7, principal: 1699.82, soldFinal: 8713.81, asigurare: 15.63 },
  { data: "2030-11-18", suma: 1786.53, dobanda: 72.54, principal: 1713.99, soldFinal: 6999.82, asigurare: 12.56 },
  { data: "2030-12-18", suma: 1786.53, dobanda: 58.27, principal: 1728.26, soldFinal: 5271.56, asigurare: 9.46 },
  { data: "2031-01-18", suma: 1786.53, dobanda: 43.89, principal: 1742.64, soldFinal: 3528.92, asigurare: 6.33 },
  { data: "2031-02-18", suma: 1786.52, dobanda: 29.38, principal: 1757.14, soldFinal: 1771.78, asigurare: 3.18 },
  { data: "2031-03-18", suma: 1786.53, dobanda: 14.75, principal: 1771.78, soldFinal: 0.0, asigurare: 0.0 },
];

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
  categoriiVenit: [
    { id: 1, label: 'Bonuri masă' },
    { id: 2, label: 'Bonus' },
    { id: 3, label: 'Diurnă' },
    { id: 4, label: 'Alte venituri' },
  ],
  emisiuniTezaur: [
    { id: 1, label: 'Tezaur 1 an' },
    { id: 2, label: 'Tezaur 3 ani' },
    { id: 3, label: 'Tezaur 5 ani' },
    { id: 4, label: 'Fidelis RON' },
    { id: 5, label: 'Fidelis EUR' },
  ],
  credit: {
    suma: 84450, dobanda: 9.99, dae: 12.96, rata: 1786.52, asigurare: 145,
    durata: 58, comisionRambursare: 1, dataStart: '2026-06-18', soldActual: 84450,
    contract: '18099406', dataContract: '2026-05-02'
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
    '2026-05': { 'Bonuri masă': 360, 'Bonus': 1750, 'Diurnă': 1200 },
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
  scadShowAll: false,
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
      migrateCategoriiVenit(state.data);
      migrateEmisiuniTezaur(state.data);
      migrateCreditScadentar(state.data);
      migrateReguliCategorizare(state.data);
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
    if (field === 'suma') {
      u.suma = parseRON(value);
    } else if (field === 'luni') {
      var n = parseInt(value, 10);
      u.luni = (isNaN(n) || n <= 0) ? null : Math.min(600, n);
    } else if (field === 'startMonth') {
      // Validate YYYY-MM, else keep previous
      if (/^\d{4}-(0[1-9]|1[0-2])$/.test(String(value || ''))) u.startMonth = value;
    } else {
      u[field] = value;
    }
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
function addReguliCat() {
  if (!Array.isArray(state.data.reguliCategorizare)) state.data.reguliCategorizare = [];
  var cats = (state.data.categoriiVar || []);
  state.data.reguliCategorizare.push({
    id: getNextId(state.data.reguliCategorizare),
    pattern: '',
    categorie: cats.length ? cats[cats.length - 1].label : '__SKIP__'
  });
  saveData();
  render();
}
function updateReguliCat(id, field, value) {
  if (!Array.isArray(state.data.reguliCategorizare)) return;
  state.data.reguliCategorizare = state.data.reguliCategorizare.map(function(r) {
    if (r.id !== id) return r;
    var u = cloneObj(r);
    u[field] = value;
    return u;
  });
  saveData();
  render();
}
function removeReguliCat(id) {
  state.data.reguliCategorizare = (state.data.reguliCategorizare || []).filter(function(r) { return r.id !== id; });
  saveData();
  render();
}

function addEmisiune() {
  if (!Array.isArray(state.data.emisiuniTezaur)) state.data.emisiuniTezaur = [];
  state.data.emisiuniTezaur.push({ id: getNextId(state.data.emisiuniTezaur), label: '' });
  saveData();
  render();
}
function updateEmisiune(id, newLabel) {
  if (!Array.isArray(state.data.emisiuniTezaur)) return;
  state.data.emisiuniTezaur = state.data.emisiuniTezaur.map(function(e) {
    if (e.id !== id) return e;
    return { id: e.id, label: newLabel };
  });
  saveData();
  render();
}
function removeEmisiune(id) {
  state.data.emisiuniTezaur = (state.data.emisiuniTezaur || []).filter(function(e) { return e.id !== id; });
  saveData();
  render();
}

function addCategorieVenit() {
  if (!Array.isArray(state.data.categoriiVenit)) state.data.categoriiVenit = [];
  state.data.categoriiVenit.push({ id: getNextId(state.data.categoriiVenit), label: '' });
  saveData();
  render();
}
function updateCategorieVenit(id, newLabel) {
  if (!Array.isArray(state.data.categoriiVenit)) return;
  var old;
  state.data.categoriiVenit = state.data.categoriiVenit.map(function(c) {
    if (c.id !== id) return c;
    old = c.label;
    return { id: c.id, label: newLabel };
  });
  if (old && newLabel && old !== newLabel && state.data.venituri) {
    Object.keys(state.data.venituri).forEach(function(luna) {
      var m = state.data.venituri[luna];
      if (m && m[old] !== undefined) {
        m[newLabel] = m[old];
        delete m[old];
      }
    });
  }
  saveData();
  render();
}
async function removeCategorieVenit(id) {
  var cat = (state.data.categoriiVenit || []).filter(function(c) { return c.id === id; })[0];
  if (!cat) return;
  var hasData = false;
  Object.keys(state.data.venituri || {}).forEach(function(luna) {
    var m = state.data.venituri[luna];
    if (m && m[cat.label] != null && parseRON(m[cat.label]) !== 0) hasData = true;
  });
  if (hasData) {
    var alsoDelete = await showConfirm({
      title: 'Șterge categoria "' + cat.label + '"',
      body: 'Există sume introduse pentru această categorie de venit. Le ștergi sau le păstrezi orfan în date?',
      okLabel: 'Șterge tot',
      cancelLabel: 'Păstrează sumele',
      icon: 'trash-2'
    });
    if (alsoDelete) {
      Object.keys(state.data.venituri).forEach(function(luna) {
        var m = state.data.venituri[luna];
        if (m && m[cat.label] !== undefined) delete m[cat.label];
      });
    }
  }
  state.data.categoriiVenit = state.data.categoriiVenit.filter(function(c) { return c.id !== id; });
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
  var cats = Array.isArray(d.categoriiVenit) ? d.categoriiVenit : [];
  var luniCuDate = LUNI_KEYS.filter(function(l) {
    var v = d.venituri[l] || {};
    return cats.some(function(c) { return (v[c.label] || 0) > 0; });
  });
  var count = luniCuDate.length || 1;
  var variabile = {};
  var totalVar = 0;
  cats.forEach(function(c) {
    var sum = luniCuDate.reduce(function(s, l) { return s + ((d.venituri[l] || {})[c.label] || 0); }, 0) / count;
    variabile[c.label] = sum;
    totalVar += sum;
  });
  var salariuNet = (d.profil && d.profil.salariuNet) ? d.profil.salariuNet : DATI_INITIALE.profil.salariuNet;
  return { salariu: salariuNet, variabile: variabile, categorii: cats, total: salariuNet + totalVar };
}

function calcMediiCheltuieli(d) {
  var fixe = Array.isArray(d.cheltuieliFixe) ? d.cheltuieliFixe : [];
  // Average fixed = mean of monthly totals over visible months (respects start/luni windows)
  var totalFixe = LUNI_KEYS.length ? (LUNI_KEYS.reduce(function(s, l) { return s + totalFixeLuna(d, l); }, 0) / LUNI_KEYS.length) : 0;
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

function getScadentar(d) {
  return (d && d.credit && Array.isArray(d.credit.scadentar)) ? d.credit.scadentar : [];
}

function platiTrecute(scadentar, refIso) {
  return scadentar.filter(function(p) { return p.data <= refIso; });
}

function platiViitoare(scadentar, refIso) {
  return scadentar.filter(function(p) { return p.data > refIso; });
}

function soldDupaPlatiTrecute(scadentar, refIso, sumaInitiala) {
  var trec = platiTrecute(scadentar, refIso);
  if (trec.length === 0) return sumaInitiala || 0;
  return trec[trec.length - 1].soldFinal;
}

function todayIso() {
  var d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

function calcLuniRamase() {
  var scad = getScadentar(state.data);
  if (scad.length > 0) {
    return platiViitoare(scad, todayIso()).length;
  }
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
  html += statCard('wallet',       'Venituri medii',  formatRON(mediiV.total),  'Salariu + ' + ((mediiV.categorii || []).length) + ' categorii', '');
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
  (mediiV.categorii || []).forEach(function(c) {
    html += '<div class="stat-row"><span>' + esc(c.label) + '</span><span class="stat-val">' + formatRON(mediiV.variabile[c.label] || 0) + '</span></div>';
  });
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
    html += '<thead><tr><th>Denumire</th><th class="num">Sumă RON/lună</th><th>Start</th><th class="num">Luni (gol = perpetual)</th><th class="num">Total perioadă</th><th></th></tr></thead><tbody>';
    var defaultStart = (d.profil && d.profil.startMonth) || '2026-05';
    d.cheltuieliFixe.forEach(function(f) {
      var start = f.startMonth || defaultStart;
      var luni = parseInt(f.luni, 10) || 0;
      var perioada = luni > 0 ? (parseRON(f.suma) || 0) * luni : null;
      html += '<tr>';
      html += '<td><input type="text" class="input w-full" value="' + esc(f.label || '') + '" placeholder="Ex: Netflix, Card credit..." onchange="updateCheltuialaFixa(' + f.id + ', \'label\', this.value)"></td>';
      html += '<td class="num"><input type="number" class="input num w-28" value="' + (f.suma || 0) + '" onchange="updateCheltuialaFixa(' + f.id + ', \'suma\', this.value)"></td>';
      html += '<td><input type="text" class="input mono" style="width:90px;" value="' + esc(start) + '" placeholder="YYYY-MM" pattern="\\d{4}-\\d{2}" onchange="updateCheltuialaFixa(' + f.id + ', \'startMonth\', this.value)"></td>';
      html += '<td class="num"><input type="number" min="0" max="600" class="input num w-20" value="' + (luni || '') + '" placeholder="∞" onchange="updateCheltuialaFixa(' + f.id + ', \'luni\', this.value)"></td>';
      html += '<td class="num mono text-mid">' + (perioada != null ? formatRON(perioada) : '—') + '</td>';
      html += '<td><button class="btn-del" onclick="removeCheltuialaFixa(' + f.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
      html += '</tr>';
    });
    var totalFixeNow = LUNI_KEYS.length > 0 ? totalFixeLuna(d, LUNI_KEYS[0]) : 0;
    html += '</tbody><tfoot><tr><td>Total fixe în prima lună vizibilă (' + (LUNI[0] || '') + ')</td><td class="num">' + formatRON(totalFixeNow) + '</td><td colspan="4"></td></tr></tfoot>';
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

  // CATEGORII VENITURI PANEL
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="trending-up"></i> Categorii venituri</div>';
  html += '  <button class="btn-add" onclick="addCategorieVenit()"><i data-lucide="plus"></i> Adaugă categorie</button>';
  html += '</div>';
  html += '<div class="panel">';
  if (!d.categoriiVenit || d.categoriiVenit.length === 0) {
    html += '<div class="audit-empty">Nicio categorie. Salariul net fix din Profil rămâne separat — aici adaugi bonusuri, bonuri masă, diurnă, alte venituri.</div>';
  } else {
    html += '<div class="table-wrap"><table>';
    html += '<thead><tr><th>Denumire categorie</th><th class="num">Total mediu / lună</th><th></th></tr></thead><tbody>';
    var mediiVen = calcMediiVenituri(d);
    d.categoriiVenit.forEach(function(c) {
      var avg = mediiVen.variabile[c.label] || 0;
      html += '<tr>';
      html += '<td><input type="text" class="input w-full" value="' + esc(c.label || '') + '" placeholder="Ex: Bonus, Diurna, Cadou..." onchange="updateCategorieVenit(' + c.id + ', this.value)"></td>';
      html += '<td class="num mono text-mid">' + formatRON(avg) + '</td>';
      html += '<td><button class="btn-del" onclick="removeCategorieVenit(' + c.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += '<div class="info-box" style="margin-top:0.85rem;">';
    html += '<i data-lucide="info"></i>';
    html += '<div>Salariul net fix vine din câmpul din "Profil". Categoriile de aici se completează lunar în tabul Venituri (ex: bonusuri variabile, comisioane, cadouri).</div>';
    html += '</div>';
  }
  html += '</div></div>';

  // REGULI CATEGORIZARE AUTO
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="zap"></i> Reguli categorizare automată (import bancar)</div>';
  html += '  <button class="btn-add" onclick="addReguliCat()"><i data-lucide="plus"></i> Adaugă regulă</button>';
  html += '</div>';
  html += '<div class="panel">';
  if (!d.reguliCategorizare || d.reguliCategorizare.length === 0) {
    html += '<div class="audit-empty">Nicio regulă. La import bancar tranzacțiile vor fi puse în "Alte" până când adăugi reguli.</div>';
  } else {
    var categoriiTinta = ['__SKIP__'].concat(
      (d.cheltuieliFixe || []).map(function(c) { return c.label; }),
      (d.categoriiVar || []).map(function(c) { return c.label; })
    );
    html += '<div class="table-wrap"><table>';
    html += '<thead><tr><th>Pattern (regex)</th><th>Categorie țintă</th><th></th></tr></thead><tbody>';
    d.reguliCategorizare.forEach(function(r) {
      html += '<tr>';
      html += '<td><input type="text" class="input mono w-full" value="' + esc(r.pattern || '') + '" placeholder="Ex: KAUFLAND|AUCHAN" onchange="updateReguliCat(' + r.id + ', \'pattern\', this.value)"></td>';
      html += '<td><select class="select cs-enhance" onchange="updateReguliCat(' + r.id + ', \'categorie\', this.value)">';
      categoriiTinta.forEach(function(c) {
        var lbl = c === '__SKIP__' ? '— ignoră —' : c;
        html += '<option value="' + esc(c) + '"' + (r.categorie === c ? ' selected' : '') + '>' + esc(lbl) + '</option>';
      });
      html += '</select></td>';
      html += '<td><button class="btn-del" onclick="removeReguliCat(' + r.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += '<div class="info-box" style="margin-top:0.85rem;">';
    html += '<i data-lucide="info"></i>';
    html += '<div>Pattern-urile sunt regex JavaScript case-insensitive, testate pe descrierea completă a tranzacției (detalii + beneficiar + locație). Categoria "— ignoră —" sare peste tranzacția respectivă (ex: subscrieri Tezaur care nu sunt cheltuieli).</div>';
    html += '</div>';
  }
  html += '</div></div>';

  // EMISIUNI TEZAUR PANEL
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="coins"></i> Emisiuni Tezaur disponibile</div>';
  html += '  <button class="btn-add" onclick="addEmisiune()"><i data-lucide="plus"></i> Adaugă emisiune</button>';
  html += '</div>';
  html += '<div class="panel">';
  if (!d.emisiuniTezaur || d.emisiuniTezaur.length === 0) {
    html += '<div class="audit-empty">Nicio emisiune. Apasă "Adaugă" pentru a defini emisiuni vizibile în dropdown-ul Tezaur.</div>';
  } else {
    html += '<div class="table-wrap"><table>';
    html += '<thead><tr><th>Denumire emisiune</th><th></th></tr></thead><tbody>';
    d.emisiuniTezaur.forEach(function(e) {
      html += '<tr>';
      html += '<td><input type="text" class="input w-full" value="' + esc(e.label || '') + '" placeholder="Ex: Tezaur 1 an, Fidelis EUR..." onchange="updateEmisiune(' + e.id + ', this.value)"></td>';
      html += '<td><button class="btn-del" onclick="removeEmisiune(' + e.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += '<div class="info-box" style="margin-top:0.85rem;">';
    html += '<i data-lucide="info"></i>';
    html += '<div>Lista apare în dropdown-ul "Emisiune" din tabul Fond urgență → Titluri Tezaur. Subscrierile existente păstrează emisiunea inițială chiar dacă o ștergi din listă.</div>';
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
  var scad = getScadentar(d);
  var today = todayIso();
  var trec = platiTrecute(scad, today);
  var viit = platiViitoare(scad, today);
  var soldEstimat = soldDupaPlatiTrecute(scad, today, cr.suma);
  var totalPlatit = trec.reduce(function(s, p) { return s + (p.suma || 0) + (p.asigurare || 0); }, 0);
  var totalRamas = viit.reduce(function(s, p) { return s + (p.suma || 0) + (p.asigurare || 0); }, 0);
  var totalDobandaRamasa = viit.reduce(function(s, p) { return s + (p.dobanda || 0); }, 0);

  var html = '';

  // Stat cards
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="landmark"></i> Credit activ — scadenţar ING Home\'Bank</div></div>';
  html += '<div class="stat-grid">';
  html += statCard('banknote', 'Sold rămas', formatRON(soldEstimat), trec.length + ' / ' + scad.length + ' rate plătite', 'danger');
  html += statCard('calendar-clock', 'Luni rămase', viit.length, 'din ' + scad.length + ' total', 'warning');
  html += statCard('coins', 'Total rămas de plătit', formatRON(totalRamas), 'capital + dobandă + asigurare', 'danger');
  html += statCard('trending-down', 'Dobândă viitoare', formatRON(totalDobandaRamasa), 'rămasă până la final', 'warning');
  html += '</div></div>';

  // Two-column: details + simulare
  html += '<div class="section">';
  html += '<div class="stat-grid" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));">';

  // Detalii
  html += '<div class="panel danger">';
  html += '<div class="panel-head"><div class="panel-title"><i data-lucide="file-text"></i> Detalii credit</div></div>';
  if (cr.contract) html += '<div class="stat-row"><span>Contract</span><span class="mono">' + esc(cr.contract) + ' / ' + esc(cr.dataContract || '') + '</span></div>';
  html += '<div class="stat-row"><span>Sumă inițială</span><span class="stat-val danger">' + formatRON(cr.suma) + '</span></div>';
  html += '<div class="stat-row"><span>Sold estimat azi</span><span class="stat-val danger">' + formatRON(soldEstimat) + '</span></div>';
  html += '<div class="stat-row"><span>Sold actual (manual)</span>';
  html += '<input type="number" class="input num w-28" value="' + cr.soldActual + '" onchange="updateCreditSold(this.value)"></div>';
  html += '<div class="stat-row"><span>Dobândă anuală</span><span class="mono">' + cr.dobanda + ' %</span></div>';
  html += '<div class="stat-row"><span>DAE</span><span class="mono">' + cr.dae + ' %</span></div>';
  html += '<div class="stat-row"><span>Rată standard</span><span class="stat-val danger">' + formatRON(cr.rata) + '</span></div>';
  html += '<div class="stat-row"><span>Asigurare curentă</span><span class="stat-val danger">' + formatRON(viit[0] ? viit[0].asigurare : 0) + '</span></div>';
  html += '<div class="stat-row"><span>Comision rambursare</span><span class="mono">' + cr.comisionRambursare + ' %</span></div>';
  html += '<div class="stat-row"><span>Durată totală</span><span class="mono">' + scad.length + ' rate</span></div>';
  html += '<div class="stat-row"><span>Prima rată</span><span class="mono">' + esc(scad[0] ? scad[0].data : '—') + '</span></div>';
  html += '<div class="stat-row"><span>Ultima rată</span><span class="mono">' + esc(scad[scad.length - 1] ? scad[scad.length - 1].data : '—') + '</span></div>';
  html += '</div>';

  // Simulare
  html += '<div class="panel accent">';
  html += '<div class="panel-head"><div class="panel-title"><i data-lucide="calculator"></i> Simulare rambursare anticipată</div></div>';
  html += '<div class="field"><label class="field-label">Sold credit curent (RON)</label>';
  html += '<input type="number" id="sim-sold" class="input num w-full" value="' + soldEstimat.toFixed(2) + '" oninput="recalcSimulare()"></div>';
  html += '<div class="field"><label class="field-label">Sumă rambursare (RON)</label>';
  html += '<input type="number" id="sim-suma" class="input num w-full" value="5000" oninput="recalcSimulare()"></div>';
  html += '<div class="field"><label class="field-label">Luni rămase</label>';
  html += '<input type="number" id="sim-luni" class="input num w-full" value="' + viit.length + '" oninput="recalcSimulare()"></div>';
  html += '<div id="sim-rezultat" class="sim-result"></div>';
  html += '</div>';

  html += '</div></div>';

  // Scadentar real
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="calendar"></i> Scadenţar complet (ING Home\'Bank)</div>';
  html += '  <div style="display:flex;gap:0.5rem;">';
  html += '    <button class="btn-back" onclick="toggleScadentarVizibil()" id="btn-scad-vizibil"><i data-lucide="filter"></i> ' + (state.scadShowAll ? 'Doar rămase' : 'Toate') + '</button>';
  html += '  </div>';
  html += '</div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>#</th><th>Data</th><th class="num">Rată</th><th class="num">Dobândă</th><th class="num">Capital</th><th class="num">Sold rămas</th><th class="num">Asigurare</th><th class="num">Total</th><th>Status</th></tr></thead><tbody>';
  scad.forEach(function(p, i) {
    var isPast = p.data <= today;
    if (!state.scadShowAll && isPast) return;
    var total = (p.suma || 0) + (p.asigurare || 0);
    var statusBadge = isPast
      ? '<span class="tag" style="background:var(--success-soft);color:var(--success);"><i data-lucide="check"></i> plătită</span>'
      : (i === trec.length
        ? '<span class="tag" style="background:var(--warning-soft);color:var(--warning);"><i data-lucide="clock"></i> următoarea</span>'
        : '<span class="tag" style="background:var(--bg-elev3);color:var(--text-mid);">viitoare</span>');
    var trClass = isPast ? ' style="opacity:0.55;"' : (i === trec.length ? ' style="background:var(--accent-soft);"' : '');
    html += '<tr' + trClass + '>';
    html += '<td class="muted mono">' + (i + 1) + '</td>';
    html += '<td class="mono">' + esc(p.data) + '</td>';
    html += '<td class="num neg">' + formatRON(p.suma) + '</td>';
    html += '<td class="num neg">' + formatRON(p.dobanda) + '</td>';
    html += '<td class="num">' + formatRON(p.principal) + '</td>';
    html += '<td class="num accent">' + formatRON(p.soldFinal) + '</td>';
    html += '<td class="num">' + formatRON(p.asigurare) + '</td>';
    html += '<td class="num neg">' + formatRON(total) + '</td>';
    html += '<td>' + statusBadge + '</td>';
    html += '</tr>';
  });
  html += '</tbody><tfoot>';
  html += '<tr><td colspan="2">Total plătit până azi</td><td class="num">' + formatRON(trec.reduce(function(s,p){return s+(p.suma||0);},0)) + '</td><td class="num">' + formatRON(trec.reduce(function(s,p){return s+(p.dobanda||0);},0)) + '</td><td class="num">' + formatRON(trec.reduce(function(s,p){return s+(p.principal||0);},0)) + '</td><td></td><td class="num">' + formatRON(trec.reduce(function(s,p){return s+(p.asigurare||0);},0)) + '</td><td class="num">' + formatRON(totalPlatit) + '</td><td></td></tr>';
  html += '<tr><td colspan="2">Total rămas de plătit</td><td class="num">' + formatRON(viit.reduce(function(s,p){return s+(p.suma||0);},0)) + '</td><td class="num">' + formatRON(totalDobandaRamasa) + '</td><td class="num">' + formatRON(viit.reduce(function(s,p){return s+(p.principal||0);},0)) + '</td><td></td><td class="num">' + formatRON(viit.reduce(function(s,p){return s+(p.asigurare||0);},0)) + '</td><td class="num">' + formatRON(totalRamas) + '</td><td></td></tr>';
  html += '</tfoot></table></div></div></div>';

  return html;
}

function toggleScadentarVizibil() {
  state.scadShowAll = !state.scadShowAll;
  render();
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
    var emisiuniList = (d.emisiuniTezaur || []).map(function(e) { return e.label; });
    if (t.emisiune && emisiuniList.indexOf(t.emisiune) < 0) emisiuniList.unshift(t.emisiune);
    html += '<td><select class="select cs-enhance" onchange="updateTezaur(' + t.id + ', \'emisiune\', this.value)">';
    emisiuniList.forEach(function(opt) {
      html += '<option value="' + esc(opt) + '"' + (t.emisiune === opt ? ' selected' : '') + '>' + esc(opt) + '</option>';
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

  (d.categoriiVenit || []).forEach(function(c) {
    var label = c.label || '';
    var labelAttr = label.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    html += '<tr><td class="muted">' + esc(label) + '</td>';
    LUNI_KEYS.forEach(function(l) {
      var val = (d.venituri[l] || {})[label] || '';
      html += '<td class="num"><input type="number" class="input num w-20" value="' + val + '" onchange="updateVenit(\'' + l + '\', \'' + labelAttr + '\', this.value)"></td>';
    });
    html += '</tr>';
  });

  var totalsV = LUNI_KEYS.map(function(l) {
    var v = d.venituri[l] || {};
    return (d.categoriiVenit || []).reduce(function(s, c) { return s + (v[c.label] || 0); }, salariu);
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
    LUNI_KEYS.forEach(function(lk) {
      if (cheltuialaFixaActiva(f, lk)) {
        html += '<td class="num neg">' + formatRON(f.suma) + '</td>';
      } else {
        html += '<td class="num text-dim">—</td>';
      }
    });
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

  var totalsC = LUNI_KEYS.map(function(l) {
    var c = d.cheltuieli[l] || {};
    return totalFixeLuna(d, l) + Object.values(c).reduce(function(s, v) { return s + v; }, 0);
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
      html += '      <button class="icon-btn" onclick="showImportModal()" title="Importă tranzacții bancare"><i data-lucide="upload"></i></button>';
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
async function exportCSV() {
  await showExportModal();
}

function showExportModal() {
  return new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    var optsHTML = '';
    LUNI_KEYS.forEach(function(k, i) {
      optsHTML += '<option value="' + k + '">' + esc(LUNI[i]) + ' (' + k + ')</option>';
    });
    overlay.innerHTML =
      '<div class="modal" role="dialog" aria-modal="true" style="max-width:480px;">' +
      '  <div class="modal-title"><i data-lucide="download"></i> Export CSV</div>' +
      '  <div class="modal-body">' +
      '    <div class="field"><label class="field-label"><input type="radio" name="exp-mode" value="total" checked> Export complet (toate ' + LUNI_KEYS.length + ' luni vizibile)</label></div>' +
      '    <div class="field"><label class="field-label"><input type="radio" name="exp-mode" value="range"> Export pe perioadă</label></div>' +
      '    <div id="range-fields" style="display:flex;gap:0.5rem;opacity:0.4;pointer-events:none;">' +
      '      <div class="field" style="flex:1;"><label class="field-label">De la</label><select id="exp-from" class="select w-full">' + optsHTML + '</select></div>' +
      '      <div class="field" style="flex:1;"><label class="field-label">Până la</label><select id="exp-to" class="select w-full">' + optsHTML + '</select></div>' +
      '    </div>' +
      '  </div>' +
      '  <div class="modal-actions">' +
      '    <button class="modal-btn" data-act="cancel">Anulează</button>' +
      '    <button class="modal-btn primary" data-act="ok">Descarcă</button>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(overlay);
    refreshIcons();
    var toSel = overlay.querySelector('#exp-to');
    if (toSel) toSel.value = LUNI_KEYS[LUNI_KEYS.length - 1];
    var radios = overlay.querySelectorAll('input[name="exp-mode"]');
    var rangeFields = overlay.querySelector('#range-fields');
    radios.forEach(function(r) {
      r.addEventListener('change', function() {
        if (overlay.querySelector('input[name="exp-mode"]:checked').value === 'range') {
          rangeFields.style.opacity = 1;
          rangeFields.style.pointerEvents = 'auto';
        } else {
          rangeFields.style.opacity = 0.4;
          rangeFields.style.pointerEvents = 'none';
        }
      });
    });

    function close(val) {
      document.body.removeChild(overlay);
      document.removeEventListener('keydown', onKey);
      resolve(val);
    }
    function onKey(e) { if (e.key === 'Escape') close(false); }
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) return close(false);
      var act = e.target.closest('[data-act]');
      if (!act) return;
      if (act.dataset.act === 'cancel') return close(false);
      var mode = overlay.querySelector('input[name="exp-mode"]:checked').value;
      var keys = LUNI_KEYS.slice();
      var labels = LUNI.slice();
      if (mode === 'range') {
        var from = overlay.querySelector('#exp-from').value;
        var to = overlay.querySelector('#exp-to').value;
        if (from > to) { var tmp = from; from = to; to = tmp; }
        var newKeys = [], newLabels = [];
        LUNI_KEYS.forEach(function(k, i) { if (k >= from && k <= to) { newKeys.push(k); newLabels.push(LUNI[i]); } });
        keys = newKeys; labels = newLabels;
      }
      if (keys.length === 0) { alert('Interval gol — alege alte luni.'); return; }
      generateAndDownloadCSV(keys, labels);
      close(true);
    });
    document.addEventListener('keydown', onKey);
  });
}

function generateAndDownloadCSV(keys, labels) {
  var d = state.data;
  var lines = [];
  var range = labels.length === LUNI.length ? 'total' : (keys[0] + ' → ' + keys[keys.length - 1]);
  lines.push('Budget Tracker - ' + (d.profil.nume || 'Ion') + ' - Export ' + range);

  lines.push('');
  lines.push('VENITURI');
  lines.push('Categorie,' + labels.join(','));
  lines.push('Salariu net,' + labels.map(function() { return d.profil.salariuNet || 0; }).join(','));
  (d.categoriiVenit || []).forEach(function(c) {
    var label = c.label || '';
    lines.push(label.replace(/,/g, ' ') + ',' + keys.map(function(l) { return (d.venituri[l] || {})[label] || 0; }).join(','));
  });

  lines.push('');
  lines.push('CHELTUIELI');
  lines.push('Categorie,' + labels.join(','));
  (d.cheltuieliFixe || []).forEach(function(f) {
    var row = keys.map(function(lk) { return cheltuialaFixaActiva(f, lk) ? (f.suma || 0) : 0; }).join(',');
    lines.push((f.label || '').replace(/,/g, ' ') + ',' + row);
  });
  (d.categoriiVar || []).forEach(function(c) {
    var label = c.label || '';
    lines.push(label.replace(/,/g, ' ') + ',' + keys.map(function(l) { return (d.cheltuieli[l] || {})[label] || 0; }).join(','));
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
  var suffix = (labels.length === LUNI.length) ? 'total' : (keys[0] + '_' + keys[keys.length - 1]);
  a.download = 'budget-tracker-' + ((d.profil.nume || 'ion').toLowerCase()) + '-' + suffix + '.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ====================================================================
// BANK CSV IMPORT (ING Home'Bank format)
// ====================================================================

// Simple RFC-4180-ish CSV row splitter: handles quoted fields with embedded commas
function csvSplit(line) {
  var out = [], cur = '', inQ = false;
  for (var i = 0; i < line.length; i++) {
    var ch = line[i];
    if (inQ) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') { inQ = false; }
      else { cur += ch; }
    } else {
      if (ch === '"') { inQ = true; }
      else if (ch === ',') { out.push(cur); cur = ''; }
      else { cur += ch; }
    }
  }
  out.push(cur);
  return out;
}

// "19 mai 2026" -> "2026-05-19"
var LUNI_RO_NUM = { 'ian':1,'feb':2,'mar':3,'apr':4,'mai':5,'iun':6,'iul':7,'aug':8,'sep':9,'oct':10,'noi':11,'dec':12,
  'ianuarie':1,'februarie':2,'martie':3,'aprilie':4,'iunie':6,'iulie':7,'septembrie':9,'octombrie':10,'noiembrie':11,'decembrie':12 };
function parseDataIngRo(s) {
  if (!s) return null;
  var m = String(s).trim().match(/^(\d{1,2})\s+([a-zăâîșțA-ZĂÂÎȘȚ]+)\s+(\d{4})$/);
  if (!m) return null;
  var d = parseInt(m[1], 10);
  var monthName = m[2].toLowerCase().replace(/[ăâîșț]/g, function(c) { return {'ă':'a','â':'a','î':'i','ș':'s','ț':'t'}[c]; });
  var mo = LUNI_RO_NUM[monthName.substring(0,3)] || LUNI_RO_NUM[monthName];
  if (!mo) return null;
  var y = parseInt(m[3], 10);
  return y + '-' + String(mo).padStart(2, '0') + '-' + String(d).padStart(2, '0');
}

// Parse ING transaction export CSV. Returns [{ data, dataIso, detalii, beneficiar, tranzactieAt, suma, sens }]
function parseIngCsv(text) {
  var lines = text.split(/\r?\n/);
  var tx = [];
  var current = null;
  var headerSeen = false;
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    if (!line.trim()) continue;
    var cols = csvSplit(line);
    if (!headerSeen) {
      if (cols[0] && /^Data$/i.test(cols[0].trim())) { headerSeen = true; continue; }
      continue;
    }
    // Tranzactie row: A=data, D=detalii, E=debit, G=credit, H=balanta
    var dataCol = (cols[0] || '').trim();
    if (parseDataIngRo(dataCol)) {
      if (current) tx.push(current);
      var debit = parseRON(cols[4] || '0');
      var credit = parseRON(cols[6] || '0');
      var sens = debit > 0 ? 'debit' : (credit > 0 ? 'credit' : 'zero');
      current = {
        data: dataCol,
        dataIso: parseDataIngRo(dataCol),
        detalii: (cols[3] || '').trim(),
        beneficiar: '',
        tranzactieAt: '',
        descriereFull: (cols[3] || '').trim(),
        suma: debit > 0 ? debit : credit,
        sens: sens,
      };
    } else if (current) {
      // Detail row: column D carries metadata
      var meta = (cols[3] || '').trim();
      if (!meta) continue;
      current.descriereFull += ' | ' + meta;
      if (/^Beneficiar:/i.test(meta)) current.beneficiar = meta.replace(/^Beneficiar:/i, '').trim();
      else if (/^Tranzactie la:/i.test(meta)) current.tranzactieAt = meta.replace(/^Tranzactie la:/i, '').trim();
    }
    // Stop at footer rows (Roxana Petria / Alexandra Ilie etc.)
    if (cols[1] && /Roxana Petria|Alexandra Ilie|Sef Serviciu/i.test(cols[1])) {
      if (current) { tx.push(current); current = null; }
    }
  }
  if (current) tx.push(current);
  return tx;
}

function categorizeAuto(tx, reguli) {
  var hay = (tx.descriereFull || '').toUpperCase();
  for (var i = 0; i < reguli.length; i++) {
    var r = reguli[i];
    var p = r.pattern;
    if (!p) continue;
    try {
      if (new RegExp(p, 'i').test(hay)) return r.categorie || null;
    } catch (e) { /* invalid regex — skip */ }
  }
  return null;
}

async function showImportModal() {
  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML =
    '<div class="modal" role="dialog" aria-modal="true" style="max-width:920px;width:95%;">' +
    '  <div class="modal-title"><i data-lucide="upload"></i> Importă tranzacții bancare (CSV ING)</div>' +
    '  <div class="modal-body">' +
    '    <div class="field"><label class="field-label">Selectează fișierul CSV exportat din ING Home\'Bank</label>' +
    '      <input type="file" id="imp-file" accept=".csv,text/csv" class="input w-full"></div>' +
    '    <div id="imp-summary" class="info-box" style="display:none;"><i data-lucide="info"></i><div></div></div>' +
    '    <div id="imp-preview" style="max-height:50vh;overflow:auto;margin-top:0.75rem;"></div>' +
    '  </div>' +
    '  <div class="modal-actions">' +
    '    <button class="modal-btn" data-act="cancel">Anulează</button>' +
    '    <button class="modal-btn primary" data-act="apply" disabled>Aplică în buget</button>' +
    '  </div>' +
    '</div>';
  document.body.appendChild(overlay);
  refreshIcons();

  var parsed = [];
  var fileInput = overlay.querySelector('#imp-file');
  var summary = overlay.querySelector('#imp-summary');
  var preview = overlay.querySelector('#imp-preview');
  var applyBtn = overlay.querySelector('[data-act="apply"]');

  function close() {
    document.body.removeChild(overlay);
    document.removeEventListener('keydown', onKey);
  }
  function onKey(e) { if (e.key === 'Escape') close(); }

  fileInput.addEventListener('change', function() {
    var f = fileInput.files[0];
    if (!f) return;
    var reader = new FileReader();
    reader.onload = function() {
      try {
        var text = reader.result;
        parsed = parseIngCsv(text).filter(function(t) { return t.sens === 'debit' && t.suma > 0; });
        var reguli = state.data.reguliCategorizare || [];
        var categories = (state.data.categoriiVar || []).map(function(c) { return c.label; })
          .concat((state.data.cheltuieliFixe || []).map(function(c) { return c.label; }));
        parsed.forEach(function(t) {
          var auto = categorizeAuto(t, reguli);
          t.categorie = (auto && categories.indexOf(auto) >= 0) ? auto : (auto || categories[categories.length - 1] || 'Alte');
          t.skip = (auto === '__SKIP__');
          if (t.skip) t.categorie = '__SKIP__';
        });
        renderPreview();
      } catch (err) {
        preview.innerHTML = '<div class="callout danger"><i data-lucide="alert-triangle"></i> Eroare la parsare: ' + esc(String(err.message || err)) + '</div>';
        refreshIcons();
      }
    };
    reader.readAsText(f, 'utf-8');
  });

  function renderPreview() {
    var allCategories = ['__SKIP__'].concat(
      (state.data.cheltuieliFixe || []).map(function(c) { return c.label; }),
      (state.data.categoriiVar || []).map(function(c) { return c.label; })
    );
    var summByMonthCat = {};
    var nSkip = 0, nApply = 0;
    parsed.forEach(function(t) {
      if (t.categorie === '__SKIP__') { nSkip++; return; }
      var mk = t.dataIso ? t.dataIso.substring(0, 7) : 'altele';
      summByMonthCat[mk] = summByMonthCat[mk] || {};
      summByMonthCat[mk][t.categorie] = (summByMonthCat[mk][t.categorie] || 0) + t.suma;
      nApply++;
    });
    summary.style.display = 'flex';
    summary.querySelector('div').innerHTML =
      '<strong>' + parsed.length + '</strong> tranzacții debit găsite' +
      ' <span class="sep">·</span> <strong>' + nApply + '</strong> de aplicat' +
      ' <span class="sep">·</span> <strong>' + nSkip + '</strong> ignorate (Tezaur / __SKIP__)';
    applyBtn.disabled = (nApply === 0);

    var h = '<div class="table-wrap"><table>';
    h += '<thead><tr><th>Data</th><th>Descriere</th><th class="num">Sumă</th><th>Categorie</th></tr></thead><tbody>';
    parsed.forEach(function(t, idx) {
      var descShort = t.detalii + (t.tranzactieAt ? ' — ' + t.tranzactieAt : (t.beneficiar ? ' — ' + t.beneficiar : ''));
      h += '<tr' + (t.categorie === '__SKIP__' ? ' style="opacity:0.45;"' : '') + '>';
      h += '<td class="mono">' + esc(t.dataIso || t.data) + '</td>';
      h += '<td style="max-width:340px;font-size:0.78rem;">' + esc(descShort) + '</td>';
      h += '<td class="num neg">' + formatRON(t.suma) + '</td>';
      h += '<td><select class="select" data-imp-cat="' + idx + '">';
      allCategories.forEach(function(c) {
        var lbl = c === '__SKIP__' ? '— ignoră —' : c;
        h += '<option value="' + esc(c) + '"' + (t.categorie === c ? ' selected' : '') + '>' + esc(lbl) + '</option>';
      });
      h += '</select></td>';
      h += '</tr>';
    });
    h += '</tbody></table></div>';
    preview.innerHTML = h;
    preview.querySelectorAll('select[data-imp-cat]').forEach(function(sel) {
      sel.addEventListener('change', function() {
        var idx = parseInt(sel.dataset.impCat, 10);
        parsed[idx].categorie = sel.value;
        parsed[idx].skip = sel.value === '__SKIP__';
        renderPreview();
      });
    });
    refreshIcons();
  }

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) return close();
    var act = e.target.closest('[data-act]');
    if (!act) return;
    if (act.dataset.act === 'cancel') return close();
    if (act.dataset.act === 'apply') {
      var fixedLabels = (state.data.cheltuieliFixe || []).reduce(function(s, c) { s[c.label] = true; return s; }, {});
      var added = 0;
      parsed.forEach(function(t) {
        if (t.categorie === '__SKIP__' || fixedLabels[t.categorie]) return; // skip ratele fixe — ele se sumează automat
        var mk = t.dataIso ? t.dataIso.substring(0, 7) : null;
        if (!mk) return;
        if (!state.data.cheltuieli[mk]) state.data.cheltuieli[mk] = {};
        state.data.cheltuieli[mk][t.categorie] = (state.data.cheltuieli[mk][t.categorie] || 0) + t.suma;
        added++;
      });
      saveData();
      close();
      render();
      setTimeout(function() {
        showConfirm({
          title: 'Import complet',
          body: added + ' tranzacții adăugate în buget. Cheltuielile fixe (chirie, rată credit) au fost păstrate intacte — sunt deja înregistrate prin rândul fix lunar.',
          okLabel: 'OK',
          cancelLabel: '',
          icon: 'check-circle'
        });
      }, 100);
    }
  });
  document.addEventListener('keydown', onKey);
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
