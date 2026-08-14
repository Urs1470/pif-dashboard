import { apiJson } from './api.js'

// CE A VAZUT PAGINA ULTIMA DATA, TINUT IN AFARA PAGINII.
//
// `{#key routeKey}` din App distruge blocul de continut la fiecare schimbare de
// ruta, deci orice `$state` din componenta moare cu ea. Paginile care isi tin
// datele in store la nivel de modul (Planificator, /projects, /tasks) traiesc
// bine cu asta: revii pe tab si vezi instant ce era, iar scheletul e gardat pe
// „nu am nimic de aratat". Cele care si le tin in componenta — Calendar,
// pagina de proiect, Departament — porneau de la zero SI PUNEAU SCHELET LA
// FIECARE INTRARE, nu doar la prima.
//
// Trei pagini din sapte cu un comportament, patru cu altul: aceeasi apasare,
// doua raspunsuri. Fisierul asta il face pe al doilea universal, fara sa ceara
// fiecarei pagini sa-si mute starea intr-un store propriu — cheia e URL-ul,
// deci merge la fel si cand raspunsul depinde de o luna, de un orizont sau de
// un id.
//
// NU e o memorie care inlocuieste cererea. E memoria care tine ecranul plin cat
// timp cererea se face oricum (stale-while-revalidate): `dinCache` da SINCRON
// ultimul raspuns, `preia` il improspateaza intotdeauna.

const intrari = new Map()   // url -> { date, cand }
const inZbor = new Map()    // url -> Promise, ca doua cereri simultane sa fie una

// Cat tinem. O sesiune deschisa toata ziua trece prin zeci de luni de calendar
// si de proiecte; fara plafon, harta creste cat tine sesiunea. `Map` pastreaza
// ordinea inserarii, deci prima cheie e cea mai veche.
const MAX = 40

function scrie(url, date) {
  if (intrari.has(url)) intrari.delete(url)   // re-inserat = redevine cel mai nou
  intrari.set(url, { date, cand: Date.now() })
  while (intrari.size > MAX) intrari.delete(intrari.keys().next().value)
}

/** Ce stim ACUM despre URL-ul asta, fara sa asteptam nimic.
 *  `undefined` inseamna „n-am vazut niciodata", si e diferit de `null`, care
 *  poate fi un raspuns valid al serverului. */
export function dinCache(url) {
  const i = intrari.get(url)
  return i ? i.date : undefined
}

/**
 * Aduce URL-ul si tine minte raspunsul.
 *
 * `proaspat` e singurul parametru, si separa cele doua chemari:
 *   0    — pagina care se monteaza. Cere INTOTDEAUNA de la server; cache-ul a
 *          umplut deja ecranul, iar cererea il corecteaza.
 *   >0   — preincarcarea de la hover. Daca raspunsul e mai nou de atat, nu mai
 *          intreaba: altfel trecerea cursorului peste dock ar trage o cerere la
 *          fiecare intrare, si sunt cinci taburi unul langa altul.
 *
 * Cererile in zbor se impart: preincarcarea de la hover si montarea de dupa
 * click cad pe aceeasi promisiune, deci clicul nu porneste a doua cerere.
 */
export function preia(url, { proaspat = 0 } = {}) {
  if (proaspat > 0) {
    const i = intrari.get(url)
    if (i && Date.now() - i.cand < proaspat) return Promise.resolve(i.date)
  }
  const z = inZbor.get(url)
  if (z) return z

  const p = apiJson(url)
    .then((date) => { inZbor.delete(url); scrie(url, date); return date })
    .catch((e) => { inZbor.delete(url); throw e })
  inZbor.set(url, p)
  return p
}

/** Uita ce stim despre URL-urile care incep cu prefixul dat.
 *  Se cheama dupa o scriere care schimba un raspuns pe care nu-l reincarca
 *  nimeni imediat. Cererile in zbor NU se anuleaza: ele sunt deja pe drum si
 *  aduc starea de dupa scriere. */
export function uita(prefix) {
  for (const url of [...intrari.keys()]) {
    if (url.startsWith(prefix)) intrari.delete(url)
  }
}
