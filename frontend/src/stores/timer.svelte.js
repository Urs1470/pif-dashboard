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
    if (timer.active?.start_time) {
      timer.elapsed = Math.floor((Date.now() - new Date(timer.active.start_time).getTime()) / 1000)
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
    // API: { timers: [{kind, session_id, project_id, task_id, global_task_id, start_time, label}], active: bool }
    timer.active = data.timers?.[0] || null
    if (timer.active?.start_time) {
      timer.elapsed = Math.floor((Date.now() - new Date(timer.active.start_time).getTime()) / 1000)
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

// Stop whichever timer is currently active (project/task/global), regardless of
// where the stop was triggered (Header chip, Home card, project page).
export async function stopActiveTimer() {
  const a = timer.active
  if (!a) return
  if (a.kind === 'project' && a.project_id) await stopProjectTimer(a.project_id)
  else if (a.kind === 'task' && a.task_id) await stopTaskTimer(a.task_id)
  else if (a.kind === 'global_task' && a.global_task_id) await stopGlobalTaskTimer(a.global_task_id)
  await loadActiveTimer()
}

export async function startProjectTimer(projectId) {
  await apiJson(`/api/proiecte/${projectId}/timer/start`, { method: 'POST' })
  await loadActiveTimer()
}

export async function stopProjectTimer(projectId) {
  await apiJson(`/api/proiecte/${projectId}/timer/stop`, { method: 'POST' })
  await loadActiveTimer()
}

export async function stopProjectTimerWithNote(projectId, data) {
  const result = await apiJson(`/api/proiecte/${projectId}/timer/stop-with-note`, { method: 'POST', body: data })
  await loadActiveTimer()
  return result
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

export async function startSubtaskTimer(subtaskId) {
  await apiJson(`/api/subtasks/${subtaskId}/timer/start`, { method: 'POST' })
  await loadActiveTimer()
}

export async function stopSubtaskTimer(subtaskId) {
  await apiJson(`/api/subtasks/${subtaskId}/timer/stop`, { method: 'POST' })
  await loadActiveTimer()
}

export async function addManualTime(kind, id, durata_secunde, data) {
  const endpoints = {
    project: `/api/proiecte/${id}/timer/manual`,
    task: `/api/tasks/${id}/timer/manual`,
    global_task: `/api/global-tasks/${id}/timer/manual`,
    subtask: `/api/subtasks/${id}/timer/manual`,
  }
  return apiJson(endpoints[kind], { method: 'POST', body: { durata_secunde, data } })
}

export async function deleteTimerSession(sessionId) {
  return apiJson(`/api/timer/${sessionId}`, { method: 'DELETE' })
}

export async function deleteGlobalTimerSession(sessionId) {
  return apiJson(`/api/global-task-timer/${sessionId}`, { method: 'DELETE' })
}

export async function loadTaskTimer(taskId) {
  return apiJson(`/api/tasks/${taskId}/timer`)
}

export async function loadGlobalTaskTimer(taskId) {
  return apiJson(`/api/global-tasks/${taskId}/timer`)
}

export async function loadSubtaskTimer(subtaskId) {
  return apiJson(`/api/subtasks/${subtaskId}/timer`)
}
