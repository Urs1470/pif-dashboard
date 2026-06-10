const STATUS_LABELS = {
  in_lucru: 'In lucru',
  in_asteptare: 'In asteptare',
  finalizat: 'Finalizat',
  anulat: 'Anulat',
}

const PRIORITY_LABELS = {
  scazuta: 'Scazuta',
  normala: 'Normala',
  ridicata: 'Ridicata',
  urgenta: 'Urgenta',
}

const PRIORITY_COLORS = {
  scazuta: 'var(--text-dim)',
  normala: 'var(--info)',
  ridicata: 'var(--warning)',
  urgenta: 'var(--danger)',
}

export function statusLabel(status) {
  return STATUS_LABELS[status] || status || '—'
}

export function priorityLabel(p) {
  return PRIORITY_LABELS[p] || p || '—'
}

export function priorityColor(p) {
  return PRIORITY_COLORS[p] || 'var(--text-secondary)'
}

export function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('ro-RO', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function formatDateShort(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
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
