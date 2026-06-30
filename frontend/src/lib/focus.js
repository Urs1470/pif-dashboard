// Cross-page "focus this item" — set a key before navigating, and the matching
// row on the destination page scrolls itself to the center of the scroll area and
// flashes a highlight. Dashboard-wide pattern for deep-linking to a specific item
// (e.g. clicking a task on Home jumps to it on /tasks or the project page).

let pendingKey = null

const reduceMotion = typeof window !== 'undefined'
  && (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false)

// Build a stable key. kind: 'global' (global task) | 'task' (project task) | etc.
export function focusKey(kind, id) {
  return `${kind}:${id}`
}

// Call right before navigate(); the destination consumes it on mount.
export function requestFocus(key) {
  pendingKey = key
}

// Svelte action: use:focusOnLand={focusKey(...)}. When this element's key matches
// the pending focus request, scroll it to center (smooth) and flash a highlight,
// then consume the request so it only fires once.
export function focusOnLand(node, key) {
  function maybe() {
    if (!key || pendingKey !== key) return
    pendingKey = null
    // Defer one frame so layout has settled (data just rendered + the router's
    // scroll-to-top has already run) — otherwise the centering is off.
    requestAnimationFrame(() => {
      try {
        node.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
      } catch (_) {
        node.scrollIntoView()
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
