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
//   spre STANGA  -> descopera panoul de actiuni (ramane deschis pana il inchizi)
//   spre DREAPTA -> bifeaza, cu o cursa lunga si prag mare, ca sa nu se intample
//                   din greseala cand derulezi lista cu degetul mare
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

const PRAG_DIRECTIE = 8      // px pana la care decidem daca e gest orizontal
const PRAG_DESCHIDE = 0.4    // fractiune din latimea panoului
const PRAG_BIFA = 0.42       // fractiune din latimea randului

let deschisAcum = null       // {node, inchide} — randul deschis, oriunde in pagina

export function inchideGlisarea() {
  deschisAcum?.inchide()
  deschisAcum = null
}

/**
 * @param {HTMLElement} node randul; trebuie sa contina `.gl-fata` si (optional) `.gl-actiuni`
 * @param {{ latime?: number, onBifa?: () => void, activ?: boolean }} opt
 */
export function glisare(node, opt = {}) {
  let { latime = 0, onBifa = null, activ = true } = opt
  const fata = node.querySelector('.gl-fata')
  if (!fata) return {}

  let x0 = 0, y0 = 0
  let dir = null               // null | 'orizontal' | 'vertical'
  let dx = 0
  let deschis = false
  let pointerId = null
  let aGlisat = false

  const pune = (v, animat) => {
    fata.style.transition = animat ? 'transform var(--dur-base) var(--ease)' : 'none'
    fata.style.transform = `translateX(${v}px)`
    node.classList.toggle('gl-tras', v !== 0)
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
    pointerId = e.pointerId
    x0 = e.clientX; y0 = e.clientY
    dir = null; dx = 0; aGlisat = false
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
    if (v < -latime) v = -latime - (Math.abs(v + latime) * 0.25)
    if (v > 0 && !onBifa) v = v * 0.18
    dx = v
    pune(v, false)
    node.classList.toggle('gl-bifa', !!onBifa && v > node.offsetWidth * PRAG_BIFA)
  }

  function onUp(e) {
    if (e.pointerId !== pointerId) return
    pointerId = null
    try { node.releasePointerCapture?.(e.pointerId) } catch (_) {}
    if (dir !== 'orizontal') { dir = null; return }
    dir = null
    node.classList.remove('gl-bifa')

    if (onBifa && dx > node.offsetWidth * PRAG_BIFA) {
      // Randul pleaca spre dreapta si abia apoi se bifeaza — miscarea e
      // confirmarea, nu un efect decorativ dupa fapt.
      pune(node.offsetWidth, true)
      setTimeout(() => { onBifa(); pune(0, false) }, 160)
      return
    }
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
