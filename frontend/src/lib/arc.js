// ===== ARC CU VITEZA — pentru ce se MUTA si poate fi INTRERUPT =====
//
// DE CE EXISTA, si de ce nu ajunge o tranzitie CSS.
//
// `tokens.css` are deja arcuri: `--ease-arc` si `--ease-arc-elan` sunt un oscilator
// amortizat esantionat in 33 de puncte. Ele arata bine cat timp animatia PORNESTE
// DIN REPAUS si nu e deranjata. Dar o curba prestabilita nu poate reprezenta o
// VITEZA INITIALA — iar cand tinta se schimba in zbor, browserul porneste o
// tranzitie noua de la viteza ZERO. Se vede ca o clipa de stagnare: obiectul care
// zbura intr-o directie se opreste sec, apoi pleaca in cealalta.
//
// Masurat pe tenta din bara de sus (2026-08-24, sonda `proba_intrerupere.py`):
// apesi un tab, apoi altul in zbor — tenta mai urca 6 cadre in directia veche
// (+8.7, +5.6, +3.2, +1.2 px/cadru) inainte sa se intoarca. Aia e discontinuitatea.
//
// WWDC23 „Animate with springs" / „Explore SwiftUI animation": exact asta e motivul
// pentru care Apple foloseste arcuri peste tot — „springs are the only type of
// animation that maintains continuity both for static cases and cases with an
// initial velocity". Cand un arc e retargetat, viteza pe care o avea devine viteza
// initiala catre noua destinatie.
//
// PARAMETRIZAREA E A LOR, nu mass/stiffness/damping: `durata` (perceptuala, in
// secunde) si `bounce` (-1..1). Conversia e cea din sesiune:
//     stiffness = (2π / durata)²
//     damping   = bounce >= 0 ? 4π(1 - bounce) / durata
//                             : 4π / (durata · (1 + bounce))
//     mass      = 1
// bounce 0 = neted, .15 = coada lunga si vioaie, .3 = saltaret vizibil; peste ~.4
// devine exagerat pentru interfata.
//
// CIFRA NU E CEA DIN TOKENS, SI ARE UN MOTIV MASURAT. Comentariul de la
// `--ease-arc-elan` spune „bounce .28", dar esantionul lui `linear()` are varful la
// 1.0384. Integrat cu conversia de mai sus, .28 da doar 3.20% depasire; ca sa iasa
// exact 3.84% trebuie bounce .298. Adica esantionul a fost generat cu o convertire
// putin diferita de a lor. Aici se foloseste .298 tocmai ca MISCAREA SA RAMANA
// IDENTICA cu ce e livrat: singurul lucru care se schimba e continuitatea vitezei
// la intrerupere, nu caracterul. (Perechea, pentru `--ease-arc`: 0.42s cu bounce
// .201 da varful 1.0111, exact ca esantionul lui.)
//
// SCRIE DIRECT IN DOM, nu prin stare reactiva: e valoare de cadru, ca `--gl-p` sau
// `--dx` (vezi nota din `tokens.css`). Un `$state` scris de 60 de ori pe secunda ar
// pune tot arborele componentei pe drumul de reactualizare degeaba.

import { motion } from './motion.svelte.js'

// Pas fix de integrare. Semi-implicit Euler e stabil la pasi mici; 1/240 s da
// patru substeps pe cadru la 60Hz, si ramane exact si la 120Hz.
const PAS = 1 / 240
// Peste atat, cadrul nu mai e „un cadru" (tab in fundal, GC, telefon incarcat).
// Fara plafon, un dt de doua secunde ar arunca arcul in alta galaxie.
const DT_MAX = 1 / 15
// ...dar daca lipsa a fost LUNGA, plafonarea singura nu ajunge: la intoarcere arcul
// ar avea de recuperat zeci de cadre si s-ar tarai vizibil spre tinta. O absenta de
// peste atat nu mai e o animatie intrerupta, e alta sesiune de privit — deci se sare
// direct pe tinta. (Se vede intr-un tab lasat in fundal, si in panoul de
// previzualizare de aici, care nu compoziteaza si deci nu da cadre deloc.)
const GOL_LUNG = 0.5

// Praguri de asezare. Sub ele miscarea nu se mai vede, deci se opreste bucla —
// altfel un arc „aproape ajuns" ar tine un rAF pornit la nesfarsit.
const PRAG_DIST = 0.4    // px
const PRAG_VITEZA = 6    // px/s

/**
 * @param {object} o
 * @param {number} o.durata   secunde (perceptuala, nu timpul pana la oprire)
 * @param {number} o.bounce   -1..1
 * @param {(valori: Record<string, number>) => void} o.scrie  chemat la fiecare cadru
 */
export function creeazaArc({ durata = 0.38, bounce = 0.298, scrie }) {
  const k = (2 * Math.PI / durata) ** 2
  const c = bounce >= 0
    ? 4 * Math.PI * (1 - bounce) / durata
    : 4 * Math.PI / (durata * (1 + bounce))

  /** @type {Map<string, {x: number, v: number, t: number, gata: boolean}>} */
  const canale = new Map()
  let cerere = 0
  let ultim = 0

  function canal(nume) {
    let ca = canale.get(nume)
    if (!ca) {
      ca = { x: 0, v: 0, t: 0, gata: true }
      canale.set(nume, ca)
    }
    return ca
  }

  function valori() {
    const o = {}
    for (const [nume, ca] of canale) o[nume] = ca.x
    return o
  }

  function porneste() {
    if (cerere) return
    ultim = 0
    cerere = requestAnimationFrame(pas)
  }

  function pas(acum) {
    cerere = 0
    const brut = ultim ? (acum - ultim) / 1000 : PAS
    const dt = Math.min(brut, DT_MAX)
    const sarim = brut > GOL_LUNG
    ultim = acum

    let inMiscare = false
    for (const ca of canale.values()) {
      if (ca.gata) continue
      if (sarim) {
        ca.x = ca.t
        ca.v = 0
        ca.gata = true
        continue
      }
      let ramas = dt
      while (ramas > 0) {
        const h = Math.min(PAS, ramas)
        // a = -k·(x - tinta) - c·v   (masa 1)
        const a = -k * (ca.x - ca.t) - c * ca.v
        ca.v += a * h            // semi-implicit: viteza intai, pozitia cu ea
        ca.x += ca.v * h
        ramas -= h
      }
      if (Math.abs(ca.x - ca.t) < PRAG_DIST && Math.abs(ca.v) < PRAG_VITEZA) {
        ca.x = ca.t
        ca.v = 0
        ca.gata = true
      } else {
        inMiscare = true
      }
    }

    scrie(valori())
    if (inMiscare) cerere = requestAnimationFrame(pas)
  }

  return {
    /**
     * Muta tinta unui canal. VITEZA CURENTA SE PASTREAZA — asta e tot rostul.
     * `instant` sare direct (prima asezare, sau `prefers-reduced-motion`).
     */
    tinteste(nume, tinta, { instant = false } = {}) {
      const ca = canal(nume)
      ca.t = tinta
      if (instant || motion.reduced) {
        ca.x = tinta
        ca.v = 0
        ca.gata = true
        scrie(valori())
        return
      }
      if (Math.abs(ca.x - ca.t) < PRAG_DIST && Math.abs(ca.v) < PRAG_VITEZA) {
        ca.x = tinta
        ca.gata = true
        scrie(valori())
        return
      }
      ca.gata = false
      porneste()
    },

    /** Valoarea curenta a unui canal (pentru masuratori si probe). */
    valoare(nume) {
      return canal(nume).x
    },

    opreste() {
      if (cerere) cancelAnimationFrame(cerere)
      cerere = 0
      for (const ca of canale.values()) ca.gata = true
    },
  }
}
