// Utilitare de dată pentru Calendar. Toate lucrează pe ISO 'YYYY-MM-DD' și pe
// ora LOCALĂ — `new Date('2026-08-01')` e interpretat UTC și, pe fus estic,
// sare cu o zi înapoi. De aceea construim mereu cu `new Date(y, m, d)`.

export const WEEKDAYS = ['Lu', 'Ma', 'Mi', 'Jo', 'Vi', 'Sâ', 'Du']

const LUNI = ['ianuarie', 'februarie', 'martie', 'aprilie', 'mai', 'iunie',
  'iulie', 'august', 'septembrie', 'octombrie', 'noiembrie', 'decembrie']

export function parseISO(iso) {
  if (!iso) return null
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

export function toISO(d) {
  if (!d) return ''
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function todayISO() {
  return toISO(new Date())
}

export function addDays(iso, n) {
  const d = parseISO(iso)
  if (!d) return ''
  d.setDate(d.getDate() + n)
  return toISO(d)
}

/** Câte zile de la `a` la `b` (b - a). Negativ dacă b e înainte. */
export function diffDays(a, b) {
  const da = parseISO(a), db = parseISO(b)
  if (!da || !db) return null
  return Math.round((db - da) / 86400000)
}

export function isWeekend(iso) {
  const d = parseISO(iso)
  if (!d) return false
  const w = d.getDay()
  return w === 0 || w === 6
}

export function monthLabel(iso) {
  const d = parseISO(iso)
  return d ? `${LUNI[d.getMonth()]} ${d.getFullYear()}` : ''
}

export function dayLabel(iso) {
  const d = parseISO(iso)
  if (!d) return ''
  return d.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long' })
}

export function shortDate(iso) {
  const d = parseISO(iso)
  if (!d) return ''
  return `${d.getDate()} ${LUNI[d.getMonth()].slice(0, 3)}`
}

/** Prima zi a lunii care conține `iso`. */
export function monthStart(iso) {
  const d = parseISO(iso) || new Date()
  return toISO(new Date(d.getFullYear(), d.getMonth(), 1))
}

export function addMonths(iso, n) {
  const d = parseISO(iso) || new Date()
  return toISO(new Date(d.getFullYear(), d.getMonth() + n, 1))
}

/** Luni-ul săptămânii care conține `iso` (săptămâna europeană). */
export function weekStart(iso) {
  const d = parseISO(iso)
  if (!d) return ''
  const off = (d.getDay() + 6) % 7
  d.setDate(d.getDate() - off)
  return toISO(d)
}

/**
 * Zilele afișate în grilă, mereu multiplu de 7, începând de luni.
 * `mod`: 'luna' — luna lui `anchor`, completată cu zilele vecine până la
 *        săptămâni întregi (cele din afara lunii vin cu `alta = true`);
 *        'saptamani' — N săptămâni de la luni-ul curent.
 */
export function buildGrid(anchor, mod, saptamani = 2) {
  if (mod === 'saptamani') {
    const s = weekStart(anchor)
    return Array.from({ length: saptamani * 7 }, (_, i) => ({ iso: addDays(s, i), alta: false }))
  }
  const ms = monthStart(anchor)
  const luna = parseISO(ms).getMonth()
  const s = weekStart(ms)
  const total = Math.ceil((diffDays(s, ms) + zileInLuna(ms)) / 7) * 7
  return Array.from({ length: total }, (_, i) => {
    const iso = addDays(s, i)
    return { iso, alta: parseISO(iso).getMonth() !== luna }
  })
}

export function zileInLuna(iso) {
  const d = parseISO(iso)
  return new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()
}
