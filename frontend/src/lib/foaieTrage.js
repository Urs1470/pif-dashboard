// ===== FOAIA MICA SE TRAGE IN JOS SI SE INCHIDE =====
//
// DE CE EXISTA. `DatePicker` si `SelectorOra` se deschid pe telefon ca foi lipite de
// baza ecranului, si amandoua desenau un MANER — bara de 4px care spune „trage-ma".
// Niciuna n-avea gestul. Adica exact reprosul pe care Ion l-a facut deja o data,
// scris in `Modal.svelte`: „manerul era pana atunci DECOR: un dreptunghi care arata
// a maner si nu facea nimic." Acolo a fost reparat; foile astea doua, care se
// deschid DIN foaia de task, au ramas cu decorul.
//
// DE CE NU REFOLOSESC `lib/tragere.js`. `incepeTragere` e facut pentru
// apasa-lung-apoi-trage (are temporizator de apasare, prag de anulare): potrivit
// pentru o banda de perioada, gresit pentru o foaie, care trebuie sa plece din prima.
//
// DE CE SE LEAGA PE FOAIE, NU PE MANER. Aceeasi lectie, tot din `Modal.svelte`, cu
// masuratoare: „foaia incepe la 468, bara sta la 476-480, iar antetul abia la 482 —
// deci primii 14px, cu tot cu singurul semn care spune «trage-ma», nu faceau nimic."
// Ion: „de TOT ANTETUL, nu de bara de 4px." Deci gestul asculta pe toata foaia si se
// aprinde doar daca degetul a plecat din BANDA DE SUS — unde sta si manerul.
//
// TAPUL TRECE MAI DEPARTE. Anteturile astea au butoane inauntru (sagetile de luna,
// comutatorul ora/minut). Gestul nu captureaza nimic pana nu s-a miscat peste prag
// SI mai mult pe verticala decat pe orizontala; pana atunci apasarea e a butonului.

import { urmaritor } from './gesturi.js'
import { creeazaArc } from './arc.js'

// Cat din capul foii raspunde la tragere. 64 = manerul plus antetul, adica fix
// suprafata pe care degetul o tinteste cand vrea sa inchida.
const BANDA_SUS = 64
// Cat trebuie sa se miste degetul ca gestul sa devina al foii. Sub atat, e un tap.
const PRAG = 8
// Cat din inaltimea foii trebuie sa fi parcurs POZITIA PROIECTATA ca sa se inchida.
// Proiectata, nu cea in care s-a oprit degetul: asa o aruncare scurta si iute si o
// tragere lunga si lenesa ajung la aceeasi concluzie — ca la foaia mare.
const PRAG_INCHIDE = 0.32

/**
 * @param {HTMLElement} nod  foaia (`.dp-pop.sheet` / `.so-pop.sheet`)
 * @param {{ activ: boolean, laInchidere: () => void }} cfg
 */
export function foaieTrage(nod, cfg) {
  let optiuni = cfg
  let id = null
  let y0 = 0
  let x0 = 0
  let pornit = false
  let dy = 0
  const vit = urmaritor()

  const arc = creeazaArc({
    durata: 0.42,
    bounce: 0.201,
    scrie: ({ y }) => { nod.style.transform = y ? 'translateY(' + y.toFixed(1) + 'px)' : '' },
    laFinal: () => { nod.style.transform = ''; nod.style.willChange = '' },
  })

  function jos(e) {
    if (!optiuni.activ || id !== null) return
    if (e.pointerType === 'mouse') return          // foaia exista doar pe telefon
    const r = nod.getBoundingClientRect()
    if (e.clientY - r.top > BANDA_SUS) return      // degetul e in continut, nu pe cap
    arc.opreste()
    id = e.pointerId
    y0 = e.clientY
    x0 = e.clientX
    dy = 0
    pornit = false
    vit.porneste(e.clientY)
  }

  function misca(e) {
    if (e.pointerId !== id) return
    const d = e.clientY - y0
    if (!pornit) {
      // Mai mult pe verticala decat pe orizontala, si peste prag: abia atunci e al foii.
      if (Math.abs(d) < PRAG || Math.abs(e.clientX - x0) > Math.abs(d)) return
      if (d < 0) { id = null; return }             // in sus n-are unde
      pornit = true
      try { nod.setPointerCapture(id) } catch (_) { /* a disparut */ }
      nod.style.willChange = 'transform'
    }
    // Peste capatul de sus nu se trece: foaia e lipita de baza, n-are unde sa urce.
    dy = Math.max(0, d)
    vit.adauga(e.clientY)
    nod.style.transform = 'translateY(' + dy.toFixed(1) + 'px)'
    if (e.cancelable) e.preventDefault()
  }

  function sus(e) {
    if (e.pointerId !== id) return
    id = null
    if (!pornit) return
    pornit = false
    const h = nod.getBoundingClientRect().height || 1
    if (vit.proiectat(dy) > h * PRAG_INCHIDE) {
      // Nu se anima iesirea aici: foaia are deja tranzitia ei de inchidere, iar doua
      // miscari pe acelasi obiect s-ar compune (lectia din `Modal.svelte`, `lasa()`).
      nod.style.transform = ''
      nod.style.willChange = ''
      optiuni.laInchidere?.()
      return
    }
    // Revine, cu viteza degetului. `viteza()` e px/ms, arcul lucreaza in px/s.
    arc.preia('y', dy, vit.viteza() * 1000, 0)
  }

  nod.addEventListener('pointerdown', jos, { passive: true })
  nod.addEventListener('pointermove', misca)
  nod.addEventListener('pointerup', sus, { passive: true })
  nod.addEventListener('pointercancel', sus, { passive: true })

  return {
    update(nou) { optiuni = nou },
    destroy() {
      arc.opreste()
      nod.removeEventListener('pointerdown', jos)
      nod.removeEventListener('pointermove', misca)
      nod.removeEventListener('pointerup', sus)
      nod.removeEventListener('pointercancel', sus)
    },
  }
}
