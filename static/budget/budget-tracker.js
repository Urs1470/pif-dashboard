// ====================================================================
// Budget Tracker - Vanilla JS (PIF design system)
// ====================================================================

var LUNI_LABELS_RO = ['Ian','Feb','Mar','Apr','Mai','Iun','Iul','Aug','Sep','Oct','Noi','Dec'];
var LUNI = ['Mai','Iun','Iul','Aug','Sep','Oct','Noi','Dec']; // recomputed by refreshLuni()
var LUNI_KEYS = ['2026-05','2026-06','2026-07','2026-08','2026-09','2026-10','2026-11','2026-12']; // recomputed
var LUNI_COUNT = 12; // default; overridden by d.profil.numarLuni
var CHELTUIELI_VARIABILE_DEFAULT = [
  'Alimente', 'Mâncare restaurant', 'Transport', 'Utilități & facturi',
  'Sănătate & îngrijire', 'Îmbrăcăminte', 'Casă & întreținere',
  'Divertisment & timp liber', 'Abonamente', 'Educație & dezvoltare',
  'Cadouri & evenimente', 'Călătorii & vacanțe', 'Taxe & asigurări',
  'Alte credite', 'Alte'
];
var CATEGORII_VENIT_DEFAULT = ['Bonuri de masă', 'Bonus & prime', 'Diurnă & deconturi', 'Dobânzi & dividende', 'Alte venituri'];

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

// Track which transaction refs have already been imported
function migrateImportedRefs(data) {
  if (!data) return;
  if (!Array.isArray(data.importedRefs)) data.importedRefs = [];
}

// Goals / saving objectives
function migrateGoals(data) {
  if (!data) return;
  if (!Array.isArray(data.goals)) data.goals = [];
}

// Import sessions history (for undo). Kept ~6 months.
function migrateImportHistory(data) {
  if (!data) return;
  if (!Array.isArray(data.importHistory)) data.importHistory = [];
}

// Drop import sessions older than 6 months
function pruneImportHistory(data) {
  if (!data || !Array.isArray(data.importHistory)) return;
  var cutoff = Date.now() - 182 * 24 * 60 * 60 * 1000;
  data.importHistory = data.importHistory.filter(function(imp) {
    var t = imp.ts ? new Date(imp.ts).getTime() : 0;
    return t >= cutoff;
  });
}

// ETF investments (manual tracking)
function migrateEtf(data) {
  if (!data) return;
  if (!Array.isArray(data.etf)) data.etf = [];
}

// VWCE-focused tracking with live price proxy
function migrateVwce(data) {
  if (!data) return;
  if (!data.vwce || typeof data.vwce !== 'object') {
    data.vwce = {
      symbol: 'VWCE.DE',
      isin: 'IE00BK5BQT80',
      nume: 'Vanguard FTSE All-World UCITS ETF',
      exchange: 'XETRA',
      currency: 'EUR',
      tranzactii: [],
      alimentari: [],
      pretCurent: 0,
      previousClose: 0,
      changePct: 0,
      lastUpdate: null,
      lastUpdateLocal: null,
    };
  }
  if (!Array.isArray(data.vwce.tranzactii)) data.vwce.tranzactii = [];
  if (!Array.isArray(data.vwce.alimentari)) data.vwce.alimentari = [];
}

// Special import categories that route money to investments instead of expenses
var IMPORT_SPECIAL_CATS = ['__SKIP__', '__TEZAUR__', '__TRADEVILLE__'];
function specialCatLabel(c) {
  return {
    '__SKIP__': '— ignoră —',
    '__TEZAUR__': '→ Subscriere Tezaur',
    '__TRADEVILLE__': '→ Alimentare Tradeville'
  }[c] || c;
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
  var mapping = { bonuri: 'Bonuri de masă', bonus: 'Bonus & prime', diurna: 'Diurnă & deconturi' };
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

// Guarantee a given variable category exists (for retro-fitting new defaults
// onto already-saved data). Idempotent — case-insensitive match.
function ensureCategorieVar(data, label) {
  if (!data) return;
  if (!Array.isArray(data.categoriiVar)) data.categoriiVar = [];
  var exists = data.categoriiVar.some(function(c) {
    return ((c && c.label) || '').toLowerCase() === label.toLowerCase();
  });
  if (!exists) {
    data.categoriiVar.push({ id: getNextId(data.categoriiVar), label: label });
  }
}

// Rename a variable expense category and migrate its data + rules
function renameCategorieVar(data, oldLabel, newLabel) {
  if (!data || !Array.isArray(data.categoriiVar)) return;
  var found = false;
  data.categoriiVar.forEach(function(c) { if (c && c.label === oldLabel) { c.label = newLabel; found = true; } });
  if (!found) return;
  Object.keys(data.cheltuieli || {}).forEach(function(luna) {
    var m = data.cheltuieli[luna];
    if (m && m[oldLabel] !== undefined) {
      m[newLabel] = (m[newLabel] || 0) + m[oldLabel];
      delete m[oldLabel];
    }
  });
  (data.reguliCategorizare || []).forEach(function(r) { if (r && r.categorie === oldLabel) r.categorie = newLabel; });
}

// Rename an income category and migrate its data + rules
function renameCategorieVenit(data, oldLabel, newLabel) {
  if (!data || !Array.isArray(data.categoriiVenit)) return;
  var found = false;
  data.categoriiVenit.forEach(function(c) { if (c && c.label === oldLabel) { c.label = newLabel; found = true; } });
  if (!found) return;
  Object.keys(data.venituri || {}).forEach(function(luna) {
    var m = data.venituri[luna];
    if (m && m[oldLabel] !== undefined) {
      m[newLabel] = (m[newLabel] || 0) + m[oldLabel];
      delete m[oldLabel];
    }
  });
  (data.reguliCategorizare || []).forEach(function(r) { if (r && r.categorie === oldLabel) r.categorie = newLabel; });
}

// One-shot category structure alignment (v2). Renames legacy categories to the
// balanced structure and adds the missing ones. Guarded by data.categoriesAligned.
function migrateCategoriesV2(data) {
  if (!data || data.categoriesAligned) return;
  // Expense renames
  renameCategorieVar(data, 'Facturi', 'Utilități & facturi');
  renameCategorieVar(data, 'Sănătate', 'Sănătate & îngrijire');
  renameCategorieVar(data, 'Divertisment', 'Divertisment & timp liber');
  // Income renames
  renameCategorieVenit(data, 'Bonuri masă', 'Bonuri de masă');
  renameCategorieVenit(data, 'Bonus', 'Bonus & prime');
  renameCategorieVenit(data, 'Diurnă', 'Diurnă & deconturi');
  // New expense categories
  ['Casă & întreținere', 'Educație & dezvoltare', 'Cadouri & evenimente',
   'Călătorii & vacanțe', 'Taxe & asigurări'].forEach(function(label) {
    ensureCategorieVar(data, label);
  });
  // New income category
  ensureCategorieVenit(data, 'Dobânzi & dividende');
  data.categoriesAligned = true;
}

// Guarantee an income category exists. Idempotent — case-insensitive match.
function ensureCategorieVenit(data, label) {
  if (!data) return;
  if (!Array.isArray(data.categoriiVenit)) data.categoriiVenit = [];
  var exists = data.categoriiVenit.some(function(c) {
    return ((c && c.label) || '').toLowerCase() === label.toLowerCase();
  });
  if (!exists) data.categoriiVenit.push({ id: getNextId(data.categoriiVenit), label: label });
}

// Guarantee a categorisation rule routing to `categorie` exists. Idempotent —
// skips if any rule already targets that category. `prepend` gives the new
// rule priority over older rules during categorizeAuto's first-match scan.
function ensureRegula(data, pattern, categorie, prepend) {
  if (!data) return;
  if (!Array.isArray(data.reguliCategorizare)) data.reguliCategorizare = [];
  var exists = data.reguliCategorizare.some(function(r) { return r && r.categorie === categorie; });
  if (exists) return;
  var rule = { id: getNextId(data.reguliCategorizare), pattern: pattern, categorie: categorie };
  if (prepend) data.reguliCategorizare.unshift(rule);
  else data.reguliCategorizare.push(rule);
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
// Round to 2 decimals, killing binary-float drift (0.1+0.2 etc.)
function round2(n) {
  if (typeof n !== 'number' || !isFinite(n)) return 0;
  return Math.round((n + (n >= 0 ? 1 : -1) * Number.EPSILON) * 100) / 100;
}

// Robust money parser — handles thousands separators in both RO ("2.000,00")
// and US ("2,000.00") notation, plain numbers, and native input.value.
// Result is always rounded to 2 decimals.
function parseRON(str) {
  if (str == null) return 0;
  var s = String(str).trim().replace(/\s/g, '');
  if (!s) return 0;
  var neg = /^-/.test(s);
  s = s.replace(/[^0-9.,]/g, '');
  if (!s) return 0;
  var lastComma = s.lastIndexOf(',');
  var lastDot = s.lastIndexOf('.');
  if (lastComma > -1 && lastDot > -1) {
    // Both present — the later one is the decimal separator
    if (lastComma > lastDot) s = s.replace(/\./g, '').replace(/,/g, '.');
    else s = s.replace(/,/g, '');
  } else if (lastComma > -1) {
    var commaCount = (s.match(/,/g) || []).length;
    if (commaCount > 1) s = s.replace(/,/g, '');           // multiple = thousands
    else if (/^\d{1,3},\d{3}$/.test(s)) s = s.replace(/,/g, ''); // "5,000" = thousands
    else s = s.replace(/,/g, '.');                          // "146,99" = decimal
  } else if (lastDot > -1) {
    var dotCount = (s.match(/\./g) || []).length;
    if (dotCount > 1) s = s.replace(/\./g, '');             // multiple = thousands
    else if (/^\d{1,3}\.\d{3}$/.test(s)) s = s.replace(/\./g, ''); // "2.000" = thousands
    // else single dot, 1-2 decimals — leave as decimal
  }
  var n = parseFloat(s);
  if (isNaN(n)) return 0;
  return round2(neg ? -Math.abs(n) : n);
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
  { id: 4,  pattern: 'Subscriere Tezaur',                 categorie: '__TEZAUR__' },
  { id: 5,  pattern: 'KAUFLAND|AUCHAN|CARREFOUR|MEGA IMAGE|LIDL|PROFI|PENNY|SELGROS|FRESH MARKET', categorie: 'Alimente' },
  { id: 17, pattern: 'RESTAURANT|MCDONALD|KFC|STARBUCKS|BURGER KING|PIZZA|GLOVO|TAZZ|FOODPANDA|SUSHI|TACO|BISTRO|CAFE|COFFEE', categorie: 'Mâncare restaurant' },
  { id: 6,  pattern: 'ENGIE|ELECTRICA|APA NOVA|E\\.ON|HIDROELECTRICA|ENEL|DISTRIGAZ',           categorie: 'Utilități & facturi' },
  { id: 7,  pattern: 'VODAFONE|DIGI|RDS|RCS|ORANGE|TELEKOM',                                   categorie: 'Utilități & facturi' },
  { id: 8,  pattern: 'MEDICAL|FARMACIE|FARMACIA|CATENA|SENSIBLU|HELPNET|REGINA MARIA|MEDLIFE|MEDICOVER|CLUJ MEDICAL', categorie: 'Sănătate & îngrijire' },
  { id: 9,  pattern: 'BOLT|UBER|FREE NOW|FREENOW|TAXIFY',                                      categorie: 'Transport' },
  { id: 10, pattern: 'OMV|MOL|PETROM|ROMPETROL|LUKOIL|SOCAR',                                  categorie: 'Transport' },
  { id: 11, pattern: 'NETFLIX|SPOTIFY|HBO|YOUTUBE|APPLE\\.COM|GOOGLE|MICROSOFT|ADOBE',         categorie: 'Abonamente' },
  { id: 12, pattern: 'H\\&M|ZARA|RESERVED|BERSHKA|PULL\\&BEAR|C\\&A|DECATHLON',                categorie: 'Îmbrăcăminte' },
  { id: 13, pattern: 'CINEMA|TEATRU|CONCERT|BOWLING|ESCAPE ROOM',                              categorie: 'Divertisment & timp liber' },
  { id: 18, pattern: 'IKEA|DEDEMAN|LEROY MERLIN|BRICO|HORNBACH|JYSK',                          categorie: 'Casă & întreținere' },
  { id: 19, pattern: 'RCA|CASCO|ASIGURARE AUTO|IMPOZIT|ANAF|TAXA',                             categorie: 'Taxe & asigurări' },
  // Income rules (matched on credit transactions)
  { id: 14, pattern: 'SALARIU|VENIT SALARIAL|LEAFA|LEFE',                                      categorie: '__SKIP__' },
  { id: 15, pattern: 'BONUS|PRIMA|TICHETE|BONURI DE MASA|BONURI MASA',                         categorie: 'Bonus & prime' },
  { id: 16, pattern: 'DIURNA|DELEGATIE|DECONT DEPLASARE',                                      categorie: 'Diurnă & deconturi' },
  { id: 20, pattern: 'DOBANDA|DIVIDEND|CUPON',                                                 categorie: 'Dobânzi & dividende' },
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
    { id: 1,  label: 'Alimente' },
    { id: 2,  label: 'Mâncare restaurant' },
    { id: 3,  label: 'Transport' },
    { id: 4,  label: 'Utilități & facturi' },
    { id: 5,  label: 'Sănătate & îngrijire' },
    { id: 6,  label: 'Îmbrăcăminte' },
    { id: 7,  label: 'Casă & întreținere' },
    { id: 8,  label: 'Divertisment & timp liber' },
    { id: 9,  label: 'Abonamente' },
    { id: 10, label: 'Educație & dezvoltare' },
    { id: 11, label: 'Cadouri & evenimente' },
    { id: 12, label: 'Călătorii & vacanțe' },
    { id: 13, label: 'Taxe & asigurări' },
    { id: 14, label: 'Alte credite' },
    { id: 15, label: 'Alte' },
  ],
  categoriiVenit: [
    { id: 1, label: 'Bonuri de masă' },
    { id: 2, label: 'Bonus & prime' },
    { id: 3, label: 'Diurnă & deconturi' },
    { id: 4, label: 'Dobânzi & dividende' },
    { id: 5, label: 'Alte venituri' },
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
    '2026-05': { 'Bonuri de masă': 360, 'Bonus & prime': 1750, 'Diurnă & deconturi': 1200 },
    '2026-06': {}, '2026-07': {}, '2026-08': {}, '2026-09': {}, '2026-10': {}, '2026-11': {}, '2026-12': {}
  },
  cheltuieli: {
    '2026-05': { 'Sănătate & îngrijire': 200 },
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
      ensureCategorieVar(state.data, 'Alte credite');
      ensureCategorieVar(state.data, 'Mâncare restaurant');
      migrateCategoriiVenit(state.data);
      migrateEmisiuniTezaur(state.data);
      migrateCreditScadentar(state.data);
      migrateReguliCategorizare(state.data);
      ensureRegula(state.data, 'RESTAURANT|MCDONALD|KFC|STARBUCKS|BURGER KING|PIZZA|GLOVO|TAZZ|FOODPANDA|SUSHI|TACO|BISTRO|CAFE|COFFEE', 'Mâncare restaurant', true);
      migrateCategoriesV2(state.data);
      migrateImportedRefs(state.data);
      migrateGoals(state.data);
      migrateEtf(state.data);
      migrateImportHistory(state.data);
      pruneImportHistory(state.data);
      migrateVwce(state.data);
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
  state.data.cheltuieliFixe.push({ id: getNextId(state.data.cheltuieliFixe), label: '', suma: 0, platit: {} });
  saveData();
  render();
}
function toggleCheltuialaFixaPaid(id, lunaKey) {
  if (!Array.isArray(state.data.cheltuieliFixe)) return;
  state.data.cheltuieliFixe = state.data.cheltuieliFixe.map(function(f) {
    if (f.id !== id) return f;
    var u = cloneObj(f);
    if (!u.platit) u.platit = {};
    u.platit[lunaKey] = !u.platit[lunaKey];
    if (!u.platit[lunaKey]) delete u.platit[lunaKey];
    return u;
  });
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

// "1 an" -> 12, "6 luni" -> 6, "3 ani" -> 36
function maturitateLuni(s) {
  if (!s) return 12;
  var m = String(s).match(/(\d+)\s*(luni|lun[ăa]|ani|an)/i);
  if (!m) return 12;
  var n = parseInt(m[1], 10) || 1;
  return /lun/i.test(m[2]) ? n : n * 12;
}

// Add N months to a YYYY-MM-DD date, return YYYY-MM-DD
function addMonthsIso(iso, months) {
  if (!iso) return '';
  var p = String(iso).split('-');
  var y = parseInt(p[0], 10), mo = parseInt(p[1], 10), d = parseInt(p[2] || '1', 10);
  if (!y || !mo) return '';
  var idx = (mo - 1) + months;
  var ny = y + Math.floor(idx / 12);
  var nm = (idx % 12) + 1;
  return ny + '-' + String(nm).padStart(2, '0') + '-' + String(d || 1).padStart(2, '0');
}

function daysBetween(isoA, isoB) {
  if (!isoA || !isoB) return 0;
  var a = new Date(isoA + 'T00:00:00');
  var b = new Date(isoB + 'T00:00:00');
  if (isNaN(a) || isNaN(b)) return 0;
  return Math.round((b - a) / 86400000);
}

// Full metrics for a Tezaur subscription
function tezaurMetrics(t) {
  var suma = parseRON(t.suma) || 0;
  var dobPct = parseRON(t.dobanda) || 0;
  var luni = maturitateLuni(t.maturitate);
  var dataScad = t.dataScadenta || (t.dataSubscriere ? addMonthsIso(t.dataSubscriere, luni) : '');
  var dobandaAnuala = suma * dobPct / 100;
  var dobandaTotala = dobandaAnuala * luni / 12;
  var today = todayIso();
  var zileTotal = (t.dataSubscriere && dataScad) ? daysBetween(t.dataSubscriere, dataScad) : 0;
  var zileTrecute = t.dataSubscriere ? Math.max(0, daysBetween(t.dataSubscriere, today)) : 0;
  var fractie = zileTotal > 0 ? Math.min(1, zileTrecute / zileTotal) : 0;
  var dobandaAcumulata = round2(dobandaTotala * fractie);
  var matur = dataScad ? (today >= dataScad) : false;
  var zileRamase = dataScad ? daysBetween(today, dataScad) : 0;
  return {
    suma: suma, dobPct: dobPct, luni: luni, dataScad: dataScad,
    dobandaAnuala: dobandaAnuala, dobandaTotala: round2(dobandaTotala),
    dobandaAcumulata: dobandaAcumulata, valoareAzi: round2(suma + dobandaAcumulata),
    valoareLaScadenta: round2(suma + dobandaTotala),
    matur: matur, zileRamase: zileRamase, progres: Math.round(fractie * 100)
  };
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
  var soldCredit = soldDupaPlatiTrecute(getScadentar(d), todayIso(), d.credit.suma);
  var avereNeta = totalActive - soldCredit;

  var html = '';

  // NEXT PAYMENT WIDGET (credit)
  var scad = getScadentar(d);
  var todayStr = todayIso();
  var viit = platiViitoare(scad, todayStr);
  if (viit.length > 0) {
    var np = viit[0];
    var dToday = new Date(todayStr + 'T00:00:00');
    var dNext = new Date(np.data + 'T00:00:00');
    var diffDays = Math.round((dNext - dToday) / (1000 * 60 * 60 * 24));
    var totalNext = (np.suma || 0) + (np.asigurare || 0);
    var dayLabel = diffDays === 0 ? 'astăzi' : (diffDays === 1 ? 'mâine' : 'în ' + diffDays + ' zile');
    html += '<div class="next-payment">';
    html += '  <div class="next-payment-icon"><i data-lucide="calendar-clock"></i></div>';
    html += '  <div class="next-payment-body">';
    html += '    <div class="next-payment-title">Următoarea rată credit</div>';
    html += '    <div class="next-payment-line">';
    html += '      <span class="mono">' + formatRON(totalNext) + ' RON</span>';
    html += '      <span class="text-mid">scadenţa <strong class="mono">' + esc(np.data) + '</strong> · capital ' + formatRON(np.principal) + ' · dobandă ' + formatRON(np.dobanda) + ' · asigurare ' + formatRON(np.asigurare) + '</span>';
    html += '    </div>';
    html += '  </div>';
    html += '  <div class="next-payment-count">' + esc(dayLabel) + '</div>';
    html += '</div>';
  }

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

  // CHART: surplus lunar (bars) + distributie cheltuieli (donut)
  var surplusBars = LUNI_KEYS.map(function(lk, i) {
    var v = (d.venituri[lk] || {});
    var totalV = (d.profil.salariuNet || 0) + (d.categoriiVenit || []).reduce(function(s, c) { return s + (v[c.label] || 0); }, 0);
    var c = (d.cheltuieli[lk] || {});
    var totalC = totalFixeLuna(d, lk) + Object.values(c).reduce(function(s, x) { return s + x; }, 0);
    return { value: totalV - totalC, label: LUNI[i] };
  });
  var donutSlices = [];
  // Fixed expenses grouped by item
  (d.cheltuieliFixe || []).forEach(function(f) {
    var v = 0;
    LUNI_KEYS.forEach(function(lk) { if (cheltuialaFixaActiva(f, lk)) v += parseRON(f.suma) || 0; });
    if (v > 0) donutSlices.push({ label: f.label, value: v });
  });
  // Variable categories aggregated across visible months
  (d.categoriiVar || []).forEach(function(c) {
    var v = LUNI_KEYS.reduce(function(s, lk) { return s + ((d.cheltuieli[lk] || {})[c.label] || 0); }, 0);
    if (v > 0) donutSlices.push({ label: c.label, value: v });
  });
  donutSlices.sort(function(a, b) { return b.value - a.value; });

  html += '<div class="section" style="margin-top:1.25rem;">';
  html += '<div class="stat-grid" style="grid-template-columns: 2fr 1fr;">';
  html += '<div class="chart-card">';
  html += '  <div class="chart-head"><div class="chart-title"><i data-lucide="bar-chart-3"></i> Surplus lunar (venituri − cheltuieli)</div><div class="chart-meta">' + LUNI_KEYS.length + ' luni</div></div>';
  html += '  <div class="chart-body">' + svgBars(surplusBars, { height: 200 }) + '</div>';
  html += '</div>';
  html += '<div class="chart-card">';
  html += '  <div class="chart-head"><div class="chart-title"><i data-lucide="pie-chart"></i> Distribuție cheltuieli</div><div class="chart-meta">cumulat</div></div>';
  html += '  <div class="chart-body chart-flex">';
  html += '    <div>' + svgDonut(donutSlices, { size: 180, centerLabel: formatRON(donutSlices.reduce(function(s, x){return s+x.value;}, 0)), centerSub: 'total cheltuieli' }) + '</div>';
  html += '    <div>' + donutLegend(donutSlices.slice(0, 8)) + '</div>';
  html += '  </div>';
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

  return html;
}

// ====================================================================
// RENDER: Setari (toate panourile editabile)
// ====================================================================
function renderSetari() {
  var d = state.data;
  var html = '';

  // PROFIL PANEL (editable)
  html += '<div class="section">';
  html += '<div class="section-title"><div class="section-title-left"><i data-lucide="user-cog"></i> Profil</div></div>';
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
    var categoriiTinta = IMPORT_SPECIAL_CATS.concat(
      (d.cheltuieliFixe || []).map(function(c) { return c.label; }),
      (d.categoriiVar || []).map(function(c) { return c.label; }),
      (d.categoriiVenit || []).map(function(c) { return c.label; })
    );
    html += '<div class="table-wrap"><table>';
    html += '<thead><tr><th>Pattern (regex)</th><th>Categorie țintă</th><th></th></tr></thead><tbody>';
    d.reguliCategorizare.forEach(function(r) {
      html += '<tr>';
      html += '<td><input type="text" class="input mono w-full" value="' + esc(r.pattern || '') + '" placeholder="Ex: KAUFLAND|AUCHAN" onchange="updateReguliCat(' + r.id + ', \'pattern\', this.value)"></td>';
      html += '<td><select class="select cs-enhance" onchange="updateReguliCat(' + r.id + ', \'categorie\', this.value)">';
      categoriiTinta.forEach(function(c) {
        var lbl = (IMPORT_SPECIAL_CATS.indexOf(c) >= 0) ? specialCatLabel(c) : c;
        html += '<option value="' + esc(c) + '"' + (r.categorie === c ? ' selected' : '') + '>' + esc(lbl) + '</option>';
      });
      html += '</select></td>';
      html += '<td><button class="btn-del" onclick="removeReguliCat(' + r.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += '<div class="info-box" style="margin-top:0.85rem;">';
    html += '<i data-lucide="info"></i>';
    html += '<div>Pattern-urile sunt regex JavaScript case-insensitive, testate pe descrierea completă a tranzacției (detalii + beneficiar + locație). Categorii speciale: <strong>→ Subscriere Tezaur</strong> creează automat o intrare în tabelul Tezaur; <strong>→ Alimentare Tradeville</strong> înregistrează banii transferați la broker (nu ca cheltuială); <strong>— ignoră —</strong> sare peste tranzacție. Pentru transferurile către Tradeville adaugă o regulă cu IBAN-ul contului tău Tradeville → Alimentare Tradeville.</div>';
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
  html += '<div class="stat-row"><span>Sold rămas azi</span><span class="stat-val danger">' + formatRON(soldEstimat) + '</span></div>';
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

  // Sold credit line chart
  if (scad.length > 0) {
    var soldPoints = scad.map(function(p, i) { return { x: i + 1, y: p.soldFinal, label: p.data }; });
    // Prepend "azi" point with current estimated balance
    soldPoints.unshift({ x: 0, y: cr.suma || soldPoints[0].y, label: 'start' });
    html += '<div class="section">';
    html += '<div class="chart-card">';
    html += '  <div class="chart-head"><div class="chart-title"><i data-lucide="trending-down"></i> Evoluție sold credit</div><div class="chart-meta">' + scad.length + ' rate · ' + viit.length + ' rămase</div></div>';
    html += '  <div class="chart-body">' + svgLine(soldPoints, { height: 200, markerX: trec.length }) + '</div>';
    html += '</div></div>';
  }

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

// ====================================================================
// SVG MINI-CHARTS (vanilla, no deps)
// ====================================================================

// Line chart for time-series like sold credit. Returns SVG markup.
function svgLine(points, opts) {
  opts = opts || {};
  var w = opts.width || 760, h = opts.height || 180;
  var pad = { t: 16, r: 14, b: 24, l: 56 };
  var iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  if (!points || points.length === 0) return '';
  var ys = points.map(function(p) { return p.y; });
  var xs = points.map(function(p) { return p.x; });
  var minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
  var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
  if (maxY === minY) maxY = minY + 1;
  if (maxX === minX) maxX = minX + 1;
  var sx = function(x) { return pad.l + (x - minX) / (maxX - minX) * iw; };
  var sy = function(y) { return pad.t + ih - (y - minY) / (maxY - minY) * ih; };
  var pathD = points.map(function(p, i) { return (i === 0 ? 'M' : 'L') + sx(p.x).toFixed(1) + ',' + sy(p.y).toFixed(1); }).join(' ');
  var areaD = pathD + ' L' + sx(maxX).toFixed(1) + ',' + (pad.t + ih).toFixed(1) + ' L' + sx(minX).toFixed(1) + ',' + (pad.t + ih).toFixed(1) + ' Z';
  // Y axis ticks (4)
  var ticks = '';
  for (var k = 0; k <= 4; k++) {
    var y = pad.t + ih - (k / 4) * ih;
    var val = minY + (k / 4) * (maxY - minY);
    ticks += '<line x1="' + pad.l + '" x2="' + (pad.l + iw) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="var(--border)" stroke-width="0.5" stroke-dasharray="2 4"/>';
    ticks += '<text x="' + (pad.l - 6) + '" y="' + (y + 3).toFixed(1) + '" font-family="var(--font-mono)" font-size="10" fill="var(--text-dim)" text-anchor="end">' + Math.round(val).toLocaleString('ro-RO') + '</text>';
  }
  // marker
  var marker = '';
  if (opts.markerX != null) {
    var mp = points.find(function(p) { return p.x === opts.markerX; });
    if (mp) {
      marker = '<circle cx="' + sx(mp.x).toFixed(1) + '" cy="' + sy(mp.y).toFixed(1) + '" r="5" fill="var(--warning)" stroke="var(--bg-elev1)" stroke-width="2"/>';
    }
  }
  return '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;max-height:' + h + 'px;">' +
    ticks +
    '<path d="' + areaD + '" fill="var(--accent-soft)" stroke="none"/>' +
    '<path d="' + pathD + '" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>' +
    marker +
    '</svg>';
}

// Vertical bar chart with positive/negative split (green/red)
function svgBars(bars, opts) {
  opts = opts || {};
  var w = opts.width || 760, h = opts.height || 200;
  var pad = { t: 18, r: 14, b: 34, l: 60 };
  var iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  if (!bars || bars.length === 0) return '<div class="text-dim mono" style="padding:1rem;font-size:0.8rem;">Nicio dată</div>';
  var values = bars.map(function(b) { return b.value || 0; });
  var maxV = Math.max.apply(null, values.concat(0));
  var minV = Math.min.apply(null, values.concat(0));
  var range = maxV - minV || 1;
  var zeroY = pad.t + ih * (maxV / range);
  var barW = iw / bars.length;
  var inner = barW * 0.62;
  var bandPad = (barW - inner) / 2;
  var rects = '';
  var labels = '';
  bars.forEach(function(b, i) {
    var v = b.value || 0;
    var color = v >= 0 ? 'var(--success)' : 'var(--danger)';
    var x = pad.l + i * barW + bandPad;
    var yTop = v >= 0 ? pad.t + (ih * (maxV - v) / range) : zeroY;
    var bh = Math.max(1, Math.abs(v / range) * ih);
    rects += '<rect x="' + x.toFixed(1) + '" y="' + yTop.toFixed(1) + '" width="' + inner.toFixed(1) + '" height="' + bh.toFixed(1) + '" fill="' + color + '" rx="3"><title>' + esc(b.label) + ': ' + formatRON(v) + ' RON</title></rect>';
    labels += '<text x="' + (x + inner / 2).toFixed(1) + '" y="' + (pad.t + ih + 16) + '" font-family="var(--font-mono)" font-size="10" fill="var(--text-dim)" text-anchor="middle">' + esc(b.label) + '</text>';
  });
  // axis
  var axis = '<line x1="' + pad.l + '" x2="' + (pad.l + iw) + '" y1="' + zeroY.toFixed(1) + '" y2="' + zeroY.toFixed(1) + '" stroke="var(--border)" stroke-width="1"/>';
  // ticks left
  var ticks = '';
  for (var k = 0; k <= 4; k++) {
    var ty = pad.t + (k / 4) * ih;
    var tv = maxV - (k / 4) * range;
    ticks += '<text x="' + (pad.l - 6) + '" y="' + (ty + 3).toFixed(1) + '" font-family="var(--font-mono)" font-size="10" fill="var(--text-dim)" text-anchor="end">' + Math.round(tv).toLocaleString('ro-RO') + '</text>';
  }
  return '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;max-height:' + h + 'px;">' +
    ticks + rects + axis + labels +
    '</svg>';
}

// Donut chart with central label
function svgDonut(slices, opts) {
  opts = opts || {};
  var sz = opts.size || 220;
  var cx = sz / 2, cy = sz / 2;
  var rOut = sz / 2 - 4, rIn = rOut * 0.62;
  var total = slices.reduce(function(s, x) { return s + (x.value || 0); }, 0);
  if (total <= 0) return '<div class="text-dim mono" style="padding:1rem;font-size:0.8rem;text-align:center;">Nicio dată</div>';
  var palette = ['var(--accent)', 'var(--danger)', 'var(--warning)', 'var(--violet)', 'var(--success)', '#6ea8fe', '#f59e0b', '#a855f7', '#10b981', '#ef4444', '#3b82f6', '#84cc16'];
  var ang = -Math.PI / 2;
  var paths = '';
  slices.forEach(function(s, i) {
    if (!s.value) return;
    var a2 = ang + (s.value / total) * Math.PI * 2;
    var large = (a2 - ang) > Math.PI ? 1 : 0;
    var x1 = cx + rOut * Math.cos(ang), y1 = cy + rOut * Math.sin(ang);
    var x2 = cx + rOut * Math.cos(a2), y2 = cy + rOut * Math.sin(a2);
    var x3 = cx + rIn * Math.cos(a2), y3 = cy + rIn * Math.sin(a2);
    var x4 = cx + rIn * Math.cos(ang), y4 = cy + rIn * Math.sin(ang);
    var color = s.color || palette[i % palette.length];
    var d = 'M' + x1.toFixed(1) + ',' + y1.toFixed(1) +
            ' A' + rOut + ',' + rOut + ' 0 ' + large + ' 1 ' + x2.toFixed(1) + ',' + y2.toFixed(1) +
            ' L' + x3.toFixed(1) + ',' + y3.toFixed(1) +
            ' A' + rIn + ',' + rIn + ' 0 ' + large + ' 0 ' + x4.toFixed(1) + ',' + y4.toFixed(1) +
            ' Z';
    paths += '<path d="' + d + '" fill="' + color + '" stroke="var(--bg-elev1)" stroke-width="2"><title>' + esc(s.label) + ': ' + formatRON(s.value) + ' RON (' + (s.value/total*100).toFixed(1) + '%)</title></path>';
    ang = a2;
  });
  var centerLbl = opts.centerLabel || formatRON(total) + ' RON';
  var centerSub = opts.centerSub || 'total';
  return '<svg viewBox="0 0 ' + sz + ' ' + sz + '" style="width:100%;max-width:' + sz + 'px;height:auto;">' +
    paths +
    '<text x="' + cx + '" y="' + cy + '" font-family="var(--font-mono)" font-size="' + (sz/14) + '" font-weight="600" fill="var(--text)" text-anchor="middle">' + esc(centerLbl) + '</text>' +
    '<text x="' + cx + '" y="' + (cy + sz/12) + '" font-family="var(--font-sans)" font-size="' + (sz/22) + '" fill="var(--text-dim)" text-anchor="middle">' + esc(centerSub) + '</text>' +
    '</svg>';
}

function donutLegend(slices) {
  var total = slices.reduce(function(s, x) { return s + (x.value || 0); }, 0) || 1;
  var palette = ['var(--accent)', 'var(--danger)', 'var(--warning)', 'var(--violet)', 'var(--success)', '#6ea8fe', '#f59e0b', '#a855f7', '#10b981', '#ef4444', '#3b82f6', '#84cc16'];
  var h = '<div class="donut-legend">';
  slices.forEach(function(s, i) {
    if (!s.value) return;
    var color = s.color || palette[i % palette.length];
    h += '<div class="legend-item"><span class="legend-swatch" style="background:' + color + '"></span><span class="legend-label">' + esc(s.label) + '</span><span class="legend-value mono">' + formatRON(s.value) + '</span><span class="legend-pct mono text-dim">' + (s.value/total*100).toFixed(1) + '%</span></div>';
  });
  h += '</div>';
  return h;
}

function toggleScadentarVizibil() {
  state.scadShowAll = !state.scadShowAll;
  render();
}

function toggleActionsMenu(ev) {
  if (ev) ev.stopPropagation();
  var menu = document.getElementById('actions-menu');
  if (!menu) return;
  var willOpen = !menu.classList.contains('open');
  menu.classList.toggle('open', willOpen);
  if (willOpen) {
    setTimeout(function() {
      document.addEventListener('click', closeActionsMenu, { once: true });
    }, 0);
  }
}
function closeActionsMenu() {
  var menu = document.getElementById('actions-menu');
  if (menu) menu.classList.remove('open');
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
  var tezMetrics = d.tezaur.map(tezaurMetrics);
  var totalTez = tezMetrics.reduce(function(s, m) { return s + m.suma; }, 0);
  var totalDobTotala = tezMetrics.reduce(function(s, m) { return s + m.dobandaTotala; }, 0);
  var totalDobAcum = tezMetrics.reduce(function(s, m) { return s + m.dobandaAcumulata; }, 0);
  var totalValoareAzi = tezMetrics.reduce(function(s, m) { return s + m.valoareAzi; }, 0);
  // next maturity
  var viitoare = tezMetrics.filter(function(m) { return !m.matur && m.dataScad; })
    .sort(function(a, b) { return (a.dataScad || '').localeCompare(b.dataScad || ''); });
  var urmMat = viitoare[0];

  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '<div class="section-title-left"><i data-lucide="coins"></i> Titluri de stat Tezaur</div>';
  html += '<button class="btn-add" onclick="addTezaur()"><i data-lucide="plus"></i> Adaugă subscriere</button>';
  html += '</div>';

  // Stat cards
  html += '<div class="stat-grid" style="margin-bottom:1rem;">';
  html += statCard('coins', 'Total investit', formatRON(totalTez), d.tezaur.length + ' subscrieri', '');
  html += statCard('trending-up', 'Valoare azi', formatRON(totalValoareAzi), 'dobândă acumulată ' + formatRON(totalDobAcum), 'success');
  html += statCard('gift', 'Dobândă la maturitate', formatRON(totalDobTotala), 'total câștig dacă ții până la final', 'success');
  html += statCard('calendar-clock', 'Următoarea maturitate', urmMat ? urmMat.dataScad : '—', urmMat ? (urmMat.zileRamase + ' zile') : 'nicio scadență viitoare', 'warning');
  html += '</div>';

  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Emisiune</th><th>Data subscriere</th><th class="num">Sumă</th><th class="num">Dobândă %</th><th>Maturitate</th><th>Data scadență</th><th class="num">Dobândă acumulată</th><th class="num">Valoare azi</th><th class="num">La maturitate</th><th>Status</th><th></th></tr></thead><tbody>';

  d.tezaur.forEach(function(t, i) {
    var m = tezMetrics[i];
    html += '<tr>';
    var emisiuniList = (d.emisiuniTezaur || []).map(function(e) { return e.label; });
    if (t.emisiune && emisiuniList.indexOf(t.emisiune) < 0) emisiuniList.unshift(t.emisiune);
    html += '<td><select class="select cs-enhance" onchange="updateTezaur(' + t.id + ', \'emisiune\', this.value)">';
    emisiuniList.forEach(function(opt) {
      html += '<option value="' + esc(opt) + '"' + (t.emisiune === opt ? ' selected' : '') + '>' + esc(opt) + '</option>';
    });
    html += '</select></td>';
    html += '<td><input type="text" class="input fp-date w-32" value="' + esc(t.dataSubscriere || '') + '" placeholder="YYYY-MM-DD" onchange="updateTezaur(' + t.id + ', \'dataSubscriere\', this.value)"></td>';
    html += '<td class="num"><input type="number" class="input num w-28" value="' + (t.suma || 0) + '" onchange="updateTezaur(' + t.id + ', \'suma\', this.value)"></td>';
    html += '<td class="num"><input type="number" step="0.01" class="input num w-20" value="' + (t.dobanda || 0) + '" onchange="updateTezaur(' + t.id + ', \'dobanda\', this.value)"></td>';
    html += '<td><select class="select cs-enhance" onchange="updateTezaur(' + t.id + ', \'maturitate\', this.value)">';
    ['6 luni','1 an','2 ani','3 ani','5 ani'].forEach(function(opt) {
      html += '<option value="' + opt + '"' + (t.maturitate === opt ? ' selected' : '') + '>' + opt + '</option>';
    });
    html += '</select></td>';
    html += '<td class="mono text-mid">' + esc(m.dataScad || '—') + '</td>';
    html += '<td class="num accent">' + formatRON(m.dobandaAcumulata) + '</td>';
    html += '<td class="num">' + formatRON(m.valoareAzi) + '</td>';
    html += '<td class="num accent">' + formatRON(m.valoareLaScadenta) + '</td>';
    if (m.matur) {
      html += '<td><span class="tag" style="background:var(--success-soft);color:var(--success);"><i data-lucide="check"></i> maturat</span></td>';
    } else if (m.dataScad) {
      var urgent = m.zileRamase <= 30;
      html += '<td><span class="tag" style="background:' + (urgent ? 'var(--warning-soft);color:var(--warning)' : 'var(--accent-soft);color:var(--accent)') + ';">' + m.progres + '% · ' + m.zileRamase + ' z</span></td>';
    } else {
      html += '<td><span class="text-dim">—</span></td>';
    }
    html += '<td><button class="btn-del" onclick="removeTezaur(' + t.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
    html += '</tr>';
  });

  html += '</tbody><tfoot>';
  html += '<tr><td colspan="2">Total</td>';
  html += '<td class="num">' + formatRON(totalTez) + '</td>';
  html += '<td colspan="3"></td>';
  html += '<td class="num">+' + formatRON(totalDobAcum) + '</td>';
  html += '<td class="num">' + formatRON(totalValoareAzi) + '</td>';
  html += '<td class="num">+' + formatRON(totalDobTotala) + '</td>';
  html += '<td colspan="2"></td></tr>';
  html += '</tfoot></table></div>';
  html += '<div class="info-box" style="margin-top:0.85rem;">';
  html += '<i data-lucide="info"></i>';
  html += '<div>Data scadenței se calculează automat din data subscrierii + maturitate. Dobânda acumulată e pro-rata (proporțional cu timpul scurs). Dobânda la maturitate = dobândă anuală × durata titlului — un titlu pe 3 ani câștigă de 3 ori dobânda anuală.</div>';
  html += '</div>';
  html += '</div></div>';

  // Proiecție avere netă — calculată automat din active curente + scadenar credit
  var totalFondCurent = d.fondUrgenta.reduce(function(s, f) { return s + (parseRON(f.suma) || 0); }, 0);
  var totalTezaurCurent = d.tezaur.reduce(function(s, t) { return s + (parseRON(t.suma) || 0); }, 0);
  var activeCurente = totalFondCurent + totalTezaurCurent;
  var scadEv = getScadentar(d);
  var averePts = LUNI_KEYS.map(function(lk, i) {
    var refIso = lk + '-28';
    var sold = soldDupaPlatiTrecute(scadEv, refIso, d.credit.suma);
    return { x: i, y: activeCurente - sold, label: LUNI[i] };
  });
  var averePrima = averePts.length ? averePts[0].y : 0;
  var avereUltima = averePts.length ? averePts[averePts.length - 1].y : 0;

  html += '<div class="section">';
  html += '<div class="chart-card">';
  html += '  <div class="chart-head"><div class="chart-title"><i data-lucide="line-chart"></i> Proiecție avere netă</div><div class="chart-meta">active curente − sold credit</div></div>';
  html += '  <div class="chart-meta" style="margin-bottom:0.4rem;">' + esc(LUNI[0] || '') + ': <span class="' + (averePrima >= 0 ? 'pl-pos' : 'pl-neg') + '">' + formatRON(averePrima) + '</span> → ' + esc(LUNI[LUNI.length-1] || '') + ': <span class="' + (avereUltima >= 0 ? 'pl-pos' : 'pl-neg') + '">' + formatRON(avereUltima) + '</span></div>';
  html += '  <div class="chart-body">' + svgLine(averePts, { height: 200 }) + '</div>';
  html += '  <div class="info-box" style="margin-top:0.75rem;">';
  html += '<i data-lucide="info"></i>';
  html += '<div>Calcul automat: <strong>' + formatRON(activeCurente) + ' RON</strong> active curente (fond ' + formatRON(totalFondCurent) + ' + tezaur ' + formatRON(totalTezaurCurent) + ') minus soldul creditului din scadenar, lună de lună. Pe măsură ce achiți ratele, averea netă crește chiar dacă activele rămân constante.</div>';
  html += '  </div>';
  html += '</div></div>';

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
  var emis = ((state.data.emisiuniTezaur || [])[0] || {}).label || 'Tezaur 1 an';
  var azi = todayIso();
  state.data.tezaur.push({
    id: getNextId(state.data.tezaur),
    emisiune: emis,
    dataSubscriere: azi,
    suma: 0,
    dobanda: 6.30,
    maturitate: '1 an',
    dataScadenta: addMonthsIso(azi, 12)
  });
  saveData();
  render();
}
function updateTezaur(id, field, value) {
  state.data.tezaur = state.data.tezaur.map(function(t) {
    if (t.id !== id) return t;
    var u = cloneObj(t);
    if (field === 'suma' || field === 'dobanda') u[field] = parseRON(value);
    else u[field] = value;
    // Auto-recompute scadenta when subscriere or maturitate changes
    if (field === 'dataSubscriere' || field === 'maturitate') {
      if (u.dataSubscriere) u.dataScadenta = addMonthsIso(u.dataSubscriere, maturitateLuni(u.maturitate));
    }
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

  // Import banner — primary data-entry path
  var nImported = (d.importedRefs || []).length;
  html += '<div class="section">';
  html += '<div class="next-payment" style="border-color:var(--accent);">';
  html += '  <div class="next-payment-icon" style="background:var(--accent-soft);color:var(--accent);"><i data-lucide="upload"></i></div>';
  html += '  <div class="next-payment-body">';
  html += '    <div class="next-payment-title">Import extras bancar</div>';
  html += '    <div class="next-payment-line"><span class="text-mid">Încarcă CSV-ul ING — venituri și cheltuieli se completează și categorizează automat.' + (nImported > 0 ? ' <strong>' + nImported + '</strong> tranzacții importate până acum.' : '') + '</span></div>';
  html += '  </div>';
  html += '  <div style="display:flex;gap:0.5rem;flex-shrink:0;">';
  html += '    <button class="btn-back" onclick="showImportHistory()" title="Istoric importuri"><i data-lucide="history"></i> Istoric</button>';
  html += '    <button class="btn-add" onclick="showImportModal()"><i data-lucide="upload"></i> Importă CSV</button>';
  html += '  </div>';
  html += '</div>';
  html += '</div>';

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
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="receipt"></i> Cheltuieli lunare</div>';
  html += '  <div style="display:flex;gap:0.6rem;font-size:0.7rem;color:var(--text-dim);align-items:center;">';
  html += '    <span><i data-lucide="mouse-pointer-click" style="width:11px;height:11px;vertical-align:-1px;"></i> click pe o sumă fixă = marchează plătit</span>';
  html += '    <span style="display:inline-flex;align-items:center;gap:0.2rem;"><span style="width:14px;height:6px;border-radius:1px;background:var(--danger);"></span>+20% peste medie</span>';
  html += '    <span style="display:inline-flex;align-items:center;gap:0.2rem;"><span style="width:14px;height:6px;border-radius:1px;background:var(--success);"></span>-20% sub medie</span>';
  html += '  </div>';
  html += '</div>';
  html += '<div class="panel">';
  html += '<div class="table-wrap"><table>';
  html += '<thead><tr><th>Categorie</th>';
  LUNI.forEach(function(l) { html += '<th class="num">' + l + '</th>'; });
  html += '</tr></thead><tbody>';

  (d.cheltuieliFixe || []).forEach(function(f) {
    html += '<tr class="fixed"><td>' + esc(f.label || '—') + '</td>';
    LUNI_KEYS.forEach(function(lk) {
      if (cheltuialaFixaActiva(f, lk)) {
        var paid = !!(f.platit && f.platit[lk]);
        html += '<td class="num neg fix-cell' + (paid ? ' paid' : '') + '" onclick="toggleCheltuialaFixaPaid(' + f.id + ', \'' + lk + '\')" title="' + (paid ? 'Plătit — click ca să anulezi' : 'Click pentru a marca plătit') + '">' + formatRON(f.suma) + '</td>';
      } else {
        html += '<td class="num text-dim">—</td>';
      }
    });
    html += '</tr>';
  });

  (d.categoriiVar || []).forEach(function(c) {
    var label = c.label || '';
    var labelAttr = label.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    // Precompute mean over months that have a positive value, for outlier marking
    var vals = LUNI_KEYS.map(function(x) { return (d.cheltuieli[x] || {})[label] || 0; });
    var posVals = vals.filter(function(v) { return v > 0; });
    var meanAll = posVals.length ? posVals.reduce(function(s, v) { return s + v; }, 0) / posVals.length : 0;
    html += '<tr><td class="muted">' + esc(label) + '</td>';
    LUNI_KEYS.forEach(function(l, idx) {
      var val = vals[idx];
      var deltaClass = '';
      if (val > 0 && meanAll > 0) {
        if (val > meanAll * 1.2) deltaClass = ' over-mean';
        else if (val < meanAll * 0.8) deltaClass = ' under-mean';
      }
      html += '<td class="num' + deltaClass + '"><input type="number" class="input num w-20" value="' + (val || '') + '" onchange="updateCheltuiala(\'' + l + '\', \'' + labelAttr + '\', this.value)"></td>';
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
// RENDER: Goals (obiective economisire)
// ====================================================================
function goalNeedPerMonth(g) {
  if (!g || !g.dataTarget || !g.sumaTarget) return 0;
  var ramas = (parseRON(g.sumaTarget) || 0) - (parseRON(g.contribuit) || 0);
  if (ramas <= 0) return 0;
  var today = new Date();
  var target = new Date(g.dataTarget + 'T00:00:00');
  var luni = (target.getFullYear() - today.getFullYear()) * 12 + (target.getMonth() - today.getMonth());
  if (luni <= 0) return ramas;
  return ramas / luni;
}

function renderGoals() {
  var d = state.data;
  var goals = d.goals || [];
  var mediiV = calcMediiVenituri(d);
  var mediiC = calcMediiCheltuieli(d);
  var surplus = mediiV.total - mediiC.total;
  var totalNecesar = goals.reduce(function(s, g) { return s + goalNeedPerMonth(g); }, 0);

  var html = '';

  // Header info
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="target"></i> Obiective economisire</div>';
  html += '  <button class="btn-add" onclick="addGoal()"><i data-lucide="plus"></i> Adaugă obiectiv</button>';
  html += '</div>';
  html += '<div class="stat-grid">';
  html += statCard('piggy-bank', 'Surplus mediu', formatRON(surplus), 'pentru economii', surplus >= 0 ? 'success' : 'danger');
  html += statCard('calendar-clock', 'Necesar lunar pentru obiective', formatRON(totalNecesar), goals.length + ' obiective active', totalNecesar > surplus ? 'danger' : 'warning');
  var disponibil = surplus - totalNecesar;
  html += statCard(disponibil >= 0 ? 'check-circle' : 'alert-triangle', 'Disponibil după obiective', (disponibil >= 0 ? '+' : '') + formatRON(disponibil), disponibil >= 0 ? 'rezervă liberă' : 'surplus insuficient', disponibil >= 0 ? 'success' : 'danger');
  html += '</div></div>';

  // Goals grid
  html += '<div class="section">';
  if (goals.length === 0) {
    html += '<div class="panel"><div class="audit-empty">Niciun obiectiv. Apasă "Adaugă obiectiv" pentru a defini ținte de economisire (vacanță, fond educație, depozit, etc.).</div></div>';
  } else {
    html += '<div class="goals-grid">';
    goals.forEach(function(g) {
      var target = parseRON(g.sumaTarget) || 0;
      var contribuit = parseRON(g.contribuit) || 0;
      var ramas = Math.max(0, target - contribuit);
      var pct = target > 0 ? Math.min(100, (contribuit / target) * 100) : 0;
      var done = contribuit >= target && target > 0;
      var necesar = goalNeedPerMonth(g);
      var today = new Date();
      var targetDate = g.dataTarget ? new Date(g.dataTarget + 'T00:00:00') : null;
      var luniRamase = targetDate ? Math.max(0, (targetDate.getFullYear() - today.getFullYear()) * 12 + (targetDate.getMonth() - today.getMonth())) : null;
      var late = targetDate && targetDate < today && !done;
      var cardCls = done ? ' done' : (late ? ' late' : '');
      html += '<div class="goal-card' + cardCls + '">';
      html += '  <div class="goal-head">';
      html += '    <div class="goal-label"><i data-lucide="' + (done ? 'check-circle-2' : (late ? 'alert-octagon' : 'target')) + '"></i><input type="text" class="input w-full" value="' + esc(g.label || '') + '" placeholder="Ex: Vacanță Spania, Fond educație..." style="background:transparent;border:none;padding:2px;font-size:0.95rem;font-weight:600;" onchange="updateGoal(' + g.id + ', \'label\', this.value)"></div>';
      html += '    <div class="goal-actions"><button class="btn-del" onclick="removeGoal(' + g.id + ')" title="Șterge obiectiv"><i data-lucide="trash-2"></i></button></div>';
      html += '  </div>';
      html += '  <div class="goal-bar-wrap"><div class="goal-bar" style="width:' + pct.toFixed(1) + '%;"></div></div>';
      html += '  <div class="goal-stats">';
      html += '    <div><div class="goal-stat-label">Strâns</div><div class="goal-stat-value success">' + formatRON(contribuit) + '</div></div>';
      html += '    <div><div class="goal-stat-label">Țintă</div><div class="goal-stat-value">' + formatRON(target) + '</div></div>';
      html += '    <div><div class="goal-stat-label">' + pct.toFixed(0) + '% complet</div><div class="goal-stat-value ' + (done ? 'success' : (late ? 'danger' : '')) + '">' + formatRON(ramas) + ' rămas</div></div>';
      html += '  </div>';
      html += '  <div class="goal-stats">';
      html += '    <div><div class="goal-stat-label">Țintă suma (RON)</div><input type="number" class="input num w-full" value="' + (target || 0) + '" onchange="updateGoal(' + g.id + ', \'sumaTarget\', this.value)"></div>';
      html += '    <div><div class="goal-stat-label">Dată țintă</div><input type="text" class="input fp-date w-full" value="' + esc(g.dataTarget || '') + '" placeholder="YYYY-MM-DD" onchange="updateGoal(' + g.id + ', \'dataTarget\', this.value)"></div>';
      html += '    <div><div class="goal-stat-label">Necesar / lună</div><div class="goal-stat-value ' + (necesar > surplus ? 'danger' : 'warning') + '">' + formatRON(necesar) + '</div></div>';
      html += '  </div>';
      if (luniRamase !== null) {
        html += '  <div style="font-size:0.72rem;color:var(--text-dim);margin-top:0.3rem;"><i data-lucide="calendar" style="width:11px;height:11px;vertical-align:-1px;"></i> ' + (done ? 'Atins!' : (late ? 'Termen depășit' : luniRamase + ' luni rămase')) + (g.nota ? ' · ' + esc(g.nota) : '') + '</div>';
      }
      html += '  <div class="goal-contribute">';
      html += '    <input type="number" class="input num" id="contrib-input-' + g.id + '" placeholder="Adaugă contribuție RON">';
      html += '    <button class="btn-add" onclick="contribuieGoal(' + g.id + ')"><i data-lucide="plus"></i> Contribuie</button>';
      html += '  </div>';
      html += '</div>';
    });
    html += '</div>';
  }
  html += '</div>';

  return html;
}

function addGoal() {
  if (!Array.isArray(state.data.goals)) state.data.goals = [];
  var today = new Date();
  var nextYear = new Date(today.getFullYear() + 1, today.getMonth(), today.getDate());
  var defaultDate = nextYear.toISOString().substring(0, 10);
  state.data.goals.push({
    id: getNextId(state.data.goals),
    label: '',
    sumaTarget: 5000,
    contribuit: 0,
    dataTarget: defaultDate,
    nota: ''
  });
  saveData();
  render();
}
function updateGoal(id, field, value) {
  if (!Array.isArray(state.data.goals)) return;
  state.data.goals = state.data.goals.map(function(g) {
    if (g.id !== id) return g;
    var u = cloneObj(g);
    if (field === 'sumaTarget' || field === 'contribuit') u[field] = parseRON(value);
    else u[field] = value;
    return u;
  });
  saveData();
  render();
}
function removeGoal(id) {
  state.data.goals = (state.data.goals || []).filter(function(g) { return g.id !== id; });
  saveData();
  render();
}
function contribuieGoal(id) {
  var inp = document.getElementById('contrib-input-' + id);
  if (!inp) return;
  var val = parseRON(inp.value);
  if (val <= 0) return;
  var g = (state.data.goals || []).find(function(x) { return x.id === id; });
  if (!g) return;
  g.contribuit = round2((parseRON(g.contribuit) || 0) + val);
  saveData();
  render();
}

// ====================================================================
// RENDER: Investitii (ETF / actiuni - manual tracking)
// ====================================================================
function etfMetrics(pos) {
  var cantitate = parseRON(pos.cantitate) || 0;
  var pretMediu = parseRON(pos.pretMediu) || 0;
  var pretCurent = parseRON(pos.pretCurent) || pretMediu;
  var investit = cantitate * pretMediu;
  var valoare = cantitate * pretCurent;
  var pl = valoare - investit;
  var plPct = investit > 0 ? (pl / investit) * 100 : 0;
  return { cantitate: cantitate, pretMediu: pretMediu, pretCurent: pretCurent, investit: investit, valoare: valoare, pl: pl, plPct: plPct };
}

// Find the closest historical close on or before `dateIso`. Falls back to v.pretCurent.
function getVwcePriceOnDate(dateIso) {
  var v = (state.data && state.data.vwce) || {};
  if (!dateIso) return parseRON(v.pretCurent) || 0;
  var history = v.priceHistory || [];
  if (history.length === 0) return parseRON(v.pretCurent) || 0;
  var targetMs = new Date(dateIso + 'T12:00:00Z').getTime();
  // history is chronological; pick last point with t*1000 <= targetMs, else first point
  var match = null;
  for (var i = 0; i < history.length; i++) {
    var ts = history[i].t * 1000;
    if (ts <= targetMs) match = history[i];
    else break;
  }
  if (!match) match = history[0];
  return match.c || (parseRON(v.pretCurent) || 0);
}

function vwceTotals(v) {
  var tranzactii = (v && v.tranzactii) || [];
  var cantitate = tranzactii.reduce(function(s, t) { return s + (parseInt(t.cantitate, 10) || 0); }, 0);
  var investitEur = tranzactii.reduce(function(s, t) {
    var qty = parseInt(t.cantitate, 10) || 0;
    var pretAchiz = parseRON(t.pretAchizitie) || (qty > 0 && t.sumaEur ? parseRON(t.sumaEur) / qty : getVwcePriceOnDate(t.data));
    var lineEur = qty * pretAchiz;
    return s + lineEur + (parseRON(t.comision) || 0);
  }, 0);
  var pretMediu = cantitate > 0 ? investitEur / cantitate : 0;
  var pretCurent = parseRON(v.pretCurent) || 0;
  var valoareEur = cantitate * pretCurent;
  var plEur = valoareEur - investitEur;
  var plPct = investitEur > 0 ? (plEur / investitEur) * 100 : 0;
  return { cantitate: cantitate, investitEur: investitEur, pretMediu: pretMediu, pretCurent: pretCurent, valoareEur: valoareEur, plEur: plEur, plPct: plPct };
}

function renderInvestitii() {
  var d = state.data;
  var v = d.vwce || {};
  var t = vwceTotals(v);
  var changePct = parseFloat(v.changePct) || 0;
  var change = parseFloat(v.change) || 0;
  var cursRon = parseRON(v.cursRon) || 0;
  var lastUpdate = v.lastUpdateLocal ? new Date(v.lastUpdateLocal) : null;
  var lastUpdateStr = lastUpdate ? lastUpdate.toLocaleString('ro-RO', { dateStyle: 'short', timeStyle: 'short' }) : 'niciodată';
  var fmtEur = function(x) { return formatRON(x); };
  var ron = function(eur) { return cursRon > 0 ? '≈ ' + formatRON(eur * cursRon) + ' RON' : ''; };

  var html = '';

  // Header card: VWCE info + live price
  html += '<div class="section">';
  html += '<div class="chart-card" style="border-color:var(--accent-ring);">';
  html += '  <div style="display:flex;gap:1rem;align-items:flex-start;flex-wrap:wrap;">';
  html += '    <div style="flex:1;min-width:240px;">';
  html += '      <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.3rem;">';
  html += '        <i data-lucide="briefcase" style="color:var(--accent);width:18px;height:18px;"></i>';
  html += '        <span class="etf-symbol" style="font-size:1.1rem;">' + esc(v.symbol || 'VWCE.DE') + '</span>';
  html += '        <span class="etf-broker">' + esc(v.exchange || 'XETRA') + '</span>';
  html += '        <span class="etf-broker">Tradeville</span>';
  html += '        <span class="tag" style="background:var(--accent-soft);color:var(--accent);">Accumulating</span>';
  html += '      </div>';
  html += '      <div style="font-size:0.85rem;color:var(--text);">' + esc(v.nume || 'Vanguard FTSE All-World UCITS ETF') + '</div>';
  html += '      <div style="font-size:0.72rem;color:var(--text-dim);font-family:var(--font-mono);">ISIN ' + esc(v.isin || 'IE00BK5BQT80') + '</div>';
  html += '      <div style="font-size:0.72rem;color:var(--text-dim);margin-top:0.3rem;display:flex;align-items:flex-start;gap:0.35rem;"><i data-lucide="info" style="width:12px;height:12px;flex-shrink:0;margin-top:2px;"></i><span>ETF de acumulare — dividendele se reinvestesc automat în fond. Tot randamentul e reflectat în preț, nu primești dividende cash.</span></div>';
  html += '    </div>';
  html += '    <div style="text-align:right;min-width:200px;">';
  html += '      <div style="font-family:var(--font-mono);font-size:1.6rem;font-weight:700;color:var(--accent);">' + fmtEur(t.pretCurent) + ' EUR</div>';
  if (change !== 0 || changePct !== 0) {
    var cClass = change >= 0 ? 'pl-pos' : 'pl-neg';
    html += '      <div class="' + cClass + '" style="font-size:0.82rem;">' + (change >= 0 ? '+' : '') + fmtEur(change) + ' (' + (changePct >= 0 ? '+' : '') + changePct.toFixed(2) + '%) azi</div>';
  }
  if (cursRon > 0) {
    html += '      <div style="font-size:0.72rem;color:var(--text-dim);margin-top:0.2rem;">' + ron(t.pretCurent) + ' · curs ' + cursRon.toFixed(2) + '</div>';
  }
  html += '      <div style="font-size:0.7rem;color:var(--text-dim);margin-top:0.2rem;">Ultima actualizare: ' + esc(lastUpdateStr) + '</div>';
  html += '      <button class="btn-add" style="margin-top:0.5rem;" onclick="refreshVwcePrice()"><i data-lucide="refresh-cw"></i> Actualizează preț</button>';
  html += '    </div>';
  html += '  </div>';
  html += '</div></div>';

  // Stat cards
  var plClass = t.plEur > 0 ? 'success' : (t.plEur < 0 ? 'danger' : '');
  html += '<div class="section">';
  html += '<div class="stat-grid">';
  html += statCard('hash', 'Total unități', String(t.cantitate), v.tranzactii.length + ' tranzacții', '');
  html += statCard('wallet', 'Investit', fmtEur(t.investitEur) + ' EUR', ron(t.investitEur), '');
  html += statCard('trending-up', 'Valoare curentă', fmtEur(t.valoareEur) + ' EUR', cursRon > 0 ? ron(t.valoareEur) : 'preț mediu ' + fmtEur(t.pretMediu) + ' EUR', plClass);
  html += statCard(t.plEur >= 0 ? 'arrow-up-right' : 'arrow-down-right', 'Profit / pierdere', (t.plEur >= 0 ? '+' : '') + fmtEur(t.plEur) + ' EUR', (t.plEur >= 0 ? '+' : '') + t.plPct.toFixed(2) + '%' + (cursRon > 0 ? ' · ' + (t.plEur >= 0 ? '+' : '') + formatRON(t.plEur * cursRon) + ' RON' : ''), plClass);
  html += '</div></div>';

  // Tradeville cash transfers (from bank import)
  var alimentari = v.alimentari || [];
  if (alimentari.length > 0) {
    var totalTransferat = alimentari.reduce(function(s, a) { return s + (parseRON(a.suma) || 0); }, 0);
    var investitRonEq = cursRon > 0 ? t.investitEur * cursRon : 0;
    var cashNeinvestit = investitRonEq > 0 ? (totalTransferat - investitRonEq) : null;
    html += '<div class="section">';
    html += '<div class="info-box">';
    html += '<i data-lucide="arrow-left-right"></i>';
    html += '<div>Transferat la Tradeville: <strong class="mono">' + formatRON(totalTransferat) + ' RON</strong> din ' + alimentari.length + ' alimentări importate.';
    if (cashNeinvestit !== null) {
      html += ' Investit în VWCE: <strong class="mono">' + formatRON(investitRonEq) + ' RON</strong>.';
      if (cashNeinvestit > 1) html += ' Cash neinvestit estimat: <strong class="mono">' + formatRON(cashNeinvestit) + ' RON</strong> — adaugă tranzacții VWCE pentru unitățile cumpărate.';
    }
    html += '</div></div>';
    html += '</div>';
  }

  // Chart: VWCE price + portfolio value evolution
  var series = (v.priceHistory || []);
  if (series.length > 1) {
    var rng = v.chartRange || '3mo';
    var rangeOpts = [
      { v: '5d', l: '5 z' },
      { v: '1mo', l: '1 L' },
      { v: '3mo', l: '3 L' },
      { v: '6mo', l: '6 L' },
      { v: '1y', l: '1 an' },
      { v: '2y', l: '2 ani' },
      { v: '5y', l: '5 ani' },
      { v: 'max', l: 'tot' },
    ];
    var pricePts = series.map(function(p, i) { return { x: i, y: p.c, label: new Date(p.t * 1000).toLocaleDateString('ro-RO') }; });
    var firstC = series[0].c, lastC = series[series.length - 1].c;
    var rangeChange = ((lastC - firstC) / firstC) * 100;
    var firstDate = new Date(series[0].t * 1000).toLocaleDateString('ro-RO', { day: '2-digit', month: 'short', year: 'numeric' });
    var lastDate = new Date(series[series.length - 1].t * 1000).toLocaleDateString('ro-RO', { day: '2-digit', month: 'short', year: 'numeric' });

    html += '<div class="section">';
    html += '<div class="chart-card">';
    html += '  <div class="chart-head">';
    html += '    <div class="chart-title"><i data-lucide="line-chart"></i> Evoluție preț VWCE</div>';
    html += '    <div style="display:flex;gap:0.25rem;">';
    rangeOpts.forEach(function(o) {
      var active = o.v === rng;
      html += '<button class="tab' + (active ? ' active' : '') + '" style="padding:0.25rem 0.55rem;font-size:0.72rem;" onclick="setVwceRange(\'' + o.v + '\')">' + esc(o.l) + '</button>';
    });
    html += '    </div>';
    html += '  </div>';
    html += '  <div class="chart-meta" style="margin-bottom:0.4rem;">' + esc(firstDate) + ' → ' + esc(lastDate) + ' · <span class="' + (rangeChange >= 0 ? 'pl-pos' : 'pl-neg') + '">' + (rangeChange >= 0 ? '+' : '') + rangeChange.toFixed(2) + '%</span> pe intervalul ales</div>';
    html += '  <div class="chart-body">' + svgLine(pricePts, { height: 220 }) + '</div>';
    html += '</div>';

    // Portfolio value evolution if user has positions
    if (t.cantitate > 0) {
      var portPts = series.map(function(p, i) { return { x: i, y: p.c * t.cantitate, label: new Date(p.t * 1000).toLocaleDateString('ro-RO') }; });
      var firstVal = portPts[0].y, lastVal = portPts[portPts.length - 1].y;
      html += '<div class="chart-card">';
      html += '  <div class="chart-head"><div class="chart-title"><i data-lucide="trending-up"></i> Evoluție valoare portofoliu (cantitate curentă × preț istoric)</div><div class="chart-meta">' + fmtEur(firstVal) + ' EUR → ' + fmtEur(lastVal) + ' EUR</div></div>';
      html += '  <div class="chart-body">' + svgLine(portPts, { height: 180 }) + '</div>';
      html += '  <div style="font-size:0.7rem;color:var(--text-dim);margin-top:0.4rem;font-style:italic;">Notă: graficul folosește cantitatea curentă pe toată perioada — nu reflectă cumpărările progresive (DCA).</div>';
      html += '</div>';
    }
    html += '</div>';
  } else if (v.lastUpdateLocal) {
    html += '<div class="section"><div class="chart-card"><div class="audit-empty">Apasă "Actualizează preț" pentru a încărca istoricul prețurilor.</div></div></div>';
  }

  // Transactions table
  html += '<div class="section">';
  html += '<div class="section-title">';
  html += '  <div class="section-title-left"><i data-lucide="list"></i> Tranzacții VWCE</div>';
  html += '  <button class="btn-add" onclick="addVwceTx()"><i data-lucide="plus"></i> Adaugă tranzacție</button>';
  html += '</div>';
  html += '<div class="panel">';
  if (v.tranzactii.length === 0) {
    html += '<div class="audit-empty">Nicio tranzacție. Apasă "Adaugă tranzacție" pentru fiecare achiziție VWCE (data + sumă EUR + cantitate primită).</div>';
  } else {
    html += '<div class="table-wrap"><table>';
    html += '<thead><tr>';
    html += '<th>Data</th><th class="num">Cantitate</th><th class="num">Preț achiziție (auto)</th><th class="num">Sumă EUR (auto)</th><th class="num">Comision EUR</th><th>Notă</th><th></th>';
    html += '</tr></thead><tbody>';
    v.tranzactii.slice().sort(function(a, b) { return (a.data || '').localeCompare(b.data || ''); }).forEach(function(tx) {
      var pretCalc = parseRON(tx.pretAchizitie) || getVwcePriceOnDate(tx.data);
      var sumaCalc = (parseInt(tx.cantitate, 10) || 0) * pretCalc;
      html += '<tr>';
      html += '<td><input type="text" class="input fp-date" style="width:120px;" value="' + esc(tx.data || '') + '" placeholder="YYYY-MM-DD" onchange="updateVwceTx(' + tx.id + ', \'data\', this.value)"></td>';
      html += '<td class="num"><input type="number" step="1" min="0" class="input num w-20" value="' + (parseInt(tx.cantitate, 10) || 0) + '" onchange="updateVwceTx(' + tx.id + ', \'cantitate\', this.value)"></td>';
      html += '<td class="num mono text-mid">' + fmtEur(pretCalc) + '</td>';
      html += '<td class="num mono">' + fmtEur(sumaCalc) + '</td>';
      html += '<td class="num"><input type="number" step="0.01" class="input num w-20" value="' + (tx.comision || 0) + '" onchange="updateVwceTx(' + tx.id + ', \'comision\', this.value)"></td>';
      html += '<td><input type="text" class="input" style="width:200px;" value="' + esc(tx.nota || '') + '" placeholder="DCA / lump sum..." onchange="updateVwceTx(' + tx.id + ', \'nota\', this.value)"></td>';
      html += '<td><button class="btn-del" onclick="removeVwceTx(' + tx.id + ')" title="Șterge"><i data-lucide="trash-2"></i></button></td>';
      html += '</tr>';
    });
    var totCant = v.tranzactii.reduce(function(s, x) { return s + (parseInt(x.cantitate, 10) || 0); }, 0);
    var totEur = v.tranzactii.reduce(function(s, x) {
      var p = parseRON(x.pretAchizitie) || getVwcePriceOnDate(x.data);
      return s + (parseInt(x.cantitate, 10) || 0) * p;
    }, 0);
    var totCom = v.tranzactii.reduce(function(s, x) { return s + (parseRON(x.comision) || 0); }, 0);
    html += '</tbody><tfoot><tr><td>Total</td><td class="num">' + totCant + '</td><td class="num">' + fmtEur(t.pretMediu) + '</td><td class="num">' + fmtEur(totEur) + '</td><td class="num">' + fmtEur(totCom) + '</td><td colspan="2"></td></tr></tfoot></table></div>';
    html += '<div class="info-box" style="margin-top:0.85rem;">';
    html += '<i data-lucide="info"></i>';
    html += '<div>Introdu doar <strong>data</strong> + <strong>cantitatea</strong> (număr întreg — Tradeville nu permite ETF fracționare). Prețul achiziție și suma EUR se calculează automat din istoricul VWCE la data tranzacției.</div>';
    html += '</div>';
  }
  html += '</div></div>';

  return html;
}

async function refreshVwcePrice(silent) {
  var v = state.data.vwce || {};
  var symbol = v.symbol || 'VWCE.DE';
  var rng = state.vwceChartRange || v.chartRange || '3mo';
  if (!silent) setSaveStatus('pending');
  try {
    var r = await fetch('/budget/api/quote/' + encodeURIComponent(symbol) + '?range=' + encodeURIComponent(rng), { credentials: 'same-origin' });
    if (!r.ok) {
      var err = await r.json().catch(function() { return { error: 'HTTP ' + r.status }; });
      throw new Error(err.error || 'HTTP ' + r.status);
    }
    var q = await r.json();
    state.data.vwce.pretCurent = round2(q.price || 0);
    state.data.vwce.previousClose = round2(q.previousClose || 0);
    state.data.vwce.change = round2(q.change || 0);
    state.data.vwce.changePct = round2(q.changePct || 0);
    state.data.vwce.currency = q.currency || 'EUR';
    state.data.vwce.exchange = q.exchange || state.data.vwce.exchange;
    state.data.vwce.lastUpdate = q.fetchedAt;
    state.data.vwce.lastUpdateLocal = new Date().toISOString();
    state.data.vwce.chartRange = rng;
    state.data.vwce.priceHistory = q.series || [];
    // Also fetch EUR/RON FX rate
    try {
      var rfx = await fetch('/budget/api/quote/' + encodeURIComponent('EURRON=X') + '?range=5d', { credentials: 'same-origin' });
      if (rfx.ok) {
        var fx = await rfx.json();
        if (fx.price) state.data.vwce.cursRon = fx.price;
      }
    } catch (fxErr) { console.warn('FX fetch failed:', fxErr); }
    await saveDataNow();
    render();
  } catch (e) {
    if (!silent) {
      setSaveStatus('error');
      showConfirm({
        title: 'Eroare la actualizare preț',
        body: 'Nu am putut obține cotația pentru ' + symbol + ': ' + (e.message || e),
        okLabel: 'OK', cancelLabel: '', icon: 'alert-triangle'
      });
    } else {
      console.warn('VWCE silent refresh failed:', e.message || e);
    }
  }
}

function setVwceRange(rng) {
  state.vwceChartRange = rng;
  refreshVwcePrice(false);
}

// Investitii tab = VWCE portfolio + Fond urgenta + Tezaur + Evolutie active
function renderInvestitiiTab() {
  return renderInvestitii() + renderFondUrgenta();
}

function addVwceTx() {
  if (!state.data.vwce) migrateVwce(state.data);
  var todayIsoStr = new Date().toISOString().substring(0, 10);
  var pretZi = getVwcePriceOnDate(todayIsoStr);
  state.data.vwce.tranzactii.push({
    id: getNextId(state.data.vwce.tranzactii),
    data: todayIsoStr,
    cantitate: 1,
    sumaEur: pretZi,           // auto: 1 unitate * pret
    pretAchizitie: pretZi,      // auto: pret la data
    comision: 0,
    nota: ''
  });
  saveData();
  render();
}
function updateVwceTx(id, field, value) {
  if (!state.data.vwce || !Array.isArray(state.data.vwce.tranzactii)) return;
  state.data.vwce.tranzactii = state.data.vwce.tranzactii.map(function(tx) {
    if (tx.id !== id) return tx;
    var u = cloneObj(tx);
    if (field === 'cantitate') {
      var qty = parseInt(value, 10);
      if (isNaN(qty) || qty < 0) qty = 0;
      u.cantitate = qty;
    } else if (field === 'comision') {
      u[field] = parseRON(value);
    } else {
      u[field] = value;
    }
    // Recompute auto fields when data or cantitate changes
    if (field === 'data' || field === 'cantitate') {
      var pretZi = getVwcePriceOnDate(u.data);
      u.pretAchizitie = pretZi;
      u.sumaEur = (u.cantitate || 0) * pretZi;
    }
    return u;
  });
  saveData();
  render();
}
function removeVwceTx(id) {
  if (!state.data.vwce) return;
  state.data.vwce.tranzactii = (state.data.vwce.tranzactii || []).filter(function(tx) { return tx.id !== id; });
  saveData();
  render();
}

function addEtf() {
  if (!Array.isArray(state.data.etf)) state.data.etf = [];
  state.data.etf.push({
    id: getNextId(state.data.etf),
    simbol: '',
    nume: '',
    isin: '',
    cantitate: 0,
    pretMediu: 0,
    pretCurent: 0,
    moneda: 'RON',
    sursa: 'BVB',
    broker: 'Tradeville',
    dataAchizitie: '',
    nota: ''
  });
  saveData();
  render();
}
function updateEtf(id, field, value) {
  if (!Array.isArray(state.data.etf)) return;
  state.data.etf = state.data.etf.map(function(e) {
    if (e.id !== id) return e;
    var u = cloneObj(e);
    if (field === 'cantitate' || field === 'pretMediu' || field === 'pretCurent') u[field] = parseRON(value);
    else u[field] = value;
    return u;
  });
  saveData();
  render();
}
function removeEtf(id) {
  state.data.etf = (state.data.etf || []).filter(function(e) { return e.id !== id; });
  saveData();
  render();
}

// ====================================================================
// MAIN RENDER
// ====================================================================
function render() {
  var tabs = [
    { id: 'buget-lunar',  label: 'Dashboard',  icon: 'layout-dashboard' },
    { id: 'venituri',     label: 'Cash flow',  icon: 'arrow-left-right' },
    { id: 'credite',      label: 'Credit',     icon: 'landmark' },
    { id: 'investitii',   label: 'Investiții', icon: 'trending-up' },
    { id: 'goals',        label: 'Obiective',  icon: 'target' },
    { id: 'setari',       label: 'Setări',     icon: 'sliders-horizontal' },
  ];

  var tabContent = {
    'buget-lunar': renderBugetLunar,
    'credite': renderCredite,
    'investitii': renderInvestitiiTab,
    'goals': renderGoals,
    'setari': renderSetari,
    'venituri': renderVenituri,
  };

  // Guard: drop stale tab ids (e.g. removed 'fond-urgenta')
  if (!tabContent[state.activeTab]) state.activeTab = 'buget-lunar';

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
  html += '      <button class="icon-btn" onclick="toggleTheme()" title="Comută tema"><i data-lucide="' + themeIcon + '"></i></button>';
  html += '      <div class="actions-wrap">';
  html += '        <button class="icon-btn" onclick="toggleActionsMenu(event)" title="Mai multe acțiuni" id="btn-actions"><i data-lucide="more-vertical"></i></button>';
  html += '        <div class="actions-menu" id="actions-menu">';
  html += '          <button class="menu-item" onclick="closeActionsMenu();exportCSV()"><i data-lucide="download"></i> Export CSV</button>';
  html += '          <button class="menu-item" onclick="closeActionsMenu();showAudit()"><i data-lucide="history"></i> Istoric modificări</button>';
  html += '          <div class="menu-divider"></div>';
  html += '          <button class="menu-item danger" onclick="closeActionsMenu();resetData()"><i data-lucide="rotate-ccw"></i> Resetează date</button>';
  html += '          <div class="menu-divider"></div>';
  html += '          <a class="menu-item" href="/logout"><i data-lucide="log-out"></i> Ieșire</a>';
  html += '        </div>';
  html += '      </div>';
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
  if (tabId === 'credite') setTimeout(recalcSimulare, 0);
  if (tabId === 'investitii') maybeAutoRefreshVwce();
}

function maybeAutoRefreshVwce() {
  var v = (state.data && state.data.vwce) || null;
  if (!v) return;
  var last = v.lastUpdateLocal ? new Date(v.lastUpdateLocal).getTime() : 0;
  var ageMs = Date.now() - last;
  // Refresh if older than 1h or never fetched
  if (ageMs > 60 * 60 * 1000) {
    refreshVwcePrice(true);
  }
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

// Parse ING transaction export CSV. Returns [{data, dataIso, detalii, beneficiar, tranzactieAt, ref, suma, sens}]
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
        ref: '',
        descriereFull: (cols[3] || '').trim(),
        suma: debit > 0 ? debit : credit,
        sens: sens,
      };
    } else if (current) {
      var meta = (cols[3] || '').trim();
      if (!meta) continue;
      current.descriereFull += ' | ' + meta;
      if (/^Beneficiar:/i.test(meta)) current.beneficiar = meta.replace(/^Beneficiar:/i, '').trim();
      else if (/^Tranzactie la:/i.test(meta)) current.tranzactieAt = meta.replace(/^Tranzactie la:/i, '').trim();
      else if (/^Referinta:/i.test(meta)) current.ref = meta.replace(/^Referinta:/i, '').trim();
      else if (/^Numar autorizare:/i.test(meta) && !current.ref) current.ref = 'auth:' + meta.replace(/^Numar autorizare:/i, '').trim();
    }
    if (cols[1] && /Roxana Petria|Alexandra Ilie|Sef Serviciu/i.test(cols[1])) {
      if (current) { tx.push(current); current = null; }
    }
  }
  if (current) tx.push(current);
  // Synthetic ref fallback (data + suma + first 30 chars of detalii) so duplicate detection works even when Referinta missing
  tx.forEach(function(t) {
    if (!t.ref) t.ref = 'syn:' + (t.dataIso || t.data) + ':' + (t.suma || 0).toFixed(2) + ':' + (t.detalii || '').substring(0, 30);
  });
  return tx;
}

// Suggest a regex pattern from a transaction's merchant/beneficiar
function suggestPatternFromTx(tx) {
  var source = (tx.tranzactieAt || tx.beneficiar || tx.detalii || '').toUpperCase();
  // Strip trailing country/city tail (e.g. "BOLT.EUO2605151016  EE  Tallinn")
  source = source.replace(/\s+(RO|EE|US|DE|FR|GB|IT|ES|NL|BE)\s+.*/i, '');
  // Take a meaningful chunk: alpha+digits before two-spaces or end
  var m = source.match(/^[A-ZĂÂÎȘȚ0-9\.\&\-]{3,}(?:[\s\.][A-ZĂÂÎȘȚ0-9\.\&\-]{3,})?/);
  if (!m) return null;
  var token = m[0].replace(/\d+$/, '').trim(); // strip trailing digits
  if (token.length < 3) return null;
  // Escape regex metachars
  return token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
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
    '    <div class="field"><label class="field-label">Selectează fișierul CSV exportat din ING Home\'Bank — venituri și cheltuieli se importă împreună</label>' +
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
  var importFileName = '';
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
    importFileName = f.name || 'import.csv';
    var reader = new FileReader();
    reader.onload = function() {
      try {
        var text = reader.result;
        parsed = parseIngCsv(text).filter(function(t) { return (t.sens === 'debit' || t.sens === 'credit') && t.suma > 0; });
        var reguli = state.data.reguliCategorizare || [];
        var importedSet = (state.data.importedRefs || []).reduce(function(s, r) { s[r] = true; return s; }, {});
        var chCats = (state.data.categoriiVar || []).map(function(c) { return c.label; })
          .concat((state.data.cheltuieliFixe || []).map(function(c) { return c.label; }));
        var venitCats = (state.data.categoriiVenit || []).map(function(c) { return c.label; });
        parsed.forEach(function(t) {
          t.tip = t.sens === 'credit' ? 'venit' : 'cheltuiala';
          t.duplicate = !!(t.ref && importedSet[t.ref]);
          t.autoCategoryInitial = categorizeAuto(t, reguli);
          var auto = t.autoCategoryInitial;
          var pool = t.tip === 'venit' ? venitCats : chCats;
          if (t.duplicate) {
            t.categorie = '__SKIP__'; t.skip = true;
          } else if (auto === '__SKIP__') {
            t.categorie = '__SKIP__'; t.skip = true;
          } else if (auto && pool.indexOf(auto) >= 0) {
            t.categorie = auto; t.skip = false;
          } else {
            // fallback to the catch-all category for this type
            t.categorie = pool.length ? pool[pool.length - 1] : '__SKIP__';
            t.skip = (t.categorie === '__SKIP__');
          }
          t.userOverridden = false;
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
    var chCategories = IMPORT_SPECIAL_CATS.concat(
      (state.data.cheltuieliFixe || []).map(function(c) { return c.label; }),
      (state.data.categoriiVar || []).map(function(c) { return c.label; })
    );
    var venitCategories = ['__SKIP__'].concat(
      (state.data.categoriiVenit || []).map(function(c) { return c.label; })
    );
    var nSkip = 0, nApplyCh = 0, nApplyV = 0, nDup = 0, nInvest = 0;
    parsed.forEach(function(t) {
      if (t.duplicate) { nDup++; return; }
      if (t.categorie === '__SKIP__') { nSkip++; return; }
      if (t.categorie === '__TEZAUR__' || t.categorie === '__TRADEVILLE__') { nInvest++; return; }
      if (t.tip === 'venit') nApplyV++;
      else nApplyCh++;
    });
    summary.style.display = 'flex';
    summary.querySelector('div').innerHTML =
      '<strong>' + parsed.length + '</strong> tranzacții găsite' +
      ' <span class="sep">·</span> <strong>' + nApplyCh + '</strong> cheltuieli' +
      ' <span class="sep">·</span> <strong>' + nApplyV + '</strong> venituri' +
      (nInvest > 0 ? ' <span class="sep">·</span> <strong>' + nInvest + '</strong> investiții' : '') +
      ' <span class="sep">·</span> <strong>' + nSkip + '</strong> ignorate' +
      (nDup > 0 ? ' <span class="sep">·</span> <strong>' + nDup + '</strong> duplicate' : '');
    applyBtn.disabled = ((nApplyCh + nApplyV + nInvest) === 0);

    var h = '<div class="table-wrap"><table>';
    h += '<thead><tr><th>Data</th><th>Tip</th><th>Descriere</th><th class="num">Sumă</th><th>Categorie</th></tr></thead><tbody>';
    parsed.forEach(function(t, idx) {
      var descShort = t.detalii + (t.tranzactieAt ? ' — ' + t.tranzactieAt : (t.beneficiar ? ' — ' + t.beneficiar : ''));
      var rowStyle = '';
      if (t.duplicate) rowStyle = ' style="opacity:0.35;"';
      else if (t.categorie === '__SKIP__') rowStyle = ' style="opacity:0.45;"';
      var isVenit = t.tip === 'venit';
      var isInvest = t.categorie === '__TEZAUR__' || t.categorie === '__TRADEVILLE__';
      var tipChip = isInvest
        ? '<span class="tag" style="background:var(--violet-soft);color:var(--violet);">investiție</span>'
        : (isVenit
          ? '<span class="tag" style="background:var(--success-soft);color:var(--success);">venit</span>'
          : '<span class="tag" style="background:var(--danger-soft);color:var(--danger);">cheltuială</span>');
      h += '<tr' + rowStyle + '>';
      h += '<td class="mono">' + esc(t.dataIso || t.data) + (t.duplicate ? ' <span class="tag" style="background:var(--warning-soft);color:var(--warning);font-size:0.62rem;">dup</span>' : '') + '</td>';
      h += '<td>' + tipChip + '</td>';
      h += '<td style="max-width:300px;font-size:0.78rem;">' + esc(descShort) + '</td>';
      h += '<td class="num ' + (isVenit ? 'pl-pos' : 'neg') + '">' + (isVenit ? '+' : '') + formatRON(t.suma) + '</td>';
      h += '<td><select class="select" data-imp-cat="' + idx + '">';
      (isVenit ? venitCategories : chCategories).forEach(function(c) {
        var lbl = (IMPORT_SPECIAL_CATS.indexOf(c) >= 0) ? specialCatLabel(c) : c;
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
        var t = parsed[idx];
        t.categorie = sel.value;
        t.skip = sel.value === '__SKIP__';
        // If user picked a different category than what auto suggested, flag for learning
        if (t.autoCategoryInitial !== sel.value && !t.duplicate) t.userOverridden = true;
        else t.userOverridden = false;
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
      var addedCh = 0, addedV = 0, addedTez = 0, addedTrv = 0, refsAdded = [];
      var importItems = [];   // recorded for undo
      // Collect candidate new rules from user overrides
      var ruleProposals = {};
      parsed.forEach(function(t) {
        if (t.duplicate) return;
        if (t.userOverridden && t.categorie && t.categorie !== '__SKIP__') {
          var pat = suggestPatternFromTx(t);
          if (pat && pat.length >= 3) {
            var key = pat + '|' + t.categorie;
            ruleProposals[key] = ruleProposals[key] || { pattern: pat, categorie: t.categorie, count: 0 };
            ruleProposals[key].count++;
          }
        }
        if (t.categorie === '__SKIP__') return;
        var mk = t.dataIso ? t.dataIso.substring(0, 7) : null;
        if (!mk) return;
        // Investment transfers — route to Tezaur / Tradeville instead of expenses
        if (t.categorie === '__TEZAUR__') {
          if (!Array.isArray(state.data.tezaur)) state.data.tezaur = [];
          var tezId = getNextId(state.data.tezaur);
          state.data.tezaur.push({
            id: tezId,
            emisiune: ((state.data.emisiuniTezaur || [])[0] || {}).label || 'Tezaur',
            dataSubscriere: t.dataIso || '',
            suma: t.suma,
            dobanda: 0,
            maturitate: '1 an',
            dataScadenta: ''
          });
          importItems.push({ type: 'tezaur', tezaurId: tezId, suma: t.suma, ref: t.ref || '' });
          addedTez++;
          if (t.ref) refsAdded.push(t.ref);
          return;
        }
        if (t.categorie === '__TRADEVILLE__') {
          if (!state.data.vwce) migrateVwce(state.data);
          if (!Array.isArray(state.data.vwce.alimentari)) state.data.vwce.alimentari = [];
          state.data.vwce.alimentari.push({ data: t.dataIso || '', suma: t.suma, ref: t.ref || '' });
          importItems.push({ type: 'tradeville', data: t.dataIso || '', suma: t.suma, ref: t.ref || '' });
          addedTrv++;
          if (t.ref) refsAdded.push(t.ref);
          return;
        }
        if (t.tip === 'venit') {
          if (!state.data.venituri[mk]) state.data.venituri[mk] = {};
          state.data.venituri[mk][t.categorie] = round2((state.data.venituri[mk][t.categorie] || 0) + t.suma);
          importItems.push({ type: 'venit', mk: mk, categorie: t.categorie, suma: t.suma, ref: t.ref || '' });
          addedV++;
        } else {
          if (fixedLabels[t.categorie]) return; // fixed expenses counted via the fixed row
          if (!state.data.cheltuieli[mk]) state.data.cheltuieli[mk] = {};
          state.data.cheltuieli[mk][t.categorie] = round2((state.data.cheltuieli[mk][t.categorie] || 0) + t.suma);
          importItems.push({ type: 'cheltuiala', mk: mk, categorie: t.categorie, suma: t.suma, ref: t.ref || '' });
          addedCh++;
        }
        if (t.ref) refsAdded.push(t.ref);
      });
      var added = addedCh + addedV;
      // Persist imported refs (deduped)
      if (!Array.isArray(state.data.importedRefs)) state.data.importedRefs = [];
      var refSet = state.data.importedRefs.reduce(function(s, r) { s[r] = true; return s; }, {});
      refsAdded.forEach(function(r) { if (!refSet[r]) { state.data.importedRefs.push(r); refSet[r] = true; } });
      // Record the import session for the history / undo
      if (importItems.length > 0) {
        if (!Array.isArray(state.data.importHistory)) state.data.importHistory = [];
        state.data.importHistory.push({
          id: 'imp_' + Date.now(),
          ts: new Date().toISOString(),
          fileName: importFileName,
          items: importItems,
          summary: { cheltuieli: addedCh, venituri: addedV, tezaur: addedTez, tradeville: addedTrv }
        });
        pruneImportHistory(state.data);
      }
      saveData();
      close();
      render();
      var proposalsList = Object.keys(ruleProposals).map(function(k) { return ruleProposals[k]; });
      // Avoid proposing rules already present
      var existingPatterns = (state.data.reguliCategorizare || []).map(function(r) { return (r.pattern || '').toUpperCase(); });
      proposalsList = proposalsList.filter(function(p) { return existingPatterns.indexOf(p.pattern.toUpperCase()) < 0; });
      setTimeout(function() {
        if (proposalsList.length > 0) {
          showRuleProposals(proposalsList, added);
        } else {
          var invMsg = '';
          if (addedTez > 0) invMsg += ' ' + addedTez + ' subscrieri Tezaur create (completează dobânda în tab Investiții).';
          if (addedTrv > 0) invMsg += ' ' + addedTrv + ' alimentări Tradeville înregistrate.';
          showConfirm({
            title: 'Import complet',
            body: addedCh + ' cheltuieli și ' + addedV + ' venituri adăugate.' + invMsg + ' Cheltuielile fixe au fost păstrate intacte.',
            okLabel: 'OK',
            cancelLabel: '',
            icon: 'check-circle'
          });
        }
      }, 100);
    }
  });
  document.addEventListener('keydown', onKey);
}

// Revert an import session: subtract the amounts, drop created Tezaur rows /
// Tradeville top-ups, release the imported refs, remove the history entry.
async function deleteImport(id) {
  var imp = (state.data.importHistory || []).filter(function(x) { return x.id === id; })[0];
  if (!imp) return;
  var ok = await showConfirm({
    title: 'Șterge importul',
    body: 'Se anulează ' + imp.items.length + ' modificări din "' + imp.fileName + '". Sumele adăugate se scad, subscrierile Tezaur și alimentările Tradeville create de acest import se șterg. Tranzacțiile vor putea fi reimportate.',
    okLabel: 'Șterge importul', cancelLabel: 'Anulează', icon: 'trash-2'
  });
  if (!ok) return;
  var refsToRemove = {};
  (imp.items || []).forEach(function(it) {
    if (it.ref) refsToRemove[it.ref] = true;
    if (it.type === 'cheltuiala') {
      var m = state.data.cheltuieli[it.mk];
      if (m && m[it.categorie] != null) {
        m[it.categorie] = round2(m[it.categorie] - it.suma);
        if (m[it.categorie] <= 0.001) delete m[it.categorie];
      }
    } else if (it.type === 'venit') {
      var mv = state.data.venituri[it.mk];
      if (mv && mv[it.categorie] != null) {
        mv[it.categorie] = round2(mv[it.categorie] - it.suma);
        if (mv[it.categorie] <= 0.001) delete mv[it.categorie];
      }
    } else if (it.type === 'tezaur') {
      state.data.tezaur = (state.data.tezaur || []).filter(function(t) { return t.id !== it.tezaurId; });
    } else if (it.type === 'tradeville') {
      var arr = (state.data.vwce && state.data.vwce.alimentari) || [];
      for (var i = 0; i < arr.length; i++) {
        if ((it.ref && arr[i].ref === it.ref) || (arr[i].data === it.data && arr[i].suma === it.suma)) {
          arr.splice(i, 1); break;
        }
      }
    }
  });
  state.data.importedRefs = (state.data.importedRefs || []).filter(function(r) { return !refsToRemove[r]; });
  state.data.importHistory = (state.data.importHistory || []).filter(function(x) { return x.id !== id; });
  saveData();
  render();
  // Re-open the history so the user sees the result
  setTimeout(showImportHistory, 120);
}

function showImportHistory() {
  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  var hist = (state.data.importHistory || []).slice().sort(function(a, b) {
    return (b.ts || '').localeCompare(a.ts || '');
  });
  var body = '';
  if (hist.length === 0) {
    body = '<div class="audit-empty">Niciun import în ultimele 6 luni. Importurile apar aici după ce încarci un CSV bancar.</div>';
  } else {
    body = '<div class="import-history-list">';
    hist.forEach(function(imp) {
      var when = imp.ts ? new Date(imp.ts).toLocaleString('ro-RO', { dateStyle: 'short', timeStyle: 'short' }) : '';
      var s = imp.summary || {};
      var chips = '';
      if (s.cheltuieli) chips += '<span class="tag" style="background:var(--danger-soft);color:var(--danger);">' + s.cheltuieli + ' cheltuieli</span> ';
      if (s.venituri) chips += '<span class="tag" style="background:var(--success-soft);color:var(--success);">' + s.venituri + ' venituri</span> ';
      if (s.tezaur) chips += '<span class="tag" style="background:var(--violet-soft);color:var(--violet);">' + s.tezaur + ' Tezaur</span> ';
      if (s.tradeville) chips += '<span class="tag" style="background:var(--violet-soft);color:var(--violet);">' + s.tradeville + ' Tradeville</span> ';
      body += '<div class="import-history-item">';
      body += '  <div style="flex:1;min-width:0;">';
      body += '    <div style="font-size:0.85rem;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + esc(imp.fileName || 'import.csv') + '</div>';
      body += '    <div class="mono" style="font-size:0.7rem;color:var(--text-dim);">' + esc(when) + ' · ' + (imp.items || []).length + ' modificări</div>';
      body += '    <div style="margin-top:0.35rem;">' + chips + '</div>';
      body += '  </div>';
      body += '  <button class="btn-del" onclick="deleteImport(\'' + esc(imp.id) + '\')" title="Șterge importul"><i data-lucide="trash-2"></i></button>';
      body += '</div>';
    });
    body += '</div>';
  }
  overlay.innerHTML =
    '<div class="modal" role="dialog" aria-modal="true" style="max-width:560px;">' +
    '  <div class="modal-title"><i data-lucide="history"></i> Istoric importuri (ultimele 6 luni)</div>' +
    '  <div class="modal-body" style="max-height:60vh;overflow:auto;">' + body + '</div>' +
    '  <div class="modal-actions"><button class="modal-btn" data-act="close">Închide</button></div>' +
    '</div>';
  document.body.appendChild(overlay);
  refreshIcons();
  function close() { document.body.removeChild(overlay); document.removeEventListener('keydown', onKey); }
  function onKey(e) { if (e.key === 'Escape') close(); }
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) return close();
    if (e.target.closest('[data-act="close"]')) close();
  });
  document.addEventListener('keydown', onKey);
}

function showRuleProposals(proposals, addedCount) {
  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  var rows = proposals.map(function(p, i) {
    return '<label class="rule-proposal" style="display:flex;align-items:center;gap:0.6rem;padding:0.5rem 0;border-bottom:1px solid var(--border);">' +
      '  <input type="checkbox" data-rp="' + i + '" checked>' +
      '  <span class="mono" style="flex:1;color:var(--accent);">' + esc(p.pattern) + '</span>' +
      '  <i data-lucide="arrow-right" style="color:var(--text-dim);width:14px;height:14px;"></i>' +
      '  <span class="tag">' + esc(p.categorie) + '</span>' +
      '  <span class="mono text-dim" style="font-size:0.72rem;">×' + p.count + '</span>' +
      '</label>';
  }).join('');
  overlay.innerHTML =
    '<div class="modal" role="dialog" aria-modal="true" style="max-width:520px;">' +
    '  <div class="modal-title"><i data-lucide="zap"></i> Învăță reguli noi din corectările tale</div>' +
    '  <div class="modal-body">' +
    '    <div style="margin-bottom:0.75rem;color:var(--text-mid);font-size:0.85rem;">' + addedCount + ' tranzacții importate. Ai modificat manual ' + proposals.length + ' categorii — vrei să adaug reguli automate ca pe viitor să le categorizez singur?</div>' +
    '    <div>' + rows + '</div>' +
    '  </div>' +
    '  <div class="modal-actions">' +
    '    <button class="modal-btn" data-act="skip">Nu, mulțumesc</button>' +
    '    <button class="modal-btn primary" data-act="ok">Adaugă regulile bifate</button>' +
    '  </div>' +
    '</div>';
  document.body.appendChild(overlay);
  refreshIcons();
  function close() { document.body.removeChild(overlay); document.removeEventListener('keydown', onKey); }
  function onKey(e) { if (e.key === 'Escape') close(); }
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) return close();
    var act = e.target.closest('[data-act]');
    if (!act) return;
    if (act.dataset.act === 'skip') return close();
    if (act.dataset.act === 'ok') {
      if (!Array.isArray(state.data.reguliCategorizare)) state.data.reguliCategorizare = [];
      overlay.querySelectorAll('input[data-rp]:checked').forEach(function(cb) {
        var p = proposals[parseInt(cb.dataset.rp, 10)];
        state.data.reguliCategorizare.push({
          id: getNextId(state.data.reguliCategorizare),
          pattern: p.pattern,
          categorie: p.categorie
        });
      });
      saveData();
      close();
      render();
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
  if (state.activeTab === 'investitii') setTimeout(maybeAutoRefreshVwce, 0);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
