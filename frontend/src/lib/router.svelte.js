import { tick } from 'svelte'
import { motion } from './motion.svelte.js'
import { PRAG_TELEFON } from './ecran.svelte.js'

// ATERIZAREA PE TELEFON: fara ruta in URL, aplicatia porneste pe taskurile
// PERSONALE, nu pe Acasa. Telefonul se deschide ca sa vezi ce ai de facut in
// viata ta, nu ca sa citesti panoul de proiecte — pe desktop, unde ziua incepe
// cu proiectele, Acasa ramane aterizarea.
//
// Sfera traieste in URL (`?sfera=personal`, vezi Tasks.svelte), deci aterizarea
// e o singura ruta, nu un state care ar mai trebui pastrat undeva.
//
// Se ruleaza AICI, la initializarea modulului, si scrie hash-ul cu
// `replaceState` INAINTE de prima citire: asa `router` porneste direct pe ruta
// buna (fara sa clipeasca Acasa) si fara sa lase o intrare de istoric in urma,
// pe care butonul „inapoi" de pe Android ar duce-o inapoi la Acasa.
//
// Pragul e importat, nu rescris: a cincea copie a lui „768" e exact ce previne
// `ecran.svelte.js`.
const ATERIZARE_TELEFON = '/tasks?sfera=personal'

function aterizareInitiala() {
  if (typeof window === 'undefined') return null
  if (getRaw()) return null            // ruta ceruta explicit: link, notificare, refresh
  if (!(window.matchMedia?.(PRAG_TELEFON)?.matches ?? false)) return null
  return ATERIZARE_TELEFON
}

const _aterizare = aterizareInitiala()
if (_aterizare) {
  try { window.history.replaceState(null, '', '#' + _aterizare) }
  catch (_) { window.location.hash = '#' + _aterizare }
}

export const router = $state({ path: getPath(), query: getQuery(), params: {} })

// ISTORICUL APLICATIEI, tinut de ruter — NU de WebView. Istoricul WebView-ului
// amesteca rutele cu redirectul de dupa login si cu intrarile rescrise prin
// `replaceState` (aterizarea de mai sus, curatarea `?focus` din `focus.js`),
// deci „inapoi" pe el nu inseamna „ultima miscare" — pe Android gestul cadea
// mereu pe prima intrare, adica pe Acasa. Aici se imping DOAR schimbarile de
// ruta pe care le-a vazut aplicatia, iar `inapoi()` — chemat de gestul Android
// din `main.js` — o scoate pe ultima. Plafonat: o sesiune care sta deschisa
// zile intregi n-are nevoie de mii de intrari.
const istoric = []
const ISTORIC_MAX = 100
let curenta = getRaw() || '/'   // dupa aterizare, deci ruta reala de start
let _dinInapoi = false          // intoarcerea e un POP: nu se inregistreaza pe ea insasi

// PRIMA INCARCARE E ALTCEVA DECAT O NAVIGARE.
//
// `.ruta-in` (invelisul urca 10px) si `.cell-in` (celulele sosesc in scara) se
// jucau la FIECARE montare de pagina — deci si la fiecare schimbare de tab,
// peste tranzitia pe care browserul o joaca deja pe radacina. Trei animatii de
// intrare pe aceiasi pixeli, doua axe, si opacitati care se INMULTESC: la
// mijlocul drumului o celula ajungea pe la 0,13 in loc de 0,5. Pagina nu sosea
// o data, aparea de trei ori.
//
// Cand tranzitia o detine browserul, ea e singura care are voie sa se joace.
// Ce ramane pentru cele doua e exact cazul pentru care au fost scrise: prima
// deschidere a aplicatiei, cand nu exista nicio pagina veche de la care sa vii.
//
// STEAGUL SE STINGE, NU SE APRINDE. Gardat invers (o clasa pusa doar in timpul
// tranzitiei) ar fi fost o capcana: `animation-name` care revine de la `none`
// la un nume REPORNESTE animatia, deci scoaterea clasei dupa tranzitie ar fi
// jucat exact miscarea pe care o suprima. Aici clasa doar dispare, iar
// animatia primei pagini s-a terminat de mult.
//
// SI E PUSA IN `index.html`, nu aici: asa exista inainte de primul cadru, si
// asa o primeste si `calc.html` — pagina publica a Calculatorului, care
// randeaza aceeasi componenta fara sa incarce vreodata routerul. Pusa din
// modulul asta, /calc ar fi ramas fara sosire si nimic n-ar fi aratat de ce.
// Aici e doar stingerea.
const STEAG_PRIMA = 'prima-incarcare'

// Calea goala dintr-o ruta bruta („/tasks?sfera=personal" -> „/tasks").
const cale = (brut) => ((brut || '/').split('?')[0]) || '/'

function inregistreaza(path) {
  if (typeof document !== 'undefined') {
    document.documentElement.classList.remove(STEAG_PRIMA)
  }
  const pop = _dinInapoi
  // Steagul se consuma AICI, nu in ramura de push: daca tinta pop-ului ar
  // coincide cu ruta curenta (nu se navigheaza nicaieri), un steag ramas ar
  // inghiti in tacere urmatoarea inregistrare adevarata.
  _dinInapoi = false
  if (path === curenta) return
  // O PAGINA NOUA INCEPE DE SUS.
  //
  // `.app-content` NU e container de derulare (intentionat — vezi App.svelte),
  // deci `main.scrollTop = 0`, scris in ascultatorul de `hashchange`, era un
  // no-op de la bun inceput: fereastra e cea care deruleaza. Rezultatul era ca
  // treceai de la o lista lunga, derulata jos, la Calendar — si aterizai in
  // mijlocul lui, fara sa fi derulat nimic.
  //
  // Doar la schimbarea CAII: `?sfera=`, `?zi=` si rescrierile lui `focus.js`
  // schimba interogarea pe aceeasi pagina, iar acolo pozitia e a ta.
  // Sarit fara animatie, fiindca in ramura cu View Transitions apelul e
  // INAUNTRUL callbackului: instantaneul vechi e deja luat, deci saltul cade
  // sub cross-fade si nu se vede. Un `smooth` ar dura peste tranzitie si s-ar
  // vedea pagina noua alunecand singura in sus.
  if (typeof window !== 'undefined' && cale(path) !== cale(curenta)) {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }
  if (!pop) {
    istoric.push(curenta)
    if (istoric.length > ISTORIC_MAX) istoric.shift()
  }
  curenta = path
}

// Un pas inapoi in istoricul aplicatiei. Intoarce `false` cand nu mai e unde —
// atunci apelantul decide ce inseamna „inapoi de pe radacina" (pe Android:
// aplicatia trece in fundal, vezi `main.js`).
export function inapoi() {
  if (istoric.length === 0) return false
  _dinInapoi = true
  navigate(istoric.pop())
  return true
}

const vtSupported = typeof document !== 'undefined' && typeof document.startViewTransition === 'function'
export function viewTransitionsOn() { return vtSupported && !motion.reduced }

function getRaw() {
  const hash = window.location.hash
  return hash.startsWith('#') ? hash.slice(1) : ''
}

function getPath() {
  const raw = getRaw() || '/'
  return raw.split('?')[0] || '/'
}

// Query string carried inside the hash (e.g. #/tasks?focus=global:123). Parsed out
// so route matching still works on the bare path, and exposed as router.query.
function getQuery() {
  const raw = getRaw()
  const qi = raw.indexOf('?')
  if (qi === -1) return {}
  const out = {}
  new URLSearchParams(raw.slice(qi + 1)).forEach((v, k) => { out[k] = v })
  return out
}

function matchRoute(pattern, path) {
  const patternParts = pattern.split('/')
  const pathParts = path.split('/')
  if (patternParts.length !== pathParts.length) return null
  const params = {}
  for (let i = 0; i < patternParts.length; i++) {
    if (patternParts[i].startsWith(':')) {
      params[patternParts[i].slice(1)] = pathParts[i]
    } else if (patternParts[i] !== pathParts[i]) {
      return null
    }
  }
  return params
}

function parseQuery(path) {
  const qi = (path || '').indexOf('?')
  if (qi === -1) return {}
  const out = {}
  new URLSearchParams(path.slice(qi + 1)).forEach((v, k) => { out[k] = v })
  return out
}

// Apply a route synchronously (no animation): updates router state immediately and
// syncs the URL hash. Used inside View-Transition callbacks (so the DOM swap happens
// inside the transition) and as the no-VT fallback.
export function applyPath(path) {
  inregistreaza(path)
  router.path = (path.split('?')[0]) || '/'
  router.query = parseQuery(path)
  const target = '#' + path
  if (window.location.hash !== target) window.location.hash = target
}

// VT-aware navigation: cross-fades the whole view on every route change where the
// browser supports the View Transitions API (progressive enhancement). Falls back
// to an instant apply otherwise / under reduced-motion.
// TRANZITIA SE TERMINA PE PAGINA, NU PE SCHELET.
//
// `startViewTransition` ingheata pagina veche, iar callbackul pornea `import()`
// FARA sa-l astepte: la prima vizita pe o ruta, tranzitia se incheia pe schelet,
// iar pagina adevarata aparea dupa ea, printr-o taietura. Si scheletul e acelasi
// pentru Calendar, Planificator si Calculator — o forma pe care n-o are nicio
// pagina. A doua oara, cu modulul in cache, aceeasi apasare era curata: acelasi
// gest, doua raspunsuri diferite.
//
// App-ul e cel care stie sa incarce ruta (el tine `lazyCache`), deci si-o
// inregistreaza aici. Cursa de 180ms e plafonul: sub el (aproape intotdeauna —
// chunkul e local) tranzitia se termina pe pagina adevarata; peste el ramane
// scheletul, dar tranzitia nu se blocheaza pe o retea moarta.
let preincarcaRuta = null
export function setPreincarcaRuta(fn) { preincarcaRuta = fn }

/** Incalzeste o ruta fara sa navigheze la ea: modulul ei si, daca pagina si-a
 *  exportat `pregateste()`, si datele. Tacuta prin definitie — nimic din ce
 *  face nu se vede pe ecran, deci nici un esec n-are unde sa fie raportat.
 *
 *  Exportata pentru cele cateva drumuri care NU trec prin `use:link`: cardul de
 *  proiect din /projects e un `role="button"` care cheama `navigate()` de mana
 *  (ca sa poata scrie si lista de „recente" inainte). Fara asta, singurul drum
 *  din aplicatie catre o pagina care chiar are ce incarca ar fi ramas fara
 *  preincarcare — adica exact cel mai scump. */
export function preincarca(path) {
  if (!preincarcaRuta) return
  try { Promise.resolve(preincarcaRuta(path)).catch(() => {}) } catch (_) {}
}

const pauza = (ms) => new Promise((r) => setTimeout(r, ms))
// 250, nu 180: de cand `preincarcaRuta` aduce si DATELE, nu doar chunkul,
// plafonul trebuie sa incapa un dus-intors in reteaua locala. Peste el nu se
// asteapta — o retea moarta n-are voie sa blocheze navigarea; atunci ramane
// scheletul paginii, care e exact ce era inainte peste tot.
const PLAFON_INCARCARE = 250
// PE ATINGERE, 100. Intre apasare si primul cadru care se misca nu au voie sa
// treaca mai mult de ~100ms, altfel degetul nu primeste nimic inapoi si gestul
// se citeste ca lag (Ion: „are un delay de la click pana se porneste tranzitia").
// Pe o ruta vazuta deja, preincarcarea se rezolva din cache intr-un tact si nu
// se asteapta nimic; pe una noua, ramane scheletul paginii, care se misca si el.
const PLAFON_ATINGERE = 100
const plafonIncarcare = () =>
  (typeof window !== 'undefined' && window.matchMedia?.('(hover: none)').matches)
    ? PLAFON_ATINGERE : PLAFON_INCARCARE

export function navigate(path) {
  // PREINCARCAREA STA SI AICI, nu doar in actiunea `link`.
  //
  // Jumatate din navigarile aplicatiei cheama `navigate()` de mana: cardul de
  // proiect, banda de perioada din Planificator care duce la `#/calendar?zi=…`,
  // saritura din paleta, drumul inapoi din pagina de proiect. Toate ocoleau
  // `link`, deci si preincarcarea — si tocmai una dintre ele a fost raportata:
  // „daca am o trimitere catre calendar si dau click de pe acasa sau din
  // planificator".
  //
  // Chemat AICI castiga doar cateva zeci de milisecunde (suntem deja in click),
  // dar are un efect care conteaza: pana la `applyPath` cererea e in zbor, deci
  // montarea paginii cade pe ea in loc sa porneasca a doua.
  preincarca(path)

  // ACEEASI PAGINA, ALT FILTRU — NU E O SCHIMBARE DE PAGINA.
  //
  // Ion: „la comutatia dintre taskuri personale si lucru parca se reincarca
  // pagina si se vede asta." Se vedea fiindca ASA ERA: sfera traieste in
  // interogare (`#/tasks?sfera=personal`), comutatorul cheama `navigate`, iar
  // `navigate` pornea o View Transition pe RADACINA — adica pe tot ecranul,
  // antet si continut, pentru o filtrare care nu cere nicio cerere de retea.
  // De la „drumul lat" din 15 august tot ecranul si aluneca 30px, deci reprosul
  // a devenit imposibil de ignorat.
  //
  // Regula: tranzitia de radacina e a RUTEI. Cand calea nu se schimba, ce s-a
  // schimbat e o stare din pagina, iar pagina isi are deja propria miscare
  // pentru ea (in Taskuri: `{#key listaCheie}` cu `alunecare` directionala).
  // Doua animatii peste aceiasi pixeli e exact ce s-a reparat pe 14 august.
  if (cale(path) === router.path) { applyPath(path); return }

  if (!viewTransitionsOn()) { applyPath(path); return }
  try {
    document.startViewTransition(async () => {
      // Inainte de `applyPath`: asa cache-ul e deja cald cand efectul din App
      // citeste noua ruta, deci `LoadedComponent` nu mai trece prin `null`.
      if (preincarcaRuta) {
        try { await Promise.race([preincarcaRuta(path), pauza(plafonIncarcare())]) } catch (_) {}
      }
      applyPath(path)
      await tick()
    })
  } catch (_) {
    applyPath(path)
  }
}

export function link(node) {
  function handleClick(e) {
    if (e.ctrlKey || e.metaKey || e.shiftKey) return
    e.preventDefault()
    const href = node.getAttribute('href')
    if (href) navigate(href)
  }
  // MUNCA INCEPE LA INTENTIE, NU LA CONFIRMARE.
  //
  // Intre clipa in care cursorul intra pe un tab si click trec 100-150ms; intre
  // apasare si ridicarea degetului, inca 80-120. In tot intervalul asta nu se
  // intampla nimic — desi e cam cat dureaza un chunk local plus un dus-intors
  // in reteaua din casa. Preincarcarea muta asteptarea INAINTEA apasarii, unde
  // nu se simte, fiindca inca nu te-ai hotarat.
  //
  // Sta in `link`, nu in Doc: aceeasi actiune e pe fiecare navigare din
  // aplicatie (dock, marca din antet, foaia „Mai mult", drumul inapoi din
  // pagina de proiect), deci toate o primesc dintr-un singur loc.
  //
  // Fara paza proprie: `pointerenter` si `pointerdown` cad amandoua pe aceeasi
  // atingere de deget, iar plimbarea cursorului peste dock trece peste cinci
  // taburi. Cele doua guri le inchide `cache.js` — cererile in zbor se impart,
  // iar fereastra de prospetime taie repetarile.
  function intentie() {
    const href = node.getAttribute('href')
    if (href) preincarca(href)
  }
  node.addEventListener('click', handleClick)
  node.addEventListener('pointerenter', intentie)
  node.addEventListener('pointerdown', intentie)
  return {
    destroy() {
      node.removeEventListener('click', handleClick)
      node.removeEventListener('pointerenter', intentie)
      node.removeEventListener('pointerdown', intentie)
    },
  }
}

export function resolveRoute(routes, caleAnume = null) {
  const path = caleAnume ?? router.path
  for (const [pattern, component] of Object.entries(routes)) {
    const params = matchRoute(pattern, path)
    if (params !== null) return { component, params, pattern }
  }
  return null
}

if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', () => {
    // Schimbarile venite din afara `applyPath` (service worker-ul, la atingerea
    // unei notificari, scrie hash-ul direct — vezi `main.js`) intra si ele in
    // istoric. Dupa un `applyPath`, `curenta` e deja ruta noua, deci apelul e
    // un no-op — nu se dubleaza.
    inregistreaza(getRaw() || '/')
    router.path = getPath()
    router.query = getQuery()
    // Derularea o duce `inregistreaza` (pe fereastra, care e scrollerul real).
    // Aici ramane doar mutarea focusului, pentru cititoarele de ecran si pentru
    // ca tastatura sa continue din pagina noua, nu din dockul apasat.
    document.getElementById('main-content')?.focus({ preventScroll: true })
  })
}
