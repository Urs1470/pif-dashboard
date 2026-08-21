// URMA DE PE APARAT — jurnalul unei deschideri de foaie, milisecunda cu milisecunda.
//
// DE CE EXISTA. Tastatura nu exista pe masina de dezvoltare; `audit_tastatura.py`
// o emuleaza, dar emularea e o ipoteza despre aparat (cand porneste IME-ul, daca
// raporteaza inaltimea dintr-o data sau cadru cu cadru, cat dureaza). Ion: „trebuie
// sa poti face milisecunda cu milisecunda, am Gboard, Honor Magic 6 Pro." Singurul
// mod e sa masori ACOLO. Jurnalul asta inregistreaza, pe aparat, tot ce conteaza
// pentru coregrafia foii — cand s-a deschis, cand a primit focus campul, fiecare
// `resize`/`scroll` al `visualViewport` cu valoarea lui, si pozitia foii la
// fiecare cadru — si il pune in clipboard, de unde ajunge intr-un mesaj.
//
// Se porneste din adresa: `#/?urma=1` (si se opreste cu `?urma=0`). Cat e pornit,
// un buton mic „Urmă" sta pe ecran (vezi `components/Urma.svelte`). Nu costa nimic
// cand e oprit: toate functiile ies la prima linie.

const CHEIE = 'pif-urma'
const CHEIE_ULTIMA = 'pif-urma-ultima'
const DURATA = 2600   // ms inregistrate dupa deschidere

export function urmaActiva() {
  try { return localStorage.getItem(CHEIE) === '1' } catch (_) { return false }
}
export function porneste(activ) {
  try { activ ? localStorage.setItem(CHEIE, '1') : localStorage.removeItem(CHEIE) } catch (_) {}
}

let jurnal = null
let t0 = 0
let ceas = null
let raf = 0

function acum() { return Math.round((performance.now() - t0) * 10) / 10 }

/** Porneste o inregistrare noua. Se cheama la deschiderea unei foi. */
export function urmaStart(eticheta) {
  if (!urmaActiva()) return
  urmaStop()
  t0 = performance.now()
  const vv = window.visualViewport
  jurnal = [{
    t: 0, e: 'start', ce: eticheta,
    ua: navigator.userAgent.slice(0, 120),
    innerHeight: window.innerHeight, vv: vv ? Math.round(vv.height) : null,
    kbStiut: localStorage.getItem('pif-kb'), latStiuta: localStorage.getItem('pif-kb-lat'),
    dpr: window.devicePixelRatio,
  }]
  const cadru = () => {
    const f = document.querySelector('.modal.sheet')
    const b = document.querySelector('.backdrop')
    const r = f ? f.getBoundingClientRect() : null
    jurnal.push({
      t: acum(), e: 'cadru',
      top: r ? Math.round(r.top) : null, h: r ? Math.round(r.height) : null,
      pb: b ? Math.round(parseFloat(getComputedStyle(b).paddingBottom)) : null,
      kb: getComputedStyle(document.documentElement).getPropertyValue('--kb').trim(),
      vv: vv ? Math.round(vv.height) : null,
    })
    raf = requestAnimationFrame(cadru)
  }
  raf = requestAnimationFrame(cadru)
  ceas = setTimeout(urmaStop, DURATA)
}

/** Un eveniment cu nume, oriunde in drum. */
export function urmaEvent(e, extra) {
  if (!jurnal) return
  jurnal.push({ t: acum(), e, ...(extra || {}) })
}

export function urmaStop() {
  if (!jurnal) return
  cancelAnimationFrame(raf)
  clearTimeout(ceas)
  // Cadrele identice consecutive se strang: ce conteaza e CAND se schimba ceva.
  const strans = []
  let prev = null
  for (const p of jurnal) {
    if (p.e === 'cadru') {
      const k = `${p.top}|${p.h}|${p.pb}|${p.kb}|${p.vv}`
      if (k === prev) continue
      prev = k
    }
    strans.push(p)
  }
  try { localStorage.setItem(CHEIE_ULTIMA, JSON.stringify(strans)) } catch (_) {}
  jurnal = null
}

export function ultimaUrma() {
  try { return localStorage.getItem(CHEIE_ULTIMA) || '' } catch (_) { return '' }
}
