import { apiJson } from '../lib/api.js'
import { updateTask, updateGlobalTask } from './tasks.svelte.js'
import { localToday, tomorrowISO } from '../lib/planDates.js'

// "Planificator" — 14-day operational swimlane. Lanes = projects (each carrying
// its overall interval) with their tasks, plus a "Globale" lane. Read-model comes
// from GET /api/plan; mutations reuse the task stores + the agenda planning rule.
const LS_WEEKENDS = 'pif-plan-weekends'
function readWeekends() {
  try { return localStorage.getItem(LS_WEEKENDS) !== '0' } catch { return true }
}

export const plan = $state({
  lanes: [],
  backlog: [],
  start: '',
  days: 14,
  today: '',
  showDone: false,
  showWeekends: readWeekends(), // evidentiaza weekendurile (doar in modul pe zile)
  loading: false,
  error: null,
})

export function toggleWeekends() {
  plan.showWeekends = !plan.showWeekends
  try { localStorage.setItem(LS_WEEKENDS, plan.showWeekends ? '1' : '0') } catch {}
}

export async function loadPlan() {
  plan.loading = true
  plan.error = null
  try {
    const t = localToday()
    const done = plan.showDone ? '&done=1' : ''
    const data = await apiJson(`/api/plan?start=${t}&days=${plan.days}&today=${t}${done}`)
    plan.lanes = Array.isArray(data.lanes) ? data.lanes : []
    plan.backlog = Array.isArray(data.backlog) ? data.backlog : []
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

// Un task are o singura data (v33) — vezi stores/agenda.svelte.js.
export async function moveTaskDate(tip, id, date) {
  if (!date) return
  await patch(tip, id, { data_scadenta: date })
  await loadPlan()
}

export function moveTaskTomorrow(tip, id) {
  return moveTaskDate(tip, id, tomorrowISO())
}

// Setter pentru tragerea barei pe swimlane. Cu o singura data nu mai exista
// „intinderea" unui interval: bara se muta, atat.
export async function setTaskDates(tip, id, body) {
  await patch(tip, id, body)
  await loadPlan()
}

// Un task din sertarul „fara termen", pus pe o zi: primeste termenul acelei zile.
export async function scheduleBacklog(tip, id, date) {
  if (!date) return
  await patch(tip, id, { data_scadenta: date })
  await loadPlan()
}

export async function toggleTaskDone(tip, id, currentStatus) {
  const next = currentStatus === 'done' ? 'to_do' : 'done'
  const res = await patch(tip, id, { status: next })
  await loadPlan()
  return res
}
