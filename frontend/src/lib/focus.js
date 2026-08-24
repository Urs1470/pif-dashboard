// Cross-page "focus this item": the focus request lives in the URL (?focus inside
// the hash, e.g. #/tasks?focus=global:123) so it is shareable and reload-safe. On
// the destination page the matching row scrolls itself to the center of the
// viewport and flashes a highlight, then the param is consumed.

import { router, navigate } from './router.svelte.js'
import { motion } from './motion.svelte.js'

export function focusKey(kind, id) {
  return `${kind}:${id}`
}

export function focusHref(path, kind, id) {
  // Calea poate avea deja un query (#/tasks?sfera=personal) — un al doilea `?`
  // ar face getQuery sa citeasca `sfera = 'personal?focus=...'`.
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}focus=${encodeURIComponent(focusKey(kind, id))}`
}

/**
 * Deschide un element in pagina lui si il aduce in centru cu un semn (hasura).
 *
 * AICI A FOST UN MORPH, si l-am scos pe 2026-08-24 fiindca nu functiona.
 * Ideea era ca elementul apasat sa „devina" randul-tinta printr-o tranzitie cu
 * element partajat (View Transitions, `focus-morph`). Masurat in Chromium real,
 * pe desktop:
 *   - callbackul `startViewTransition` tinea ecranul INGHETAT ~657ms de fiecare
 *     data (chiar peste plafonul de 600ms), la ORICE tinta — si pagina de proiect
 *     (grea), si /tasks (usoara), si la revizit cald;
 *   - la sfarsitul callbackului NICIUN element nu avea `focus-morph`, deci morph-ul
 *     nu avea nici macar ce anima: `applyPath` demonteaza pagina veche INAUNTRUL
 *     callbackului (sursa dispare), iar randul-tinta se eticheteaza abia intr-un
 *     `requestAnimationFrame` care nu se declanseaza cat timp VT-ul tine pagina
 *     inghetata — deci pierde mereu cursa cu plafonul.
 * Rezultatul real nu era un morph, ci ~650ms de ecran inghetat urmate de o
 * taietura. Aceeasi senzatie pe care Ion a reclamat-o pe telefon („nu s-a
 * intamplat nimic"), unde morph-ul fusese deja sarit — doar ca pe desktop
 * ramasese. Ion, 2026-08-24: „taskul din acasa la pagina sursa a taskului trebuie
 * o tranzitie mai rapida."
 *
 * Acum face exact ce facea deja ramura de atingere, peste tot: navigare simpla.
 * Pagina-tinta soseste cu propria ei intrare animata (`.ruta-in` + `.cell-in`,
 * vezi `global.css`), iar `focusOnLand` aduce randul in centru INSTANT si il
 * hasureaza — asa stii pe ce ai apasat. Fara niciun cadru inghetat.
 */
export function focusNavigate(_sourceEl, path, kind, id) {
  navigate(focusHref(path, kind, id))
}

// CINE ASTEAPTA O ATERIZARE. Actiunea isi verifica cheia la montare si la
// schimbarea ei — dar nu si cand se schimba `router.query.focus` sub un rand deja
// montat. Asta se intampla exact la CREARE: randul nou apare, si abia dupa aia
// stim ce id are. Fara lista asta, semnul ar functiona doar cand vii dintr-o
// navigare, nu cand tocmai ai facut lucrul.
const asteptatori = new Set()

/** Aprinde semnul pe randul cu cheia data, fara sa navigheze nicaieri.
 *  Pentru cazurile in care aterizarea nu vine dintr-un drum, ci dintr-o fapta:
 *  ai creat un task si trebuie sa vezi UNDE a cazut. */
export function marcheazaAterizarea(kind, id) {
  if (!id) return
  router.query = { ...router.query, focus: focusKey(kind, id) }
  for (const f of [...asteptatori]) {
    try { f() } catch (_) {}
  }
}

// Svelte action: use:focusOnLand={focusKey(...)} on the destination row.
export function focusOnLand(node, key) {
  function maybe() {
    if (!key || router.query.focus !== key) return

    // CHEIA SE CONSUMA CAND SE SI FOLOSESTE, NU CAND SE GASESTE.
    //
    // Aici statea, tacut, motivul pentru care „nu toate trimiterile de pe Acasa
    // hasureaza" (Ion, 2026-08-21). Consumarea se facea AICI, la montarea
    // randului, iar hasura se punea abia in `requestAnimationFrame` — un cadru
    // mai tarziu. Intre cele doua, lista se re-randeaza: randurile sunt cheiate
    // pe `t.id`, dar sunt GRUPATE, iar cand datele proaspete muta un task dintr-o
    // grupa in alta, blocul lui e desfacut si refacut. Nodul vechi ramane
    // detasat, clasa i se pune lui — invizibila — iar nodul NOU nu mai are ce
    // potrivi, fiindca `?focus=` disparuse deja din URL.
    //
    // Masurat pe telefon (390x844): `classList.add('focus-flash')` chemat la
    // 82ms, `.focus-flash` niciodata prezent in document, esantionat la 8ms timp
    // de 2,5 secunde. De-aia mergea uneori — cand datele erau deja calde si lista
    // nu se mai re-randa, nodul supravietuia cadrului.
    //
    // Acum se consuma in cadrul urmator, si DOAR daca nodul mai e in pagina.
    // Daca a fost inlocuit, `?focus=` ramane in URL si randul nou il gaseste.
    const consuma = () => {
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
    }

    requestAnimationFrame(() => {
      // Nodul poate fi INLOCUIT intre montare si cadrul asta (vezi nota de mai
      // sus). Atunci nu se consuma si nu se marcheaza nimic: randul care ii ia
      // locul gaseste `?focus=` intact si isi face el aterizarea.
      if (!node.isConnected) return
      consuma()
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

      if (needsScroll) {
        // INSTANT, NU `smooth`. Derularea lina adauga ~400ms DUPA ce pagina a
        // sosit: randul aluneca spre centru cat timp tu deja te uiti la lista, si
        // exact asta se citeste ca „lent, intarziat" (Ion, 2026-08-21). Cu `auto`
        // pagina SOSESTE cu randul deja in centru — zero asteptare, iar semnalul
        // „pe asta ai apasat" il da inelul care pulseaza.
        try { node.scrollIntoView({ behavior: 'auto', block: 'center' }) } catch (_) { node.scrollIntoView() }
      }

      // HASURA PORNESTE IMEDIAT (`hasuraRand`, global.css): fara decalaj — Ion a
      // citit orice asteptare drept lag. 1800: animatia de 1600 plus o rasuflare.
      node.classList.add('focus-flash')
      setTimeout(() => node.classList.remove('focus-flash'), motion.reduced ? 3200 : 1800)
    })
  }
  maybe()
  asteptatori.add(maybe)
  return {
    update(newKey) { key = newKey; maybe() },
    destroy() { asteptatori.delete(maybe) },
  }
}
