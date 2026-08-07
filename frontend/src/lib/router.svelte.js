import { tick } from 'svelte'
import { motion } from './motion.svelte.js'

export const router = $state({ path: getPath(), query: getQuery(), params: {} })

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
    router.path = getPath()
    router.query = getQuery()
    const main = document.getElementById('main-content')
    if (main) { main.scrollTop = 0; main.focus({ preventScroll: true }) }
  })
}
