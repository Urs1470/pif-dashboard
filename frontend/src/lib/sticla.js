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

  // REFLEXUL SE APRINDE SI SUB DEGET (Ion, 2026-08-24).
  //
  // Era legat DOAR pe aparate cu cursor, cu doua motive care s-au dovedit
  // amandoua greșite pentru produsul asta:
  //   - „pe telefon nu exista pointer care sa zaboveasca" — dar sesiunea Apple pe
  //     Liquid Glass spune exact invers: „Liquid Glass responds to interaction by
  //     instantly flexing and energizing with light... starting right under your
  //     fingertips, the glow spreads throughout the element." Reflexul nu e pentru
  //     zabovire, e RASPUNSUL la atingere. Pe telefon lipsea tocmai unde conteaza.
  //   - `prefers-reduced-motion` — scos la cererea explicita a lui Ion.
  // Acum se leaga pe pointer, indiferent de fel: `pointerdown` da punctul de
  // pornire (sub deget), `pointermove` il urmareste, iar ridicarea il stinge.
  // Nu se ramifica pe `pointerType`: cu mouse, `pointermove` face ce facea si
  // inainte, iar `pointerdown` doar il aprinde mai devreme.
  const cuReflex = optiuni.reflex ?? true

  // CAT TIMP DEGETUL E JOS, LUMINA NU SE STINGE.
  // Masurat: la `touchMove`, Chromium trimite si `pointerleave` — deci un `pleaca`
  // legat orbeste pe el stingea reflexul chiar in timpul gestului (`--spec` cadea
  // la 0 desi degetul era inca pe sticla). Cu mouse-ul, `pointerleave` inseamna
  // chiar ce zice si trebuie sa stinga; cu degetul, doar ridicarea o face.
  let jos = false

  function misca(e) {
    if (e.type === 'pointerdown') jos = true
    const r = nod.getBoundingClientRect()
    if (!r.width || !r.height) return
    nod.style.setProperty('--mx', ((e.clientX - r.left) / r.width).toFixed(3))
    nod.style.setProperty('--my', ((e.clientY - r.top) / r.height).toFixed(3))
    nod.style.setProperty('--spec', '1')
  }
  function pleaca(e) {
    if (e && e.type === 'pointerleave' && jos) return
    jos = false
    nod.style.setProperty('--spec', '0')
  }

  const LEGATURI = [
    ['pointerdown', misca],
    ['pointermove', misca],
    ['pointerup', pleaca],
    ['pointercancel', pleaca],
    ['pointerleave', pleaca],
  ]
  if (cuReflex) {
    for (const [ev, fn] of LEGATURI) nod.addEventListener(ev, fn, { passive: true })
  }

  return {
    destroy() {
      if (cuReflex) {
        for (const [ev, fn] of LEGATURI) nod.removeEventListener(ev, fn)
      }
      for (const s of create) s.remove()
      nod.__sticla = false
    },
  }
}
