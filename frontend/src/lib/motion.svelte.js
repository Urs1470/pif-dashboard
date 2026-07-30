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
