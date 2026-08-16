// CAND PLEACA VALUL DE DESCHIDERE.
//
// Valul insusi (markup, stil, plasa de siguranta) e in `index.html`, fiindca
// trebuie desenat in primul cadru, inaintea acestui bundle. Aici ramane singura
// intrebare care are nevoie de aplicatie ca s-o raspunda: CAND e pagina de
// dedesubt gata sa fie vazuta.
//
// „Gata" inseamna trei lucruri deodata, si toate trei au fost masurate ca fiind
// vizibile pe telefon la pornire:
//
//   1. DATELE ATERIZARII au sosit. Altfel valul pleaca de pe schelete, si vezi
//      exact schimbul pe care il acopeream.
//   2. FONTURILE sunt asezate. `document.fonts` trecea prin `loading` la 1004ms
//      SI la 1533ms (vezi nota din `index.html`), adica textul se rescria de
//      doua ori dupa ce apucai sa-l citesti. Un font care se schimba sub val nu
//      se vede; unul care se schimba dupa, da.
//   3. Cadrul a fost DESENAT. O promisiune rezolvata inseamna doar ca datele
//      sunt in memorie: Svelte isi aseaza schimbarile intr-un microtask, iar
//      browserul le picteaza la urmatorul cadru. De aceea doua `rAF`: primul
//      prinde cadrul in care se aseaza DOM-ul, al doilea pe cel in care chiar
//      s-a pictat.
//
//   4. …SI NU MAI E NICIUN SCHELET PE ECRAN. Punctele 1-3 pareau sa acopere
//      asta, si nu o acopereau. Masurat, cu API-ul incetinit ca peste tunel si
//      cu memoria locala goala (adica exact o pornire dupa ore intregi):
//      valul pleca la 4308ms, pe plafonul din `index.html`, iar raspunsul venea
//      la 6309 — deci scheletul a stat DESCOPERIT 115 cadre, aproape doua
//      secunde. Ion: „vad un schelet pentru o fractiune de secunda; daca am
//      taskuri sa vad direct taskuri, iar daca lista e goala sa vad lista goala,
//      fara incarcare."
//      Promisiunea cererii nu e o garantie ca pagina s-a asezat — plafonul o
//      poate intrece, si atunci tot ce facem e sa mutam asteptarea de sub val in
//      fata ochilor. Singurul lucru care raspunde CHIAR la intrebarea „mai
//      astepti ceva?" e ecranul insusi.
//
// Nu asteptam la nesfarsit. Plafonul e mai mare decat inainte, dinadins: cand
// reteaua chiar e proasta, o marca linistita citeste mai bine decat patru dungi
// gri, si nu minte cu nimic — chiar se incarca. Iar cazurile in care ceva
// merge PROST nu asteapta plafonul: o cerere picata da `ErrorState`, nu schelet,
// deci poarta se deschide imediat.

/** Ce inseamna „pagina inca asteapta", in markup. `.asteptare` e invelisul
 *  starii de asteptare (vezi `global.css`), `.skeleton` e dunga insasi — a doua
 *  prinde si locurile care pun schelete fara invelis. */
const SELECTOR_ASTEPTARE = '.asteptare, .skeleton'

/** Peste atat, valul pleaca oricum. Perechea lui din `index.html` e mai mare cu
 *  o marja, ca plasa de acolo sa nu taie poarta de aici inainte sa se pronunte. */
const PLAFON = 5000

/**
 * @param {Promise<any>|null} dateleAterizarii cererea rutei pe care se deschide
 *        aplicatia, daca exista una. Fara ea se asteapta doar fonturile.
 */
export function splashDupa(dateleAterizarii) {
  const val = /** @type {any} */ (window).__splash
  if (!val) return   // desktop, sau valul a fost deja scos

  const pana = performance.now() + PLAFON

  const cadruPictat = () =>
    new Promise((gata) => requestAnimationFrame(() => requestAnimationFrame(gata)))

  // Se intreaba pe cadru, nu pe cronometru: raspunsul se schimba exact atunci
  // cand se schimba si ce se vede.
  const faraAsteptare = () => new Promise((gata) => {
    const verifica = () => {
      if (performance.now() >= pana || !document.querySelector(SELECTOR_ASTEPTARE)) return gata()
      requestAnimationFrame(verifica)
    }
    requestAnimationFrame(verifica)
  })

  Promise.all([
    dateleAterizarii || Promise.resolve(),
    document.fonts?.ready || Promise.resolve(),
  ])
    .catch(() => {})
    .then(cadruPictat)
    .then(faraAsteptare)
    .then(() => val.gata())
}
