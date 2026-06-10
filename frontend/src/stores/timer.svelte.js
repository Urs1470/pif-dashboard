import { apiJson } from '../lib/api.js'

export const timer = $state({
  active: null,
  loading: false,
  elapsed: 0,
})

let tickInterval = null

function startTick() {
  stopTick()
  tickInterval = setInterval(() => {
    if (timer.active?.running_since) {
      timer.elapsed = Math.floor((Date.now() - new Date(timer.active.running_since).getTime()) / 1000)
    }
  }, 1000)
}

function stopTick() {
  if (tickInterval) {
    clearInterval(tickInterval)
    tickInterval = null
  }
  timer.elapsed = 0
}

export async function loadActiveTimer() {
  timer.loading = true
  try {
    const data = await apiJson('/api/timer/active')
    timer.active = data.active || data || null
    if (timer.active?.running_since) {
      timer.elapsed = Math.floor((Date.now() - new Date(timer.active.running_since).getTime()) / 1000)
      startTick()
    } else {
      stopTick()
    }
  } catch (e) {
    timer.active = null
    stopTick()
  } finally {
    timer.loading = false
  }
}

export async function startProjectTimer(projectId) {
  await apiJson(`/api/proiecte/${projectId}/timer/start`, { method: 'POST' })
  await loadActiveTimer()
}

export async function stopProjectTimer(projectId) {
  await apiJson(`/api/proiecte/${projectId}/timer/stop`, { method: 'POST' })
  await loadActiveTimer()
}

export async function startTaskTimer(taskId) {
  await apiJson(`/api/tasks/${taskId}/timer/start`, { method: 'POST' })
  await loadActiveTimer()
}

export async function stopTaskTimer(taskId) {
  await apiJson(`/api/tasks/${taskId}/timer/stop`, { method: 'POST' })
  await loadActiveTimer()
}

export async function startGlobalTaskTimer(taskId) {
  await apiJson(`/api/global-tasks/${taskId}/timer/start`, { method: 'POST' })
  await loadActiveTimer()
}

export async function stopGlobalTaskTimer(taskId) {
  await apiJson(`/api/global-tasks/${taskId}/timer/stop`, { method: 'POST' })
  await loadActiveTimer()
}
