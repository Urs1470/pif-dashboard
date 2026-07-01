// Shared motion tokens (mirrors tokens.css --dur-fast/base/slow, duplicated here since
// CSS custom properties can't be read as numbers into svelte/transition params) and a
// single reactive prefers-reduced-motion source, so every component gets a live update
// if the OS-level preference changes mid-session instead of reading matchMedia() once.
export const DUR_FAST = 120
export const DUR_BASE = 200
export const DUR_SLOW = 320

function readReducedMotion() {
  return typeof window !== 'undefined'
    && (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false)
}

export const motion = $state({ reduced: readReducedMotion() })

if (typeof window !== 'undefined' && window.matchMedia) {
  window.matchMedia('(prefers-reduced-motion: reduce)')
    .addEventListener?.('change', (e) => { motion.reduced = e.matches })
}

// Zeroes out a duration when the user prefers reduced motion.
export function motionDuration(ms) {
  return motion.reduced ? 0 : ms
}
