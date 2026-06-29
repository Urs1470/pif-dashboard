export const PROJECT_STATUS_LABELS = {
  in_lucru: 'În Lucru',
  in_asteptare: 'În Așteptare',
  'in_așteptare': 'În Așteptare',
  blocat: 'Blocat',
  finalizat: 'Finalizat',
}

export const TASK_STATUS_LABELS = {
  to_do: 'To Do',
  in_lucru: 'În Lucru',
  in_asteptare: 'În Așteptare',
  'in_așteptare': 'În Așteptare',
  blocat: 'Blocat',
  done: 'Finalizat',
  finalizat: 'Finalizat',
}

export const STATUS_COLORS = {
  in_lucru: 'var(--accent)',
  in_asteptare: 'var(--warning)',
  'in_așteptare': 'var(--warning)',
  blocat: 'var(--danger)',
  finalizat: 'var(--success)',
  done: 'var(--success)',
  to_do: 'var(--text-dim)',
}

const PRIORITY_LABELS = {
  urgent: 'Urgent',
  normal: 'Normal',
  minor: 'Minor',
}

const PRIORITY_COLORS = {
  urgent: 'var(--danger)',
  normal: 'var(--warning)',
  minor: 'var(--text-faint)',
}

export function statusLabel(status) {
  return TASK_STATUS_LABELS[status] || PROJECT_STATUS_LABELS[status] || status || '—'
}

export function priorityLabel(p) {
  const key = (p || '').toLowerCase()
  return PRIORITY_LABELS[key] || p || '—'
}

export function priorityColor(p) {
  const key = (p || '').toLowerCase()
  return PRIORITY_COLORS[key] || 'var(--text-secondary)'
}

// Live ticking timer display: seconds -> HH:MM:SS.
export function formatElapsed(sec) {
  const s = Math.max(0, Math.floor(sec || 0))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

export function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('ro-RO', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function formatDateShort(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })
}

// A recurring task's next auto-spawned occurrence is dated in the future. We hide
// it from active lists until its scadenta arrives, so completing today's instance
// reads as "done" instead of an identical unchecked copy reappearing.
export function isFutureRecurrence(t) {
  if (!t || !t.recurenta || !String(t.recurenta).trim()) return false
  const d = (t.data_scadenta || '').slice(0, 10)
  if (!d) return false
  const today = new Date().toLocaleDateString('en-CA') // local YYYY-MM-DD
  return d > today
}

export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0h'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

export function timeAgo(iso) {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'acum'
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  return `${Math.floor(diff / 86400)}z`
}
