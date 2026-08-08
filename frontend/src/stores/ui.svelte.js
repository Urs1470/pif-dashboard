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

// UN SINGUR TOAST PE ECRAN, 4 SECUNDE.
//
// Era o stiva: bifezi trei taskuri la rand si primesti trei casete suprapuse,
// fiecare cu „Anulează", fara sa scrie pe niciuna PE CARE task. Trei butoane
// identice pentru trei actiuni diferite nu e o confirmare, e o loterie.
//
// Inlocuirea nu are voie sa fie tacuta: un toast-undo scos de pe ecran trebuie
// sa se DECIDA. Daca l-am arunca pur si simplu, `onCommit` n-ar mai rula
// niciodata — adica randul ar ramane sters din interfata si nesters din baza,
// exact felul de nepotrivire care se descopera la urmatoarea reincarcare.
// Deci: cine pleaca, se comite.
const DURATA_TOAST = 4000

function faceLoc() {
  for (const t of [...ui.toasts]) {
    if (toastMeta[t.id]) finishToast(t.id, false)
    else dismissToast(t.id)
  }
}

export function toast(message, type = 'info', duration = DURATA_TOAST) {
  faceLoc()
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
export function toastUndo(message, { onUndo, onCommit, actionLabel = 'Anulează', duration = DURATA_TOAST } = {}) {
  faceLoc()
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

