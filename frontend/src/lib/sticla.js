// ===== SUPRAFATA DE STICLA (AURORA, 2026-08-23) =====
//
// Materialul barelor de navigatie. NU e o textura de imprastiat pe carduri: se
// pune DOAR acolo unde continutul chiar trece pe dedesubt — bara de sus pe
// desktop, antetul si dockul pe telefon. Handoff: `design/handoff-aurora/`.
//
// DE CE ACTIUNE, si nu componenta care invaleste. Bara e un `<nav>`/`<header>`
// cu layoutul lui; o componenta ar mai adauga un nivel de DOM intre el si
// copii, si atunci `flex` de pe bara nu mai vede sloturile. Actiunea pune
// straturile ca PRIMI copii si lasa elementul in pace. Acelasi tipar ca
// `use:apasareLunga` si ca `lib/glisare.js`.
//
// DE CE CSS-UL E IN `global.css`, nu intr-o componenta. Straturile se creeaza la
// RULARE, deci nu apar in markup — iar Svelte TAIE din build regulile ale caror
// selectoare nu le gaseste in markup. `global.css` nu trece prin compilatorul de
// componente, deci nu e taiat. Capcana asta a mancat deja doua reguli in acest
// repo (vezi `.trow-wrap.deschis .gl-fata` si `:global(.modal-body) > .td-jos`).
//
// STRATURILE, in ordine (containerul NU are `background`: altfel n-are ce refracta):
//   1. blur + saturatie          — `--glass-filter`
//   2. banda-lentila pe contur   — `--glass-edge`, decupata cu `mask-composite`
//   3. tenta                     — `--glass-bg`
//   4. reflexul care urmareste cursorul — `--glass-spec-a/-b`
// Stratul 2 e ce deosebeste materialul asta de glassmorphismul obisnuit: fara el
// raman blur + chenar + umbra, adica orice alta aplicatie. Filtrele SVG in
// `backdrop-filter: url(#…)` NU merg in Chromium, de aceea muchia e facuta cu
// masca, nu cu `feDisplacementMap`.

const STRATURI = ['s-blur', 's-edge', 's-tint', 's-spec']

/**
 * @param {HTMLElement} nod
 * @param {{ reflex?: boolean, spec?: string }} optiuni
 *   reflex — leaga reflexul specular (implicit: doar pe aparate cu cursor)
 *   spec   — raza elipsei de reflex, ex. '150px 74px' (dock: '110px 60px')
 */
export function sticla(nod, optiuni = {}) {
  // Idempotenta: acelasi steag ca la `--dock-h`/`--kb`. O a doua aplicare pe
  // acelasi nod ar dubla straturile, si al doilea set ar sta peste continut.
  if (nod.__sticla) return { destroy() {} }
  nod.__sticla = true

  const create = []
  for (const clasa of STRATURI) {
    const s = document.createElement('span')
    s.className = clasa
    s.setAttribute('aria-hidden', 'true')
    create.push(s)
  }
  // Inaintea continutului, ca sa stea DEDESUBT fara z-index scris de mana:
  // continutul e `position: relative` in CSS, deci urca singur peste ele.
  nod.prepend(...create)

  if (optiuni.spec) nod.style.setProperty('--spec-raza', optiuni.spec)

  // REFLEXUL E NUMAI PENTRU CURSOR. Pe telefon nu exista pointer care sa
  // zaboveasca: efectul ar fi invizibil, dar ar costa un al patrulea strat
  // compozitat si un ascultator pe fiecare cadru al degetului. Iar cine a cerut
  // mai putina miscare nu primeste un gradient care se aprinde sub mana.
  const areCursor = window.matchMedia('(hover: hover)').matches
  const vreaMiscare = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const cuReflex = (optiuni.reflex ?? true) && areCursor && vreaMiscare

  function misca(e) {
    const r = nod.getBoundingClientRect()
    if (!r.width || !r.height) return
    nod.style.setProperty('--mx', ((e.clientX - r.left) / r.width).toFixed(3))
    nod.style.setProperty('--my', ((e.clientY - r.top) / r.height).toFixed(3))
    nod.style.setProperty('--spec', '1')
  }
  function pleaca() {
    nod.style.setProperty('--spec', '0')
  }

  if (cuReflex) {
    nod.addEventListener('pointermove', misca)
    nod.addEventListener('pointerleave', pleaca)
  }

  return {
    destroy() {
      if (cuReflex) {
        nod.removeEventListener('pointermove', misca)
        nod.removeEventListener('pointerleave', pleaca)
      }
      for (const s of create) s.remove()
      nod.__sticla = false
    },
  }
}
