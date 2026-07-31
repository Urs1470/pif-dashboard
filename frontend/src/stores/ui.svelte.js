// Tema traieste in `lib/tema.svelte.js` (o foloseste si bundle-ul separat /calc).
// Aici raman doar re-exporturile, ca importurile existente sa nu se rupa.
import { tema, setMod, cicleazaTema } from '../lib/tema.svelte.js'

export { tema, setMod }
export const toggleTheme = cicleazaTema
/** Compatibilitate: fixeaza explicit o tema (deci iese din „auto"). */
export function setTheme(theme) { setMod(theme === 'light' ? 'light' : 'dark') }

export const ui = $state({
  toasts: [],
  // Context de pagina afisat in bara de sus (ex. salutul de pe Home). Paginile
  // il seteaza pe mount si il curata pe destroy; gol => header doar cu brand.
  pageHeader: { title: '', subtitle: '' },
})

let toastId = 0
// Metadata pentru toast-urile cu actiune „Anulează" (undo). Semantica e
// deferred-commit: apelantul scoate din UI imediat, iar stergerea reala (onCommit)
// ruleaza la expirare / inchidere; „Anulează" (onUndo) o repune.
const toastMeta = {}

export function toast(message, type = 'info', duration = 3000) {
  const id = ++toastId
  ui.toasts.push({ id, message, type })
  if (duration > 0) {
    setTimeout(() => dismissToast(id), duration)
  }
  return id
}

// Toast cu buton „Anulează". onCommit ruleaza la expirare/inchidere (comite
// stergerea), onUndo la apasarea butonului (revine). Fix reversibil pentru
// stergeri: caller-ul scoate optimist din UI, apoi decide aici comitere vs revenire.
export function toastUndo(message, { onUndo, onCommit, actionLabel = 'Anulează', duration = 6000 } = {}) {
  const id = ++toastId
  ui.toasts.push({ id, message, type: 'info', actionLabel })
  const timer = duration > 0 ? setTimeout(() => finishToast(id, false), duration) : null
  toastMeta[id] = { timer, onUndo, onCommit, done: false }
  return id
}

function finishToast(id, undone) {
  const m = toastMeta[id]
  if (!m || m.done) return
  m.done = true
  if (m.timer) clearTimeout(m.timer)
  try {
    if (undone) { if (m.onUndo) m.onUndo() }
    else { if (m.onCommit) m.onCommit() }
  } finally {
    delete toastMeta[id]
    dismissToast(id)
  }
}

// Butonul de actiune al unui toast-undo -> revine (onUndo).
export function runToastAction(id) {
  finishToast(id, true)
}

// Inchidere initiata de user (X). La un toast-undo inca nedecis => comite stergerea.
export function closeToast(id) {
  const m = toastMeta[id]
  if (m && !m.done) { finishToast(id, false); return }
  dismissToast(id)
}

export function dismissToast(id) {
  const idx = ui.toasts.findIndex(t => t.id === id)
  if (idx !== -1) ui.toasts.splice(idx, 1)
}

