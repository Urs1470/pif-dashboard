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
// Creste la fiecare `uita`. Un raspuns venit dintr-o generatie trecuta se
// intoarce apelantului, dar nu se mai scrie in memorie — vezi `preia`.
let generatie = 0

// Cat tinem. O sesiune deschisa toata ziua trece prin zeci de luni de calendar
// si de proiecte; fara plafon, harta creste cat tine sesiunea. `Map` pastreaza
// ordinea inserarii, deci prima cheie e cea mai veche.
const MAX = 40

// ===================== MEMORIA SUPRAVIETUIESTE REPORNIRII =====================
//
// Ion, dupa trei runde de reparat schimbarea de tab: „la pornirea paginilor, mai
// ales se vede la calendar, apare un schelet si dupa foarte rapid apare pagina",
// si „daca am o trimitere catre calendar si dau click de pe acasa sau din
// planificator".
//
// Toate reparatiile de pana aici ajutau doar cand raspunsul era DEJA in memoria
// filei. Patru drumuri il ocoleau, si el le nimerise pe toate:
//   - deschiderea aplicatiei (pe Android se deschide pe ultima ruta);
//   - un F5;
//   - `navigate()` chemat de mana, din afara actiunii `link`;
//   - o trimitere cu parametru (`#/calendar?zi=…`), care e alt URL.
// In toate patru memoria filei e goala, deci se vede asteptarea.
//
// Solutia profesionala pentru clasa asta e „local-first": service worker-ul a
// mutat APLICATIA pe telefon, iar asta muta DATELE. Cache-ul se hidrateaza
// SINCRON din disc la incarcarea modulului, deci `dinCache` raspunde inainte de
// primul cadru — pe orice ruta vazuta vreodata, oricat de rece ar fi pornirea.
//
// Trei lucruri de respectat, si toate trei sunt scrise mai jos:
//  1. `localStorage`, nu IndexedDB: e SINCRON. IndexedDB e asincron, deci n-ar
//     fi gata la primul cadru — exact lucrul pentru care exista fisierul asta.
//     Pretul e ca scrierea blocheaza firul principal, deci se scrie AMANAT si
//     plafonat (vezi `CAT_INCAPE`).
//  2. Se VERSIONEAZA. Un raspuns vechi are alta forma dupa o schimbare de API,
//     iar o pagina care se deseneaza din date de alta forma crapa la rulare, nu
//     la build. Cheia poarta versiunea; ce nu se potriveste se arunca.
//  3. Datele restaurate NU opresc improspatarea. `preia` cere oricum de la
//     server (prospetime 0 la montare) — cache-ul umple ecranul, reteaua il
//     corecteaza.
const CHEIE = 'pif-cache-v1'
// Sub 2-3 MB, cat recomanda toata lumea pentru un cache sincron. Aici nici nu
// se pune problema: raspunsurile aplicatiei sunt liste de zeci de randuri.
const CAT_INCAPE = 600 * 1024
// Ce e mai vechi de atat nu se mai restaureaza. Nu de dragul prospetimii —
// improspatarea se face oricum — ci ca sa nu deschizi aplicatia dupa o luna si
// sa vezi o clipa calendarul lunii trecute inainte sa se corecteze.
const CAT_TINE = 7 * 24 * 3600 * 1000

let deScris = 0
function programeazaScrierea() {
  if (deScris || typeof window === 'undefined') return
  // Amanat pe rand liber: `localStorage.setItem` serializeaza si scrie pe disc
  // sincron, iar asta n-are ce cauta in cadrul in care tocmai a sosit un raspuns.
  const cere = window.requestIdleCallback || ((f) => setTimeout(f, 400))
  deScris = cere(() => { deScris = 0; salveaza() }, { timeout: 3000 })
}

function salveaza() {
  try {
    const obiect = {}
    let octeti = 0
    // De la cel mai NOU spre cel mai vechi, ca plafonul sa taie coada, nu capul.
    for (const [url, i] of [...intrari.entries()].reverse()) {
      const bucata = JSON.stringify(i)
      octeti += bucata.length + url.length
      if (octeti > CAT_INCAPE) break
      obiect[url] = i
    }
    localStorage.setItem(CHEIE, JSON.stringify(obiect))
  } catch (_) {
    // Cota plina sau modul privat: memoria filei ramane, doar ca nu supravietuieste.
    try { localStorage.removeItem(CHEIE) } catch (__) {}
  }
}

function hidrateaza() {
  if (typeof window === 'undefined') return
  try {
    const brut = localStorage.getItem(CHEIE)
    if (!brut) return
    const obiect = JSON.parse(brut)
    const acum = Date.now()
    for (const [url, i] of Object.entries(obiect)) {
      if (!i || typeof i.cand !== 'number' || acum - i.cand > CAT_TINE) continue
      intrari.set(url, i)
    }
  } catch (_) {
    try { localStorage.removeItem(CHEIE) } catch (__) {}
  }
}
hidrateaza()   // SINCRON, la incarcarea modulului: `dinCache` trebuie sa stie deja.

function scrie(url, date) {
  if (intrari.has(url)) intrari.delete(url)   // re-inserat = redevine cel mai nou
  intrari.set(url, { date, cand: Date.now() })
  while (intrari.size > MAX) intrari.delete(intrari.keys().next().value)
  programeazaScrierea()
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

  const gen = generatie
  const p = apiJson(url)
    .then((date) => {
      inZbor.delete(url)
      // O cerere pornita INAINTE de o scriere nu mai are voie sa umple memoria:
      // raspunsul ei e starea de dinaintea scrierii, si ar pune-o inapoi peste
      // cea corecta. Se intoarce apelantului (el o astepta oricum), dar nu se
      // tine minte. Fara asta, „bifez un task cat timp lista se reincarca" ar
      // lasa in cache lista cu taskul nebifat, iar urmatoarea intrare pe pagina
      // s-ar deschide cu el la loc.
      if (gen === generatie) scrie(url, date)
      return date
    })
    .catch((e) => { inZbor.delete(url); throw e })
  inZbor.set(url, p)
  return p
}

/** Uita ce stim despre URL-urile care incep cu prefixul dat. Se cheama dupa
 *  fiecare scriere.
 *
 *  Sterge SI cererile in zbor din tabelul de impartire — nu le anuleaza (nu se
 *  poate, si nici n-ar trebui: cine le asteapta primeste un raspuns valid
 *  pentru clipa in care l-a cerut), doar face ca urmatorul `preia` sa porneasca
 *  una noua in loc sa se agate de una pornita inaintea scrierii.
 *
 *  Generatia e globala cu buna stiinta: o scriere pe un capat poate schimba
 *  raspunsul altuia (o perioada mutata schimba si proiectul, si calendarul), iar
 *  o aruncare in plus costa o cerere, pe cand una ratata lasa pe ecran o stare
 *  care nu mai exista. */
export function uita(prefix) {
  generatie++
  for (const url of [...intrari.keys()]) {
    if (url.startsWith(prefix)) intrari.delete(url)
  }
  for (const url of [...inZbor.keys()]) {
    if (url.startsWith(prefix)) inZbor.delete(url)
  }
  // SI PE DISC. Fara asta, o scriere urmata de o repornire ar redeschide pagina
  // cu starea de dinaintea scrierii — adica exact ce credeai ca ai schimbat.
  programeazaScrierea()
}
