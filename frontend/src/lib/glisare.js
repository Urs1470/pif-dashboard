// GLISARE PE UN RAND — gestul standard din aplicatiile de to-do pe telefon.
//
// De ce exista: pe telefon fiecare task avea sase butoane de 44px pe o linie
// proprie, deci un rand ocupa 127px si intrau patru taskuri pe ecran. Ion:
// „acum sunt cam rupte, prea mari pe inaltime; sa fie aproape de cum sunt pe
// aplicatii de to do mobile". In acele aplicatii randul e o singura linie si NU
// are niciun buton la vedere: bifa in stanga, titlul, si atat. Actiunile vin din
// gest — glisezi randul si apar.
//
// Doua directii, doua intelesuri:
//   spre DREAPTA -> bifeaza, cu o cursa lunga si prag mare, ca sa nu se intample
//                   din greseala cand derulezi lista cu degetul mare
//   spre STANGA  -> fie descopera un panou de actiuni (`latime`), fie — daca
//                   primeste `onAmana` si NICIO latime — executa un singur verb,
//                   simetric cu bifarea.
//
// DE CE EXISTA `onAmana`: panoul de patru actiuni ocupa 232px din 390, deci taskul
// pe care actionai disparea aproape complet de sub deget si nu mai stiai pe ce
// apesi; iar „Șterge", ultimul din panou, cadea exact unde ajunge o glisare rapida.
// Doua direcii cu doua modele diferite („deschide un meniu" vs „executa") se invata
// separat. Un gest = un verb, in ambele sensuri.
//
// Trei lucruri pe care le greseste orice implementare naiva si care sunt tratate
// aici explicit:
//
//  1. DERULAREA PAGINII TREBUIE SA CASTIGE cand gestul e vertical. Decidem
//     directia o singura data, la primii `PRAG_DIRECTIE` px, si nu ne mai
//     razgandim: altfel o lista lunga devine imposibil de derulat, fiindca
//     fiecare rand fura gestul. `touch-action: pan-y` lasa browserul sa faca
//     derularea verticala nativ, fara sa asteptam noi.
//  2. UN SINGUR RAND DESCHIS. Fara asta ramai cu cinci randuri deschise in urma
//     ta si nu mai stii care e starea listei.
//  3. GESTUL NU E CLICK. Dupa o glisare, `click`-ul de la ridicarea degetului ar
//     ajunge la butonul de dedesubt (sau ar deschide taskul). Il inghitim o
//     singura data, in faza de capturare.

import { PRAG_DIRECTIE, PRAG_ACTIUNE, DUR_ZBOR, puls, inBandaTaburi } from './gesturi.js'

const PRAG_DESCHIDE = 0.4    // fractiune din latimea panoului

let deschisAcum = null       // {node, inchide} — randul deschis, oriunde in pagina

export function inchideGlisarea() {
  deschisAcum?.inchide()
  deschisAcum = null
}

/**
 * @param {HTMLElement} node randul; trebuie sa contina `.gl-fata` si (optional) `.gl-actiuni`
 * @param {{ latime?: number, onBifa?: () => void, activ?: boolean, bandaTaburi?: boolean }} opt
 */
export function glisare(node, opt = {}) {
  let { latime = 0, onBifa = null, onAmana = null, activ = true, bandaTaburi = false } = opt
  const fata = node.querySelector('.gl-fata')
  if (!fata) return {}

  let x0 = 0, y0 = 0
  let dir = null               // null | 'orizontal' | 'vertical'
  let dx = 0
  let deschis = false
  let pointerId = null
  let aGlisat = false
  // Latimea randului, citita O DATA la apasare. Inainte se citea `offsetWidth` la
  // fiecare pointermove — o masuratoare de layout in mijlocul gestului, adica exact
  // unde nu vrei sa ceri browserului sa recalculeze.
  let latimeRand = 0
  let trecutDePrag = false
  let trecutDePragS = false

  const pragBifa = () => latimeRand * PRAG_ACTIUNE

  // Cat din drumul pana la prag s-a facut, 0..1. Il publicam ca variabila CSS ca
  // sa poata pista din global.css sa creasca odata cu degetul, fara ca JS-ul sa
  // scrie stiluri pe fiecare cadru.
  const puneProgres = (v) => {
    const prag = pragBifa()
    const p = onBifa && prag > 0 ? Math.min(1, Math.max(0, v / prag)) : 0
    node.style.setProperty('--gl-p', p.toFixed(3))
    // Acelasi mecanism, oglindit: `--gl-s` creste cat timp tragi spre stanga.
    const s = amanaLibera() && prag > 0 ? Math.min(1, Math.max(0, -v / prag)) : 0
    node.style.setProperty('--gl-s', s.toFixed(3))
  }

  /** Stanga executa (nu descopera) doar cand nu exista panou de descoperit. */
  const amanaLibera = () => !!onAmana && !latime

  const pune = (v, animat) => {
    fata.style.transition = animat ? 'transform var(--dur-base) var(--ease)' : 'none'
    fata.style.transform = `translateX(${v}px)`
    node.classList.toggle('gl-tras', v !== 0)
    // Cat timp tragi spre DREAPTA, panoul de actiuni (care sta ancorat la dreapta,
    // pentru gestul opus) iese de sub rand si se vede pe langa pista de bifare —
    // „Azi" aparea in mijlocul confirmarii verzi. Doua panouri deodata inseamna
    // doua raspunsuri la intrebarea „ce se intampla daca dau drumul".
    node.classList.toggle('gl-dreapta', v > 0)
    node.classList.toggle('gl-stanga', v < 0)
    if (v === 0) {
      node.style.setProperty('--gl-p', '0')
      node.style.setProperty('--gl-s', '0')
      node.classList.remove('gl-bifa')
      node.classList.remove('gl-amana')
      trecutDePrag = false
      trecutDePragS = false
    }
  }

  // COMITEREA SE LEAGA DE ANIMATIE, NU DE UN CRONOMETRU PARALEL.
  //
  // Randul zbura afara pe `--dur-base` (240ms), dar comiterea venea pe un
  // `setTimeout(…, 160)`. La 160ms randul era TELEPORTAT inapoi in ecran, la
  // opacitate 1, ca apoi `plecare` sa-l impinga din nou afara. Ultimul lucru pe
  // care il vedeai din task nu era plecarea lui, era revenirea — doua miscari
  // care se contraziceau pe aceeasi axa.
  //
  // Acum zborul are o durata proprie si scurta (130ms), iar comiterea asteapta
  // `transitionend`-ul lui: la momentul in care lista incepe sa inchida golul,
  // randul chiar a iesit. `pune(0, false)` ramane, dar se intampla cand randul e
  // deja scos din lista de catre parinte, deci nu mai e nimic de vazut.
  //
  // Cronometrul de rezerva nu e paza contra intarzierii, ci contra lui
  // `transitionend` care NU vine deloc: cu `prefers-reduced-motion` durata cade
  // la 0, iar o tranzitie de durata zero nu emite eveniment in toate browserele.
  function zboaraApoi(pana, cb) {
    let gata = false
    const comite = () => {
      if (gata) return
      gata = true
      fata.removeEventListener('transitionend', laCapat)
      cb()
      pune(0, false)
    }
    const laCapat = (e) => { if (e.propertyName === 'transform') comite() }
    fata.addEventListener('transitionend', laCapat)
    fata.style.transition = `transform ${DUR_ZBOR}ms var(--ease)`
    fata.style.transform = `translateX(${pana}px)`
    node.classList.toggle('gl-dreapta', pana > 0)
    node.classList.toggle('gl-stanga', pana < 0)
    setTimeout(comite, DUR_ZBOR + 60)
  }

  function inchide(animat = true) {
    deschis = false
    pune(0, animat)
    node.classList.remove('gl-deschis')
    if (deschisAcum?.node === node) deschisAcum = null
  }

  function deschide() {
    deschis = true
    pune(-latime, true)
    node.classList.add('gl-deschis')
    if (deschisAcum && deschisAcum.node !== node) deschisAcum.inchide()
    deschisAcum = { node, inchide }
  }

  function onDown(e) {
    if (!activ || e.pointerType === 'mouse') return   // mouse-ul are butoanele lui, pe desktop
    if (e.target.closest('.gl-actiuni')) return
    // Manerul de reordonare tine degetul pe verticala (vezi lib/reordonare.js).
    // Fara exceptia asta ambele geasturi ar porni din aceeasi apasare si randul
    // ar aluneca si lateral cat timp il muti in sus.
    if (e.target.closest('.gl-maner')) return
    // BANDA DE JOS E A TABURILOR (doar unde exista taburi de comutat — vezi
    // `BANDA_TABURI` in `gesturi.js`). Randul cedeaza el, aici, in loc ca pagina
    // sa-i fure gestul de deasupra: doua ascultatoare care se cearta pe acelasi
    // deget produc exact felul de ratare in care se bifeaza un task nevrut.
    if (bandaTaburi && inBandaTaburi(e.clientY)) return
    pointerId = e.pointerId
    x0 = e.clientX; y0 = e.clientY
    dir = null; dx = 0; aGlisat = false
    latimeRand = node.offsetWidth
    trecutDePrag = false
  }

  function onMove(e) {
    if (e.pointerId !== pointerId) return
    const ax = e.clientX - x0, ay = e.clientY - y0
    if (dir === null) {
      if (Math.abs(ax) < PRAG_DIRECTIE && Math.abs(ay) < PRAG_DIRECTIE) return
      // Decis o singura data: daca degetul a plecat mai mult pe verticala, gestul
      // apartine paginii si nu ni-l mai luam inapoi.
      dir = Math.abs(ax) > Math.abs(ay) ? 'orizontal' : 'vertical'
      // Captura e o imbunatatire, nu o conditie: daca degetul iese din rand,
      // evenimentele continua sa vina aici. Poate arunca (`NotFoundError`) daca
      // pointerul nu mai e activ — atunci pur si simplu ne descurcam fara ea, in
      // loc sa rupem restul gestului.
      if (dir === 'orizontal') { try { node.setPointerCapture?.(pointerId) } catch (_) {} }
    }
    if (dir !== 'orizontal') return
    aGlisat = true
    const baza = deschis ? -latime : 0
    let v = baza + ax
    // Spre stanga se opreste la panou; spre dreapta merge liber (cursa de bifare),
    // dar numai daca exista ce bifa.
    // Cand stanga e un verb (fara panou), cursa e libera in ambele sensuri.
    if (v < -latime && !amanaLibera()) v = -latime - (Math.abs(v + latime) * 0.25)
    if (v < 0 && !latime && !onAmana) v = v * 0.18
    if (v > 0 && !onBifa) v = v * 0.18
    dx = v
    pune(v, false)
    puneProgres(v)
    const trecutS = amanaLibera() && -v > pragBifa()
    if (trecutS !== trecutDePragS) {
      trecutDePragS = trecutS
      node.classList.toggle('gl-amana', trecutS)
      if (trecutS) puls()
    }
    const trecut = !!onBifa && v > pragBifa()
    if (trecut !== trecutDePrag) {
      trecutDePrag = trecut
      node.classList.toggle('gl-bifa', trecut)
      // Un scurt puls la trecerea pragului (vezi `puls` in lib/gesturi.js).
      if (trecut) puls()
    }
  }

  function onUp(e) {
    if (e.pointerId !== pointerId) return
    pointerId = null
    try { node.releasePointerCapture?.(e.pointerId) } catch (_) {}
    if (dir !== 'orizontal') { dir = null; return }
    dir = null

    if (onBifa && dx > pragBifa()) {
      // Randul pleaca spre dreapta si abia apoi se bifeaza — miscarea e
      // confirmarea, nu un efect decorativ dupa fapt. `gl-bifa` NU se scoate aici:
      // pista trebuie sa ramana plina si bifata cat timp randul iese de sub ea,
      // altfel ultimul lucru pe care il vezi e cum se stinge confirmarea.
      node.style.setProperty('--gl-p', '1')
      zboaraApoi(latimeRand, onBifa)
      return
    }
    if (amanaLibera() && -dx > pragBifa()) {
      // Simetric cu bifarea: randul pleaca spre stanga si abia apoi se muta
      // termenul — miscarea E confirmarea.
      node.style.setProperty('--gl-s', '1')
      zboaraApoi(-latimeRand, onAmana)
      return
    }
    node.classList.remove('gl-bifa')
    node.classList.remove('gl-amana')
    trecutDePrag = false
    trecutDePragS = false
    if (latime && dx < -latime * PRAG_DESCHIDE) deschide()
    else inchide()
  }

  // Capturare: gestul nu trebuie sa se termine intr-un click pe ce era dedesubt.
  function onClick(e) {
    if (!aGlisat) return
    aGlisat = false
    e.stopPropagation()
    e.preventDefault()
  }

  node.addEventListener('pointerdown', onDown, { passive: true })
  node.addEventListener('pointermove', onMove, { passive: true })
  node.addEventListener('pointerup', onUp)
  node.addEventListener('pointercancel', onUp)
  node.addEventListener('click', onClick, true)

  return {
    update(nou = {}) {
      latime = nou.latime ?? latime
      onBifa = nou.onBifa ?? onBifa
      onAmana = nou.onAmana ?? onAmana
      bandaTaburi = nou.bandaTaburi ?? bandaTaburi
      if (nou.activ !== undefined && nou.activ !== activ) {
        activ = nou.activ
        if (!activ) inchide(false)
      }
    },
    destroy() {
      node.removeEventListener('pointerdown', onDown)
      node.removeEventListener('pointermove', onMove)
      node.removeEventListener('pointerup', onUp)
      node.removeEventListener('pointercancel', onUp)
      node.removeEventListener('click', onClick, true)
      if (deschisAcum?.node === node) deschisAcum = null
    },
  }
}
