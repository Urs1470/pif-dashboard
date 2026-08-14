// KaTeX pentru textul bogat scris de utilizator (observatii, notite de task).
// Impachetat, nu de pe CDN: fonturile woff2 ajung in static/dist/assets si se
// servesc de pe acelasi origin, deci `font-src 'self'` din CSP le acopera.
//
// KATEX SE INCARCA DOAR CAND EXISTA MATEMATICA — si asta a fost cea mai scumpa
// linie din aplicatie.
//
// Fisierul asta il importa `RichText` si `MarkdownView`, adica ORICE loc care
// AFISEAZA text scris de utilizator. Prin ele, cele 257 KB de KaTeX (plus 29 KB
// de CSS si fonturile lui) intrau in bundle-ul principal si in chunkul paginii
// de taskuri. Masurat la prima deschidere pe telefon (4G, procesor incetinit de
// patru ori): KaTeX termina de descarcat la 1623ms si tinea banda ocupata exact
// cat timp venea chunkul paginii — ca sa afiseze o lista de to-do-uri in care
// nu exista nicio formula.
//
// Iar cazul comun nu e „nota fara formule", e „nota fara formule aproape
// intotdeauna": matematica traieste in observatiile de proiect, nu in taskuri.
// Deci verificarea se face pe TEXT, inainte de orice cerere: fara delimitatori
// nu e nimic de compus, deci nu e nimic de descarcat.

const DELIMITERS = [
  { left: '$$', right: '$$', display: true },
  { left: '\\[', right: '\\]', display: true },
  { left: '\\(', right: '\\)', display: false },
  { left: '$', right: '$', display: false },
]

// Aceiasi delimitatori ca mai sus, ca tipar. Deliberat LARG: o potrivire falsa
// costa o incarcare degeaba, una ratata lasa o formula nerandata pe ecran —
// deci pragul se pune in partea care doar incetineste, nu in cea care strica.
// `\ce{` e prins separat: mhchem se scrie tot intre delimitatori, dar tiparul
// il face vizibil in cod, langa motivul pentru care mhchem e incarcat.
const ARE_MATEMATICA = /\$|\\\(|\\\[|\\ce\{/

let cerere = null
function adu() {
  if (!cerere) {
    cerere = Promise.all([
      import('katex/contrib/auto-render'),
      import('katex/contrib/mhchem'),   // suport \ce{...} pentru chimie
      import('katex/dist/katex.min.css'),
    ])
      .then(([m]) => m.default)
      // O incarcare picata nu se tine minte: urmatoarea nota cu formule are voie
      // sa incerce din nou, in loc sa ramana necompusa pana la reincarcarea paginii.
      .catch((e) => { cerere = null; throw e })
  }
  return cerere
}

/** Compune orice $...$, $$...$$, \(...\), \[...\] dintr-un nod deja randat.
 *  Sigur pe orice element; nu arunca niciodata (formulele gresite se deseneaza
 *  rosu, inline).
 *
 *  ASINCRONA DE ACUM. Compunerea se intampla la un tick dupa randare, si numai
 *  pe textele care chiar au formule — apelantii n-au nevoie sa astepte, fiindca
 *  niciunul nu masoara nodul imediat dupa. */
export function renderMath(el) {
  if (!el) return
  if (!ARE_MATEMATICA.test(el.textContent || '')) return
  adu()
    .then((renderMathInElement) => {
      // Nodul poate fi deja scos din pagina cat timp se incarca modulul.
      if (!el.isConnected) return
      renderMathInElement(el, {
        delimiters: DELIMITERS,
        throwOnError: false,
        ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
      })
    })
    .catch(() => { /* niciodata nu stricam vederea pentru o greseala de formula */ })
}
