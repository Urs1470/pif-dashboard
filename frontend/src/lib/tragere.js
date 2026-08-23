// Tragere directa pe calendar: mouse SI deget, cu aceleasi reguli.
//
// DE CE NU HTML5 DRAG-AND-DROP (ce era pana la 2026-08-07)
//
// 1. Pe touch nu se declanseaza NICIODATA `dragstart`. Perioadele nu se puteau
//    muta cu degetul deloc — iar pe ecrane sub 620px benzile erau in plus
//    `pointer-events: none`, deci nici macar nu existau ca obiect.
// 2. Nu poate exprima „trage capatul ca sa lungesti". API-ul are un singur
//    inteles: ridici un obiect intreg si il lasi in alta parte.
// 3. Benzile stau PESTE celule, deci trebuia jonglat cu `pointer-events` ca
//    drop-ul sa stie pe ce zi a cazut. Mecanism care se strica in tacere: cand
//    nu porneste, nu arunca nimic si nu scrie nimic in consola — exact cum a
//    fost gasit.
//
// REGULILE GESTULUI
//  - mouse: incepe dupa PRAG_MOUSE px de miscare, ca un click sa ramana click
//  - deget: incepe dupa APASARE_LUNGA ms FARA miscare (apasare lunga), ca o
//    atingere scurta sa ramana atingere si ca derularea paginii sa nu fie furata
//  - derularea se blocheaza DOAR dupa ce gestul a inceput, printr-un listener
//    `touchmove` non-passive. De aceea NU punem `touch-action: none` pe banda:
//    o glisare pornita din greseala pe ea deruleaza pagina normal.

// Pragurile traiesc in `lib/gesturi.js` — o singura definitie pentru toata
// aplicatia. Se RE-exporta de aici doar ca importurile existente sa nu se rupa.
import { PRAG_MOUSE, PRAG_ANULARE, APASARE_LUNGA } from './gesturi.js'
export { PRAG_MOUSE, PRAG_ANULARE, APASARE_LUNGA }

/**
 * Porneste un gest din `pointerdown`. Cheama-l SINCRON din handler — citeste
 * `currentTarget`, care e sters dupa dispecerizare.
 *
 * @param {PointerEvent} ev
 * @param {object} cfg
 * @param {() => void}                cfg.laInceput  gestul chiar a inceput
 * @param {(x:number,y:number)=>void} cfg.laMiscare  pozitia curenta a pointerului
 * @param {() => void}                cfg.laFinal    s-a ridicat degetul/butonul
 * @param {() => void}                cfg.laAnulare  gest intrerupt (Escape, pointercancel)
 * @param {() => void}               [cfg.laAtingere] a fost doar o atingere, fara tragere
 */
export function incepeTragere(ev, cfg) {
  // Doar butonul principal. Fara asta, click-dreapta pe o banda ar apuca-o si
  // ar lasa-o agatata de cursor dupa ce se inchide meniul contextual.
  if (ev.button != null && ev.button !== 0) return

  const el = ev.currentTarget
  const id = ev.pointerId
  const tactil = ev.pointerType !== 'mouse'
  const x0 = ev.clientX
  const y0 = ev.clientY

  let pornit = false
  let incheiat = false
  let temporizator = 0

  const departe = (e) => Math.hypot(e.clientX - x0, e.clientY - y0)

  function porneste() {
    if (pornit || incheiat) return
    pornit = true
    // Capturarea tine gestul legat de elementul apucat chiar daca degetul iese
    // de pe el — altfel o tragere rapida peste marginea benzii se rupe la mijloc.
    try { el.setPointerCapture(id) } catch (_) { /* elementul a disparut */ }
    cfg.laInceput?.()
  }

  function peMiscare(e) {
    if (e.pointerId !== id) return
    if (!pornit) {
      if (tactil) {
        // S-a miscat inainte sa se implineasca apasarea: omul deruleaza pagina.
        if (departe(e) > PRAG_ANULARE) termina(false)
      } else if (departe(e) > PRAG_MOUSE) {
        porneste()
      }
      if (!pornit) return
    }
    cfg.laMiscare?.(e.clientX, e.clientY)
  }

  function peRidicare(e) {
    if (e.pointerId !== id) return
    if (pornit) {
      cfg.laMiscare?.(e.clientX, e.clientY)
      termina(true)
    } else {
      termina(false)
      cfg.laAtingere?.()
    }
  }

  function peAnulare(e) {
    if (e.pointerId !== id) return
    termina(false)
  }

  function peTasta(e) {
    if (e.key === 'Escape') termina(false)
  }

  // Non-passive, ca `preventDefault` sa poata opri derularea. Se inregistreaza
  // de la POINTERDOWN, nu la apasarea lunga: un listener adaugat dupa ce gestul
  // tactil a inceput e ignorat pentru gestul in curs.
  function blocheazaDerularea(e) {
    if (pornit) e.preventDefault()
  }

  function termina(reusit) {
    if (incheiat) return
    incheiat = true
    clearTimeout(temporizator)
    window.removeEventListener('pointermove', peMiscare)
    window.removeEventListener('pointerup', peRidicare)
    window.removeEventListener('pointercancel', peAnulare)
    window.removeEventListener('touchmove', blocheazaDerularea)
    window.removeEventListener('keydown', peTasta)
    try { el.releasePointerCapture(id) } catch (_) { /* deja eliberat */ }
    if (!pornit) return                    // n-a fost tragere: nimeni n-a fost anuntat
    if (reusit) cfg.laFinal?.()
    else cfg.laAnulare?.()
  }

  window.addEventListener('pointermove', peMiscare)
  window.addEventListener('pointerup', peRidicare)
  window.addEventListener('pointercancel', peAnulare)
  window.addEventListener('touchmove', blocheazaDerularea, { passive: false })
  window.addEventListener('keydown', peTasta)

  if (tactil) temporizator = setTimeout(porneste, APASARE_LUNGA)
}
