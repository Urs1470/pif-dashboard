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
  await createGlobalTask({ titlu: t, status: 'to_do', data_planificata: localToday() })
  await loadAgendaToday()
}

export async function scheduleForToday(tip, id) {
  await patch(tip, id, { data_planificata: localToday() })
  await loadAgendaToday()
}

// Data pe care o alegi ESTE termenul.
//
// Pana acum, mutarea propaga termenul doar daca taskul avea deja unul: „nu
// inventam un termen din simpla planificare". Ion, 2026-07-27: „daca am preluat
// un task in taskuri azi, si de acolo am mutat taskul pe o anumita data, nu se
// seteaza acea data aleasa ca deadline task, ceea ce ar fi logic."
//
// Are dreptate, si e consecvent cu tot restul: cand alegi explicit o zi, spui
// cand se face. Nu tii separat „cand planific" si „pana cand" — e aceeasi data.
// Regula se aplica doar la alegerea EXPLICITA a unei zile (mutare, maine), nu si
// la tragerea in boardul de azi, care e o unealta de concentrare, nu un angajament.
export async function moveToDate(tip, id, date) {
  if (!date) return
  await patch(tip, id, { data_planificata: date, data_scadenta: date })
  await loadAgendaToday()
}

export function moveToTomorrow(tip, id) {
  return moveToDate(tip, id, tomorrowISO())
}

export async function removeFromToday(tip, id) {
  await patch(tip, id, { data_planificata: '' })
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
