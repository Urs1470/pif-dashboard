import { apiFetch } from '../lib/api.js'
import { parseRON, getLuniKeys } from '../lib/budget-calc.js'

const API_BASE = '/budget/api'
const SAVE_DEBOUNCE_MS = 600
const LOCAL_BACKUP_KEY = 'budget-data-backup'

const SCADENTAR_REAL_DEFAULT = [
  { data: "2026-05-18", suma: 1793.9, dobanda: 682.11, principal: 1111.79, soldFinal: 81935.69, asigurare: 146.99 },
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
  { data: "2028-05-18", suma: 1786.53, dobanda: 449.95, principal: 1336.58, soldFinal: 52712.57, asigurare: 94.56 },
  { data: "2028-06-18", suma: 1786.53, dobanda: 438.82, principal: 1347.71, soldFinal: 51364.86, asigurare: 92.14 },
  { data: "2028-07-18", suma: 1786.53, dobanda: 427.59, principal: 1358.94, soldFinal: 50005.92, asigurare: 89.7 },
  { data: "2028-08-18", suma: 1786.53, dobanda: 416.28, principal: 1370.25, soldFinal: 48635.67, asigurare: 87.24 },
  { data: "2028-09-18", suma: 1786.53, dobanda: 404.87, principal: 1381.66, soldFinal: 47254.01, asigurare: 84.76 },
  { data: "2028-10-18", suma: 1786.53, dobanda: 393.37, principal: 1393.16, soldFinal: 45860.85, asigurare: 82.26 },
  { data: "2028-11-18", suma: 1786.53, dobanda: 381.77, principal: 1404.76, soldFinal: 44456.09, asigurare: 79.74 },
  { data: "2028-12-18", suma: 1786.53, dobanda: 370.08, principal: 1416.45, soldFinal: 43039.64, asigurare: 77.2 },
  { data: "2029-01-18", suma: 1786.53, dobanda: 358.29, principal: 1428.24, soldFinal: 41611.4, asigurare: 74.64 },
  { data: "2029-02-18", suma: 1786.53, dobanda: 346.4, principal: 1440.13, soldFinal: 40171.27, asigurare: 72.06 },
  { data: "2029-03-18", suma: 1786.53, dobanda: 334.41, principal: 1452.12, soldFinal: 38719.15, asigurare: 69.46 },
  { data: "2029-04-18", suma: 1786.53, dobanda: 322.32, principal: 1464.21, soldFinal: 37254.94, asigurare: 66.84 },
  { data: "2029-05-18", suma: 1786.53, dobanda: 310.13, principal: 1476.4, soldFinal: 35778.54, asigurare: 64.2 },
  { data: "2029-06-18", suma: 1786.53, dobanda: 297.84, principal: 1488.69, soldFinal: 34289.85, asigurare: 61.54 },
  { data: "2029-07-18", suma: 1786.53, dobanda: 285.44, principal: 1501.09, soldFinal: 32788.76, asigurare: 58.86 },
  { data: "2029-08-18", suma: 1786.53, dobanda: 272.95, principal: 1513.58, soldFinal: 31275.18, asigurare: 56.16 },
  { data: "2029-09-18", suma: 1786.53, dobanda: 260.34, principal: 1526.19, soldFinal: 29748.99, asigurare: 53.44 },
  { data: "2029-10-18", suma: 1786.53, dobanda: 247.64, principal: 1538.89, soldFinal: 28210.1, asigurare: 50.7 },
  { data: "2029-11-18", suma: 1786.53, dobanda: 234.82, principal: 1551.71, soldFinal: 26658.39, asigurare: 47.94 },
  { data: "2029-12-18", suma: 1786.53, dobanda: 221.9, principal: 1564.63, soldFinal: 25093.76, asigurare: 45.16 },
  { data: "2030-01-18", suma: 1786.53, dobanda: 208.87, principal: 1577.66, soldFinal: 23516.1, asigurare: 42.36 },
  { data: "2030-02-18", suma: 1786.53, dobanda: 195.74, principal: 1590.79, soldFinal: 21925.31, asigurare: 39.54 },
  { data: "2030-03-18", suma: 1786.53, dobanda: 182.49, principal: 1604.04, soldFinal: 20321.27, asigurare: 36.7 },
  { data: "2030-04-18", suma: 1786.53, dobanda: 169.13, principal: 1617.4, soldFinal: 18703.87, asigurare: 33.84 },
  { data: "2030-05-18", suma: 1786.53, dobanda: 155.67, principal: 1630.86, soldFinal: 17073.01, asigurare: 30.96 },
  { data: "2030-06-18", suma: 1786.53, dobanda: 142.09, principal: 1644.44, soldFinal: 15428.57, asigurare: 28.06 },
  { data: "2030-07-18", suma: 1786.53, dobanda: 128.39, principal: 1658.14, soldFinal: 13770.43, asigurare: 25.14 },
  { data: "2030-08-18", suma: 1786.53, dobanda: 114.59, principal: 1671.94, soldFinal: 12098.49, asigurare: 22.2 },
  { data: "2030-09-18", suma: 1786.53, dobanda: 100.67, principal: 1685.86, soldFinal: 10412.63, asigurare: 19.24 },
  { data: "2030-10-18", suma: 1786.53, dobanda: 86.63, principal: 1699.9, soldFinal: 8712.73, asigurare: 16.26 },
  { data: "2030-11-18", suma: 1786.53, dobanda: 72.48, principal: 1714.05, soldFinal: 6998.68, asigurare: 13.26 },
  { data: "2030-12-18", suma: 1786.53, dobanda: 58.21, principal: 1728.32, soldFinal: 5270.36, asigurare: 10.24 },
  { data: "2031-01-18", suma: 1786.53, dobanda: 43.83, principal: 1742.7, soldFinal: 3527.66, asigurare: 7.2 },
  { data: "2031-02-18", suma: 3556.96, dobanda: 29.34, principal: 3527.62, soldFinal: 0.04, asigurare: 4.14 },
]

const CHELTUIELI_VAR_DEFAULT = [
  'Chirie', 'Alimente', 'Mancare restaurant', 'Transport', 'Utilitati & facturi',
  'Sanatate & ingrijire', 'Imbracaminte', 'Casa & intretinere',
  'Divertisment & timp liber', 'Abonamente', 'Educatie & dezvoltare',
  'Cadouri & evenimente', 'Calatorii & vacante', 'Taxe & asigurari',
  'Alte credite', 'Alte'
]

const CATEGORII_VENIT_DEFAULT = [
  { id: 1, label: 'Bonuri de masa' },
  { id: 2, label: 'Bonus & prime' },
  { id: 3, label: 'Diurna & deconturi' },
  { id: 4, label: 'Dobanzi & dividende' },
  { id: 5, label: 'Alte venituri' },
]

const REGULI_DEFAULT = [
  { id: 1, pattern: 'Rata Credit', categorie: '__SKIP__' },
  { id: 2, pattern: 'Prima asigurare ING Credit Protect', categorie: '__SKIP__' },
  { id: 3, pattern: 'Detalii:chirie', categorie: 'Chirie' },
  { id: 4, pattern: 'Subscriere Tezaur', categorie: '__TEZAUR__' },
  { id: 5, pattern: 'KAUFLAND|AUCHAN|CARREFOUR|MEGA IMAGE|LIDL|PROFI|PENNY|SELGROS|FRESH MARKET', categorie: 'Alimente' },
  { id: 17, pattern: 'RESTAURANT|MCDONALD|KFC|STARBUCKS|BURGER KING|PIZZA|GLOVO|TAZZ|FOODPANDA|SUSHI|TACO|BISTRO|CAFE|COFFEE', categorie: 'Mancare restaurant' },
  { id: 6, pattern: 'ENGIE|ELECTRICA|APA NOVA|E\\.ON|HIDROELECTRICA|ENEL|DISTRIGAZ', categorie: 'Utilitati & facturi' },
  { id: 7, pattern: 'VODAFONE|DIGI|RDS|RCS|ORANGE|TELEKOM', categorie: 'Utilitati & facturi' },
  { id: 8, pattern: 'MEDICAL|FARMACIE|FARMACIA|CATENA|SENSIBLU|HELPNET|REGINA MARIA|MEDLIFE|MEDICOVER', categorie: 'Sanatate & ingrijire' },
  { id: 9, pattern: 'BOLT|UBER|FREE NOW|FREENOW|TAXIFY', categorie: 'Transport' },
  { id: 10, pattern: 'OMV|MOL|PETROM|ROMPETROL|LUKOIL|SOCAR', categorie: 'Transport' },
  { id: 11, pattern: 'NETFLIX|SPOTIFY|HBO|YOUTUBE|APPLE\\.COM|GOOGLE|MICROSOFT|ADOBE', categorie: 'Abonamente' },
  { id: 12, pattern: 'H\\&M|ZARA|RESERVED|BERSHKA|PULL\\&BEAR|C\\&A|DECATHLON', categorie: 'Imbracaminte' },
  { id: 14, pattern: 'SALARIU|VENIT SALARIAL', categorie: '__SKIP__' },
  { id: 15, pattern: 'BONUS|PRIMA|TICHETE|BONURI DE MASA|BONURI MASA', categorie: 'Bonus & prime' },
  { id: 16, pattern: 'DIURNA|DELEGATIE|DECONT DEPLASARE', categorie: 'Diurna & deconturi' },
  { id: 20, pattern: 'DOBANDA|DIVIDEND|CUPON', categorie: 'Dobanzi & dividende' },
]

const DATI_INITIALE = {
  profil: { nume: 'Ion', salariuNet: 7700, startMonth: '2026-05', numarLuni: 12, soldContCurent: 0, bonuriSoldInitial: 0 },
  categoriiVar: CHELTUIELI_VAR_DEFAULT.map((s, i) => ({ id: i + 1, label: s })),
  categoriiVenit: structuredClone(CATEGORII_VENIT_DEFAULT),
  emisiuniTezaur: [{ id: 1, label: 'Tezaur 1 an' }],
  reguliCategorizare: structuredClone(REGULI_DEFAULT),
  credit: { suma: 84450, dobanda: 9.99, dae: 12.96, durata: 58, dataStart: '2026-06-18', contract: '18099406', dataContract: '2026-05-02' },
  fondUrgenta: [],
  tezaur: [],
  venituri: {},
  cheltuieli: {},
  bonuriSold: {},
  vwce: { symbol: 'VWCE.DE', isin: 'IE00BK5BQT80', nume: 'Vanguard FTSE All-World UCITS ETF', exchange: 'XETRA', currency: 'EUR', tranzactii: [], alimentari: [], pretCurent: 0, previousClose: 0, changePct: 0, lastUpdateLocal: null },
  goals: [],
  importHistory: [],
  importedRefs: [],
}

function clone(o) { return JSON.parse(JSON.stringify(o)) }
function getNextId(arr) { return (arr || []).reduce((mx, i) => Math.max(mx, i?.id || 0), 0) + 1 }

// --- Migrations ---
function migrateData(data) {
  if (!data.venituri) data.venituri = {}
  if (!data.cheltuieli) data.cheltuieli = {}
  if (!data.fondUrgenta) data.fondUrgenta = []
  if (!data.tezaur) data.tezaur = []
  if (!data.profil) data.profil = clone(DATI_INITIALE.profil)
  if (!data.profil.startMonth) data.profil.startMonth = '2026-05'
  if (!data.profil.numarLuni) data.profil.numarLuni = 12
  if (data.profil.salariuNet == null) data.profil.salariuNet = 7700

  if (!Array.isArray(data.categoriiVar) || data.categoriiVar.length === 0) {
    data.categoriiVar = CHELTUIELI_VAR_DEFAULT.map((s, i) => ({ id: i + 1, label: s }))
  } else if (typeof data.categoriiVar[0] === 'string') {
    data.categoriiVar = data.categoriiVar.map((s, i) => ({ id: i + 1, label: s }))
  }

  if (!Array.isArray(data.categoriiVenit) || data.categoriiVenit.length === 0) {
    data.categoriiVenit = clone(CATEGORII_VENIT_DEFAULT)
  }

  if (!Array.isArray(data.emisiuniTezaur) || data.emisiuniTezaur.length === 0) {
    data.emisiuniTezaur = [{ id: 1, label: 'Tezaur 1 an' }]
  }

  if (!Array.isArray(data.reguliCategorizare) || data.reguliCategorizare.length === 0) {
    data.reguliCategorizare = clone(REGULI_DEFAULT)
  }

  if (!data.credit) data.credit = clone(DATI_INITIALE.credit)
  if (!Array.isArray(data.credit.scadentar) || data.credit.scadentar.length === 0) {
    data.credit.scadentar = clone(SCADENTAR_REAL_DEFAULT)
  }
  if (!data.credit.durata) data.credit.durata = 58
  if (!data.credit.dataStart) data.credit.dataStart = '2026-06-18'
  if (!data.credit.suma) data.credit.suma = 84450

  if (!data.vwce || typeof data.vwce !== 'object') {
    data.vwce = clone(DATI_INITIALE.vwce)
  }
  if (!Array.isArray(data.vwce.tranzactii)) data.vwce.tranzactii = []
  if (!Array.isArray(data.vwce.alimentari)) data.vwce.alimentari = []

  if (!data.bonuriSold) data.bonuriSold = {}
  if (!Array.isArray(data.goals)) data.goals = []
  if (!Array.isArray(data.importHistory)) data.importHistory = []
  if (!Array.isArray(data.importedRefs)) data.importedRefs = []

  data.fondUrgenta.forEach(f => { if (f && !f.dataStart) f.dataStart = new Date().toISOString().slice(0, 10) })

  if (data.profil.soldContCurent == null) {
    let buf = 0
    if (data.evolutie && typeof data.evolutie === 'object') {
      Object.keys(data.evolutie).forEach(k => { buf += data.evolutie[k]?.buffer || 0 })
    }
    data.profil.soldContCurent = buf
  }
  delete data.evolutie
  delete data.profil.bonusMedie
  if (data.credit) { delete data.credit.rata; delete data.credit.asigurare; delete data.credit.soldActual }
  data.cheltuieliFixe = []

  const luniKeys = getLuniKeys(data)
  luniKeys.forEach(l => {
    if (!data.venituri[l]) data.venituri[l] = {}
    if (!data.cheltuieli[l]) data.cheltuieli[l] = {}
  })

  return data
}

// --- State ---
export const budget = $state({
  data: null,
  loading: true,
  error: null,
  saveStatus: 'saved',
  baseUpdated: undefined,
})

let saveTimer = null

function persistLocalBackup(dirty) {
  try {
    localStorage.setItem(LOCAL_BACKUP_KEY, JSON.stringify({ data: budget.data, ts: new Date().toISOString(), dirty: !!dirty }))
  } catch (_) {}
}

export async function loadBudget() {
  budget.loading = true
  budget.error = null
  try {
    const r = await apiFetch(API_BASE + '/state')
    if (!r.ok) throw new Error('HTTP ' + r.status)
    const payload = await r.json()
    if (payload?.data) {
      budget.baseUpdated = payload.updated || null
      budget.data = migrateData(payload.data)
    } else {
      budget.data = migrateData(clone(DATI_INITIALE))
      budget.baseUpdated = payload?.updated || null
      await saveNow()
    }
    persistLocalBackup(false)
  } catch (e) {
    console.error('Budget load failed:', e)
    const backup = readLocalBackup()
    if (backup?.data) {
      budget.data = migrateData(backup.data)
      budget.baseUpdated = undefined
    } else {
      budget.data = migrateData(clone(DATI_INITIALE))
    }
    budget.error = e.message
  } finally {
    budget.loading = false
  }
}

function readLocalBackup() {
  try {
    const raw = localStorage.getItem(LOCAL_BACKUP_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed?.data ? parsed : null
  } catch (_) { return null }
}

export function markDirty() {
  budget.saveStatus = 'pending'
  persistLocalBackup(true)
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveNow(), SAVE_DEBOUNCE_MS)
}

async function saveNow() {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
  const dataForServer = clone(budget.data)
  if (dataForServer.vwce) delete dataForServer.vwce.priceHistory
  const body = { data: dataForServer }
  if (budget.baseUpdated !== undefined) body.base_updated = budget.baseUpdated

  try {
    const r = await apiFetch(API_BASE + '/state', { method: 'POST', body })
    if (r.status === 409) {
      const conflict = await r.json()
      budget.baseUpdated = conflict.server_updated
      budget.data = migrateData(conflict.server_data)
      budget.saveStatus = 'conflict'
      return
    }
    if (!r.ok) throw new Error('HTTP ' + r.status)
    const result = await r.json()
    budget.baseUpdated = result.updated
    budget.saveStatus = 'saved'
    persistLocalBackup(false)
  } catch (e) {
    console.error('Budget save failed:', e)
    budget.saveStatus = 'error'
  }
}

export function updateField(path, value) {
  let obj = budget.data
  const parts = path.split('.')
  for (let i = 0; i < parts.length - 1; i++) {
    if (!obj[parts[i]]) obj[parts[i]] = {}
    obj = obj[parts[i]]
  }
  obj[parts[parts.length - 1]] = value
  markDirty()
}

export function getNextBudgetId(arr) { return getNextId(arr) }

export async function refreshVwcePrice() {
  try {
    const r = await apiFetch(API_BASE + '/quote/VWCE.DE')
    if (!r.ok) return
    const q = await r.json()
    if (q.price) {
      budget.data.vwce.pretCurent = q.price
      budget.data.vwce.previousClose = q.previousClose || 0
      budget.data.vwce.changePct = q.changePct || 0
      budget.data.vwce.change = q.change || 0
      budget.data.vwce.lastUpdateLocal = new Date().toISOString()
      if (q.history) budget.data.vwce.priceHistory = q.history
      markDirty()
    }
  } catch (_) {}
}
