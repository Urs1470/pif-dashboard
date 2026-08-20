// Tema traieste in `lib/tema.svelte.js` (o foloseste si bundle-ul separat /calc).
// Aici raman doar re-exporturile, ca importurile existente sa nu se rupa.
import { tema, setMod, cicleazaTema } from '../lib/tema.svelte.js'
import { facut, refuzat } from '../lib/gesturi.js'
import { umanizeaza } from '../lib/erori.js'

export { tema, setMod }
export const toggleTheme = cicleazaTema
/** Compatibilitate: fixeaza explicit o tema (deci iese din „auto"). */
export function setTheme(theme) { setMod(theme === 'light' ? 'light' : 'dark') }

// `pageHeader` a plecat (standardizarea titlurilor, 2026-08-09): titlul unei
// pagini se scrie IN pagina, in `.page-title-row` — bara tine doar marca.
export const ui = $state({
  toasts: [],
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
    // Toastul FIX nu e „locul" nimanui: el nu confirma o actiune care tocmai s-a
    // intamplat, ci anunta o stare care tine pana o rezolvi. Aruncat de un
    // „Task șters" care trece, anuntul de actualizare n-ar mai reveni pana la
    // urmatoarea reincarcare — adica exact pana dupa ce nu mai era nevoie de el.
    if (t.fix) continue
    if (toastMeta[t.id]) finishToast(t.id, false)
    else dismissToast(t.id)
  }
}

export function toast(message, type = 'info', duration = DURATA_TOAST) {
  // „NU SE POATE", in mana. Toastul de eroare vine intotdeauna dupa o actiune pe
  // care a pornit-o utilizatorul (o salvare, o mutare, o stergere), deci degetul
  // e inca pe ecran si merita raspunsul — iar textul, pe telefon, apare fix acolo
  // unde nu te uiti. Vezi vocabularul din `lib/gesturi.js`: se vibreaza pentru ce
  // a facut DEGETUL, si un esec al actiunii lui e exact asta.
  if (type === 'error') refuzat()
  faceLoc()
  const id = ++toastId
  // TRADUCEREA SE FACE AICI, NU LA APELANT. Cele 71 de locuri care scriu
  // `Eroare: ${e.message}` trimit mai departe sirul browserului, in engleza;
  // singurul punct prin care trec toate e asta. Vezi `lib/erori.js`.
  ui.toasts.push({ id, message: type === 'error' ? umanizeaza(message) : message, type })
  if (duration > 0) {
    setTimeout(() => dismissToast(id), duration)
  }
  return id
}

// Toast cu buton „Anulează". onCommit ruleaza la expirare/inchidere (comite
// stergerea), onUndo la apasarea butonului (revine). Fix reversibil pentru
// stergeri: caller-ul scoate optimist din UI, apoi decide aici comitere vs revenire.
export function toastUndo(message, { onUndo, onCommit, actionLabel = 'Anulează', duration = DURATA_TOAST } = {}) {
  // „GATA, S-A FACUT". `toastUndo` e chemat EXACT cand o actiune a schimbat date
  // si se poate da inapoi — bifare, mutare, stergere. E singurul punct din
  // aplicatie care stie cu certitudine ca fapta s-a comis, deci aici sta
  // confirmarea, nu imprastiata prin cele sase locuri care il cheama.
  facut()
  faceLoc()
  const id = ++toastId
  ui.toasts.push({ id, message, type: 'info', actionLabel })
  const timer = duration > 0 ? setTimeout(() => finishToast(id, false), duration) : null
  toastMeta[id] = { timer, onUndo, onCommit, done: false }
  return id
}

// ===== TOASTUL FIX — anuntul care nu pleaca singur =====
//
// Banda de actualizare era construita cu `document.createElement` in `main.js`,
// adica singurul loc de interfata din aplicatie care n-a trecut prin nicio tura
// de design: buton de 26px pe telefon, chenar colorat pe o suprafata plutitoare,
// fara `aria-live`, fara miscare, imposibil de inchis, si se putea DUBLA (fiecare
// `updatefound` adauga inca una, iar in WebView banda de service worker si cea de
// APK apareau amandoua).
//
// Banda ESTE un toast — o fasie plutitoare cu un mesaj si o actiune. Toastul are
// deja pozitia, miscarea, tinta de 44px, unicitatea si `aria-live`. Ii trebuiau
// doua lucruri: sa nu plece dupa 4 secunde, si un chip care poate purta procent.
//
// `cheie` + `prioritate` rezolva dublarea LA SURSA, nu prin curatenie dupa:
// exista un singur toast fix per cheie, iar cine are prioritate mai mare il ia pe
// al celuilalt. Carcasa (APK) bate interfata (service worker) fiindca ea cere o
// instalare, cealalta doar o reincarcare.
const cheiFixe = {}

/**
 * @param {string} cheie  ce anume anunta (o singura instanta per cheie)
 * @returns {number} id-ul toastului, sau 0 daca a fost refuzat de unul cu
 *   prioritate mai mare — apelantul NU trebuie sa retina id-ul altcuiva.
 */
export function toastFix(cheie, {
  message, ico = 'info', rol = 'neutru', actionLabel = '', onAction, progres = null, prioritate = 0,
} = {}) {
  const vechi = ui.toasts.find(t => t.fix && t.cheie === cheie)
  if (vechi) {
    if (prioritate < (vechi.prioritate ?? 0)) return 0
    dismissToast(vechi.id)
  }
  const id = ++toastId
  ui.toasts.push({ id, message, ico, rol, actionLabel, onAction, progres, prioritate, cheie, fix: true })
  cheiFixe[cheie] = id
  return id
}

/** Schimba pe loc ce scrie un toast fix (stare, procent, actiune). */
export function actualizeazaToast(id, patch) {
  const t = ui.toasts.find(x => x.id === id)
  if (t) Object.assign(t, patch)
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

// Butonul de actiune: la un toast fix executa ce i s-a dat si il LASA pe ecran
// (apesi „Actualizează", incepe descarcarea, si tocmai acolo apare procentul);
// la un toast-undo revine (onUndo).
export function runToastAction(id) {
  const t = ui.toasts.find(x => x.id === id)
  if (t?.onAction) { t.onAction(id); return }
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
  if (idx === -1) return
  const t = ui.toasts[idx]
  if (t.cheie && cheiFixe[t.cheie] === id) delete cheiFixe[t.cheie]
  ui.toasts.splice(idx, 1)
}

