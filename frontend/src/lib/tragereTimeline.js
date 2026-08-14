// TRAGEREA PE O PISTA DE ZILE — Planificator si Calendar.
//
// Ion: „alungirile, compactarile si mutarile trebuie sa fie maxim de fluide si
// reactive". Ce le facea sa nu fie, punct cu punct:
//
//  1. DOUA MODELE PE ACELASI ECRAN. `startDrag` scria `el.style.left = want+'%'`
//     (direct in DOM), `apucaCapatImpl` trecea prin `$state` (deci re-randa).
//     Acelasi gest, doua cai, doua feluri de a se simti.
//  2. CUANTIZARE LA FIECARE CADRU. `Math.round(dx / dayW)` inseamna ca obiectul
//     nu urmareste degetul: sta pe loc pana treci jumatate de zi, apoi SARE.
//     Pe un orizont de 14 zile o zi are ~64px, deci 32px de gest nu produceau
//     nicio miscare pe ecran.
//  3. `getBoundingClientRect()` IN FIECARE `pointermove`. O masuratoare de
//     layout in mijlocul gestului, adica exact unde nu vrei sa ceri browserului
//     sa recalculeze.
//  4. FARA COALESCARE. Pe Android vin 120-240 de evenimente pe secunda, fiecare
//     invalidand starea; randarea nu tine pasul si gestul se simte in urma.
//  5. `left`/`width` = LAYOUT la fiecare cadru, si nicio tranzitie pe pozitie —
//     deci dupa commit + reincarcare obiectul se teleporta pe ziua noua.
//
// Regula modulului: MASOARA O DATA, MISCA PE `transform`, COALESCEAZA PE rAF,
// CUANTIZEAZA DOAR LA COMMIT. Previzualizarea nu re-randeaza pagina: scrie doua
// variabile CSS si atat.

import { incepeTragere } from './tragere.js'

/** Numarul de zile intre doua ISO (b - a), pe calendar local. */
function difZile(a, b) {
  const [ay, am, ad] = a.split('-').map(Number)
  const [by, bm, bd] = b.split('-').map(Number)
  return Math.round((Date.UTC(by, bm - 1, bd) - Date.UTC(ay, am - 1, ad)) / 86400000)
}

/** ISO + n zile. */
function plusZile(iso, n) {
  const [y, m, d] = iso.split('-').map(Number)
  const t = new Date(Date.UTC(y, m - 1, d + n))
  return `${t.getUTCFullYear()}-${String(t.getUTCMonth() + 1).padStart(2, '0')}-${String(t.getUTCDate()).padStart(2, '0')}`
}

/**
 * Trage un obiect pe o pista de zile.
 *
 * @param {PointerEvent} ev  evenimentul de `pointerdown` (se cheama SINCRON)
 * @param {object} cfg
 * @param {HTMLElement} cfg.pista     pista; se masoara O DATA, la apasare
 * @param {HTMLElement} cfg.obiect    elementul care se misca (primeste `--dx`)
 * @param {number}      cfg.zile      cate zile are fereastra
 * @param {string}      cfg.ziStart   ISO, prima zi din fereastra
 * @param {string}      cfg.ziObiect  ISO, ziua actuala a obiectului APUCAT
 * @param {(p:{dx:number, zi:string, delta:number})=>void} [cfg.laPreview]
 * @param {(zi:string, delta:number)=>(void|Promise<void>)} cfg.laCommit
 * @param {()=>void} [cfg.laAnulare]
 * @param {()=>void} [cfg.laInceput]
 * @param {()=>void} [cfg.laAtingere]
 * @param {number}   [cfg.minDelta]   limita inferioara a deplasarii, in zile
 * @param {number}   [cfg.maxDelta]   limita superioara
 */
export function tragePeZile(ev, cfg) {
  const {
    pista, obiect, zile, ziStart, ziObiect,
    laPreview, laCommit, laAnulare, laInceput, laAtingere,
    minDelta = -Infinity, maxDelta = Infinity,
  } = cfg
  if (!pista || !obiect || !zile) return

  // O SINGURA MASURATOARE, la apasare. Fereastra nu se schimba cat tine gestul.
  let ziW = 1
  let x0 = ev.clientX
  let dx = 0
  let delta = 0          // zile intregi, calculate doar pentru previzualizare
  let raf = 0
  let ultimDelta = null

  const idxStart = difZile(ziStart, ziObiect)

  function scrie() {
    raf = 0
    obiect.style.setProperty('--dx', dx.toFixed(1) + 'px')
    // Ziua-tinta se publica pe PISTA, nu pe obiect: o citeste celula care se
    // aprinde sub cursor, iar ea nu e copilul obiectului tras.
    if (delta !== ultimDelta) {
      ultimDelta = delta
      const idx = Math.min(zile - 1, Math.max(0, idxStart + delta))
      pista.style.setProperty('--zi-tinta', String(idx))
      laPreview?.({ dx, zi: plusZile(ziObiect, delta), delta })
    }
  }

  incepeTragere(ev, {
    laInceput() {
      const r = pista.getBoundingClientRect()
      ziW = r.width / zile
      // `will-change` DOAR cat tine gestul: lasat permanent, tine un strat de
      // compozitare pentru fiecare banda din pagina.
      obiect.style.willChange = 'transform'
      obiect.classList.add('se-trage')
      pista.classList.add('pista-trage')
      laInceput?.()
    },
    laMiscare(x) {
      dx = x - x0
      // Cuantizarea e DOAR pentru previzualizare (ce zi se aprinde); `--dx`
      // ramane continuu, deci obiectul urmareste degetul pixel cu pixel.
      const d = Math.round(dx / ziW)
      delta = Math.min(maxDelta, Math.max(minDelta, d))
      if (!raf) raf = requestAnimationFrame(scrie)
    },
    laFinal() {
      if (raf) { cancelAnimationFrame(raf); raf = 0 }
      curata()
      if (delta === 0) { laAtingere?.(); return }
      // SNAPUL CONFIRMA (90ms): obiectul se aseaza pe ziua intreaga, apoi se
      // comite. Fara el, ultimul lucru vazut e obiectul intre doua zile.
      obiect.style.transition = 'transform var(--dur-press) var(--ease)'
      obiect.style.setProperty('--dx', (delta * ziW).toFixed(1) + 'px')
      const zi = plusZile(ziObiect, delta)
      const d = delta
      setTimeout(() => {
        obiect.style.transition = ''
        obiect.style.removeProperty('--dx')
        laCommit?.(zi, d)
      }, 90)
    },
    laAnulare() {
      if (raf) { cancelAnimationFrame(raf); raf = 0 }
      curata()
      obiect.style.removeProperty('--dx')
      laAnulare?.()
    },
    laAtingere,
  })

  function curata() {
    obiect.style.willChange = ''
    obiect.classList.remove('se-trage')
    pista.classList.remove('pista-trage')
    pista.style.removeProperty('--zi-tinta')
  }
}

export { difZile, plusZile }
