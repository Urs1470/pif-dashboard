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

function inregistreaza(path) {
  const pop = _dinInapoi
  // Steagul se consuma AICI, nu in ramura de push: daca tinta pop-ului ar
  // coincide cu ruta curenta (nu se navigheaza nicaieri), un steag ramas ar
  // inghiti in tacere urmatoarea inregistrare adevarata.
  _dinInapoi = false
  if (path === curenta) return
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

const pauza = (ms) => new Promise((r) => setTimeout(r, ms))
const PLAFON_INCARCARE = 180

export function navigate(path) {
  if (!viewTransitionsOn()) { applyPath(path); return }
  try {
    document.startViewTransition(async () => {
      // Inainte de `applyPath`: asa cache-ul e deja cald cand efectul din App
      // citeste noua ruta, deci `LoadedComponent` nu mai trece prin `null`.
      if (preincarcaRuta) {
        try { await Promise.race([preincarcaRuta(path), pauza(PLAFON_INCARCARE)]) } catch (_) {}
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
  node.addEventListener('click', handleClick)
  return { destroy() { node.removeEventListener('click', handleClick) } }
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
    const main = document.getElementById('main-content')
    if (main) { main.scrollTop = 0; main.focus({ preventScroll: true }) }
  })
}
