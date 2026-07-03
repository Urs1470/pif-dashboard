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

// Planning a task only ever writes data_planificata (never data_scadenta), so a
// task's deadline is never disturbed. Dispatch to the right task store fn by tip.
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

export async function moveToDate(tip, id, date, opts = {}) {
  if (!date) return
  const body = { data_planificata: date }
  // Daca taskul e scadent (deadline azi sau deja depasit), amanarea muta si
  // deadline-ul pe noua zi — altfel ramane vesnic restant, cu termenul in trecut.
  // Deadline-urile din VIITOR nu se ating: planning-ul ramane separat de termen
  // pentru taskurile pe care doar le lucrezi inainte de scadenta.
  const scad = (opts.data_scadenta || '').slice(0, 10)
  if (scad && scad <= localToday()) body.data_scadenta = date
  await patch(tip, id, body)
  await loadAgendaToday()
}

export function moveToTomorrow(tip, id, opts = {}) {
  return moveToDate(tip, id, tomorrowISO(), opts)
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
