// Date helpers for the Planificator (operational swimlane). All math is done on
// LOCAL calendar days (never UTC) so a day column never drifts near midnight —
// same idiom as agenda.localToday / formatters.isFutureRecurrence.

const pad = (n) => String(n).padStart(2, '0')

export function localToday() {
  return new Date().toLocaleDateString('en-CA') // YYYY-MM-DD, local
}

export function tomorrowISO() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toLocaleDateString('en-CA')
}

export function isoDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// Parse 'YYYY-MM-DD' into a LOCAL midnight Date (ignoring any time part).
export function parseISO(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || '')
  if (!m) return null
  return new Date(+m[1], +m[2] - 1, +m[3])
}

// Whole-day difference (b - a) in days, or null if either is unparsable.
export function dayDiff(a, b) {
  const da = parseISO(a)
  const db = parseISO(b)
  if (!da || !db) return null
  return Math.round((db - da) / 86400000)
}

const WD = ['Du', 'Lu', 'Ma', 'Mi', 'Jo', 'Vi', 'Sâ']
const MO = ['ian', 'feb', 'mar', 'apr', 'mai', 'iun', 'iul', 'aug', 'sep', 'oct', 'nov', 'dec']

// The day columns for the window [start, start+days).
export function buildDays(start, days) {
  const s = parseISO(start)
  if (!s) return []
  const out = []
  for (let i = 0; i < days; i++) {
    const d = new Date(s.getFullYear(), s.getMonth(), s.getDate() + i)
    const dow = d.getDay() // 0 Sun .. 6 Sat
    out.push({
      i,
      iso: isoDate(d),
      dow,
      isWeekend: dow === 0 || dow === 6,
      dayNum: d.getDate(),
      wd: WD[dow],
      month: MO[d.getMonth()],
      isMonthStart: d.getDate() === 1 || i === 0,
    })
  }
  return out
}

// Add n whole days to a 'YYYY-MM-DD' (local), returning 'YYYY-MM-DD'.
export function addDays(iso, n) {
  const d = parseISO(iso)
  if (!d) return iso
  return isoDate(new Date(d.getFullYear(), d.getMonth(), d.getDate() + n))
}

export function clampNum(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v))
}

// A bar rectangle (percent of the track) from a span [startDate, dueDate] clamped
// to the window. Either date may be empty; a single present date => a 1-day bar.
// Returns null when the span falls entirely outside the window.
export function spanRect(startDate, dueDate, start, days) {
  const a = (startDate || dueDate || '').slice(0, 10)
  const b = (dueDate || startDate || '').slice(0, 10)
  if (!a && !b) return null
  const lo = a < b ? a : b
  const hi = a < b ? b : a
  const dLo = dayDiff(start, lo)
  const dHi = dayDiff(start, hi)
  if (dLo == null || dHi == null) return null
  const left = Math.max(0, Math.min(days, dLo))
  const right = Math.max(0, Math.min(days, dHi + 1)) // end = start of the day after
  if (right <= 0 || left >= days || right <= left) return null // fully outside / empty
  return {
    left: (left / days) * 100,
    width: ((right - left) / days) * 100,
    clippedLeft: dLo < 0,
    clippedRight: dHi >= days,
    single: lo === hi,
  }
}
