// REORDONARE PRIN TRAGERE, PE ATINGERE.
//
// De ce exista: reordonarea listei „Astăzi" se facea prin `draggable="true"` +
// evenimente HTML5 de drag. Acelea NU EXISTA pe touch — niciun telefon nu le
// emite. Ca inlocuitor, fiecare rand primise doua sageti (sus/jos) de 40×22px:
// 76 de tinte sub prag pe un singur ecran, plus doua iconite pe fiecare rand
// dintr-o lista care tocmai fusese adusa la o singura linie.
//
// Aici gestul e cel din aplicatiile native: apuci un maner si tragi randul.
// Trei decizii care conteaza:
//
//  1. SE TRAGE DE UN MANER, NU DE RAND. Un rand care se ia la tragere dupa o
//     apasare lunga se bate pe acelasi deget cu derularea si cu glisarea
//     laterala, si nu poti spune dinainte care castiga. Manerul e explicit:
//     `touch-action: none` doar pe el, deci restul randului deruleaza si
//     gliseaza mai departe, exact ca inainte.
//  2. ORDINEA DIN DOM NU SE ATINGE CAT TIMP TRAGI. Lista e randata de Svelte
//     dintr-un array; daca am muta noduri cu mana, urmatoarea randare le-ar pune
//     inapoi. Deci mutam doar `transform`-uri, iar la ridicarea degetului
//     anuntam O SINGURA data mutarea si lasam Svelte sa rearanjeze (cu `flip`).
//  3. TINTA SE DECIDE DUPA MIJLOCUL RANDULUI TRAS, nu dupa cat a mers degetul.
//     Randurile n-au toate aceeasi inaltime (unul cu doua chipuri e mai inalt),
//     deci un pas fix ar aluneca dupa cateva pozitii.

import { PRAG_MOUSE, puls } from './gesturi.js'

// Pornirea reordonarii e acelasi prag ca al mouse-ului: sub atat, e un click.
const PRAG_PORNIRE = PRAG_MOUSE

/**
 * Actiune Svelte pentru CONTAINERUL listei.
 *
 * @param {HTMLElement} node containerul; copiii care se muta sunt `selectorRand`
 * @param {{
 *   activ?: boolean,
 *   selectorRand?: string,
 *   selectorManer?: string,
 *   onMutare?: (din: number, la: number) => void,
 * }} opt
 */
export function reordonare(node, opt = {}) {
  let {
    activ = true,
    selectorRand = '[data-rand]',
    selectorManer = '[data-maner]',
    onMutare = () => {},
  } = opt

  let randuri = []            // nodurile, in ordinea din DOM, la inceputul tragerii
  let cutii = []              // dreptunghiurile lor, inghetate la inceput
  let din = -1                // indexul randului tras
  let la = -1                 // indexul unde ar ajunge acum
  let y0 = 0
  let pornit = false
  let pointerId = null
  let tras = null             // nodul tras

  const inaltimeCu = (i) => cutii[i].height + 6   // + distanta dintre randuri

  function curata() {
    for (const r of randuri) { r.style.transform = ''; r.style.transition = '' }
    tras?.classList.remove('reord-tras')
    node.classList.remove('reord-activ')
    randuri = []; cutii = []; din = -1; la = -1
    pornit = false; pointerId = null; tras = null
  }

  function onDown(e) {
    if (!activ || pointerId !== null) return
    const maner = e.target.closest?.(selectorManer)
    if (!maner || !node.contains(maner)) return
    const rand = maner.closest(selectorRand)
    if (!rand) return
    randuri = [...node.querySelectorAll(selectorRand)]
    din = randuri.indexOf(rand)
    if (din < 0) { randuri = []; return }
    tras = rand
    la = din
    y0 = e.clientY
    pointerId = e.pointerId
    cutii = randuri.map(r => r.getBoundingClientRect())
    e.preventDefault()        // fara asta, Safari incepe selectia de text
  }

  function onMove(e) {
    if (e.pointerId !== pointerId || din < 0) return
    const dy = e.clientY - y0
    if (!pornit) {
      if (Math.abs(dy) < PRAG_PORNIRE) return
      pornit = true
      node.classList.add('reord-activ')
      tras.classList.add('reord-tras')
      try { node.setPointerCapture?.(pointerId) } catch (_) {}
      puls(8)
    }

    // Mijlocul randului tras, in coordonatele de la inceput.
    const mijloc = cutii[din].top + cutii[din].height / 2 + dy
    const mij = (i) => cutii[i].top + cutii[i].height / 2
    // JUMATATEA RANDULUI TRAS, nu mijlocul vecinului.
    // Prima versiune cerea sa treci de mijlocul vecinului asa cum statea el la
    // inceput — dar vecinul se DA LA O PARTE cand treci pe langa el, deci pana
    // sa ajungi acolo el nu mai e acolo. Rezultatul: trageai peste doua randuri
    // si sareai doar unul, si greseala crestea cu fiecare pozitie. Pragul corect
    // e la jumatatea drumului dintre doua locuri — adica mijlocul vecinului minus
    // jumatate din inaltimea randului tras.
    const prag = inaltimeCu(din) / 2
    let tinta = din
    while (tinta > 0 && mijloc < mij(tinta - 1) + prag) tinta--
    while (tinta < cutii.length - 1 && mijloc > mij(tinta + 1) - prag) tinta++
    la = tinta

    for (let i = 0; i < randuri.length; i++) {
      if (i === din) { randuri[i].style.transform = `translateY(${dy}px)`; continue }
      randuri[i].style.transition = 'transform var(--dur-fast) var(--ease)'
      // Randurile dintre pozitia veche si cea noua se dau la o parte cu exact
      // inaltimea randului tras — asa golul urmareste degetul.
      let d = 0
      if (din < la && i > din && i <= la) d = -inaltimeCu(din)
      else if (din > la && i >= la && i < din) d = inaltimeCu(din)
      randuri[i].style.transform = d ? `translateY(${d}px)` : ''
    }
  }

  function onUp(e) {
    if (e.pointerId !== pointerId) return
    try { node.releasePointerCapture?.(e.pointerId) } catch (_) {}
    const a = din, b = la, chiar = pornit && a >= 0 && b >= 0 && a !== b
    curata()
    if (chiar) onMutare(a, b)
  }

  // Ridicarea degetului dupa o tragere nu trebuie sa ajunga si ca un click pe
  // randul de dedesubt (unde ar deschide taskul).
  function onClick(e) {
    if (!pornit && din < 0) return
    if (e.target.closest?.(selectorManer)) { e.stopPropagation(); e.preventDefault() }
  }

  node.addEventListener('pointerdown', onDown)
  node.addEventListener('pointermove', onMove, { passive: true })
  node.addEventListener('pointerup', onUp)
  node.addEventListener('pointercancel', onUp)
  node.addEventListener('click', onClick, true)

  return {
    update(nou = {}) {
      if (nou.onMutare) onMutare = nou.onMutare
      if (nou.activ !== undefined && nou.activ !== activ) {
        activ = nou.activ
        if (!activ && din >= 0) curata()
      }
    },
    destroy() {
      node.removeEventListener('pointerdown', onDown)
      node.removeEventListener('pointermove', onMove)
      node.removeEventListener('pointerup', onUp)
      node.removeEventListener('pointercancel', onUp)
      node.removeEventListener('click', onClick, true)
    },
  }
}
