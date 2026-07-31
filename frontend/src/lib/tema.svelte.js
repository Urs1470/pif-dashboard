// TEMA URMEAZA SISTEMUL (cerinta Ion, 2026-07-31).
//
// Trei moduri, nu doua: `auto` (implicit — ce zice sistemul de operare) plus
// `light`/`dark` ca sa poti forta cand vrei altceva decat el. Doua stari n-ar fi
// ajuns: prima atingere pe comutator te-ar fi scos din „auto" definitiv, fara
// niciun drum inapoi.
//
// Sta in `lib/`, nu in `stores/ui.svelte.js`, fiindca il foloseste si aplicatia
// de sine statatoare de la `/calc` — care e alt bundle si n-are ce cauta cu
// toasturile si restul starii de UI doar ca sa stie ce culoare are pagina.

export const MODURI = ['auto', 'light', 'dark']

const MQ_DARK = '(prefers-color-scheme: dark)'
const CHEIE = 'theme-mod'

// Culorile barei de sus a browserului pe telefon — `--bg` din tokens.css, per tema.
// Daca schimbi `--bg`, schimba-le si aici: nu se pot citi din CSS inainte ca tema
// sa fie aplicata, iar o bara ramasa inchisa peste o aplicatie deschisa se vede.
const BARA = { dark: '#12100d', light: '#f6f1e7' }

export function temaSistemului() {
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark'
  return window.matchMedia(MQ_DARK).matches ? 'dark' : 'light'
}

// MIGRARE, o singura data. Fara ea functia ceruta n-ar fi facut NIMIC vizibil:
// browserul avea deja `theme` fixat in localStorage de la comutatorul vechi, iar
// un „auto" folosit doar cand nu exista nimic stocat l-ar fi lasat pironit pe
// valoarea veche. Cheia noua marcheaza ca migrarea s-a facut, deci nu se repeta
// si nu suprascrie o alegere facuta DUPA ea.
//
// Oglindita in `frontend/index.html`, `frontend/calc.html` si
// `templates/login.html`: fiecare document care se deseneaza inainte de bundle
// isi pune tema singur, altfel apare o clipa de tema gresita la fiecare
// deschidere. Daca schimbi logica, schimb-o in toate patru.
function modInitial() {
  if (typeof localStorage === 'undefined') return 'auto'
  const stocat = localStorage.getItem(CHEIE)
  if (MODURI.includes(stocat)) return stocat
  localStorage.removeItem('theme')     // cheia veche, dark/light fixat
  localStorage.setItem(CHEIE, 'auto')
  return 'auto'
}

export const tema = $state({
  mod: modInitial(),          // 'auto' | 'light' | 'dark' — ce ai ales
  sistem: temaSistemului(),   // ce zice sistemul ACUM
  efectiva: 'dark',           // ce se vede; calculata la incarcare, mai jos
})

function aplica() {
  const efectiv = tema.mod === 'auto' ? tema.sistem : tema.mod
  tema.efectiva = efectiv
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', efectiv)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', BARA[efectiv])
}

export function setMod(mod) {
  if (!MODURI.includes(mod)) return
  tema.mod = mod
  try { localStorage.setItem(CHEIE, mod) } catch (_) {}
  aplica()
}

/** Ciclu auto -> deschisa -> inchisa -> auto. */
export function cicleazaTema() {
  setMod(tema.mod === 'auto' ? 'light' : tema.mod === 'light' ? 'dark' : 'auto')
}

// Sistemul se poate schimba SUB aplicatie: Android/iOS comuta pe program de
// noapte, Windows la apus. Fara ascultatorul asta, „urmeaza sistemul" ar insemna
// de fapt „a urmat sistemul cand ai deschis-o".
if (typeof window !== 'undefined' && window.matchMedia) {
  window.matchMedia(MQ_DARK).addEventListener?.('change', (e) => {
    tema.sistem = e.matches ? 'dark' : 'light'
    if (tema.mod === 'auto') aplica()
  })
}

aplica()
