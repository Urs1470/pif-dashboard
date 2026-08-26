// Ajutoare de data pe ZILE CALENDARISTICE LOCALE (niciodata UTC), ca o zi sa nu
// alunece langa miezul noptii — acelasi idiom ca `agenda.localToday` si
// `formatters.isFutureRecurrence`.
//
// NUMELE E ISTORIC. Fisierul s-a nascut pentru Planificator (swimlane-ul
// operational), care a fost scos pe 2026-08-26. Ce a ramas nu are nimic de-a face
// cu el: patru functii generice folosite de `parserTask` (care citeste „marti" sau
// „pe 12" dintr-un titlu scris de mana) si de `ImplPeriodModal` (numarul
// saptamanii ISO, scris langa interval).
//
// CE A PLECAT ODATA CU PAGINA, ca sa nu se caute degeaba in istoric:
// `buildColumns`, `grupeazaColoane`, `buildDays`, `spanRect`, `dayDiff`,
// `numeLuna`, `ziLuna`, `clampNum`, `tomorrowISO` — geometria antetului de timp
// si a barelor. Erau ale ganttului si n-au ramas fara el cu niciun apelant.
// (`tomorrowISO` mai exista, dar in `stores/agenda.svelte.js`, unde e chemat.)
//
// De ce fisierul NU s-a topit in `calendarDates.js`: acela isi are propriile
// `parseISO`/`addDays`, scrise pentru grila lunii, iar `parserTask` are un banc
// de probe scris peste acestea (`parserTask.test.js`). Doua implementari care
// arata la fel dar nu sunt aceeasi nu se contopesc fara sa se masoare intai.

const pad = (n) => String(n).padStart(2, '0')

export function localToday() {
  return new Date().toLocaleDateString('en-CA') // YYYY-MM-DD, local
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

export function addDays(iso, n) {
  const d = parseISO(iso)
  if (!d) return iso
  return isoDate(new Date(d.getFullYear(), d.getMonth(), d.getDate() + n))
}
