import { apiJson } from '../lib/api.js'
import { preia, dinCache, uita } from '../lib/cache.js'

// ORICE SCRIERE INVALIDEAZA LISTA, INTR-UN SINGUR LOC.
// De cand citirea trece prin `preia`, o lista tinuta minte din greseala se
// vede: revii pe tab si taskul bifat e la loc, pentru cateva cadre sau pana la
// urmatoarea reincarcare. Pus in mutatii, nu la apelanti — jumatate din ele
// (bifarea, mutarea termenului) isi scriu starea local si NU mai reincarca.
// UN TASK SE VEDE IN TREI LOCURI, deci o scriere le invalideaza pe toate trei.
// `/api/plan` e cel usor de uitat: Planificatorul isi ia randurile de acolo, iar
// mutarile lui cheama `updateTask`/`updateGlobalTask` si apoi `loadPlan()` — care
// de acum se seedeaza SINCRON din memorie. Fara linia asta, o bara trasa cu
// degetul ar clipi inapoi in pozitia veche exact in clipa in care ridici degetul.
function uitaLista() {
  uita('/api/global-tasks')
  uita('/api/plan')
}
// Taskurile de PROIECT nu-si stiu proiectul aici (`updateTask` primeste doar
// id-ul taskului), deci prefixul e cel larg. Costa o cerere in plus la
// urmatoarea intrare pe /projects; alternativa ar fi o lista de proiecte care
// arata alt numar de taskuri decat are.
function uitaTaskuriProiect() {
  uita('/api/plan')
  uita('/api/proiecte')
}

export const tasks = $state({
  items: [],
  loading: false,
  error: null,
  filters: { status: '', search: '' },
})

export const globalTasks = $state({
  items: [],
  loading: false,
  error: null,
})

// URL-ul listei, scris o singura data: il cere si pagina (la montare), si
// incalzirea de la pornire din `main.js`. Doua sabloane pentru acelasi raspuns
// s-ar desparti tacut, iar cererea pornita devreme n-ar mai fi cea pe care o
// asteapta pagina — deci s-ar face doua.
export function urlGlobalTasks(opts = {}) {
  const params = new URLSearchParams()
  if (opts.status) params.set('status', opts.status)
  if (opts.categorie) params.set('categorie', opts.categorie)
  if (opts.arhiva) params.set('arhiva', 'true')
  if (opts.sfera) params.set('sfera', opts.sfera)
  const qs = params.toString()
  return `/api/global-tasks${qs ? '?' + qs : ''}`
}

export async function loadGlobalTasks(opts = {}) {
  const url = urlGlobalTasks(opts)
  // Ce stim deja se pune SINCRON — vezi nota din `plan.svelte.js`.
  const gata = dinCache(url)
  if (gata !== undefined) {
    globalTasks.items = Array.isArray(gata) ? gata : gata.tasks || []
    globalTasks.error = null
  } else {
    globalTasks.loading = true
    globalTasks.error = null
  }
  try {
    // Prin `preia`, nu direct: la pornirea pe telefon cererea se da o data din
    // `main.js` (imediat, in paralel cu chunkul paginii) si a doua oara de aici,
    // cand pagina se monteaza. Cererile in zbor se impart, deci raman una
    // singura — si e cea care a pornit cu ~900ms mai devreme.
    const data = await preia(url)
    globalTasks.items = Array.isArray(data) ? data : data.tasks || []
  } catch (e) {
    if (gata === undefined) globalTasks.error = e.message
  } finally {
    globalTasks.loading = false
  }
}

export async function createTask(projectId, data) {
  const result = await apiJson(`/api/proiecte/${projectId}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  uitaTaskuriProiect()
  return result
}

export async function updateTask(taskId, data) {
  const result = await apiJson(`/api/tasks/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  uitaTaskuriProiect()
  return result
}

export async function deleteTask(taskId) {
  await apiJson(`/api/tasks/${taskId}`, { method: 'DELETE' })
}

export async function createGlobalTask(data, reloadOpts = {}) {
  const result = await apiJson('/api/global-tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  uitaLista()
  // Reload-ul pastreaza vederea apelantului (sfera/arhiva) — altfel un task
  // adaugat din vederea Personal ar repicta lista cu cea de munca.
  await loadGlobalTasks(reloadOpts)
  return result
}

export async function updateGlobalTask(id, data) {
  const result = await apiJson(`/api/global-tasks/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  uitaLista()
  return result
}

export async function deleteGlobalTask(taskId) {
  await apiJson(`/api/global-tasks/${taskId}`, { method: 'DELETE' })
  uitaLista()
}

export async function loadSubtasks(taskId) {
  return apiJson(`/api/tasks/${taskId}/subtasks`)
}

export async function createSubtask(taskId, titlu) {
  return apiJson(`/api/tasks/${taskId}/subtasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ titlu }),
  })
}

export async function updateSubtask(id, data) {
  return apiJson(`/api/subtasks/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function deleteSubtask(id) {
  return apiJson(`/api/subtasks/${id}`, { method: 'DELETE' })
}
