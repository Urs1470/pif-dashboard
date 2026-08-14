import { apiJson } from '../lib/api.js'
import { preia, dinCache, uita } from '../lib/cache.js'

export const projects = $state({
  items: [],
  loading: false,
  error: null,
  filters: { status: '', tip: '', search: '' },
  // Vezi nota de la `incarcat` din `agenda.svelte.js`: „avem un raspuns" nu e
  // acelasi lucru cu „avem randuri", iar garda `loading && items.length === 0`
  // le confunda. Se vede doar cand lista e chiar goala — atunci fiecare
  // incarcare da schelet, apoi starea goala.
  incarcat: false,
})

// Vezi nota de la `urlProiect`: URL-ul listei il cer si pagina, si
// preincarcarea de la hover.
export function urlProiecte() {
  const params = new URLSearchParams()
  if (projects.filters.status) params.set('status', projects.filters.status)
  if (projects.filters.tip) params.set('tip', projects.filters.tip)
  const qs = params.toString()
  return `/api/proiecte${qs ? '?' + qs : ''}`
}

function aseazaProiecte(data) {
  projects.incarcat = true
  let items = Array.isArray(data) ? data : data.projects || []
  if (projects.filters.search) {
    const q = projects.filters.search.toLowerCase()
    items = items.filter(p =>
      (p.nume || '').toLowerCase().includes(q) ||
      (p.cod_proiect || '').toLowerCase().includes(q) ||
      (p.client || '').toLowerCase().includes(q) ||
      (p.echipament_principal || '').toLowerCase().includes(q)
    )
  }
  projects.items = items
}

export async function loadProjects() {
  const url = urlProiecte()
  // Ce stim deja se pune SINCRON, inainte de primul cadru — vezi nota din
  // `plan.svelte.js`: fara asta pagina se randa cu rama si fara carduri, si abia
  // dupa un dus-intors aparea continutul.
  const gata = dinCache(url)
  if (gata !== undefined) { aseazaProiecte(gata); projects.error = null }
  else projects.loading = true
  try {
    aseazaProiecte(await preia(url))
  } catch (e) {
    if (gata === undefined) projects.error = e.message
  } finally {
    projects.loading = false
  }
}

export async function createProject(data) {
  const result = await apiJson('/api/proiecte', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  uitaProiectele()
  await loadProjects()
  return result
}

// CE STIE CACHE-UL DEVINE GRESIT LA FIECARE SCRIERE, SI SE UITA AICI.
//
// Nu la fiecare apelant: pagina de proiect isi salveaza campurile lungi fara sa
// mai reincarce (isi scrie starea locala, ca sa nu clipeasca), deci intrarea din
// memorie ar fi ramas cea de dinaintea editarii — iar urmatoarea intrare pe
// pagina s-ar fi deschis, pentru cateva cadre, cu TEXTUL VECHI. Pus in
// mutatiile store-ului, orice drum de scriere e acoperit, si cele care se vor
// scrie de acum inainte la fel.
//
// Prefixul acopera si `/tasks` de sub proiect: sunt aceeasi entitate, iar o
// scriere pe proiect poate schimba ce se vede in lista lui (statusul, de pilda,
// muta proiectul intre sectiuni).
// Un singur prefix ajunge: `/api/proiecte` acopera si lista (cu sau fara
// filtre in interogare), si `/api/proiecte/<id>`, si `/tasks`-ul de sub el.
function uitaProiectele() {
  uita('/api/proiecte')
}

export async function updateProject(id, data) {
  const result = await apiJson(`/api/proiecte/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  uitaProiectele()
  await loadProjects()
  return result
}

export async function deleteProject(id) {
  await apiJson(`/api/proiecte/${id}`, { method: 'DELETE' })
  uitaProiectele()
  await loadProjects()
}

// URL-urile paginii de proiect, exportate: le cere si pagina (ca sa se deschida
// cu ce stie deja), si preincarcarea de la hover din Doc. Scrise a doua oara in
// pagina, s-ar desparti de astea la prima schimbare de ruta pe server, iar
// cache-ul n-ar mai fi lovit niciodata — fara ca nimic sa dea eroare.
export const urlProiect = (id) => `/api/proiecte/${id}`
export const urlTaskuriProiect = (id) => `/api/proiecte/${id}/tasks`

export async function loadProjectDetail(id) {
  return preia(urlProiect(id))
}

export async function loadProjectTasks(id) {
  return preia(urlTaskuriProiect(id))
}

export async function loadClients(search = '') {
  const qs = search ? `?search=${encodeURIComponent(search)}` : ''
  return apiJson(`/api/clienti${qs}`)
}
