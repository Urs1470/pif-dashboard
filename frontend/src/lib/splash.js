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
// Nu asteptam la nesfarsit: `index.html` are propriul plafon, iar aici cea mai
// lenta dintre asteptari e oricum intrecuta de el. Cererea de date NU respinge
// niciodata (vezi `loadGlobalTasks`), dar o prindem oricum — o eroare in lantul
// asta ar lasa valul pe ecran pana la plafon, adica ar transforma o retea
// proasta intr-o pornire lunga.

/**
 * @param {Promise<any>|null} dateleAterizarii cererea rutei pe care se deschide
 *        aplicatia, daca exista una. Fara ea se asteapta doar fonturile.
 */
export function splashDupa(dateleAterizarii) {
  const val = /** @type {any} */ (window).__splash
  if (!val) return   // desktop, sau valul a fost deja scos

  const cadruPictat = () =>
    new Promise((gata) => requestAnimationFrame(() => requestAnimationFrame(gata)))

  Promise.all([
    dateleAterizarii || Promise.resolve(),
    document.fonts?.ready || Promise.resolve(),
  ])
    .then(cadruPictat)
    .catch(() => {})
    .then(() => val.gata())
}
