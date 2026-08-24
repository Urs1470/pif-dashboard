// ===== CAT S-A DERULAT, CA VALOARE PENTRU CSS =====
//
// DE CE EXISTA. Sticla de pe barele de navigatie e translucida tocmai fiindca
// continutul trece pe dedesubt — dar pana acum ea nu STIA daca trece ceva sau nu.
// Arata identic pe o pagina scurta, unde n-are ce acoperi, si pe una lunga, unde
// stă peste text in mișcare.
//
// Apple face doua lucruri exact aici, si le numeste (WWDC25 „Meet Liquid Glass"):
//   „As text scrolls underneath, shadows become more prominent to create
//    additional separation."
//   „As content begins to scroll underneath a glass element, the effect gently
//    dissolves the content into the background, lifting the glass visually above
//    the moving content, and allowing floating elements like titles to always
//    remain legible."
// Amandoua au nevoie de un singur numar: cat s-a derulat. De aici iese.
//
// DOUA VARIABILE, fiindca sunt doua muchii:
//   --derulat      0..1 pe primii `PRAG` px de la varf. Muchia de SUS: bara sau
//                  antetul chiar au ceva pe dedesubt.
//   --derulat-jos  0 sau 1 — mai e continut sub pliu? Muchia de JOS, a dockului
//                  plutitor: la capatul listei n-are ce sa acopere, deci umbra si
//                  voalul se sting si dockul se aseaza pe pagina.
//
// SCRIE PE `<html>`, ca `--dock-h` si `--kb`: doua bare si doua muchii citesc
// aceleasi valori, iar o stare reactiva scrisa la fiecare cadru de derulare ar
// pune tot arborele pe drumul de reactualizare degeaba.
//
// COALESCENT PE CADRU. `scroll` se trimite mai des decat se deseneaza; fara
// `requestAnimationFrame` s-ar scrie de doua-trei ori pentru acelasi cadru.

// Cat de repede se aprinde muchia de sus. 24px = cam un rand de text: sub atat
// n-ai derulat, ai tremurat.
const PRAG = 24
// Marja de la capatul de jos sub care consideram ca AI AJUNS. Fara ea, o pagina a
// carei inaltime nu e un numar intreg de pixeli n-ar ajunge niciodata la 0.
const MARJA_JOS = 4

let pornit = false
let cerere = 0
let ultimSus = -1
let ultimJos = -1

function scrie() {
  cerere = 0
  const y = window.scrollY || document.documentElement.scrollTop || 0
  const sus = Math.min(1, Math.max(0, y / PRAG))
  const inalt = document.documentElement.scrollHeight
  const jos = y + window.innerHeight < inalt - MARJA_JOS ? 1 : 0
  const s = document.documentElement.style
  // Se scrie doar la SCHIMBARE, si rotunjit: la trei zecimale ochiul nu vede
  // diferenta, iar CSS-ul nu se mai recalculeaza pentru nimic.
  const susR = Math.round(sus * 1000) / 1000
  if (susR !== ultimSus) { s.setProperty('--derulat', String(susR)); ultimSus = susR }
  if (jos !== ultimJos) { s.setProperty('--derulat-jos', String(jos)); ultimJos = jos }
}

function cere() {
  if (!cerere) cerere = requestAnimationFrame(scrie)
}

/** Se cheama O DATA, din App. Intoarce functia de oprire. */
export function urmaresteDerularea() {
  if (pornit || typeof window === 'undefined') return () => {}
  pornit = true
  scrie()
  window.addEventListener('scroll', cere, { passive: true })
  window.addEventListener('resize', cere, { passive: true })
  // Inaltimea paginii se schimba si FARA derulare sau redimensionare: un rand
  // bifat pleaca din lista, o foaie se deschide, un grup se desface. Fara asta,
  // `--derulat-jos` ar rămâne pe valoarea de la ultima derulare.
  const ro = new ResizeObserver(cere)
  ro.observe(document.documentElement)
  return () => {
    window.removeEventListener('scroll', cere)
    window.removeEventListener('resize', cere)
    ro.disconnect()
    if (cerere) cancelAnimationFrame(cerere)
    cerere = 0
    pornit = false
  }
}
