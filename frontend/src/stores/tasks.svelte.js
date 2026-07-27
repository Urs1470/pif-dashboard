import { apiJson } from '../lib/api.js'

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

export async function loadGlobalTasks(opts = {}) {
  globalTasks.loading = true
  globalTasks.error = null
  try {
    const params = new URLSearchParams()
    if (opts.status) params.set('status', opts.status)
    if (opts.categorie) params.set('categorie', opts.categorie)
    if (opts.arhiva) params.set('arhiva', 'true')
    const qs = params.toString()
    const data = await apiJson(`/api/global-tasks${qs ? '?' + qs : ''}`)
    globalTasks.items = Array.isArray(data) ? data : data.tasks || []
  } catch (e) {
    globalTasks.error = e.message
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
  return result
}

export async function updateTask(taskId, data) {
  const result = await apiJson(`/api/tasks/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return result
}

export async function deleteTask(taskId) {
  await apiJson(`/api/tasks/${taskId}`, { method: 'DELETE' })
}

export async function createGlobalTask(data) {
  const result = await apiJson('/api/global-tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  await loadGlobalTasks()
  return result
}

export async function updateGlobalTask(id, data) {
  const result = await apiJson(`/api/global-tasks/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return result
}

export async function deleteGlobalTask(taskId) {
  await apiJson(`/api/global-tasks/${taskId}`, { method: 'DELETE' })
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
