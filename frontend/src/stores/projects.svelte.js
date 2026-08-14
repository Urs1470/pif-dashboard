import { apiJson } from '../lib/api.js'
import { preia, uita } from '../lib/cache.js'

export const projects = $state({
  items: [],
  loading: false,
  error: null,
  filters: { status: '', tip: '', search: '' },
})

export async function loadProjects() {
  projects.loading = true
  projects.error = null
  try {
    const params = new URLSearchParams()
    if (projects.filters.status) params.set('status', projects.filters.status)
    if (projects.filters.tip) params.set('tip', projects.filters.tip)
    const qs = params.toString()
    const data = await apiJson(`/api/proiecte${qs ? '?' + qs : ''}`)
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
  } catch (e) {
    projects.error = e.message
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
function uitaProiectul(id) {
  uita(urlProiect(id))
}

export async function updateProject(id, data) {
  const result = await apiJson(`/api/proiecte/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  uitaProiectul(id)
  await loadProjects()
  return result
}

export async function deleteProject(id) {
  await apiJson(`/api/proiecte/${id}`, { method: 'DELETE' })
  uitaProiectul(id)
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
