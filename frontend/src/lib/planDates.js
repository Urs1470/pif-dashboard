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
const MO_FULL = ['Ian', 'Feb', 'Mar', 'Apr', 'Mai', 'Iun', 'Iul', 'Aug', 'Sep', 'Oct', 'Noi', 'Dec']

// ISO-8601 week number (Monday-based).
export function isoWeek(d) {
  const t = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const dow = (t.getDay() + 6) % 7
  t.setDate(t.getDate() - dow + 3) // nearest Thursday
  const firstThu = new Date(t.getFullYear(), 0, 4)
  const fdow = (firstThu.getDay() + 6) % 7
  firstThu.setDate(firstThu.getDate() - fdow + 3)
  return 1 + Math.round((t - firstThu) / (7 * 86400000))
}

// Header columns adapt to the window length so a 6-month view isn't 180 day-cells:
//   <=31 days -> one column per DAY (weekend flag)
//   <=92 days -> one column per ISO WEEK
//   else      -> one column per calendar MONTH
// Bars still position by exact day-fraction (spanRect), so granularity is purely
// a header/gridline concern. Columns carry pct geometry (partial at the edges).
//
// FIECARE COLOANA ISI POARTA GRUPA DE DEASUPRA (`grupa`).
// Antetul are o singura structura — grosier peste fin: saptamani peste zile, luni
// peste saptamani. Grupa nu se recalculeaza in pagina din data coloanei, fiindca
// atunci ar exista doua locuri care raspund la „din ce saptamana e ziua asta" si
// s-ar putea contrazice la granita (o saptamana care incalca doua luni). Coloana
// spune singura in ce grupa intra; pagina doar aduna coloanele consecutive cu
// aceeasi eticheta.
//
// `unitCerut` forteaza granularitatea fina. Planificatorul cere `week` si la 6L
// (180 de zile), fiindca la orizontul lung antetul trebuie sa fie luni peste
// SAPTAMANI, iar reperele se strang intr-un numar pe saptamana — o grila pe luni
// n-ar avea de ce sa agate numarul. Ganttul de proiect nu cere nimic si ramane
// pe scara veche: fereastra lui vine din date si poate tine un an, unde 52 de
// coloane de saptamana ar insemna o pista de trei ecrane.
export function buildColumns(start, days, unitCerut) {
  const s = parseISO(start)
  if (!s) return { unit: 'day', cols: [] }
  const unit = unitCerut || (days <= 31 ? 'day' : days <= 92 ? 'week' : 'month')
  const winStart = s
  const winEnd = new Date(s.getFullYear(), s.getMonth(), s.getDate() + days) // exclusive
  const pct = (dt) => clampNum((dt - winStart) / 86400000 / days, 0, 1) * 100
  const cols = []

  if (unit === 'day') {
    for (let i = 0; i < days; i++) {
      const d = new Date(s.getFullYear(), s.getMonth(), s.getDate() + i)
      const dow = d.getDay()
      cols.push({
        key: 'd' + i, leftPct: (i / days) * 100, widthPct: (1 / days) * 100,
        main: String(d.getDate()), sub: WD[dow], iso: isoDate(d),
        isWeekend: dow === 0 || dow === 6,
        isMonthStart: d.getDate() === 1 || i === 0, month: MO[d.getMonth()],
        grupa: 'S' + isoWeek(d),
      })
    }
  } else if (unit === 'week') {
    let cur = new Date(winStart)
    cur.setDate(cur.getDate() - ((cur.getDay() + 6) % 7)) // back to Monday
    while (cur < winEnd) {
      const next = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 7)
      const l = pct(cur < winStart ? winStart : cur)
      const r = pct(next > winEnd ? winEnd : next)
      // Luna unei saptamani e cea a JOII ei, regula ISO — si singura care nu
      // rupe grila: o saptamana care incalca doua luni trebuie sa cada intreaga
      // sub una din ele, altfel granita de luna ar taia o coloana pe din doua.
      const joi = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 3)
      // `iso` ramane gol pe coloanele de saptamana: Ganttul de proiect il compara
      // cu ziua de azi ca sa marcheze coloana curenta (`c.iso === today`), iar cu
      // data de luni acolo, saptamana s-ar aprinde o zi din sapte. Coloana care
      // CONTINE azi se afla din procente (`contineAzi`), nu dintr-o egalitate.
      cols.push({ key: 'w' + cur.getTime(), leftPct: l, widthPct: r - l,
        main: `${cur.getDate()} ${MO[cur.getMonth()]}`, sub: 'S' + isoWeek(cur), iso: '',
        grupa: MO[joi.getMonth()] })
      cur = next
    }
  } else {
    let cur = new Date(winStart.getFullYear(), winStart.getMonth(), 1)
    while (cur < winEnd) {
      const next = new Date(cur.getFullYear(), cur.getMonth() + 1, 1)
      const l = pct(cur < winStart ? winStart : cur)
      const r = pct(next > winEnd ? winEnd : next)
      cols.push({ key: 'm' + cur.getTime(), leftPct: l, widthPct: r - l,
        main: MO_FULL[cur.getMonth()], sub: String(cur.getFullYear()), iso: '',
        grupa: String(cur.getFullYear()) })
      cur = next
    }
  }
  return { unit, cols }
}

/** Coloanele fine, adunate in grupele lor (`col.grupa`), cu geometria luata din
 *  ele — nu recalculata. Asa cade granita de grupa EXACT peste muchia unei
 *  coloane: doua socoteli independente ale aceleiasi margini se despart la a
 *  treia zecimala si se vede, fiindca linia groasa a antetului coboara prin
 *  toate benzile de dedesubt.
 *  `ultima` (pe grupa) si `granita` (pe coloana fina) marcheaza unde se ingroasa
 *  separatorul; ultima coloana din pista nu are separator deloc. */
export function grupeazaColoane(cols) {
  const grupe = []
  cols.forEach((c, i) => {
    const ult = grupe[grupe.length - 1]
    if (ult && ult.eticheta === c.grupa) {
      ult.widthPct = c.leftPct + c.widthPct - ult.leftPct
      ult.pana = i
    } else {
      grupe.push({ key: 'g' + c.key, eticheta: c.grupa, leftPct: c.leftPct, widthPct: c.widthPct, de: i, pana: i })
    }
  })
  const granite = new Set(grupe.slice(0, -1).map(g => g.pana))
  return {
    grupe: grupe.map((g, i) => ({ ...g, ultima: i === grupe.length - 1 })),
    granite,
  }
}

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

// Luna scurta si ziua unei date ISO, din ACELEASI tabele ca antetul de coloane —
// subtitlul paginii spune luna pe care antetul n-o mai scrie, deci cele doua nu
// au voie sa vina din doua surse (una cu „aug", alta cu „aug." de la `toLocale`).
export function numeLuna(iso) {
  const d = parseISO(iso)
  return d ? MO[d.getMonth()] : ''
}
export function ziLuna(iso) {
  const d = parseISO(iso)
  return d ? String(d.getDate()) : ''
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
