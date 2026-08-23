// ===== CE CREEAZA „+" — declarat de PAGINA, desenat de DOCK =====
//
// AURORA muta butonul plutitor din coltul ecranului IN dock, ca sa nu mai acopere
// ultimul rand din lista. Dar ce creeaza el depinde de pagina: pe Acasa un task
// pentru azi, pe Proiecte un proiect, in pagina unui proiect un task al lui.
// Inainte, fiecare pagina isi desena propriul `.fab` — patru copii ale aceleiasi
// cutii, in patru fisiere.
//
// Registrul inverseaza relatia: pagina spune CE face, dockul stie CUM arata.
// Pe paginile unde crearea n-are sens (Calculator, Departament, Calendar)
// nimeni nu se inregistreaza, si atunci butonul pur si simplu nu exista — nu e
// ascuns cu o lista de rute tinuta in dock, care s-ar desincroniza la prima ruta
// noua.
//
// Se foloseste asa, in pagina:
//     $effect(() => inregistreazaActiune('Adaugă task', () => { showAdauga = true }))
// `$effect` cheama singur functia de curatare la demontare, deci nu ramane
// agatata o actiune a unei pagini pe care ai parasit-o.

// NUMELE E `inregistreazaActiune`, NU `inregistreaza`: acela exista deja, in
// `lib/reincarcare.svelte.js` (trage-ca-sa-reincarci), si multe pagini il importa.
// Doua importuri cu acelasi nume in acelasi fisier nu compileaza.
let curenta = $state(null)

/** Ce actiune e disponibila acum: `{ eticheta, fa }` sau `null`. */
export function actiuneNoua() {
  return curenta
}

/**
 * @param {string} eticheta  ce scrie pe buton (aria-label + title)
 * @param {() => void} fa    ce se intampla la apasare
 * @returns {() => void}     curatare, pentru `$effect`
 */
export function inregistreazaActiune(eticheta, fa) {
  curenta = { eticheta, fa }
  // Curatarea e CONDITIONATA: intre demontarea paginii vechi si montarea celei
  // noi ordinea nu e garantata, iar o stergere oarba ar putea sterge exact
  // actiunea pe care pagina urmatoare tocmai a inregistrat-o. Acelasi tipar ca
  // garda de la `--dock-h` din `Dock.svelte` si `BaraSus.svelte`.
  return () => {
    if (curenta && curenta.fa === fa) curenta = null
  }
}
