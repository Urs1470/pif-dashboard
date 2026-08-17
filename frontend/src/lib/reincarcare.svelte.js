// TRAGE SA REINCARCI — gestul care lipsea de pe telefon.
//
// De ce e nevoie: aplicatia isi ia datele la navigare si le tine in cache
// (`lib/cache.js`). Pe teren, Ion sta pe aceeasi pagina ore intregi — schimba
// ceva de pe laptop sau i se inchide un task din alta parte, si singurul mod de
// a vedea noul era sa schimbe tabul si sa se intoarca, sau sa reincarce
// aplicatia. Pe telefon, gestul pentru „mai intreaba o data" e unul singur in
// tot sistemul de operare: tragi lista in jos de la capatul de sus.
//
// UN SINGUR ASCULTATOR PENTRU TOATA APLICATIA, nu unul per pagina. Motivul e cel
// din `lib/ecran.svelte.js`: patru copii ale aceleiasi constante inseamna ca a
// cincea o poate scrie altfel, si nimic nu semnaleaza cand se desincronizeaza.
// Aici ar fi fost mai rau — patru ascultatori de `touchmove` pe acelasi document,
// fiecare cu propriul prag, s-ar fi si batut intre ei pentru acelasi deget.
// Pagina spune doar CE se reincarca (`inregistreaza`), gestul ramane al cadrului.
//
// CE NU FACE, cu bunastiinta:
//   - nu porneste cand pagina nu e la capatul de sus (`scrollY > 0`): acolo
//     gestul in jos inseamna „deruleaza inapoi", si atat;
//   - nu porneste sub un modal (`html.are-modal`): foaia are propriul gest in
//     jos, iar doua obiecte pe aceeasi axa inseamna ca niciunul nu e sigur;
//   - nu porneste cu mouse-ul: pe desktop exista F5 si nu exista elasticitate,
//     deci un gest de tragere acolo n-ar imita nimic;
//   - nu porneste daca degetul a plecat mai mult pe orizontala — acela e al
//     randului (`lib/glisare.js`), si directia se decide o singura data, la
//     `PRAG_DIRECTIE`, ca peste tot in aplicatie.

import { PRAG_DIRECTIE, pragAtins } from './gesturi.js'

/** Cat de departe poate fi tras arcul. Peste atat degetul trage in gol: nu mai
 *  adauga informatie, iar o cursa lunga transforma un gest reflex in efort. */
const CURSA_MAX = 96

/** Rezistenta: degetul face 100px, arcul se muta 55. Fara ea gestul ar parea ca
 *  desprinde lista de pagina; cu ea se simte legat, ca o banda elastica. */
const FRECARE = 0.55

/** Peste atat, ridicarea degetului reincarca. Sub, arcul se retrage si nu se
 *  intampla nimic. In px, nu in procente: aici pragul descrie DEGETUL (cat se
 *  misca o mana pana zice „da"), nu un obiect de pe ecran — vezi nota din
 *  `lib/gesturi.js` despre ce ramane absolut. */
const PRAG = 64

/** Cat sta rotita pe ecran DUPA ce s-au intors datele. Fara minimul asta, o
 *  cerere servita din cache se termina in 40ms: ai trage, ceva ar clipi, si n-ai
 *  sti daca s-a intamplat. Sub ~300ms o confirmare nu se citeste ca raspuns, se
 *  citeste ca zgomot. */
const MINIM_ROTIRE = 420

export const reincarcare = $state({
  tras: 0,          // px, 0..CURSA_MAX — cat s-a tras acum
  activ: false,     // degetul e pe ecran si gestul e al nostru
  seRoteste: false, // cererea e in zbor
})

/** Ce se reincarca pe ruta curenta. O pune pagina, o scoate la iesire. */
let mana = null

/**
 * Pagina spune ce inseamna „mai intreaba o data" pentru ea.
 * Se cheama dintr-un `$effect`, cu curatare — altfel ruta urmatoare ar
 * reincarca ce a lasat cea dinainte.
 *
 *   $effect(() => inregistreaza(async () => { await loadTasks({ fortat: true }) }))
 */
export function inregistreaza(fn) {
  mana = fn
  return () => { if (mana === fn) mana = null }
}

/** Adevarat cat timp nu exista nimic de reincarcat pe ruta asta. */
export const areIncotro = () => typeof mana === 'function'

// ---- gestul ----

let y0 = 0
let x0 = 0
let axa = null          // null | 'noi' | 'a paginii'
let pragAnuntat = false
let idAtingere = null

function poatePorni() {
  if (!areIncotro()) return false
  if (reincarcare.seRoteste) return false
  if (window.scrollY > 0) return false
  // Sub o foaie deschisa, gestul in jos e al foii.
  if (document.documentElement.classList.contains('are-modal')) return false
  return true
}

function laAtingere(e) {
  axa = null
  idAtingere = null
  pragAnuntat = false
  if (e.touches.length !== 1 || !poatePorni()) return
  idAtingere = e.touches[0].identifier
  y0 = e.touches[0].clientY
  x0 = e.touches[0].clientX
}

function laMiscare(e) {
  if (idAtingere === null) return
  const t = [...e.touches].find((x) => x.identifier === idAtingere)
  if (!t) return
  const dy = t.clientY - y0
  const dx = t.clientX - x0

  if (axa === null) {
    if (Math.abs(dy) < PRAG_DIRECTIE && Math.abs(dx) < PRAG_DIRECTIE) return
    // Decis O SINGURA data, ca la orice alt gest din aplicatie. Numai in jos si
    // numai daca verticala a castigat: restul apartine paginii sau randului.
    axa = (dy > 0 && Math.abs(dy) > Math.abs(dx)) ? 'noi' : 'a paginii'
    if (axa === 'noi') reincarcare.activ = true
  }
  if (axa !== 'noi') return

  // Intre timp pagina poate fi derulata de un al doilea deget, sau se poate
  // deschide o foaie. Daca conditiile nu mai tin, gestul se preda.
  if (window.scrollY > 0) { renunta(); return }

  const brut = Math.max(0, dy - PRAG_DIRECTIE) * FRECARE
  reincarcare.tras = Math.min(CURSA_MAX, brut)

  // `preventDefault` DOAR dupa ce gestul e al nostru: pana atunci degetul poate
  // fi inca pe drum spre o derulare, iar oprirea ei ar face pagina sa para
  // inghetata. De aceea ascultatorul e `passive: false` — fara asta apelul e
  // ignorat si browserul face si el saltul de capat de lista, peste arcul nostru.
  if (e.cancelable) e.preventDefault()

  const trecut = reincarcare.tras >= PRAG
  if (trecut !== pragAnuntat) {
    pragAnuntat = trecut
    // Degetul acopera arcul exact cand acesta se umple, deci confirmarea care nu
    // se vede se simte. O singura data per trecere.
    if (trecut) pragAtins()
  }
}

function renunta() {
  axa = null
  idAtingere = null
  pragAnuntat = false
  reincarcare.activ = false
  reincarcare.tras = 0
}

async function laRidicare() {
  if (axa !== 'noi') { renunta(); return }
  const trecut = reincarcare.tras >= PRAG
  axa = null
  idAtingere = null
  pragAnuntat = false
  reincarcare.activ = false

  if (!trecut || !mana) { reincarcare.tras = 0; return }

  // Arcul ramane la prag cat se roteste: daca s-ar retrage la 0 si ar reveni,
  // ar fi doua miscari pentru un singur raspuns.
  reincarcare.tras = PRAG
  reincarcare.seRoteste = true
  const pornit = performance.now()
  try {
    await mana()
  } catch (_) {
    // Esecul si-l spune apelantul, cu toastul lui (care vibreaza „nu se poate").
    // Aici doar inchidem gestul: un arc ramas invartind pe ecran ar minti mai
    // tare decat lipsa unui mesaj.
  } finally {
    const ramas = MINIM_ROTIRE - (performance.now() - pornit)
    if (ramas > 0) await new Promise((g) => setTimeout(g, ramas))
    reincarcare.seRoteste = false
    reincarcare.tras = 0
  }
}

if (typeof window !== 'undefined') {
  // `passive: false` doar pe `touchmove`, unde chiar chemam `preventDefault`.
  // Pe celelalte doua ramane implicitul: nu oprim nimic acolo, si un ascultator
  // ne-pasiv in plus costa la fiecare atingere din aplicatie.
  window.addEventListener('touchstart', laAtingere, { passive: true })
  window.addEventListener('touchmove', laMiscare, { passive: false })
  window.addEventListener('touchend', laRidicare, { passive: true })
  window.addEventListener('touchcancel', renunta, { passive: true })
}
