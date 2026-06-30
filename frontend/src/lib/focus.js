// Cross-page "focus this item" — the focus request lives in the URL (a ?focus=
// param inside the hash, e.g. #/tasks?focus=global:123), so it is shareable and
// reload-safe. The matching row on the destination page scrolls itself to the
// center of the viewport and flashes a highlight, then the param is consumed.
// Dashboard-wide pattern for deep-linking to a specific item.

import { router } from './router.svelte.js'

const reduceMotion = typeof window !== 'undefined'
  && (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false)

// Stable key. kind: 'global' (global task) | 'task' (project task) | etc.
export function focusKey(kind, id) {
  return `${kind}:${id}`
}

// Build a navigate() target carrying the focus request in the URL.
// focusHref('/tasks', 'global', id) -> '/tasks?focus=global%3A<id>'
export function focusHref(path, kind, id) {
  return `${path}?focus=${encodeURIComponent(focusKey(kind, id))}`
}

// Svelte action: use:focusOnLand={focusKey(...)}. When the URL's ?focus matches
// this element's key, scroll it into the center (smooth, unless already visible)
// and flash a highlight — then strip ?focus so re-renders don't re-fire.
export function focusOnLand(node, key) {
  function maybe() {
    if (!key || router.query.focus !== key) return
    // Consume: drop ?focus from the URL without navigating, and from router state.
    try { history.replaceState(null, '', '#' + router.path) } catch (_) {}
    router.query = { ...router.query, focus: undefined }
    // Defer a frame so layout has settled (data just rendered).
    requestAnimationFrame(() => {
      // Keep the sticky header from covering the target when it lands near the top.
      node.style.scrollMarginTop = 'calc(var(--header-height) + var(--space-md))'
      node.style.scrollMarginBottom = 'var(--space-md)'
      // Skip the scroll if it's already fully on screen — no pointless jump.
      const r = node.getBoundingClientRect()
      const vh = window.innerHeight || document.documentElement.clientHeight
      if (r.top < 0 || r.bottom > vh) {
        try {
          node.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
        } catch (_) {
          node.scrollIntoView()
        }
      }
      node.classList.add('focus-flash')
      const clear = () => node.classList.remove('focus-flash')
      node.addEventListener('animationend', clear, { once: true })
      setTimeout(clear, 1700) // safety net (reduced-motion has no animationend)
    })
  }
  maybe()
  return {
    update(newKey) { key = newKey; maybe() },
  }
}
