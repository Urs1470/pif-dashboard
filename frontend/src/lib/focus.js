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
  // PE TELEFON NU EXISTA MORPH. Tranzitia cu element partajat INGHEATA ecranul
  // pana cand pagina-tinta si-a montat randul — masurat: 744ms fara niciun cadru
  // dupa atingerea unui task de pe „Astăzi" — si abia apoi joaca o alunecare de
  // 300ms. Pe desktop, cu datele in cache si mouse-ul deja pe rand, e invizibil;
  // cu degetul, prin tunel, e exact senzatia de „nu s-a intamplat nimic". Ion:
  // „tranzitia de pe taskurile de acasa trebuie rafinata." Pe atingere se
  // navigheaza ca oriunde (alunecarea de ruta), iar aterizarea face restul:
  // randul vine in centru si se HASUREAZA (vezi `focusOnLand`).
  const atingere = typeof window !== 'undefined' && window.matchMedia?.('(hover: none)').matches
  if (!sourceEl || !viewTransitionsOn() || atingere) { navigate(href); return }

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
      // „LA VEDERE" INSEAMNA INTRE ANTET SI DOCK, nu oriunde in fereastra. Randul
      // tinta cadea la 780px pe un ecran de 844 — „in fereastra", deci fara
      // derulare — adica sub dock si sub butonul plutitor. Pe telefon zona
      // vizibila se termina deasupra dockului; antetul lipicios o incepe mai jos.
      const stil = getComputedStyle(document.documentElement)
      const sus = parseFloat(stil.getPropertyValue('--header-height')) || 0
      const dock = document.querySelector('.dock')
      const jos = dock && dock.getBoundingClientRect().height && getComputedStyle(dock).position === 'fixed'
        ? dock.getBoundingClientRect().top - 8 : vh
      const needsScroll = r.top < sus || r.bottom > jos

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

      // HASURA PORNESTE DUPA CE DERULAREA S-A ASEZAT, nu in timpul ei: o
      // evidentiere care ruleaza cat timp lista inca se misca se pierde —
      // ochiul urmareste miscarea, nu culoarea. Cu derulare lina, ~320ms.
      const porneste = () => {
        node.classList.add('focus-flash')
        const clear = () => node.classList.remove('focus-flash')
        node.addEventListener('animationend', clear, { once: true })
        setTimeout(clear, 2400)
      }
      if (needsScroll && !morphing && !motion.reduced) setTimeout(porneste, 320)
      else porneste()
    })
  }
  maybe()
  return {
    update(newKey) { key = newKey; maybe() },
  }
}
