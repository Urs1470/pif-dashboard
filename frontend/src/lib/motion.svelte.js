import { cubicOut } from 'svelte/easing'

// Shared motion tokens (mirrors tokens.css --dur-fast/base/slow, duplicated here since
// CSS custom properties can't be read as numbers into svelte/transition params) and a
// single reactive prefers-reduced-motion source, so every component gets a live update
// if the OS-level preference changes mid-session instead of reading matchMedia() once.
export const DUR_FAST = 120
export const DUR_BASE = 240
export const DUR_SLOW = 320

function readReducedMotion() {
  return typeof window !== 'undefined'
    && (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false)
}

export const motion = $state({ reduced: readReducedMotion() })

if (typeof window !== 'undefined' && window.matchMedia) {
  window.matchMedia('(prefers-reduced-motion: reduce)')
    .addEventListener?.('change', (e) => { motion.reduced = e.matches })
}

// Zeroes out a duration when the user prefers reduced motion.
export function motionDuration(ms) {
  return motion.reduced ? 0 : ms
}


// IESIREA UNUI RAND BIFAT.
//
// Un task bifat disparea instantaneu: la un cadru era acolo, la urmatorul nu.
// Confirmarea exista (toastul „Anulează", iar pe telefon verdele de prag), dar
// randul insusi nu spunea nimic — iar el e lucrul pe care tocmai l-ai atins.
//
// Se stinge SI se strange: numai opacitatea ar lasa un gol care se inchide brusc
// dupa aceea, iar numai inaltimea ar arata ca o eroare de layout. Impreuna se
// citesc ca „a plecat de aici". Impingerea mica spre dreapta imprumuta directia
// gestului de bifare de pe telefon (glisare spre dreapta = facut).
//
// Toate valorile se citesc din nodul REAL inainte de animatie: randurile n-au
// aceeasi inaltime (unul cu titlu pe doua linii e mai inalt), deci o inaltime
// fixa ar sari la inceputul tranzitiei.
// SOSIREA UNUI RAND NOU — perechea lui `plecare`.
//
// Iesirea exista (randul bifat se stinge si se strange), dar intrarea lipsea:
// un task adaugat sau mutat intr-o alta grupa APAREA intre doua cadre, fara
// nicio legatura vizibila cu gestul care l-a nascut. Standardul actual (si
// regula deja scrisa la `plecare`): fiecare mutare pe care ai provocat-o tu
// se vede intamplandu-se.
//
// Doar opacitate + o ridicare mica (transform — se compune pe GPU): vecinii
// isi fac singuri loc prin `animate:flip`, deci nu animam inaltimea aici —
// doua animatii de layout pe acelasi eveniment s-ar calca una pe alta.
// Se foloseste cu `|local`, ca prima incarcare a listei sa NU se joace:
// intrarea e pentru randul nou, nu pentru pagina noua.
export function sosire(node, { duration = 190 } = {}) {
  const d = motionDuration(duration)
  return {
    duration: d,
    css: (t) => `opacity: ${t}; transform: translateY(${(1 - t) * 5}px);`,
  }
}

// DESFACEREA UNUI PANOU (taskul deschis in lista).
//
// `slide` din Svelte masoara inaltimea O SINGURA DATA, la primul cadru, si
// animeaza spre ea cu `overflow: hidden`. Daca panoul se randeaza INAINTE ca
// datele sa fie acolo, tinta e inaltimea starii de asteptare: continutul care
// soseste dupa aceea nu incape si se vede TAIAT pana cand tranzitia se termina
// si inaltimea sare la loc. De aceea panoul se deschide numai cu datele in
// mana (vezi `toggleTaskExpand`) — iar aici masuram ansamblul final.
//
// Fata de `slide`: opacitatea urca pe prima jumatate a miscarii, nu in primele
// 5% ca la Svelte. Inaltimea singura se citeste ca o stergere de sus in jos;
// cu stingerea peste ea, panoul APARE, nu e descoperit.
export function desfacere(node, { duration = DUR_BASE } = {}) {
  const d = motionDuration(duration)
  const s = getComputedStyle(node)
  const nr = (v) => parseFloat(v) || 0
  // TOT ce ocupa spatiu pe verticala, nu doar inaltimea: panoul din pagina de
  // proiect are rama pe patru laturi si margine jos, iar cel din /tasks doar
  // linie sus. Daca marginea si ramele nu se strang odata cu inaltimea, raman
  // ~13px care apar dintr-un cadru — adica exact saritura pe care o repara asta.
  const h = nr(s.height)
  const pt = nr(s.paddingTop)
  const pb = nr(s.paddingBottom)
  const mt = nr(s.marginTop)
  const mb = nr(s.marginBottom)
  const bt = nr(s.borderTopWidth)
  const bb = nr(s.borderBottomWidth)
  return {
    duration: d,
    easing: cubicOut,
    css: (t) => `
      overflow: hidden;
      height: ${t * h}px;
      padding-top: ${t * pt}px;
      padding-bottom: ${t * pb}px;
      margin-top: ${t * mt}px;
      margin-bottom: ${t * mb}px;
      border-top-width: ${t * bt}px;
      border-bottom-width: ${t * bb}px;
      opacity: ${Math.min(1, t * 2)};
    `,
  }
}

export function plecare(node, { duration = 190 } = {}) {
  const d = motionDuration(duration)
  const s = getComputedStyle(node)
  const nr = (v) => parseFloat(v) || 0
  const h = nr(s.height)
  const mb = nr(s.marginBottom)
  const bt = nr(s.borderTopWidth)
  const bb = nr(s.borderBottomWidth)
  return {
    duration: d,
    // fara `easing` importat: `t` linear pe opacitate arata bine, iar inaltimea
    // se strange cu patratul lui, deci pleaca repede si se aseaza lin.
    css: (t) => `
      overflow: hidden;
      opacity: ${t};
      height: ${t * t * h}px;
      margin-bottom: ${t * t * mb}px;
      border-top-width: ${t * bt}px;
      border-bottom-width: ${t * bb}px;
      transform: translateX(${(1 - t) * 10}px);
    `,
  }
}
