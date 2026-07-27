// Doua statusuri, atat (v31). Oglindeste labels.py — sursa de adevar e acolo.
// Cheile vechi raman mapate ca un rand nemigrat sa nu se afiseze brut.
export const PROJECT_STATUS_LABELS = {
  pregatire: 'În pregătire',
  finalizat: 'Finalizat',
  in_lucru: 'În pregătire',
  in_asteptare: 'În pregătire',
  'in_așteptare': 'În pregătire',
  blocat: 'În pregătire',
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
  pregatire: 'var(--accent-on-subtle)',
  finalizat: 'var(--success)',
  // statusuri de TASK (alt vocabular, aceeasi harta de culori)
  in_lucru: 'var(--accent-on-subtle)',
  in_asteptare: 'var(--purple)',
  blocat: 'var(--danger)',
  done: 'var(--success)',
  to_do: 'var(--text-dim)',
}

// Prioritatea a plecat in v34 (era saturata: 54% „urgent"). Severitatea unui
// task se citeste acum din TERMEN — singurul lucru care chiar variaza.

export function statusLabel(status) {
  return TASK_STATUS_LABELS[status] || PROJECT_STATUS_LABELS[status] || status || '—'
}

/** Cate zile pana la termen (negativ = depasit); null daca nu are termen. */
export function zilePanaLa(d) {
  if (!d) return null
  const t = new Date(String(d).slice(0, 10))
  if (isNaN(t)) return null
  t.setHours(0, 0, 0, 0)
  const azi = new Date(); azi.setHours(0, 0, 0, 0)
  return Math.round((t - azi) / 86400000)
}

/** Culoarea de severitate a unui task, dupa termen. Inlocuieste priorityColor. */
export function dueColor(d) {
  const k = zilePanaLa(d)
  if (k === null) return 'var(--border-strong)'
  if (k < 0) return 'var(--danger)'
  if (k === 0) return 'var(--accent)'
  if (k <= 2) return 'var(--warning)'
  return 'var(--border-strong)'
}

/** Eticheta scurta si relativa: „depășit", „azi", „mâine" — altfel nimic, ca sa
 *  nu repete data deja afisata pe rand. */
export function dueLabel(d) {
  const k = zilePanaLa(d)
  if (k === null) return ''
  if (k < 0) return k === -1 ? 'depășit cu o zi' : `depășit cu ${-k} zile`
  if (k === 0) return 'azi'
  if (k === 1) return 'mâine'
  return ''
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
