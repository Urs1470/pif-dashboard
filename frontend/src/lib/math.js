// KaTeX math rendering for user-entered rich text (observatii, task notes).
// Bundled (not CDN): the woff2 fonts ship under static/dist/assets and are
// served same-origin, so the existing `font-src 'self'` CSP covers them.
import renderMathInElement from 'katex/contrib/auto-render'
import 'katex/contrib/mhchem' // adds \ce{...} chemistry support ("alt tip")
import 'katex/dist/katex.min.css'

const DELIMITERS = [
  { left: '$$', right: '$$', display: true },
  { left: '\\[', right: '\\]', display: true },
  { left: '\\(', right: '\\)', display: false },
  { left: '$', right: '$', display: false },
]

// Typeset any $...$, $$...$$, \(...\), \[...\] inside an already-rendered DOM node.
// Safe to call on any element; never throws (bad formulas render in red, inline).
export function renderMath(el) {
  if (!el) return
  try {
    renderMathInElement(el, {
      delimiters: DELIMITERS,
      throwOnError: false,
      ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
    })
  } catch (_) { /* never break the view over a math typo */ }
}
