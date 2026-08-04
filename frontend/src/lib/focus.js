// Cross-page "focus this item": the focus request lives in the URL (?focus inside
// the hash, e.g. #/tasks?focus=global:123) so it is shareable and reload-safe. On
// the destination page the matching row scrolls itself to the center of the
// viewport and flashes a highlight, then the param is consumed.
//
// morphNavigate() additionally runs a View-Transitions shared-element morph: the
// clicked card visually "becomes" the destination row (progressive enhancement —
// falls back to a plain navigate when the API is unavailable or reduced-motion).

import { tick } from 'svelte'
import { router, applyPath, navigate, viewTransitionsOn } from './router.svelte.js'
import { motion } from './motion.svelte.js'

const VT_NAME = 'focus-morph'
let morphPending = null // { key, resolve } while a morph is in flight

export function focusKey(kind, id) {
  return `${kind}:${id}`
}

export function focusHref(path, kind, id) {
  // Calea poate avea deja un query (#/tasks?sfera=personal) — un al doilea `?`
  // ar face getQuery sa citeasca `sfera = 'personal?focus=...'`.
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}focus=${encodeURIComponent(focusKey(kind, id))}`
}

// Navigate to a task and morph the clicked element into the destination row.
export function morphNavigate(sourceEl, path, kind, id) {
  const href = focusHref(path, kind, id)
  if (!sourceEl || !viewTransitionsOn()) { navigate(href); return }

  sourceEl.style.viewTransitionName = VT_NAME
  let resolveReady
  const ready = new Promise((res) => { resolveReady = res })
  morphPending = { key: focusKey(kind, id), resolve: resolveReady }

  let vt
  try {
    vt = document.startViewTransition(async () => {
      applyPath(href)
      await tick()
      // Wait for the destination row to mount + tag itself, but never freeze the
      // screen for long if the page is slow (fall through after 600ms).
      await Promise.race([ready, new Promise((r) => setTimeout(r, 600))])
      await tick()
    })
  } catch (_) {
    sourceEl.style.viewTransitionName = ''
    morphPending = null
    applyPath(href)
    return
  }
  const cleanup = () => {
    try { sourceEl.style.viewTransitionName = '' } catch (_) {}
    morphPending = null
  }
  vt.finished.then(cleanup, cleanup)
}

// Svelte action: use:focusOnLand={focusKey(...)} on the destination row.
export function focusOnLand(node, key) {
  function maybe() {
    if (!key || router.query.focus !== key) return
    // Consume: drop ?focus from the URL (no navigation) so re-renders don't re-fire.
    // DOAR focus — restul query-ului (ex. sfera=personal) ramane in URL, altfel
    // un refresh dupa aterizare ar schimba vederea.
    try {
      const rest = Object.entries(router.query)
        .filter(([k, v]) => k !== 'focus' && v != null && v !== '')
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join('&')
      history.replaceState(null, '', '#' + router.path + (rest ? '?' + rest : ''))
    } catch (_) {}
    router.query = { ...router.query, focus: undefined }

    const morphing = !!(morphPending && morphPending.key === key)
    const releaseMorph = morphing ? morphPending.resolve : null

    requestAnimationFrame(() => {
      // Keep the sticky header from covering the target near the top.
      node.style.scrollMarginTop = 'calc(var(--header-height) + var(--space-md))'
      node.style.scrollMarginBottom = 'var(--space-md)'
      const r = node.getBoundingClientRect()
      const vh = window.innerHeight || document.documentElement.clientHeight
      const needsScroll = r.top < 0 || r.bottom > vh

      if (morphing) {
        // Land at the final position INSTANTLY so the morph animates the card to
        // exactly where the row ends up; then tag the row + release the transition.
        if (needsScroll) {
          try { node.scrollIntoView({ behavior: 'auto', block: 'center' }) } catch (_) { node.scrollIntoView() }
        }
        node.style.viewTransitionName = VT_NAME
        setTimeout(() => { try { node.style.viewTransitionName = '' } catch (_) {} }, 800)
        releaseMorph?.()
      } else if (needsScroll) {
        try { node.scrollIntoView({ behavior: motion.reduced ? 'auto' : 'smooth', block: 'center' }) } catch (_) { node.scrollIntoView() }
      }

      node.classList.add('focus-flash')
      const clear = () => node.classList.remove('focus-flash')
      node.addEventListener('animationend', clear, { once: true })
      setTimeout(clear, 1700)
    })
  }
  maybe()
  return {
    update(newKey) { key = newKey; maybe() },
  }
}
