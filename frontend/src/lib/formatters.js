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
