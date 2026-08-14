import { apiJson } from '../lib/api.js'
import { createGlobalTask, updateGlobalTask, updateTask } from './tasks.svelte.js'

// "Astazi" daily-planner board state. Items are a unified list of global +
// project tasks (each carries a `tip` discriminator) planned for / due today.
export const agenda = $state({
  items: [],
  // Taskurile PERSONALE scadente azi/restante — lista separata, randata in
  // sectiunea ei de pe board; nu se amesteca niciodata cu `items` (munca).
  personale: [],
  today: '',
  loading: false,
  error: null,
  // AVEM UN RASPUNS? — diferit de „avem randuri".
  //
  // Ion: „au ramas niste ramasite acasa in cazul cand nu este niciun task."
  // Garda scrisa peste tot in aplicatie e `loading && items.length === 0`, si
  // ea CONFUNDA doua lucruri: „inca n-am primit nimic" si „raspunsul e gol".
  // Cat timp ai taskuri, confuzia nu se vede — lista nevida iese din prima
  // ramura. Cand n-ai niciunul, fiecare incarcare da schelet, apoi starea
  // goala: doua forme pentru un raspuns pe care il stiam din memorie.
  // Nici cache-ul nu putea ajuta, fiindca o lista goala restaurata arata exact
  // ca una neincarcata. De aceea raspunsul are nevoie de un steag propriu.
  incarcat: false,
})

// Local YYYY-MM-DD (NOT UTC) — SQLite date('now') is UTC and can disagree near
// midnight, so the server takes our local date via ?today=. Same idiom as
// formatters.isFutureRecurrence.
export function localToday() {
  return new Date().toLocaleDateString('en-CA')
}

export function tomorrowISO() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toLocaleDateString('en-CA')
}

// ACASA SE DESCHIDE INSTANT, din ultimul raspuns bun (cerinta Ion: „fa ca acasa
// tot sa se incarce instant precum ai facut la taskuri generale"). Cache-ul e
// pe ZIUA lui: un raspuns de ieri ar arata boardul de ieri ca si cum ar fi al
// tau de azi — iar restantele si „azi" sunt chiar ce se schimba peste noapte.
// `localStorage`, nu `sessionStorage` — RASTOARNA alegerea de dinainte, si
// merita spus de ce. Argumentul pentru sessionStorage era „un accelerator
// pentru sesiunea curenta, nu o a doua sursa de adevar care supravietuieste
// zile". Numai ca `sessionStorage` moare cand se inchide fila — iar pe Android
// exact asta INSEAMNA „pornirea aplicatiei", adica fix momentul in care Ion
// vedea asteptarea. Acceleratorul lipsea tocmai unde era nevoie de el.
// Grija din argumentul vechi ramane acoperita, si nu de tipul de stocare, ci de
// CHEIA PE ZI de mai jos: un board de ieri e respins, oricat de bine ar fi
// pastrat. Un raspuns de azi, restaurat maine, nu poate ajunge pe ecran.
const CHEIE_AGENDA = 'pif-agenda'

function dinCache() {
  try {
    const brut = localStorage.getItem(CHEIE_AGENDA)
    if (!brut) return null
    const c = JSON.parse(brut)
    return c && c.today === localToday() ? c : null
  } catch (_) { return null }
}

export async function loadAgendaToday() {
  // Scheletul apare doar cand chiar n-avem ce arata (regula din sistem:
  // `loading && items.length === 0`). Cu cache, `items` e deja plin la primul
  // cadru, deci nu se mai vede nicio dunga gri intre intrare si date.
  if (!agenda.items.length && !agenda.personale.length) {
    const c = dinCache()
    if (c) {
      agenda.items = c.items
      agenda.personale = c.personale
      agenda.today = c.today
      // Si cand ce am restaurat e GOL: stim raspunsul, deci nu se mai asteapta.
      agenda.incarcat = true
    }
  }
  agenda.loading = true
  agenda.error = null
  try {
    const data = await apiJson(`/api/agenda/today?today=${localToday()}`)
    agenda.items = Array.isArray(data.items) ? data.items : []
    agenda.personale = Array.isArray(data.personale) ? data.personale : []
    agenda.today = data.today || localToday()
    agenda.incarcat = true
    try {
      localStorage.setItem(CHEIE_AGENDA, JSON.stringify({
        items: agenda.items, personale: agenda.personale, today: agenda.today,
      }))
    } catch (_) { /* cota plina / mod privat — cache-ul e optional */ }
  } catch (e) {
    // Cu date vechi pe ecran, un esec de retea NU trebuie sa le stearga si sa
    // puna o stare de eroare peste ele: ramane ce se vede, iar reincercarea
    // urmatoare le improspateaza.
    if (!agenda.items.length && !agenda.personale.length) agenda.error = e.message
  } finally {
    agenda.loading = false
  }
}

// Dispatch to the right task store fn by tip.
function patch(tip, id, body) {
  return tip === 'global' ? updateGlobalTask(id, body) : updateTask(id, body)
}

export async function quickAddToday(titlu) {
  const t = (titlu || '').trim()
  if (!t) return
  // Brand-new ad-hoc tasks have no project -> global task, planned for today.
  await createGlobalTask({ titlu: t, status: 'to_do', data_scadenta: localToday() })
  await loadAgendaToday()
}

// A pune un task pe boardul de azi INSEAMNA a-i da termenul de azi. Din v33 nu
// mai exista o a doua data „doar de plan" — vezi comentariul de mai jos.
export async function scheduleForToday(tip, id) {
  await patch(tip, id, { data_scadenta: localToday() })
  await loadAgendaToday()
}

// UN TASK ARE O SINGURA DATA (v33). Ion: „mutarea este practic un deadline (…)
// trebuie sa fie adaugat ca deadline pur, sa nu mai dublam atat notiunile."
// Deci nu mai exista „cand planific" separat de „pana cand" — e aceeasi zi.
export async function moveToDate(tip, id, date) {
  if (!date) return
  await patch(tip, id, { data_scadenta: date })
  await loadAgendaToday()
}

export function moveToTomorrow(tip, id) {
  return moveToDate(tip, id, tomorrowISO())
}

// Scoaterea de pe board sterge DATA taskului (nu mai exista una separata de
// termen). Taskul se intoarce in sertarul „fara termen".
export async function removeFromToday(tip, id) {
  await patch(tip, id, { data_scadenta: '' })
  await loadAgendaToday()
}

export async function toggleDone(tip, id, currentStatus) {
  const next = currentStatus === 'done' ? 'to_do' : 'done'
  const res = await patch(tip, id, { status: next })
  await loadAgendaToday()
  return res
}

// Persist board order for a mixed list. Caller passes the already-reordered items.
export async function reorderAgenda(orderedItems) {
  const order = orderedItems.map(it => ({ tip: it.tip, id: it.id }))
  await apiJson('/api/agenda/reorder', { method: 'POST', body: { order } })
}

export async function loadCandidates(q = '') {
  const params = new URLSearchParams({ today: localToday() })
  if (q) params.set('q', q)
  const data = await apiJson(`/api/agenda/candidates?${params.toString()}`)
  return Array.isArray(data.items) ? data.items : []
}
