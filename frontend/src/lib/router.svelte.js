import { tick } from 'svelte'

export const router = $state({ path: getPath(), query: getQuery(), params: {} })

const reduceMotion = typeof window !== 'undefined'
  && (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false)

const vtSupported = typeof document !== 'undefined' && typeof document.startViewTransition === 'function'
export function viewTransitionsOn() { return vtSupported && !reduceMotion }

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
export function navigate(path) {
  if (!viewTransitionsOn()) { applyPath(path); return }
  try {
    document.startViewTransition(async () => { applyPath(path); await tick() })
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

export function resolveRoute(routes) {
  const path = router.path
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
