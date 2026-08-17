import { apiJson } from '../lib/api.js'
import { updateTask, updateGlobalTask, stergeTask } from './tasks.svelte.js'
import { localToday, tomorrowISO } from '../lib/planDates.js'
import { preia, dinCache, uita } from '../lib/cache.js'

// "Planificator" — 14-day operational swimlane. Lanes = projects (each carrying
// its overall interval) with their tasks, plus a "Globale" lane. Read-model comes
// from GET /api/plan; mutations reuse the task stores + the agenda planning rule.
const LS_WEEKENDS = 'pif-plan-weekends'
function readWeekends() {
  try { return localStorage.getItem(LS_WEEKENDS) !== '0' } catch { return true }
}

// TASKURILE FINALIZATE SE VAD IMPLICIT (Ion, 2026-08-17: „vreau ca atat pe desktop
// cat si pe mobil sa fie aratate taskurile finalizate by default").
//
// Erau ascunse implicit, iar pe TELEFON comutatorul „Finalizate" e
// `display: none` (vezi `.toggle` in blocul de 768px din `Plan.svelte`) — deci
// acolo nu exista NICIO cale de a le vedea. Planificatorul de pe telefon arata
// numai ce mai ai de facut, iar ce ai facut dispărea fara urma: exact invers de
// ce vrei cand te uiti la o zi trecuta.
// Se persista, ca weekendurile: daca le stingi pe desktop, rămân stinse.
const LS_DONE = 'pif-plan-done'
function readDone() {
  try { return localStorage.getItem(LS_DONE) !== '0' } catch { return true }
}

export const plan = $state({
  lanes: [],
  backlog: [],
  start: '',
  days: 14,
  today: '',
  showDone: readDone(),
  showWeekends: readWeekends(), // evidentiaza weekendurile (doar in modul pe zile)
  loading: false,
  error: null,
  // Vezi nota de la `incarcat` din `agenda.svelte.js`: „avem un raspuns" nu e
  // acelasi lucru cu „avem randuri", iar garda `loading && items.length === 0`
  // le confunda. Se vede doar cand lista e chiar goala — atunci fiecare
  // incarcare da schelet, apoi starea goala.
  incarcat: false,
})

export function toggleWeekends() {
  plan.showWeekends = !plan.showWeekends
  try { localStorage.setItem(LS_WEEKENDS, plan.showWeekends ? '1' : '0') } catch {}
}

// URL-ul ferestrei, scris o singura data: il cer si `loadPlan`, si preincarcarea
// de la hover din Doc (`pregateste` in Plan.svelte). Doua sabloane pentru acelasi
// raspuns s-ar desparti tacut, iar cererea pornita la hover n-ar mai fi cea pe
// care o asteapta pagina — deci s-ar face doua, si scheletul ar reveni.
export function urlPlan() {
  const t = localToday()
  return `/api/plan?start=${t}&days=${plan.days}&today=${t}${plan.showDone ? '&done=1' : ''}`
}

function aseaza(data, t) {
  plan.incarcat = true
  plan.lanes = Array.isArray(data.lanes) ? data.lanes : []
  plan.backlog = Array.isArray(data.backlog) ? data.backlog : []
  plan.start = data.start || t
  plan.days = data.days || plan.days
  plan.today = data.today || t
}

export async function loadPlan() {
  const t = localToday()
  const url = urlPlan()
  // CE STIM DEJA SE PUNE SINCRON, INAINTE DE PRIMUL CADRU.
  //
  // `pregateste()` incalzeste raspunsul la hover, dar pana acum nimeni nu-l
  // citea la montare: `preia` cu prospetime 0 cere INTOTDEAUNA de la server, iar
  // pagina se randa cu store-ul gol. Masurat pe telefon la atingerea tabului:
  // titlul si bara apareau la 221ms, iar randurile abia la 295 — 74ms de RAMA
  // GOALA. Ion: „tot vad schelete sau niste ramasite mai intai".
  //
  // Nu e stricta „doar la montare" ca la Calendar: aici cache-ul e sters de
  // fiecare scriere (vezi `uita` din mutatii), deci ce gaseste `dinCache` e prin
  // constructie starea de dupa ultima scriere.
  const gata = dinCache(url)
  if (gata !== undefined) { aseaza(gata, t); plan.error = null }
  else plan.loading = true
  try {
    aseaza(await preia(url), t)
  } catch (e) {
    // Cu ecranul deja plin, o improspatare picata nu-l inlocuieste cu o eroare.
    if (gata === undefined) plan.error = e.message
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
  try { localStorage.setItem(LS_DONE, plan.showDone ? '1' : '0') } catch {}
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

// Stergerea unui task DIN Planificator. Randul e scos optimist din `plan.lanes`
// de catre pagina (ca sa poata fi pus la loc din „Anulează"), iar asta e ce se
// intampla cand toastul expira: scrierea adevarata, apoi o reincarcare care aduce
// si numerele din capetele de grupa la starea nouă.
export async function deleteTaskPlan(tip, id) {
  await stergeTask(tip, id)
  await loadPlan()
}

export async function toggleTaskDone(tip, id, currentStatus) {
  const next = currentStatus === 'done' ? 'to_do' : 'done'
  const res = await patch(tip, id, { status: next })
  await loadPlan()
  return res
}
