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
const BARA = { dark: '#121417', light: '#f4f5f7' }

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

// LUMINA SE SCHIMBA, NU SE COMUTA.
//
// Toate suprafetele isi iau culoarea din tokenuri, iar tokenurile se schimba
// intr-un singur cadru: ecranul POCNEA dintr-o tema in alta. Pe telefon, in hala,
// Ion comuta des — si un pocnet pe tot ecranul e cel mai violent lucru pe care il
// face aplicatia, tocmai la o actiune care nu schimba nicio informatie.
//
// Cadrul primeste ~320ms o clasa care pune o tranzitie de CULOARE pe tot
// subarborele, apoi si-o scoate. Permanenta n-are ce cauta: fiecare hover si
// fiecare stare ar trage dupa ea 300ms, si atunci raspunsul la atingere s-ar
// simti moale peste tot.
//
// DOAR proprietati de culoare, cu bunastiinta. Miscarea nu intra in lista: o
// tranzitie de `transform` fortata pe tot arborele ar prinde, in cele 320ms,
// obiecte care se misca din alt motiv (pastila din dock, foaia trasa de deget) si
// le-ar da alta durata decat au. Tranzitiile Svelte nu sunt atinse deloc — ele
// merg pe `animation`, nu pe `transition`.
// `--dur-slow` (280) plus o marja: clasa trebuie sa traiasca putin mai mult
// decat tranzitia pe care o porneste, altfel ultimele cadre ale trecerii raman
// fara regula si culoarea sare la capat.
const DUR_TEMA = 320
let ceasTema = null

function treceLinLaTema() {
  if (typeof document === 'undefined') return
  const el = document.documentElement
  // Prima aplicare (la incarcare) NU e o comutare: acolo nu exista „de la ce"
  // sa treaca, iar o tranzitie ar intarzia primul cadru pictat.
  el.classList.add('tema-trece')
  clearTimeout(ceasTema)
  ceasTema = setTimeout(() => el.classList.remove('tema-trece'), DUR_TEMA)
}

function aplica(lin = false) {
  const efectiv = tema.mod === 'auto' ? tema.sistem : tema.mod
  if (efectiv === tema.efectiva && lin) return   // nimic de trecut
  tema.efectiva = efectiv
  if (typeof document === 'undefined') return
  if (lin) treceLinLaTema()
  document.documentElement.setAttribute('data-theme', efectiv)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', BARA[efectiv])
}

export function setMod(mod) {
  if (!MODURI.includes(mod)) return
  tema.mod = mod
  try { localStorage.setItem(CHEIE, mod) } catch (_) {}
  aplica(true)
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
    // Si schimbarea VENITA DE LA SISTEM (programul de noapte) trece lin: e
    // acelasi salt de lumina, doar ca nu l-ai cerut tu — motiv in plus sa nu
    // pocneasca.
    if (tema.mod === 'auto') aplica(true)
  })
}

aplica()
