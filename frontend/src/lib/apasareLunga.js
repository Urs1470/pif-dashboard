// APASARE LUNGA — al treilea gest al unui rand, langa glisare si derulare.
//
// DE CE E UN FISIER, NU O FUNCTIE LOCALA. Gestul exista deja in aplicatie, scris
// de mana in `pages/Tasks.svelte` pentru redenumirea unui subtask, cu doua
// constante proprii (`PRAG_LUNG = 300`, `PRAG_MISCARE = 8`) care sunt copii ale
// lui `APASARE_LUNGA` si `PRAG_DIRECTIE` din `gesturi.js`, si cu un
// `navigator.vibrate?.(12)` scris inline in loc de `puls()`. Trei valori care
// spun acelasi lucru in doua locuri se desincronizeaza fara ca nimic sa
// semnaleze — exact motivul pentru care `gesturi.js` exista.
//
// CE TREBUIE SA NU STRICE. Pe un rand de task degetul are deja trei intelesuri:
//   vertical    deruleaza lista (browserul, prin `touch-action: pan-y`)
//   orizontal   gliseaza randul (`glisare.js`)
//   pe maner    reordoneaza (`reordonare.js`, doar pe „Astăzi")
// Deci apasarea lunga are voie sa porneasca numai cand degetul NU face nimic
// altceva: prima miscare peste `PRAG_DIRECTIE` o anuleaza, in ORICE axa. Nu doar
// pe verticala: o glisare orizontala pornita incet ar trece pragul de timp
// inainte sa treaca pragul de directie, si atunci ai avea deodata si foaia
// deschisa si randul tras de sub ea.
//
// CAT DE MULT TII APASAT: `APASARE_MENIU` (420), nu `APASARE_LUNGA` (300).
// Prima versiune folosea 300, cu argumentul c-ar fi „singurul prag de apasare din
// aplicatie". Argumentul era greșit, si s-a vazut la prima folosire pe telefon:
// la 300ms foaia soseste inainte ca degetul sa se ridice, apasarea continua PE EA,
// iar WebView-ul o citeste ca long-press pe text si porneste selectia (raportat de
// Ion). Un prag care APUCA un obiect si unul care DESCHIDE un strat nu cer acelasi
// lucru de la mana — motivul intreg e scris la `APASARE_MENIU` in `gesturi.js`.
//
// DOAR PE ATINGERE. Cu mouse actiunile randului sunt la vedere (`.task-actions`
// apare la hover), deci un meniu la apasare lunga ar fi un al doilea drum catre
// ce e deja pe ecran.

import { APASARE_MENIU, PRAG_DIRECTIE, puls } from './gesturi.js'

/**
 * Actiune Svelte pentru un rand.
 *
 * @param {HTMLElement} node
 * @param {{ actiune?: () => void, activ?: boolean, ignora?: string }} opt
 *        `ignora` = selector de zone care isi au propriul gest (manerul de
 *        reordonare, panoul de actiuni), unde apasarea lunga nu porneste.
 */
export function apasareLunga(node, opt = {}) {
  let { actiune = null, activ = true, ignora = '' } = opt

  let ceas = null
  let x0 = 0, y0 = 0
  let pornit = false
  let pointerId = null

  const stop = () => {
    if (ceas) { clearTimeout(ceas); ceas = null }
    pointerId = null
  }

  function jos(e) {
    if (!activ || e.pointerType === 'mouse') return
    if (ignora && e.target.closest?.(ignora)) return
    pointerId = e.pointerId
    x0 = e.clientX; y0 = e.clientY
    pornit = false
    if (ceas) clearTimeout(ceas)
    ceas = setTimeout(() => {
      ceas = null
      pornit = true
      // Degetul acopera exact randul pe care se intampla ceva, deci confirmarea
      // care nu se vede se simte. Acelasi puls ca la trecerea pragului de
      // glisare — e acelasi lucru: „de aici, ridicarea degetului face ceva".
      puls()
      actiune?.()
    }, APASARE_MENIU)
  }

  function misca(e) {
    if (!ceas || e.pointerId !== pointerId) return
    if (Math.abs(e.clientX - x0) > PRAG_DIRECTIE || Math.abs(e.clientY - y0) > PRAG_DIRECTIE) stop()
  }

  // Dupa o apasare lunga, clicul de la ridicarea degetului ar ajunge la randul de
  // dedesubt (adica ar deschide taskul peste foaia care tocmai s-a ridicat). Se
  // inghite o singura data, in faza de capturare — exact ca in `glisare.js`.
  function clic(e) {
    if (!pornit) return
    pornit = false
    e.preventDefault()
    e.stopPropagation()
  }

  node.addEventListener('pointerdown', jos, { passive: true })
  node.addEventListener('pointermove', misca, { passive: true })
  node.addEventListener('pointerup', stop)
  node.addEventListener('pointercancel', stop)
  node.addEventListener('click', clic, true)

  return {
    update(nou = {}) {
      actiune = nou.actiune ?? actiune
      ignora = nou.ignora ?? ignora
      if (nou.activ !== undefined && nou.activ !== activ) {
        activ = nou.activ
        if (!activ) stop()
      }
    },
    destroy() {
      stop()
      node.removeEventListener('pointerdown', jos)
      node.removeEventListener('pointermove', misca)
      node.removeEventListener('pointerup', stop)
      node.removeEventListener('pointercancel', stop)
      node.removeEventListener('click', clic, true)
    },
  }
}
