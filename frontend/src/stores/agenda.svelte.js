import { apiJson } from '../lib/api.js'
import { createGlobalTask, updateGlobalTask, updateTask } from './tasks.svelte.js'

// "Astazi" daily-planner board state. Items are a unified list of global +
// project tasks (each carries a `tip` discriminator) planned for / due today.
export const agenda = $state({
  items: [],
  today: '',
  loading: false,
  error: null,
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

export async function loadAgendaToday() {
  agenda.loading = true
  agenda.error = null
  try {
    const data = await apiJson(`/api/agenda/today?today=${localToday()}`)
    agenda.items = Array.isArray(data.items) ? data.items : []
    agenda.today = data.today || localToday()
  } catch (e) {
    agenda.error = e.message
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
