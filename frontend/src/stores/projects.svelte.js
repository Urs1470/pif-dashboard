import { apiJson } from '../lib/api.js'

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

export async function updateProject(id, data) {
  const result = await apiJson(`/api/proiecte/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  await loadProjects()
  return result
}

export async function deleteProject(id) {
  await apiJson(`/api/proiecte/${id}`, { method: 'DELETE' })
  await loadProjects()
}

export async function loadProjectDetail(id) {
  return apiJson(`/api/proiecte/${id}`)
}

export async function loadProjectTasks(id) {
  return apiJson(`/api/proiecte/${id}/tasks`)
}

export async function loadClients(search = '') {
  const qs = search ? `?search=${encodeURIComponent(search)}` : ''
  return apiJson(`/api/clienti${qs}`)
}
