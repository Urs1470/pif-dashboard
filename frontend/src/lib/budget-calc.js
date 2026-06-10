const LUNI_LABELS_RO = ['Ian','Feb','Mar','Apr','Mai','Iun','Iul','Aug','Sep','Oct','Noi','Dec']

export function round2(n) {
  if (typeof n !== 'number' || !isFinite(n)) return 0
  return Math.round((n + (n >= 0 ? 1 : -1) * Number.EPSILON) * 100) / 100
}

export function formatRON(num) {
  if (num === null || num === undefined || num === '') return ''
  const n = parseFloat(num) || 0
  return new Intl.NumberFormat('ro-RO', { style: 'decimal', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)
}

export function parseRON(str) {
  if (str == null) return 0
  let s = String(str).trim().replace(/\s/g, '')
  if (!s) return 0
  const neg = /^-/.test(s)
  s = s.replace(/[^0-9.,]/g, '')
  if (!s) return 0
  const lastComma = s.lastIndexOf(',')
  const lastDot = s.lastIndexOf('.')
  if (lastComma > -1 && lastDot > -1) {
    if (lastComma > lastDot) s = s.replace(/\./g, '').replace(/,/g, '.')
    else s = s.replace(/,/g, '')
  } else if (lastComma > -1) {
    const commaCount = (s.match(/,/g) || []).length
    if (commaCount > 1) s = s.replace(/,/g, '')
    else if (/^\d{1,3},\d{3}$/.test(s)) s = s.replace(/,/g, '')
    else s = s.replace(/,/g, '.')
  } else if (lastDot > -1) {
    const dotCount = (s.match(/\./g) || []).length
    if (dotCount > 1) s = s.replace(/\./g, '')
    else if (/^\d{1,3}\.\d{3}$/.test(s)) s = s.replace(/\./g, '')
  }
  const n = parseFloat(s)
  if (isNaN(n)) return 0
  return round2(neg ? -Math.abs(n) : n)
}

export function todayIso() {
  const d = new Date()
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
}

export function diffMonths(a, b) {
  if (!a || !b) return 0
  const ap = String(a).split('-'), bp = String(b).split('-')
  return (parseInt(bp[0], 10) - parseInt(ap[0], 10)) * 12 + (parseInt(bp[1], 10) - parseInt(ap[1], 10))
}

export function addMonthsIso(iso, months) {
  if (!iso) return ''
  const p = String(iso).split('-')
  const y = parseInt(p[0], 10), mo = parseInt(p[1], 10), day = parseInt(p[2] || '1', 10)
  if (!y || !mo) return ''
  const idx = (mo - 1) + months
  const ny = y + Math.floor(idx / 12)
  const nm = (idx % 12) + 1
  const lastDay = new Date(ny, nm, 0).getDate()
  const d = Math.min(day || 1, lastDay)
  return ny + '-' + String(nm).padStart(2, '0') + '-' + String(d).padStart(2, '0')
}

export function daysBetween(isoA, isoB) {
  if (!isoA || !isoB) return 0
  const a = new Date(isoA + 'T00:00:00'), b = new Date(isoB + 'T00:00:00')
  if (isNaN(a) || isNaN(b)) return 0
  return Math.round((b - a) / 86400000)
}

export function prevMonthKey(ym) {
  const p = String(ym || '').split('-')
  let y = parseInt(p[0], 10), m = parseInt(p[1], 10)
  if (!y || !m) return null
  m -= 1
  if (m < 1) { m = 12; y -= 1 }
  return y + '-' + (m < 10 ? '0' : '') + m
}

export function generateLuni(startMonth, count) {
  startMonth = startMonth || '2026-05'
  const n = Math.max(1, Math.min(120, parseInt(count, 10) || 12))
  const parts = String(startMonth).split('-')
  const year = parseInt(parts[0], 10) || 2026
  const month = parseInt(parts[1], 10) || 5
  const keys = [], labels = []
  for (let i = 0; i < n; i++) {
    const idx = (month - 1 + i)
    const m = (idx % 12) + 1
    const y = year + Math.floor(idx / 12)
    keys.push(y + '-' + (m < 10 ? '0' : '') + m)
    labels.push(LUNI_LABELS_RO[m - 1] + (y !== year ? " '" + String(y % 100).padStart(2, '0') : ''))
  }
  return { keys, labels }
}

export function maturitateLuni(s) {
  if (!s) return 12
  const m = String(s).match(/(\d+)\s*(luni|lun[ăa]|ani|an)/i)
  if (!m) return 12
  const n = parseInt(m[1], 10) || 1
  return /lun/i.test(m[2]) ? n : n * 12
}

// --- Credit ---
export function getScadentar(d) {
  return (d?.credit?.scadentar) || []
}

export function rataCredituluiLuna(d, lunaKey) {
  const scad = getScadentar(d)
  for (const p of scad) {
    if ((p.data || '').substring(0, 7) === lunaKey) {
      return round2((p.suma || 0) + (p.asigurare || 0))
    }
  }
  return 0
}

export function totalFixeLuna(d, lunaKey) {
  return round2(rataCredituluiLuna(d, lunaKey))
}

export function platiTrecute(scadentar, refIso) {
  return scadentar.filter(p => p.data <= refIso)
}

export function platiViitoare(scadentar, refIso) {
  return scadentar.filter(p => p.data > refIso)
}

export function soldDupaPlatiTrecute(scadentar, refIso, sumaInitiala) {
  const trec = platiTrecute(scadentar, refIso)
  if (trec.length === 0) return sumaInitiala || 0
  return trec[trec.length - 1].soldFinal
}

export function getSoldCurent(d) {
  return soldDupaPlatiTrecute(getScadentar(d), todayIso(), d?.credit?.suma || 0)
}

// --- Meal card ---
const BONURI_CAT = 'Bonuri de masă'

export function cheltuieliBonuriLuna(d, lunaKey) {
  const sold = d.bonuriSold || {}
  const raw = sold[lunaKey]
  if (raw == null || raw === '') return 0
  const prevKey = prevMonthKey(lunaKey)
  const prevRaw = prevKey ? sold[prevKey] : null
  let soldDeschidere
  if (prevRaw != null && prevRaw !== '') {
    soldDeschidere = parseRON(prevRaw) || 0
  } else {
    soldDeschidere = parseRON(d.profil?.bonuriSoldInitial) || 0
  }
  const incarcat = (d.venituri[lunaKey] || {})[BONURI_CAT] || 0
  const cheltuit = soldDeschidere + incarcat - (parseRON(raw) || 0)
  return cheltuit > 0 ? round2(cheltuit) : 0
}

// --- Investments outflow ---
export function investitiiLuna(d, lunaKey) {
  const al = d.vwce?.alimentari || []
  return round2(al.reduce((s, a) => {
    return ((a.data || '').substring(0, 7) === lunaKey) ? s + (parseRON(a.suma) || 0) : s
  }, 0))
}

// --- Per-month totals ---
export function totalVenituriLuna(d, lk) {
  const v = d.venituri[lk] || {}
  return (d.profil.salariuNet || 0) +
    (d.categoriiVenit || []).reduce((s, c) => s + (v[c.label] || 0), 0)
}

export function totalCheltuieliLuna(d, lk) {
  const c = d.cheltuieli[lk] || {}
  return totalFixeLuna(d, lk) + cheltuieliBonuriLuna(d, lk) +
    Object.values(c).reduce((s, x) => s + x, 0)
}

export function surplusLuna(d, lk) {
  return round2(totalVenituriLuna(d, lk) - totalCheltuieliLuna(d, lk) - investitiiLuna(d, lk))
}

export function luniReprezentative(d) {
  const luniKeys = getLuniKeys(d)
  return luniKeys.filter(l => {
    const v = d.venituri[l] || {}, c = d.cheltuieli[l] || {}
    return Object.keys(v).some(k => (v[k] || 0) > 0) || Object.keys(c).some(k => (c[k] || 0) > 0)
  })
}

export function getLuniKeys(d) {
  const prof = d?.profil || {}
  const { keys } = generateLuni(prof.startMonth || '2026-05', parseInt(prof.numarLuni, 10) || 12)
  return keys
}

export function getLuniLabels(d) {
  const prof = d?.profil || {}
  const { labels } = generateLuni(prof.startMonth || '2026-05', parseInt(prof.numarLuni, 10) || 12)
  return labels
}

export function soldDisponibilLuna(d, lk) {
  const rep = luniReprezentative(d)
  let bal = parseRON(d.profil?.soldContCurent) || 0
  for (const r of rep) {
    bal += surplusLuna(d, r)
    if (r === lk) return round2(bal)
  }
  return null
}

export function soldDisponibilCurent(d) {
  const rep = luniReprezentative(d)
  if (rep.length === 0) return parseRON(d.profil?.soldContCurent) || 0
  return soldDisponibilLuna(d, rep[rep.length - 1])
}

// --- Averages ---
export function calcMediiVenituri(d) {
  const cats = d.categoriiVenit || []
  const luni = luniReprezentative(d)
  const count = luni.length || 1
  const variabile = {}
  let totalVar = 0
  cats.forEach(c => {
    const sum = luni.reduce((s, l) => s + ((d.venituri[l] || {})[c.label] || 0), 0) / count
    variabile[c.label] = sum
    totalVar += sum
  })
  const salariuNet = d.profil?.salariuNet || 0
  return { salariu: salariuNet, variabile, categorii: cats, total: salariuNet + totalVar, luniCount: luni.length }
}

export function calcMediiCheltuieli(d) {
  const luni = luniReprezentative(d)
  const count = luni.length || 1
  const totalFixe = luni.reduce((s, l) => s + totalFixeLuna(d, l), 0) / count
  const rataCreditMedie = round2(luni.reduce((s, l) => s + rataCredituluiLuna(d, l), 0) / count)
  const bonuriMedie = round2(luni.reduce((s, l) => s + cheltuieliBonuriLuna(d, l), 0) / count)
  const cats = d.categoriiVar || []
  const variabile = {}
  let totalVar = 0
  cats.forEach(c => {
    variabile[c.label] = luni.reduce((s, l) => s + ((d.cheltuieli[l] || {})[c.label] || 0), 0) / count
    totalVar += variabile[c.label]
  })
  return { fixe: [], totalFixe, rataCreditMedie, bonuriMedie, variabile, categorii: cats, total: totalFixe + bonuriMedie + totalVar, luniCount: luni.length }
}

// --- Tezaur ---
export function tezaurMetrics(t) {
  const suma = parseRON(t.suma) || 0
  const dobPct = parseRON(t.dobanda) || 0
  const luni = maturitateLuni(t.maturitate)
  const dataScad = t.dataSubscriere ? addMonthsIso(t.dataSubscriere, luni) : (t.dataScadenta || '')
  const dobandaAnuala = suma * dobPct / 100
  const dobandaTotala = dobandaAnuala * luni / 12
  const today = todayIso()
  const neinceput = !!(t.dataSubscriere && t.dataSubscriere > today)
  const zileTotal = (t.dataSubscriere && dataScad) ? daysBetween(t.dataSubscriere, dataScad) : 0
  const zileTrecute = t.dataSubscriere ? Math.max(0, daysBetween(t.dataSubscriere, today)) : 0
  const fractie = zileTotal > 0 ? Math.min(1, zileTrecute / zileTotal) : 0
  const dobandaAcumulata = round2(dobandaTotala * fractie)
  const matur = dataScad ? (today >= dataScad) : false
  const zileRamase = dataScad ? daysBetween(today, dataScad) : 0
  return {
    suma, dobPct, luni, dataScad,
    dobandaAnuala, dobandaTotala: round2(dobandaTotala),
    dobandaAcumulata, valoareAzi: round2(suma + dobandaAcumulata),
    valoareLaScadenta: round2(suma + dobandaTotala),
    matur, neinceput, zileRamase, progres: Math.round(fractie * 100)
  }
}

// --- Fond urgenta ---
export function fondValoareLa(f, dateIso) {
  const principal = parseRON(f.suma) || 0
  const start = f.dataStart || todayIso()
  if (!dateIso || dateIso <= start || principal <= 0) return principal
  const r1 = (parseRON(f.dobanda) || 0) / 100 * 0.9
  function grow(val, rate, fromIso, toIso) {
    const days = Math.max(0, daysBetween(fromIso, toIso))
    return val * Math.pow(1 + rate, days / 365)
  }
  if (f.dataMaturare && dateIso > f.dataMaturare && start < f.dataMaturare) {
    const r2raw = (f.dobandaDupa != null && f.dobandaDupa !== '') ? parseRON(f.dobandaDupa) : parseRON(f.dobanda)
    const r2 = (r2raw || 0) / 100 * 0.9
    const atMat = grow(principal, r1, start, f.dataMaturare)
    return atMat * Math.pow(1 + r2, Math.max(0, daysBetween(f.dataMaturare, dateIso)) / 365)
  }
  return grow(principal, r1, start, dateIso)
}

export function fondMetrics(f) {
  const today = todayIso()
  const principal = parseRON(f.suma) || 0
  const valoareAzi = round2(fondValoareLa(f, today))
  return {
    principal, valoareAzi,
    dobandaAcumulata: round2(valoareAzi - principal),
    la1an: round2(fondValoareLa(f, addMonthsIso(today, 12))),
    la2ani: round2(fondValoareLa(f, addMonthsIso(today, 24))),
    la5ani: round2(fondValoareLa(f, addMonthsIso(today, 60))),
    matur: !!(f.dataMaturare && today > f.dataMaturare)
  }
}

export function totalFondAzi(d) {
  return (d.fondUrgenta || []).reduce((s, f) => s + fondValoareLa(f, todayIso()), 0)
}

// --- VWCE ---
export function vwceTotals(v) {
  const tranzactii = v?.tranzactii || []
  const cantitate = tranzactii.reduce((s, t) => s + (parseInt(t.cantitate, 10) || 0), 0)
  const investitEur = tranzactii.reduce((s, t) => {
    const qty = parseInt(t.cantitate, 10) || 0
    const pret = parseRON(t.pretAchizitie) || 0
    return s + qty * pret + (parseRON(t.comision) || 0)
  }, 0)
  const pretMediu = cantitate > 0 ? investitEur / cantitate : 0
  const pretCurent = parseRON(v?.pretCurent) || 0
  const valoareEur = cantitate * pretCurent
  const plEur = valoareEur - investitEur
  const plPct = investitEur > 0 ? (plEur / investitEur) * 100 : 0
  return { cantitate, investitEur, pretMediu, pretCurent, valoareEur, plEur, plPct }
}

export function calcLuniRamase(d) {
  const scad = getScadentar(d)
  if (scad.length > 0) return platiViitoare(scad, todayIso()).length
  const cr = d.credit
  if (!cr?.dataStart) return cr?.durata || 60
  const parts = cr.dataStart.split('-')
  const start = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1)
  const now = new Date()
  const luniTrecute = (now.getFullYear() - start.getFullYear()) * 12 + (now.getMonth() - start.getMonth())
  return Math.max(0, (cr.durata || 60) - luniTrecute)
}

// --- ING CSV Import ---
const RO_MONTHS = { 'ianuarie':1, 'februarie':2, 'martie':3, 'aprilie':4, 'mai':5, 'iunie':6, 'iulie':7, 'august':8, 'septembrie':9, 'octombrie':10, 'noiembrie':11, 'decembrie':12 }

export function parseIngDate(s) {
  if (!s) return ''
  const m = String(s).trim().match(/^(\d{1,2})\s+([a-zăîâșț]+)\s+(\d{4})$/i)
  if (!m) return ''
  const day = parseInt(m[1], 10)
  const mon = RO_MONTHS[m[2].toLowerCase()]
  if (!mon) return ''
  return m[3] + '-' + String(mon).padStart(2, '0') + '-' + String(day).padStart(2, '0')
}

export function parseIngCsv(text) {
  const lines = text.split('\n')
  const txns = []
  let i = 0
  while (i < lines.length && !/^Data/i.test(lines[i].trim())) i++
  i++ // skip header
  while (i < lines.length) {
    const line = lines[i].trim()
    if (!line) { i++; continue }
    const cols = line.split(',')
    if (cols.length < 6) { i++; continue }
    const data = parseIngDate(cols[0].replace(/"/g, '').trim())
    if (!data) { i++; continue }
    let detalii = cols.slice(1, -4).join(',').replace(/"/g, '').trim()
    const tail = cols.slice(-4)
    const debit = parseRON(tail[0])
    const credit = parseRON(tail[1])
    txns.push({
      data,
      detalii,
      suma: credit > 0 ? credit : -debit,
      sense: credit > 0 ? 'credit' : 'debit',
      ref: 'syn:' + data + ':' + (credit || debit) + ':' + detalii.substring(0, 30)
    })
    i++
  }
  return txns
}

export function categorizeAuto(txn, rules) {
  const text = (txn.detalii || '').toUpperCase()
  for (const r of (rules || [])) {
    try {
      if (new RegExp(r.pattern, 'i').test(text)) return r.categorie
    } catch (_) {}
  }
  return null
}

// Special import categories
export const IMPORT_SPECIAL_CATS = ['__SKIP__', '__TEZAUR__', '__TRADEVILLE__']
export function specialCatLabel(c) {
  return { '__SKIP__': '-- ignora --', '__TEZAUR__': '-> Subscriere Tezaur', '__TRADEVILLE__': '-> Alimentare Tradeville' }[c] || c
}
