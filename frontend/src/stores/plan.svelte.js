import { apiJson } from '../lib/api.js'
import { updateTask, updateGlobalTask } from './tasks.svelte.js'
import { localToday, tomorrowISO } from '../lib/planDates.js'

// "Planificator" — 14-day operational swimlane. Lanes = projects (each carrying
// its overall interval) with their tasks, plus a "Globale" lane. Read-model comes
// from GET /api/plan; mutations reuse the task stores + the agenda planning rule.
export const plan = $state({
  lanes: [],
  start: '',
  days: 14,
  today: '',
  showDone: false,
  loading: false,
  error: null,
})

export async function loadPlan() {
  plan.loading = true
  plan.error = null
  try {
    const t = localToday()
    const done = plan.showDone ? '&done=1' : ''
    const data = await apiJson(`/api/plan?start=${t}&days=${plan.days}&today=${t}${done}`)
    plan.lanes = Array.isArray(data.lanes) ? data.lanes : []
    plan.start = data.start || t
    plan.days = data.days || plan.days
    plan.today = data.today || t
  } catch (e) {
    plan.error = e.message
  } finally {
    plan.loading = false
  }
}

export function setHorizon(days) {
  if (plan.days === days) return
  plan.days = days
  return loadPlan()
}

export function toggleShowDone() {
  plan.showDone = !plan.showDone
  return loadPlan()
}

function patch(tip, id, body) {
  return tip === 'global' ? updateGlobalTask(id, body) : updateTask(id, body)
}

// Rescheduling from the planner writes data_planificata AND (if the task already
// has a deadline) moves data_scadenta to the same day — identical to the agenda,
// so a task never keeps a stale termen behind its new plan.
export async function moveTaskDate(tip, id, date, opts = {}) {
  if (!date) return
  const body = { data_planificata: date }
  const scad = (opts.data_scadenta || '').slice(0, 10)
  if (scad) body.data_scadenta = date
  await patch(tip, id, body)
  await loadPlan()
}

export function moveTaskTomorrow(tip, id, opts = {}) {
  return moveTaskDate(tip, id, tomorrowISO(), opts)
}

// Explicit-date setter for drag/resize on the swimlane. `body` carries exactly the
// fields to change (data_planificata and/or data_scadenta); unlike moveTaskDate it
// does NOT auto-couple the two — a span drag preserves the span, a resize moves one
// edge. Empty string clears, an omitted key keeps the stored value (PUT COALESCE).
export async function setTaskDates(tip, id, body) {
  await patch(tip, id, body)
  await loadPlan()
}

export async function toggleTaskDone(tip, id, currentStatus) {
  const next = currentStatus === 'done' ? 'to_do' : 'done'
  const res = await patch(tip, id, { status: next })
  await loadPlan()
  return res
}
